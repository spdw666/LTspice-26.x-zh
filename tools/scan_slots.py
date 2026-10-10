# -*- coding: utf-8 -*-
r"""LTspice 26.x 槽位扫描器：找出 exe 里所有可翻译的界面文本。

用法（Windows，需要 LTspice 已安装；菜单需要 user32 读文本顺序）：
  python scan_slots.py                          # 用默认路径
  set LTSPICE_EXE=D:\path\LTspice.exe & set SLOTS_OUT=slots.json & python scan_slots.py

产出 slots.json：每条槽位带 abs（文件绝对偏移）/ nbytes（原文 UTF-16 字节数）/ text（原文）。
只读，不修改任何文件。


三类资源的文本槽全部由各自格式精确定位，不做模糊全文扫描：
  MENU   —— Win32 API 取权威文本顺序，再在 blob 内按字节顺序定位
  STRING —— 长度前缀自描述
  DIALOG —— DLGTEMPLATE / DLGTEMPLATEEX 结构逐字段解析，只取 title / windowClass / ctrl title
所有槽位均为严格等长写入（译文 UTF-16 字节数 <= 原文），零结构风险。
"""
import ctypes, json, os, struct, hashlib, sys
from ctypes import wintypes
import pefile
sys.path.insert(0, r"D:\DeepSeek Harness\ltspice-cn")
from dlg import parse_dialog

SRC = os.environ.get("LTSPICE_EXE", r"C:\Program Files\ADI\LTspice\LTspice.exe")
OUT = os.environ.get("SLOTS_OUT", "slots.json")
# 若 LTSPICE_EXE 指向已汉化的副本，扫描结果会带上中文，拿去当基准会错位；
# 基准 slots.json 必须从**原始英文 exe**扫描。
RT_MENU, RT_STRING, RT_DIALOG = 4, 6, 5

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
k32.LoadLibraryExW.restype = wintypes.HMODULE
k32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
u32.LoadMenuW.restype = wintypes.HMENU
u32.LoadMenuW.argtypes = [wintypes.HMODULE, wintypes.LPCWSTR]
u32.GetMenuStringW.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.LPWSTR, ctypes.c_int, wintypes.UINT]
u32.GetMenuItemCount.argtypes = [wintypes.HMENU]
u32.GetSubMenu.argtypes = [wintypes.HMENU, ctypes.c_int]
MF_BYPOSITION = 0x400
LOAD_LIBRARY_AS_IMAGE_RESOURCE = 0x20

HMOD = k32.LoadLibraryExW(SRC, None, LOAD_LIBRARY_AS_IMAGE_RESOURCE)
assert HMOD, "资源镜像加载失败"

def menu_texts(mid):
    hm = u32.LoadMenuW(HMOD, ctypes.cast(ctypes.c_void_p(mid), wintypes.LPCWSTR))
    if not hm:
        return None
    out = []
    def walk(m):
        for i in range(u32.GetMenuItemCount(m)):
            b = ctypes.create_unicode_buffer(1024)
            u32.GetMenuStringW(m, i, b, 1024, MF_BYPOSITION)
            out.append(b.value)
            s = u32.GetSubMenu(m, i)
            if s: walk(s)
    walk(hm)
    return out

pe = pefile.PE(SRC)
DATA = pe.__data__
def rva2off(r):
    for s in pe.sections:
        if s.VirtualAddress <= r < s.VirtualAddress + max(s.Misc_VirtualSize, s.SizeOfRawData):
            return s.PointerToRawData + (r - s.VirtualAddress)
def enc(s): return s.encode("utf-16-le")

slots = []
for e in pe.DIRECTORY_ENTRY_RESOURCE.entries:
    t = e.struct.Id
    if t not in (RT_MENU, RT_STRING, RT_DIALOG):
        continue
    for l2 in e.directory.entries:
        rid = l2.struct.Id
        ds = l2.directory.entries[0].data.struct
        off = rva2off(ds.OffsetToData)
        size = ds.Size
        blob = DATA[off:off + size]
        kind = {RT_MENU: "menu", RT_STRING: "string", RT_DIALOG: "dialog"}[t]
        found = []
        if kind == "menu":
            texts = menu_texts(rid)
            if texts is None:
                print("  ! MENU %s 无法通过 API 读取，跳过" % rid)
                continue
            pos = 0
            for tx in texts:
                if not tx:
                    continue
                nb = enc(tx)
                p = blob.find(nb, pos)
                if p < 0:
                    print("  ! MENU %s 未定位文本 %r" % (rid, tx[:40]))
                    continue
                found.append((p, tx))
                pos = p + len(nb)
        elif kind == "string":
            p = 0
            while p + 2 <= size:
                ln, = struct.unpack_from("<H", blob, p)
                if ln == 0:
                    p += 2; continue
                if p + 2 + ln * 2 > size:
                    break
                tx = blob[p+2:p+2+ln*2].decode("utf-16-le", "replace")
                found.append((p + 2, tx))
                p += 2 + ln * 2
        else:
            try:
                raw, _ex = parse_dialog(blob)
            except Exception as ex:
                print("  ! DLG %s 解析失败: %s" % (rid, ex))
                continue
            for rel, tx in raw:
                found.append((rel, tx))

        for st, tx in found:
            nb = len(enc(tx))
            slots.append({"kind": kind, "res": rid, "abs": off + st,
                          "nbytes": nb, "room": nb, "text": tx})

k32.FreeLibrary(HMOD)
json.dump({"exe": SRC, "sha256": hashlib.sha256(open(SRC, "rb").read()).hexdigest(),
           "slots": slots}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
from collections import Counter
print("槽位总数:", len(slots), Counter(s["kind"] for s in slots))
print("严格等长策略：room == nbytes 的槽位占比 %.1f%%" % (
    100 * sum(1 for s in slots if s["room"] == s["nbytes"]) / len(slots)))