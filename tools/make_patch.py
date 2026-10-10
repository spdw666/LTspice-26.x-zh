#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""LTspice 26.x 汉化补丁生成器。

读取一份在任意一台机器上扫描好的 slots.json，套用 zh_dict.json 词典，
对用户本机的 LTspice.exe 做原地等长字节替换，输出 patch（默认 JSON）。

设计要点（决定了补丁为什么可以只有几百 KB）：
  译文按"原文字符 -> 槽位偏移"重建，不需要把 70MB 的 exe 传给别人。
  LTspice 的资源加载器对条目长度极其敏感，因此所有译文都右侧补空格到与
  原文完全相同的 UTF-16 码元数，字节区间严格等长，PE 结构零改动。

安全约束：slots.json 记录的 sha256 与目标 exe 不一致时**直接失败、不产出补丁**；
每个槽位先验证边界、nbytes 与原文一致、exe 内该偏移确实是该原文，坏槽位计数并
跳过而不是写坏数据。整份补丁先在内存里生成，最后才原子写出。

用法：
  python make_patch.py --slots slots.json --dict zh_dict.json --exe LTspice.exe -o ltspice-26.1.1-zh.patch.json
  python make_patch.py --slots slots.json --dict zh_dict.json --exe LTspice.exe --verify   # 只自检，不写文件
