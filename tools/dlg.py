# -*- coding: utf-8 -*-
"""精确的 Win32 对话框模板解析器：DLGTEMPLATEEX 与旧式 DLGTEMPLATE 双格式支持。
只返回"结构字段中位置已知的文本"（窗口标题、控件类名、控件标题），不做全文扫描。"""
import struct

def _sz(b, p, n):
    """sz_Or_Ord：返回 (kind, value, next_p)。kind: 'empty' | 'ord' | 'txt'"""
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
    """返回 (slots, ok)；slots = [(rel_offset, text)]，rel_offset 对应文本首字节位置"""
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
    for _ in range(3):
        (k, v), p = _sz(blob, p, n)
        if k == "txt":
            slots.append((p - len(v) * 2 - 2, v))
    if ex:
        if style & 0x40:                      # DS_SETFONT
            pointsize, weight, italic, charset = struct.unpack_from("<HHBB", blob, p)
            p += 6
            (k, v), p = _sz(blob, p, n)
            if k == "txt":
                slots.append((p - len(v) * 2 - 2, v))
    else:
        if style & 0x40:
            p += 2                            # pointsize
            (k, v), p = _sz(blob, p, n)
            if k == "txt":
                slots.append((p - len(v) * 2 - 2, v))
    for i in range(cdit):
        p = _align4(p)
        if ex:
            helpid, iexstyle, ist, ix, iy, icx, icy, iid = struct.unpack_from("<IIIhhhhI", blob, p)
            p += 24
        else:
            ist, iexstyle, ix, iy, icx, icy, iid = struct.unpack_from("<IIhhhhH", blob, p)
            p += 18
        for _ in range(2):                    # windowClass / title
            (k, v), p = _sz(blob, p, n)
            if k == "txt":
                slots.append((p - len(v) * 2 - 2, v))
        cdsz, = struct.unpack_from("<H", blob, p)
        p += 2 + cdsz
    return slots, ex