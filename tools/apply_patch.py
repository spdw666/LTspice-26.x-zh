#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""LTspice 26.x 汉化补丁应用器（跨版本、跨机器）。

按"原文文本"匹配，不依赖绝对偏移：
  1. 读补丁里的每条记录，在目标 LTspice.exe 的资源段里定位原文；
  2. 原地写入等长译文；
  3. 移除已失效的 Authenticode 证书表目录项并重算 PE 校验和。

因此同一个补丁可以套用到同一大版本的其它小版本上（26.1.1 -> 26.1.2 等），
定位失败的条目会被跳过并统计，不会破坏文件。

用法：
  python apply_patch.py --patch ltspice-26.1.1-zh.patch.json --exe "C:/Program Files/ADI/LTspice/LTspice.exe"
  python apply_patch.py --patch ... --exe ... --restore LTspice.exe.orig.bak   # 还原备份后再打
"""
import argparse, hashlib, json, os, shutil, struct, sys

try:
    import pefile
except ImportError:
    sys.exit("需要 pefile：pip install pefile")


def find_resource_span(pe):
    for s in pe.sections:
        if s.Name.rstrip(b"\x00") == b".rsrc":
            return s.PointerToRawData, s.PointerToRawData + s.SizeOfRawData
    return None


def apply_patch(data, patch, stats):
    """data: bytearray。返回 (applied, missed) 明细。"""
    exe_bytes = bytes(data)
    missing = []
    for r in patch["records"]:
        text, zh = r["text"], r["zh"]
        nb = zh.encode("utf-16-le")
        # 优先用记录的原始偏移（同版本时最快最准）
        orig = text.encode("utf-16-le")
        off = r.get("off")
        hit = None
        if off is not None and 0 <= off < len(exe_bytes):
            if exe_bytes[off:off + len(nb)] == nb:
                stats["already"] += 1
                continue
            # 同版本时偏移精确；跨版本时该位置必须仍是这段原文才敢用
            if exe_bytes[off:off + len(orig)] == orig:
                hit = off
        if hit is None:
            hit = exe_bytes.find(orig)
            if hit < 0:
                missing.append(text)
                continue
        data[hit:hit + len(nb)] = nb
        # 清掉尾部残留（等长，不越界）
        orig_len = len(text.encode("utf-16-le"))
        if len(nb) < orig_len:
            data[hit + len(nb):hit + orig_len] = b"\x00" * (orig_len - len(nb))
        stats["applied"] += 1
    return missing


def strip_signature_and_fix_checksum(data):
    pe = pefile.PE(data=bytes(data))
    opt = pe.DOS_HEADER.e_lfanew + 4 + 20
    dd = opt + (112 if pe.OPTIONAL_HEADER.Magic == 0x20b else 96)
    cert = dd + 4 * 8
    _, c_size = struct.unpack_from("<II", data, cert)
    if c_size:
        struct.pack_into("<II", data, cert, 0, 0)
    chk = opt + 64
    struct.pack_into("<I", data, chk, 0)
    pe2 = pefile.PE(data=bytes(data))
    struct.pack_into("<I", data, chk, pe2.generate_checksum())
    return bool(c_size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", required=True)
    ap.add_argument("--exe", required=True, help="要汉化的 LTspice.exe")
    ap.add_argument("--out", help="输出路径（默认原地覆盖）")
    ap.add_argument("--backup", action="store_true", help="先备份成 <exe>.orig.bak")
    ap.add_argument("--restore", action="store_true",
                    help="先用 <exe>.orig.bak 覆盖回去，再在其上打补丁（推荐，幂等）")
    ap.add_argument("--check", action="store_true", help="只检查可应用性，不写文件")
    args = ap.parse_args()

    with open(args.patch, encoding="utf-8") as f:
        patch = json.load(f)
    if patch.get("format") != "ltspice-zh-patch/1":
        sys.exit("补丁格式不认识：%r" % patch.get("format"))

    bak = args.exe + ".orig.bak"
    if args.restore:
        if not os.path.exists(bak):
            sys.exit("找不到备份 %s" % bak)
        shutil.copyfile(bak, args.exe)
        print("已从备份还原：%s" % bak)

    cur = hashlib.sha256(open(args.exe, "rb").read()).hexdigest()
    want = patch["target"].get("sha256")
    if want and cur == want:
        print("目标就是补丁针对的原始版本 ✔  %s" % cur)
    else:
        print("目标 sha256 与补丁记录不同（按文本匹配继续）：")
        print("  补丁: %s" % want)
        print("  目标: %s" % cur)

    if args.backup and not os.path.exists(bak):
        shutil.copyfile(args.exe, bak)
        print("已备份 -> %s" % bak)

    data = bytearray(open(args.exe, "rb").read())
    stats = {"applied": 0, "already": 0}
    missing = apply_patch(data, patch, stats)
    total = len(patch["records"])
    print("替换 %d/%d 处（%d 处已是译文），未定位 %d 处"
          % (stats["applied"], total, stats["already"], len(missing)))
    if missing:
        for t in missing[:10]:
            print("  未定位: %r" % t)
        if len(missing) > 10:
            print("  ... 还有 %d 处" % (len(missing) - 10))

    if args.check:
        print("--check：未写文件")
        return

    removed = strip_signature_and_fix_checksum(data)
    print("证书表目录项已摘除" if removed else "无证书表目录项")
    print("PE 校验和已重算")

    out = args.out or args.exe
    with open(out, "wb") as f:
        f.write(bytes(data))
    print("已写出 %s  (%d bytes, sha256=%s)"
          % (out, os.path.getsize(out), hashlib.sha256(bytes(data)).hexdigest()))
    print("\n桌面快捷方式直接双击即可，卸载/还原：--restore 或把 %s 覆盖回去" % bak)


if __name__ == "__main__":
    main()