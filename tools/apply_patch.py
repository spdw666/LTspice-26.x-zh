#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""LTspice 26.x 汉化补丁应用器。

在目标 LTspice.exe 的资源段内按原文文本定位并写入等长译文，然后摘除已失效的
Authenticode 证书表目录项、重算 PE 校验和。

定位范围**严格限定在 .rsrc 段内**，绝不搜索或改写代码段等其它区域。

事务语义：先在内存里跑完整预检，**全部记录成功才允许落盘**；
只要有一条未定位 / 长度不合规 / 歧义 / 不合规，目标、--out、备份都不改动。
落盘用同目录临时文件 + 原子替换，失败清理临时文件。

用法：
  python apply_patch.py --patch ltspice-26.1.1-zh.patch.json --exe "C:/…/LTspice.exe" --backup
  python apply_patch.py --patch … --exe … --restore          # 以备份为基准重打，成功后才写回
  python apply_patch.py --patch … --exe … --out copy.exe     # 输出到新文件，不动原件
  python apply_patch.py --patch … --exe … --check             # 只检查，绝不写盘

退出码：0 = 全部替换成功；1 = 有未定位/长度不合规/歧义/不合规条目，或出错（此时绝不写盘）。
"""
import argparse, hashlib, json, os, shutil, struct, sys, tempfile

try:
    import pefile
except ImportError:
    sys.exit("需要 pefile：pip install pefile")

DEFAULT_BACKUP_SUFFIX = ".orig.bak"
# 三类可翻译资源的合法 kind；其它值说明记录不是本工具产出的，拒绝。
KINDS = ("menu", "string", "dialog")


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


def u16(s):
    """文本 -> UTF-16LE 字节。孤立代理项等编码错误抛 UnicodeEncodeError。"""
    return s.encode("utf-16-le")


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
      字段以 NUL 结尾，**边界由 NUL 位置决定**。因此译文的 UTF-16 码元数必须与
      原文完全相同，字节数也随之一致；不足补空格、超长拒绝。绝不能"填 NUL 提前
      终止字段"—— 那会让紧随其后的字体名 / 控件类 / 控件字段全部错位，对话框
      直接创建失败。

      比较必须按 **UTF-16LE 字节长度**：Python 的 len() 数的是码点，
      一个非 BMP 字符（如 emoji）算 1 码点却是 2 码元。按码点比较会放过
      "😀abcd"(6 码元) 塞进 5 码元字段，也会误拒合法的 "😀abc"(5 码元)。

    写入区间冲突预检：全部记录先定位、只在内存排定写入区间，**没有任何冲突才真正写**。
    两条记录的 [start, start+nbytes) 只要相交（含同区间不同译文、不同偏移的部分重叠），
    整批取消、一个字节都不写 —— 否则后写的记录会静默覆盖先写的，"已成功"的计数就成了假话。
    完全相同（同起止、同译文字节）的重复记录按去重处理：只写一次、也只计一次成功。
    已经汉化的记录同样占用自己的区间，参与同一套冲突检查。

    不合规记录一律不写：空原文、含 NUL 的原文/译文、非字符串字段、
    kind 不在白名单、UTF-16 编码失败 —— 计入 stats['rejected']。
    非法/越界的 off 不写也不拒，退回段内文本搜索（找不到即未定位）。

    返回未定位（missing）的原文列表。
    """
    exe_bytes = bytes(data)
    lo, hi = span
    missing, wrong_len, dup = [], [], []
    rejected = 0
    plan = []          # (start, end, nb, need_write)
    for r in patch.get("records") or []:
        if not isinstance(r, dict):
            rejected += 1
            continue
        text, zh, kind = r.get("text"), r.get("zh"), r.get("kind")
        if kind is not None and kind not in KINDS:
            rejected += 1
            continue
        if not isinstance(text, str) or not isinstance(zh, str):
            rejected += 1
            continue
        # 空原文无法定位；原文/译文含 NUL 会让字段边界再次错位
        if not text or "\x00" in text or "\x00" in zh:
            rejected += 1
            continue
        try:
            orig, nb = u16(text), u16(zh)
        except UnicodeEncodeError:
            rejected += 1
            continue
        if len(nb) != len(orig):
            wrong_len.append(text)
            continue

        off = r.get("off")
        hit = None
        if (isinstance(off, int) and not isinstance(off, bool)
                and lo <= off and off + len(orig) <= hi):
            if exe_bytes[off:off + len(nb)] == nb:
                plan.append((off, off + len(nb), nb, False))   # 已是译文，仍占区间
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
        plan.append((hit, hit + len(nb), nb, True))

    # 冲突预检：区间相交即整批失败。按起点排序后只需比较相邻区间
    # （任何重叠都会在排序后表现为某一对相邻区间相交）。
    # 完全相同的重复记录（同起止、同译文）不算冲突：去重后照常计一次成功。
    conflict = False
    prev = None
    for i in sorted(range(len(plan)), key=lambda i: plan[i][:2]):
        s, e, nb = plan[i][:3]
        if prev is not None:
            s1, e1, nb1 = plan[prev][:3]
            if s < e1:
                if (s, e, nb) != (s1, e1, nb1):
                    print("  ✘ 写入区间冲突: 记录区间 [%d,%d) 与 [%d,%d) 重叠" % (s1, e1, s, e))
                    conflict = True
                continue
        prev = i
    if conflict:
        stats["wrong_len"] = len(wrong_len)
        stats["ambiguous"] = len(dup)
        stats["rejected"] = rejected
        stats["conflict"] = 1
        stats["dup"] = 0
        for t in dup[:10]:
            print("  多处命中(已跳过): %r" % t)
        return missing

    # 无冲突：完全重复的记录去重，只写一次、也只计一次成功
    done = set()
    stats["dup"] = 0
    for start, end, nb, need_write in plan:
        key = (start, end, nb)
        if key in done:
            stats["dup"] += 1
            continue
        done.add(key)
        if need_write:
            data[start:end] = nb
            stats["applied"] += 1
        else:
            stats["already"] += 1
    stats["wrong_len"] = len(wrong_len)
    stats["ambiguous"] = len(dup)
    stats["rejected"] = rejected
    stats["conflict"] = 0
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