"""
import argparse, hashlib, json, os, sys, tempfile

try:
    import pefile
except ImportError:
    pass  # 生成器本身不需要 pefile；保留兼容旧环境的失败容忍

KINDS = ("menu", "string", "dialog")
# 对话框里只有这两类字段可翻译；class / ctrl_class / font 是结构字段，翻了对话框创建失败
TRANSLATABLE = ("title", "ctrl_title")


def _utf8_when_piped():
    """输出被重定向时强制 UTF-8：否则中文会按 cp936 编码，
    调用方按 UTF-8 解码时崩溃。真实控制台保持原样。"""
    for s in (sys.stdout, sys.stderr):
        try:
            if not s.isatty():
                s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError, OSError):
            pass


_utf8_when_piped()


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def u16units(s):
    """UTF-16 码元数。非 BMP 字符（emoji 等）算 2 码元，Python 的 len() 只算 1。"""
    return len(s.encode("utf-16-le")) // 2


def read_slot(data, s):
    """校验并读出槽位原文。返回 (text, off, nbytes)；坏槽位抛 ValueError。

    kind/text/nbytes/abs 任一非法，或 exe 内该偏移的字节与 text 不符，
    都判为坏槽位 —— 拿坏槽位写补丁等于按偏移改坏未知数据。
    """
    if not isinstance(s, dict):
        raise ValueError("槽位不是对象")
    kind, text, nbytes, off = s.get("kind"), s.get("text"), s.get("nbytes"), s.get("abs")
    if kind not in KINDS:
        raise ValueError("非法 kind %r" % (kind,))
    # 对话框里只有 title / ctrl_title 可翻译；缺 field 的老 slots.json 按可翻译处理
    if kind == "dialog" and s.get("field") not in TRANSLATABLE + (None,):
        raise ValueError("结构字段不可翻译：%r" % (s.get("field"),))
    if not isinstance(text, str) or not text or "\x00" in text:
        raise ValueError("原文为空或含 NUL")
    if not isinstance(nbytes, int) or isinstance(nbytes, bool) or nbytes <= 0 or nbytes % 2:
        raise ValueError("nbytes 非法 %r" % (nbytes,))
    if not isinstance(off, int) or isinstance(off, bool) or off < 0 or off + nbytes > len(data):
        raise ValueError("abs 越界 %r" % (off,))
    orig = data[off:off + nbytes]
    try:
        if text.encode("utf-16-le") != orig:
            raise ValueError("槽位字节与 text 不符 @%#x" % off)
    except UnicodeEncodeError:
        raise ValueError("原文编码失败 @%#x" % off)
    return text, off, nbytes


def patch_bytes(data, slots, tr, stats):
    """就地把译文写进 data（bytearray）。返回 patch 记录列表。

    坏槽位（kind/边界/字节不符）计入 stats['badslot'] 并跳过，不写任何字节。
    函数级调用方若传入不合规数据，只统计拒绝、不抛异常（CLI 层面才决定失败退出）。
    """
    records = []
    for s in slots:
        try:
            key, off, nbytes = read_slot(data, s)
        except ValueError:
            stats["badslot"] = stats.get("badslot", 0) + 1
            continue

        zh = tr.get(key)
        if not zh or zh == key:
            stats["miss"] += 1
            continue
        if not isinstance(zh, str) or "\x00" in zh:
            stats["badslot"] = stats.get("badslot", 0) + 1
            continue
        try:
            units = u16units(zh)
        except UnicodeEncodeError:
            stats["badslot"] = stats.get("badslot", 0) + 1
            continue
        orig_units = nbytes // 2

        # 三类资源的字段都以 NUL 结尾，字段**边界由 NUL 位置决定**，不是由写了多少字节决定。
        # 所以一律补空格到与原文完全相同的 **UTF-16 码元数** —— 空格的码元不是 NUL，
        # 终止 NUL 位置不变，后续结构字段就不会被读错。绝不能"填 NUL 提前终止"。
        # 长度必须按码元算：按 len() 码点算会把 "😀abcd"(6 码元) 放进 5 码元槽位，
        # 多出的 2 字节覆盖掉原字段后面的内容。
        if units > orig_units:
            stats["toolong"] += 1
            continue
        if units < orig_units:
            pad = " " * (orig_units - units)
            i = zh.find("\t")
            zh = (zh[:i] + pad + zh[i:]) if i >= 0 else (zh + pad)
        nb = zh.encode("utf-16-le")
        if len(nb) != nbytes:  # 双保险：绝不允许写出与槽位不等长的字节
            stats["badslot"] = stats.get("badslot", 0) + 1
            continue

        if bytes(data[off:off + len(nb)]) == nb:
            stats["same"] += 1
            continue
        records.append({"off": off, "text": key, "zh": zh, "kind": s["kind"]})
        # 只写译文本身，紧邻的终止 NUL 与后续结构字段保持原样
        data[off:off + len(nb)] = nb
        stats["hit"] += 1
    return records


def save_atomic(path, text):
    """同目录临时文件 + os.replace 原子写出；失败清理临时文件。"""
    path = os.path.abspath(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                               prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", required=True, help="扫描好的 slots.json")
    ap.add_argument("--dict", required=True, help="汉化词典 zh_dict.json")
    ap.add_argument("--exe", required=True, help="目标 LTspice.exe（用于校验与自检）")
    ap.add_argument("-o", "--out", help="输出补丁文件（.json）")
    ap.add_argument("--verify", action="store_true", help="只做 roundtrip 自检")
    args = ap.parse_args()

    try:
        meta = load(args.slots)
        tr = load(args.dict)
    except (OSError, ValueError) as e:
        sys.exit("输入读取失败：%s" % e)
    if not isinstance(meta, dict) or not isinstance(meta.get("slots"), list):
        sys.exit("slots.json 缺少 slots 列表")
    if not isinstance(tr, dict):
        sys.exit("词典必须是 {原文: 译文} 对象")
    if not isinstance(meta.get("sha256"), str) or not meta["sha256"]:
        sys.exit("slots.json 缺少 sha256，无法确认基准；请重跑 scan_slots.py")

    try:
        with open(args.exe, "rb") as f:
            data = bytearray(f.read())
    except OSError as e:
        sys.exit("目标 exe 读取失败：%s" % e)

    sha = hashlib.sha256(bytes(data)).hexdigest()
    if meta["sha256"] != sha:
        print("✘ slots.json 记录的 sha256 与目标 exe 不一致：")
        print("  slots: %s" % meta["sha256"])
        print("  目标 : %s" % sha)
        print("  槽位偏移已失效，拒绝生成（未创建任何输出）。")
        print("  请用**原始英文** exe 重跑 scan_slots.py。")
        sys.exit(1)
    print("exe sha256 匹配 ✔  %s" % sha)

    stats = {"hit": 0, "miss": 0, "toolong": 0, "same": 0, "unequal": 0, "badslot": 0}
    recs = patch_bytes(bytearray(data), meta["slots"], tr, stats)
    print("可用槽位 %d | 命中 %d | 未命中 %d | 超长跳过 %d | 对话框长度不等跳过 %d | 已一致 %d | 坏槽位跳过 %d"
          % (len(meta["slots"]), stats["hit"], stats["miss"], stats["toolong"],
             stats["unequal"], stats["same"], stats["badslot"]))

    if args.verify:
        # roundtrip：空词典必须一个字节都不动
        with open(args.exe, "rb") as f:
            orig = f.read()
        d2 = bytearray(orig)
        s2 = {"hit": 0, "miss": 0, "toolong": 0, "same": 0, "unequal": 0, "badslot": 0}
        patch_bytes(d2, meta["slots"], {}, s2)
        ok = bytes(d2) == orig
        ok = ok and s2["badslot"] == 0
        print("roundtrip 一致:", ok, "| 坏槽位 %d" % s2["badslot"])
        if not ok:
            sys.exit(1)
        return

    if not args.out:
        sys.exit("需要 -o 指定输出文件")
    if stats["badslot"]:
        print("✘ 有 %d 个坏槽位（越界 / 字节与原文不符 / 类型非法），"
              "slots.json 与 exe 不匹配，拒绝生成。" % stats["badslot"])
        sys.exit(1)

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
    text = json.dumps(patch, ensure_ascii=False, separators=(",", ":"))
    save_atomic(args.out, text)
    print("已写出 %s  (%.1f KB, %d 条替换)"
          % (args.out, os.path.getsize(args.out) / 1024, len(recs)))


if __name__ == "__main__":
    main()
