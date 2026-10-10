#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""LTspice 26.x 汉化补丁生成器。

读取一份在任意一台机器上扫描好的 slots.json，套用 zh_dict.json 词典，
对用户本机的 LTspice.exe 做原地等长字节替换，输出 patch（默认 JSON）。

设计要点（决定了补丁为什么可以只有几百 KB）：
  译文按"原文字符 -> 槽位偏移"重建，不需要把 70MB 的 exe 传给别人。
  LTspice 的资源加载器对条目长度极其敏感，因此所有译文都右侧补空格到与
  原文完全相同的 UTF-16 码元数，字节区间严格等长，PE 结构零改动。

用法：
  python make_patch.py --slots slots.json --dict zh_dict.json --exe LTspice.exe -o ltspice-26.1.1-zh.patch.json
  python make_patch.py --slots slots.json --dict zh_dict.json --exe LTspice.exe --verify   # 只自检，不写文件
"""
import argparse, hashlib, json, os, struct, sys

try:
    import pefile
except ImportError:
    sys.exit("需要 pefile：pip install pefile")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def patch_bytes(data, slots, tr, stats):
    """就地把译文写进 data（bytearray）。返回 patch 记录列表。"""
    records = []
    for s in slots:
        key = s["text"]
        if not key:
            continue
        zh = tr.get(key)
        if not zh or zh == key:
            stats["miss"] += 1
            continue

        nbytes, kind = s["nbytes"], s["kind"]
        units = nbytes // 2

        # 三类资源的字段都以 NUL 结尾，字段**边界由 NUL 位置决定**，不是由写了多少字节决定。
        # 所以一律补空格到与原文字符数完全相同 —— 空格的码元不是 NUL，终止 NUL 位置不变，
        # 后续结构字段就不会被读错。绝不能"填 NUL 提前终止"，那会让对话框整块错位。
        if len(zh) > units:
            stats["toolong"] += 1
            continue
        if len(zh) < units:
            pad = " " * (units - len(zh))
            i = zh.find("\t")
            zh = (zh[:i] + pad + zh[i:]) if i >= 0 else (zh + pad)
        nb = zh.encode("utf-16-le")

        off = s["abs"]
        if bytes(data[off:off + len(nb)]) == nb:
            stats["same"] += 1
            continue
        records.append({"off": off, "text": key, "zh": zh, "kind": kind})
        # 只写译文本身，紧邻的终止 NUL 与后续结构字段保持原样
        data[off:off + len(nb)] = nb
        stats["hit"] += 1
    return records


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", required=True, help="扫描好的 slots.json")
    ap.add_argument("--dict", required=True, help="汉化词典 zh_dict.json")
    ap.add_argument("--exe", required=True, help="目标 LTspice.exe（用于校验与自检）")
    ap.add_argument("-o", "--out", help="输出补丁文件（.json）")
    ap.add_argument("--verify", action="store_true", help="只做 roundtrip 自检")
    args = ap.parse_args()

    meta = load(args.slots)
    tr = load(args.dict)
    data = bytearray(open(args.exe, "rb").read())

    sha = hashlib.sha256(bytes(data)).hexdigest()
    if meta.get("sha256") and meta["sha256"] != sha:
        print("警告：slots.json 记录的 sha256 与目标 exe 不一致")
        print("  slots: %s" % meta["sha256"])
        print("  目标 : %s" % sha)
        print("  仍按偏移继续（可能错位，请重跑 scan_slots.py）")
    else:
        print("exe sha256 匹配 ✔  %s" % sha)

    stats = {"hit": 0, "miss": 0, "toolong": 0, "same": 0, "unequal": 0}
    recs = patch_bytes(bytearray(data), meta["slots"], tr, stats)
    print("可用槽位 %d | 命中 %d | 未命中 %d | 超长跳过 %d | 对话框长度不等跳过 %d | 已一致 %d"
          % (len(meta["slots"]), stats["hit"], stats["miss"], stats["toolong"],
             stats["unequal"], stats["same"]))

    if args.verify:
        # roundtrip：空词典必须一个字节都不动
        d2 = bytearray(open(args.exe, "rb").read())
        s2 = {"hit": 0, "miss": 0, "toolong": 0, "same": 0, "unequal": 0}
        patch_bytes(d2, meta["slots"], {}, s2)
        print("roundtrip 一致:", bytes(d2) == bytes(open(args.exe, "rb").read()))
        return

    if not args.out:
        sys.exit("需要 -o 指定输出文件")

    patch = {
        "format": "ltspice-zh-patch/1",
        "target": {
            "file": "LTspice.exe",
            "version": meta.get("version") or "unknown",
            "sha256": meta.get("sha256"),
        },
        "stats": stats,
        "records": recs,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(patch, f, ensure_ascii=False, separators=(",", ":"))
    print("已写出 %s  (%.1f KB, %d 条替换)"
          % (args.out, os.path.getsize(args.out) / 1024, len(recs)))


if __name__ == "__main__":
    main()