def save_atomic(path, data):
    """同目录临时文件 + os.replace 原子替换；任何失败都清理临时文件。"""
    path = os.path.abspath(path)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or ".",
                               prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(bytes(data))
        if os.path.exists(path):
            shutil.copystat(path, tmp)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", required=True)
    ap.add_argument("--exe", required=True, help="要汉化的 LTspice.exe")
    ap.add_argument("--out", help="输出路径（默认原地覆盖）")
    ap.add_argument("--backup", action="store_true",
                    help="备份成 <exe>.orig.bak（已存在同名备份时不覆盖）")
    ap.add_argument("--restore", action="store_true",
                    help="以备份（.orig.bak 或 .orig-*.bak）为基准重打，成功后才写回目标")
    ap.add_argument("--check", action="store_true", help="只检查，绝不写任何文件")
    args = ap.parse_args()

    try:
        with open(args.patch, encoding="utf-8") as f:
            patch = json.load(f)
    except (OSError, ValueError) as e:
        sys.exit("补丁读取失败：%s" % e)
    if not isinstance(patch, dict) or patch.get("format") != "ltspice-zh-patch/1":
        sys.exit("补丁格式不认识：%r"
                 % (patch.get("format") if isinstance(patch, dict) else type(patch).__name__))
    records = patch.get("records")
    if not isinstance(records, list):
        sys.exit("补丁缺少 records 列表")

    # --check 是无条件只读：连还原与备份都不做
    if args.check and (args.restore or args.backup):
        print("--check 为只读模式，忽略 --restore / --backup")
        args.restore = args.backup = False

    existing = find_backup(args.exe)
    base = args.exe
    if args.restore:
        if not existing:
            print("没有可用备份（%s%s 或 %s.orig-*.bak 都不存在）"
                  % (args.exe, DEFAULT_BACKUP_SUFFIX, args.exe))
            print("首次部署请去掉 --restore，直接加 --backup。")
            sys.exit(1)
        # 只在内存里读备份：预检全部通过之前，绝不碰目标文件
        base = existing
        print("还原基准：%s（预检通过后才写回目标）" % existing)

    try:
        with open(base, "rb") as f:
            raw = f.read()
    except OSError as e:
        sys.exit("读取基准文件失败：%s" % e)

    cur = hashlib.sha256(raw).hexdigest()
    want = (patch.get("target") or {}).get("sha256")
    if want and cur == want:
        print("目标就是补丁针对的原始版本 ✔  %s" % cur)
    else:
        print("目标 sha256 与补丁记录不同（将按文本匹配）：")
        print("  补丁: %s" % want)
        print("  目标: %s" % cur)

    # 注意：必须从内存构建 PE。pefile.PE(path) 会 mmap 并持有文件句柄，
    # Windows 下随后原地写回同名文件会以 OSError 22 失败。
    data = bytearray(raw)
    try:
        pe = pefile.PE(data=raw)
        span = resource_span(pe)
    except SystemExit:
        raise
    except Exception as e:
        sys.exit("目标不是可解析的 PE：%s" % e)
    print("资源段 .rsrc: %#x - %#x" % span)

    stats = {"applied": 0, "already": 0}
    missing = apply_patch(data, patch, stats, span)
    total = len(records)
    print("替换 %d/%d 处（%d 处已是译文），未定位 %d 处，长度不合规 %d 处，歧义 %d 处，不合规拒绝 %d 处"
          % (stats["applied"], total, stats["already"], len(missing),
             stats["wrong_len"], stats["ambiguous"], stats["rejected"]))
    n_dup = stats.get("dup", 0)
    if n_dup > 0:
        print("（另有 %d 条重复记录已去重，与已生效记录内容完全相同）" % n_dup)
    for t in missing[:10]:
        print("  未定位: %r" % t)
    if len(missing) > 10:
        print("  ... 还有 %d 处" % (len(missing) - 10))
    if stats["wrong_len"]:
        print("  ✘ 有 %d 条译文码元数与原文不符，已拒绝写入（该补丁不合规）" % stats["wrong_len"])
    if stats["rejected"]:
        print("  ✘ 有 %d 条记录不合规（空原文 / 内嵌 NUL / 类型非法 / 编码失败），已拒绝" % stats["rejected"])
    if stats["conflict"]:
        print("  ✘ 补丁内有多条记录的写入区间冲突/重叠，无法证明每条都生效，整批拒绝")

    bad = (len(missing) + stats["wrong_len"] + stats["ambiguous"] + stats["rejected"]
           + stats["conflict"])

    if args.check:
        print("--check：未写文件。退出码 %d" % (1 if bad else 0))
        sys.exit(1 if bad else 0)

    if bad:
        print("\n✘ 有 %d 条未能成功替换，整次写入已取消："
              "目标 / --out / 备份均保持未改动。" % bad)
        sys.exit(1)

    # 预检全部通过，此时才允许产生任何磁盘副作用
    if args.backup and not os.path.exists(args.exe + DEFAULT_BACKUP_SUFFIX):
        shutil.copyfile(args.exe, args.exe + DEFAULT_BACKUP_SUFFIX)
        print("已备份 -> %s" % (args.exe + DEFAULT_BACKUP_SUFFIX))

    removed = strip_signature_and_fix_checksum(data)
    print("证书表目录项已摘除" if removed else "无证书表目录项")
    print("PE 校验和已重算")

    out = args.out or args.exe
    save_atomic(out, data)
    print("已写出 %s  (%d bytes, sha256=%s)"
          % (out, os.path.getsize(out), hashlib.sha256(bytes(data)).hexdigest()))

    print("\n全部替换成功。还原：把 %s%s 覆盖回 %s"
          % (args.exe, DEFAULT_BACKUP_SUFFIX, args.exe))
    sys.exit(0)


if __name__ == "__main__":
    main()
