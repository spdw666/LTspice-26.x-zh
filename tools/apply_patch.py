#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""LTspice 26.x 汉化补丁应用器。

在目标 LTspice.exe 的资源段内按原文文本定位并写入等长译文，然后摘除已失效的
Authenticode 证书表目录项、重算 PE 校验和。

定位范围**严格限定在 .rsrc 段内**，绝不搜索或改写代码段等其它区域。

用法：
  python apply_patch.py --patch ltspice-26.1.1-zh.patch.json --exe "C:/…/LTspice.exe" --backup
  python apply_patch.py --patch … --exe … --restore          # 先用备份还原，再在其上打补丁
  python apply_patch.py --patch … --exe … --out copy.exe     # 输出到新文件，不动原件
  python apply_patch.py --patch … --exe … --check             # 只检查，绝不写盘

退出码：0 = 全部替换成功；1 = 有未定位/长度不合规的条目或出错。
"""
import argparse, hashlib, json, os, shutil, struct, sys

try:
    import pefile
except ImportError:
    sys.exit("需要 pefile：pip install pefile")

DEFAULT_BACKUP_SUFFIX = ".orig.bak"


def resource_span(pe):
    """返回 .rsrc 段的 [起始, 结束) 文件偏移。"""
    for s in pe.sections:
        if s.Name.rstrip(b"\x00") == b".rsrc":
            return s.PointerToRawData, s.PointerToRawData + s.SizeOfRawData
    raise SystemExit("目标不是 PE 文件或缺少 .rsrc 段")


def find_backup(exe):
    """找已有的备份：优先 <exe>.orig.bak，其次任意 <exe>.orig*.bak。"""
    exact = exe + DEFAULT_BACKUP_SUFFIX
    if os.path.exists(exact):
        return exact
    d, base = os.path.dirname(exe), os.path.basename(exe)
    try:
        cands = sorted(f for f in os.listdir(d)
                       if f.startswith(base + ".orig") and f.endswith(".bak"))
    except OSError:
        return None
    return os.path.join(d, cands[0]) if cands else None


def apply_patch(data, patch, stats, span):
    """就地写入译文。span = (rsrc_start, rsrc_end)，搜索范围硬限制在段内。

    长度规则（三类资源一致，违反即破坏资源）：
      字段以 NUL 结尾，**边界由 NUL 位置决定**。因此译文必须与原文字符数完全相同，
      不足补空格、超长拒绝。绝不能"填 NUL 提前终止字段"—— 那会让紧随其后的
      字体名 / 控件类 / 控件字段全部错位，对话框直接创建失败。
    """
    exe_bytes = bytes(data)
    lo, hi = span
    missing, wrong_len, dup = [], [], []
    for r in patch["records"]:
        text, zh = r["text"], r["zh"]
        orig = text.encode("utf-16-le")
        nb = zh.encode("utf-16-le")
        orig_units = len(orig) // 2
        if len(zh) != orig_units:
            wrong_len.append(text)
            continue

        off = r.get("off")
        hit = None
        if isinstance(off, int) and lo <= off and off + len(orig) <= hi:
            if exe_bytes[off:off + len(nb)] == nb:
                stats["already"] += 1
                continue
            if exe_bytes[off:off + len(orig)] == orig:
                hit = off
        if hit is None:
            # 回退：只在 .rsrc 段内搜索，且拒绝多处命中（歧义即失败，不猜）
            p1 = exe_bytes.find(orig, lo, hi)
            if p1 < 0:
                missing.append(text)
                continue
            if exe_bytes.find(orig, p1 + 1, hi) >= 0:
                dup.append(text)
                continue
            hit = p1
        data[hit:hit + len(nb)] = nb
        stats["applied"] += 1
    stats["wrong_len"] = len(wrong_len)
    stats["ambiguous"] = len(dup)
    if dup:
        for t in dup[:10]:
            print("  多处命中(已跳过): %r" % t)
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
    ap.add_argument("--backup", action="store_true",
                    help="备份成 <exe>.orig.bak（已存在同名备份时不覆盖）")
    ap.add_argument("--restore", action="store_true",
                    help="先从备份（.orig.bak 或 .orig-*.bak）还原，再打补丁")
    ap.add_argument("--check", action="store_true", help="只检查，绝不写任何文件")
    args = ap.parse_args()

    with open(args.patch, encoding="utf-8") as f:
        patch = json.load(f)
    if patch.get("format") != "ltspice-zh-patch/1":
        sys.exit("补丁格式不认识：%r" % patch.get("format"))

    # --check 是无条件只读：连还原与备份都不做
    if args.check and (args.restore or args.backup):
        print("--check 为只读模式，忽略 --restore / --backup")
        args.restore = args.backup = False

    existing = find_backup(args.exe)

    if args.restore and not args.check:
        if not existing:
            print("没有可用备份（%s%s 或 %s.orig-*.bak 都不存在）"
                  % (args.exe, DEFAULT_BACKUP_SUFFIX, args.exe))
            print("首次部署请去掉 --restore，直接加 --backup。")
            sys.exit(1)
        shutil.copyfile(existing, args.exe)
        print("已从备份还原：%s" % existing)

    cur = hashlib.sha256(open(args.exe, "rb").read()).hexdigest()
    want = patch["target"].get("sha256")
    if want and cur == want:
        print("目标就是补丁针对的原始版本 ✔  %s" % cur)
    else:
        print("目标 sha256 与补丁记录不同（将按文本匹配）：")
        print("  补丁: %s" % want)
        print("  目标: %s" % cur)

    # 注意：必须从内存构建 PE。pefile.PE(path) 会 mmap 并持有文件句柄，
    # Windows 下随后原地写回同名文件会以 OSError 22 失败。
    with open(args.exe, "rb") as f:
        raw = f.read()
    data = bytearray(raw)
    pe = pefile.PE(data=raw)
    span = resource_span(pe)
    print("资源段 .rsrc: %#x - %#x" % span)
    stats = {"applied": 0, "already": 0}
    missing = apply_patch(data, patch, stats, span)
    total = len(patch["records"])
    print("替换 %d/%d 处（%d 处已是译文），未定位 %d 处，长度不合规 %d 处，歧义 %d 处"
          % (stats["applied"], total, stats["already"], len(missing),
             stats["wrong_len"], stats["ambiguous"]))
    for t in missing[:10]:
        print("  未定位: %r" % t)
    if len(missing) > 10:
        print("  ... 还有 %d 处" % (len(missing) - 10))
    if stats["wrong_len"]:
        print("  ✘ 有 %d 条译文码元数与原文不符，已拒绝写入（该补丁不合规）" % stats["wrong_len"])

    if args.check:
        print("--check：未写文件。退出码 %d" % (0 if not missing and not stats["wrong_len"] else 1))
        sys.exit(0 if not missing and not stats["wrong_len"] else 1)

    if args.backup and not os.path.exists(args.exe + DEFAULT_BACKUP_SUFFIX):
        shutil.copyfile(args.exe, args.exe + DEFAULT_BACKUP_SUFFIX)
        print("已备份 -> %s" % (args.exe + DEFAULT_BACKUP_SUFFIX))

    removed = strip_signature_and_fix_checksum(data)
    print("证书表目录项已摘除" if removed else "无证书表目录项")
    print("PE 校验和已重算")

    out = args.out or args.exe
    with open(out, "wb") as f:
        f.write(bytes(data))
    print("已写出 %s  (%d bytes, sha256=%s)"
          % (out, os.path.getsize(out), hashlib.sha256(bytes(data)).hexdigest()))

    bad = len(missing) + stats["wrong_len"] + stats["ambiguous"]
    if bad:
        print("\n⚠ 有 %d 条未成功替换，界面会中英混排。退出码 1。" % bad)
        sys.exit(1)
    print("\n全部替换成功。还原：把 %s%s 覆盖回 %s"
          % (args.exe, DEFAULT_BACKUP_SUFFIX, args.exe))
    sys.exit(0)


if __name__ == "__main__":
    main()
