# -*- coding: utf-8 -*-
"""精确的 Win32 对话框模板解析器：DLGTEMPLATEEX 与旧式 DLGTEMPLATE 双格式支持。

只返回"结构字段中位置已知的文本"（窗口标题、控件类名、控件标题），不做全文扫描。

**关键语义**：对话框模板里的文本字段（sz_Or_Ord）以 NUL 结束，
字段边界由 NUL 位置决定 —— 不是由调用方写入的字节区间决定。
因此任何长度变化（哪怕把多余字节填成 NUL）都会让后续字段从错误位置被解析。
改写者必须保持字段的 **UTF-16 码元数完全不变**。

字段类型（kind）：
  menu        对话框菜单名（通常是空或序数，不翻译）
  class       窗口类名（通常是空或序数，不翻译）
  title       对话框标题  ← 可翻译
  font        字体名（"MS Shell Dlg"，不翻译）
  ctrl_class  控件类名（"Button" / "SysListView32"，不翻译）
  ctrl_title  控件标题  ← 可翻译
"""
import struct

# 可翻译的字段类型
TRANSLATABLE = ("title", "ctrl_title")


def _sz(b, p, n):
    """sz_Or_Ord：返回 ((kind, value), next_p)。kind: 'empty' | 'ord' | 'txt'"""
    if p + 2 > n: raise ValueError("越界")
    w, = struct.unpack_from("<H", b, p)
    if w == 0x0000:
        return ("empty", None), p + 2
    if w == 0xFFFF:
        v, = struct.unpack_from("<H", b, p + 2)
        return ("ord", v), p + 4
    e = p
    while e + 2 <= n and struct.unpack_from("<H", b, e)[0] != 0x0000:
        e += 2
    if e + 2 > n: raise ValueError("文本未终止 @%d" % p)
    return ("txt", b[p:e].decode("utf-16-le")), e + 2

def _align4(p):
    return (p + 3) & ~3

def parse_dialog(blob):
    """返回 (slots, ok)；slots = [(rel_offset, text, field_kind)]，
    rel_offset 对应文本首字节位置，field_kind 见模块 docstring。"""
    n = len(blob)
    slots = []
    ex = blob[0:2] == b"\x01\x00" and blob[2:4] == b"\xff\xff"
    if ex:
        dlgver, sig, helpid, exstyle, style, cdit, x, y, cx, cy = struct.unpack_from("<HHIIIHhhhh", blob, 0)
        p = 26
    else:
        style, exstyle, cdit, x, y, cx, cy = struct.unpack_from("<IIHhhhh", blob, 0)
        p = 18
    # menu / windowClass / title
    for name in ("menu", "class", "title"):
        (k, v), p = _sz(blob, p, n)
        if k == "txt":
            slots.append((p - len(v) * 2 - 2, v, name))
    if ex:
        if style & 0x40:                      # DS_SETFONT
            pointsize, weight, italic, charset = struct.unpack_from("<HHBB", blob, p)
            p += 6
            (k, v), p = _sz(blob, p, n)
            if k == "txt":
                slots.append((p - len(v) * 2 - 2, v, "font"))
    else:
        if style & 0x40:
            p += 2                            # pointsize
            (k, v), p = _sz(blob, p, n)
            if k == "txt":
                slots.append((p - len(v) * 2 - 2, v, "font"))
    for i in range(cdit):
        p = _align4(p)
        if ex:
            helpid, iexstyle, ist, ix, iy, icx, icy, iid = struct.unpack_from("<IIIhhhhI", blob, p)
            p += 24
        else:
            ist, iexstyle, ix, iy, icx, icy, iid = struct.unpack_from("<IIhhhhH", blob, p)
            p += 18
        for name in ("ctrl_class", "ctrl_title"):   # windowClass / title
            (k, v), p = _sz(blob, p, n)
            if k == "txt":
                slots.append((p - len(v) * 2 - 2, v, name))
        cdsz, = struct.unpack_from("<H", blob, p)
        p += 2 + cdsz
    return slots, ex
