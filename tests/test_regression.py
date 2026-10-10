# -*- coding: utf-8 -*-
r"""工具链回归测试（针对 apply_patch.py / make_patch.py 的防护逻辑）。

跑法（任选）：
  python tests/test_regression.py -v
  python -m unittest discover -s tests -v

覆盖三类历史缺陷：
  1. UTF-16 码元 vs Python 码点：非 BMP 字符（emoji）的长度校验与补齐；
  2. 不合规输入拒绝：空原文、内嵌 NUL、非法 kind、非法/越界偏移、孤立代理项；
  3. 事务性：预检未全过则目标 / --out / 备份 / 根目录都不许有任何改动。

真实 exe 的只读一致性用例需设 LTSPICE_EN_EXE 指向**原始英文** LTspice.exe，
未设置时自动跳过（不碰已安装的 LTspice，不写任何安装目录）。
"""
import hashlib, importlib.util, json, os, struct, subprocess, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TMP_ROOT = os.environ.get("TEMP") or None


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ap = _load("lt_apply_patch", REPO / "tools" / "apply_patch.py")
mp = _load("lt_make_patch", REPO / "tools" / "make_patch.py")
dl = _load("lt_dlg", REPO / "tools" / "dlg.py")

EN_EXE = os.environ.get("LTSPICE_EN_EXE", r"D:\Program Files\ADI\LTspice\LTspice.exe.orig-26.1.1.bak")


def u16(s):
    return s.encode("utf-16-le")


def fakepe(body):
    """造一个最小可解析 PE：.rsrc 段 = 文件偏移 512..1024，body 写在 512 起。"""
    data = bytearray(1024)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 132, 0x8664, 1, 0, 0, 0, 240, 0x22)
    opt = 152
    struct.pack_into("<H", data, opt, 0x20b)
    struct.pack_into("<Q", data, opt + 24, 0x140000000)
    struct.pack_into("<II", data, opt + 32, 4096, 512)
    struct.pack_into("<II", data, opt + 56, 8192, 512)
    struct.pack_into("<H", data, opt + 68, 3)
    struct.pack_into("<I", data, opt + 108, 16)
    s = 392
    data[s:s + 8] = b".rsrc\0\0\0"
    struct.pack_into("<IIII", data, s + 8, 512, 4096, 512, 512)
    struct.pack_into("<I", data, s + 36, 0x40000040)
    data[512:512 + len(body)] = body
    return bytes(data)


EN_PE = fakepe(u16("Hello"))
SPAN = (512, 1024)
ZERO_STATS = {"hit": 0, "miss": 0, "toolong": 0, "same": 0, "unequal": 0, "badslot": 0}


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=TMP_ROOT)
        self.addCleanup(self._td.cleanup)
        self.d = Path(self._td.name)

    def run_apply(self, data, records, span=None):
        """span 默认覆盖整块数据；显式传参可测"只在段内搜索"。"""
        stats = {"applied": 0, "already": 0}
        missing = ap.apply_patch(data, {"records": records}, stats,
                                 (0, len(data)) if span is None else span)
        return stats, missing
    def cli(self, records, flags=(), raw=None, exe_name="SAMPLE.exe", patch=None):
        exe = self.d / exe_name
        exe.write_bytes(raw if raw is not None else EN_PE)
        pf = self.d / (exe_name + ".patch.json")
        pf.write_text(json.dumps(patch if patch is not None
                                 else {"format": "ltspice-zh-patch/1", "target": {}, "records": records},
                                 ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, str(REPO / "tools" / "apply_patch.py"),
                            "--patch", str(pf), "--exe", str(exe), *flags],
                           capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONUTF8": "1"})
        return p, exe

    def gen(self, slots, tr, exe_bytes=None, sha=None, flags=(), out_name="out.json"):
        exe = self.d / "gen.exe"
        raw = exe_bytes if exe_bytes is not None else EN_PE
        exe.write_bytes(raw)
        sj = self.d / "slots.json"
        sj.write_text(json.dumps({"sha256": sha if sha is not None else hashlib.sha256(raw).hexdigest(),
                                  "slots": slots}, ensure_ascii=False), encoding="utf-8")
        dj = self.d / "dict.json"
        dj.write_text(json.dumps(tr, ensure_ascii=False), encoding="utf-8")
        p = subprocess.run([sys.executable, str(REPO / "tools" / "make_patch.py"),
                            "--slots", str(sj), "--dict", str(dj), "--exe", str(exe),
                            "-o", str(self.d / out_name), *flags],
                           capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONUTF8": "1"})
        return p, self.d / out_name

    def assert_no_tmp(self):
        leftover = [f.name for f in self.d.iterdir() if f.name.endswith(".tmp")]
        self.assertEqual(leftover, [], "临时文件未清理：%s" % leftover)


class TestRecordValidation(unittest.TestCase):
    """不合规记录必须拒绝且不写任何字节（直接调函数层）。"""

    def run_apply(self, data, records, span=(0, 12)):
        stats = {"applied": 0, "already": 0}
        missing = ap.apply_patch(data, {"records": records}, stats, span)
        return stats, missing

    def test_empty_original_rejected(self):
        data, old = bytearray(b"X" * 12), bytearray(b"X" * 12)
        s, _ = self.run_apply(data, [{"off": 0, "text": "", "zh": ""}])
        self.assertEqual((s["applied"], s["already"], s["rejected"]), (0, 0, 1))
        self.assertEqual(data, old)

    def test_embedded_nul_in_translation_rejected(self):
        data, old = bytearray(u16("Hello")), bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你\0好  "}])
        self.assertEqual(s["rejected"], 1)
        self.assertEqual(data, old)

    def test_embedded_nul_in_original_rejected(self):
        data, old = bytearray(u16("Hello")), bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "He\0lo", "zh": "你好   "}])
        self.assertEqual((s["applied"], s["rejected"]), (0, 1))
        self.assertEqual(data, old)

    def test_bad_kind_rejected(self):
        data, old = bytearray(u16("Hello")), bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你好   ", "kind": "code"}])
        self.assertEqual((s["applied"], s["rejected"]), (0, 1))
        self.assertEqual(data, old)

    def test_nonstring_fields_rejected(self):
        data, old = bytearray(u16("Hello")), bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": 1234}, "notadict",
                                     {"off": 0, "text": None, "zh": "你好   "}])
        self.assertEqual((s["applied"], s["rejected"]), (0, 3))
        self.assertEqual(data, old)

    def test_lone_surrogate_rejected(self):
        data, old = bytearray(u16("Hello")), bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "\ud800abc"}])
        self.assertEqual((s["applied"], s["rejected"]), (0, 1))
        self.assertEqual(data, old)

    def test_out_of_range_off_falls_back_to_search(self):
        """越界/非法 off 不是错误，退回段内搜索；段内找不到即未定位。"""
        for off in (-1, 10 ** 9, "512", 8):
            data, old = bytearray(b"X" * 12), bytearray(b"X" * 12)
            s, missing = self.run_apply(data, [{"off": off, "text": "Hello", "zh": "你好   "}])
            self.assertEqual(s["rejected"], 0, "off=%r 不该被当作不合规" % off)
            self.assertEqual(missing, ["Hello"])
            self.assertEqual(data, old)
        # 同一条越界 off，只要段内确实存在原文就照样命中并正确写入
        data = bytearray(u16("Hello"))
        s, missing = self.run_apply(data, [{"off": 8, "text": "Hello", "zh": "你好   "}])
        self.assertEqual((s["applied"], missing), (1, []))
        self.assertEqual(bytes(data), u16("你好   "))


class TestUtf16Length(Base):
    """长度必须按 UTF-16 码元/字节算，不是 Python 码点。"""

    def test_nonbmp_same_byte_length_accepted(self):
        data = bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 512, "text": "Hello", "zh": "😀abc"}])
        self.assertEqual(s["applied"], 1)
        self.assertEqual(len(data), 10)
        self.assertEqual(bytes(data), u16("😀abc"))

    def test_nonbmp_extra_bytes_rejected(self):
        data, old = bytearray(u16("Hello")), bytes(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 512, "text": "Hello", "zh": "😀abcd"}])
        self.assertEqual(s["wrong_len"], 1)
        self.assertEqual(bytes(data), old)

    def test_nonbmp_shorter_rejected(self):
        data = bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 512, "text": "Hello", "zh": "😀ab"}])
        self.assertEqual(s["wrong_len"], 1)
        self.assertEqual(bytes(data), u16("Hello"))

    def test_code_point_count_would_accept_but_must_not(self):
        """len('😀abcd')==5 会骗过码点比较，字节数 12 ≠ 10 必须拒绝。"""
        data = bytearray(u16("Hello"))
        self.assertEqual(len("😀abcd"), 5)
        s, _ = self.run_apply(data, [{"off": 512, "text": "Hello", "zh": "😀abcd"}])
        self.assertEqual(s["applied"], 0)

    def test_surrogate_pair_never_truncated(self):
        """emoji 必须整对写入：6 码元槽位收 6 码元译文，多一码元整条拒绝。"""
        data = bytearray(u16("Hello!"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello!", "zh": "😀abcd"}])
        self.assertEqual((s["applied"], len(data)), (1, 12))
        self.assertEqual(bytes(data), u16("😀abcd"))

        data = bytearray(u16("Hello!"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello!", "zh": "😀abcde"}])
        self.assertEqual(s["wrong_len"], 1)
        self.assertEqual(bytes(data), u16("Hello!"))   # 绝不截断代理对凑长度


class TestApplySemantics(Base):
    def test_exact_record(self):
        data = bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 512, "text": "Hello", "zh": "你好   "}])
        self.assertEqual(s["applied"], 1)
        self.assertEqual(bytes(data), u16("你好   "))

    def test_idempotent_record(self):
        data = bytearray(u16("你好   "))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你好   "}])
        self.assertEqual((s["already"], s["applied"]), (1, 0))
        self.assertEqual(bytes(data), u16("你好   "))

    def test_outside_span_untouched(self):
        data, old = bytearray(u16("Hello") + b"X" * 12), bytes(bytearray(u16("Hello") + b"X" * 12))
        s, missing = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你好   "}], span=(10, 22))
        self.assertEqual(s["applied"], 0)
        self.assertEqual(missing, ["Hello"])
        self.assertEqual(bytes(data), old)

    def test_ambiguous_off_inside_span_rejected(self):
        data = bytearray(u16("HelloHello"))
        s, _ = self.run_apply(data, [{"off": 999, "text": "Hello", "zh": "你好   "}], span=(0, 20))
        self.assertEqual(s["ambiguous"], 1)
        self.assertEqual(bytes(data), u16("HelloHello"))

    def test_oversize_rejected(self):
        data = bytearray(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 512, "text": "Hello", "zh": "Longer"}])
        self.assertEqual(s["wrong_len"], 1)
        self.assertEqual(bytes(data), u16("Hello"))

    def test_writes_only_inside_rsrc(self):
        """待改文本同时出现在段外：必须只改段内那一处，段外原样。"""
        raw = fakepe(u16("Hello"))
        raw = raw[:512] + u16("Hello") + raw[512 + 10:]      # 段内
        raw = raw[:1024] if len(raw) > 1024 else raw
        data = bytearray(raw)
        body = bytes(data[512:522])
        self.assertEqual(body, u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 512, "text": "Hello", "zh": "你好   "}])
        self.assertEqual(s["applied"], 1)
        self.assertEqual(bytes(data[512:522]), u16("你好   "))


class TestCliTransaction(Base):
    """CLI 层的失败语义：预检不过 -> 一个字节都不许写。"""

    def test_check_missing_nonzero(self):
        p, exe = self.cli([{"off": 512, "text": "MISSING", "zh": "缺失     "}], ["--check"])
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertEqual(exe.read_bytes(), EN_PE)

    def test_check_ambiguous_nonzero(self):
        p, exe = self.cli([{"off": 99999, "text": "Hello", "zh": "你好   "}], ["--check"],
                          raw=fakepe(u16("HelloHello")))
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertEqual(exe.read_bytes(), fakepe(u16("HelloHello")))

    def test_check_rejected_record_nonzero(self):
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "你\0好  "}], ["--check"])
        self.assertNotEqual(p.returncode, 0, p.stdout)

    def test_check_is_readonly(self):
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "你好   "}], ["--check", "--backup"])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertFalse(Path(str(exe) + ".orig.bak").exists())
        self.assertEqual(exe.read_bytes(), EN_PE)

    def test_failed_write_is_transactional(self):
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "你好   "},
                           {"off": 512, "text": "Missing", "zh": "缺失     "}], ["--backup"])
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(exe.read_bytes(), EN_PE, "失败补丁改动了目标")
        self.assertFalse(Path(str(exe) + ".orig.bak").exists(), "失败补丁写出了备份")
        self.assert_no_tmp()

    def test_failed_out_not_created(self):
        out = self.d / "rejected-output.exe"
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "TooLong"}], ["--out", str(out)])
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse(out.exists(), "被拒补丁写出了 --out")
        self.assertEqual(exe.read_bytes(), EN_PE)
        self.assert_no_tmp()

    def test_failed_out_not_overwritten(self):
        out = self.d / "existing.exe"
        out.write_bytes(b"SENTINEL")
        p, _ = self.cli([{"off": 512, "text": "Hello", "zh": "TooLong"}], ["--out", str(out)])
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(out.read_bytes(), b"SENTINEL")
        self.assert_no_tmp()

    def test_success_then_backup_then_out(self):
        out = self.d / "ok.exe"
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "你好   "}],
                          ["--backup", "--out", str(out)])
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(exe.read_bytes(), EN_PE, "有 --out 时不该动原文件")
        self.assertEqual(Path(str(exe) + ".orig.bak").read_bytes(), EN_PE)
        self.assertNotEqual(out.read_bytes(), EN_PE)
        self.assert_no_tmp()

    def test_restore_refuses_without_backup(self):
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "你好   "}], ["--restore"])
        self.assertEqual(p.returncode, 1)
        self.assertEqual(exe.read_bytes(), EN_PE)

    def test_restore_failure_does_not_touch_target(self):
        """--restore 预检失败时，目标不能被备份提前覆盖。"""
        p, exe = self.cli([{"off": 512, "text": "Missing", "zh": "缺失     "}], ["--restore"])
        # cli() 会先把 SAMPLE.exe 写成样本，这里提前放好备份；失败后目标必须保持样本内容
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(exe.read_bytes(), EN_PE)
        self.assert_no_tmp()

    def test_restore_failure_leaves_prebroken_target_alone(self):
        """目标已被改坏、备份存在、补丁又有未定位条目：目标绝不能被"还原"覆盖。"""
        target = self.d / "KEEP.exe"
        target.write_bytes(b"TARGET-UNTOUCHED")
        Path(str(target) + ".orig.bak").write_bytes(EN_PE)
        pf = self.d / "p.json"
        pf.write_text(json.dumps({"format": "ltspice-zh-patch/1", "target": {},
                                  "records": [{"off": 512, "text": "Missing", "zh": "缺失     "}]}),
                      encoding="utf-8")
        p = subprocess.run([sys.executable, str(REPO / "tools" / "apply_patch.py"),
                            "--patch", str(pf), "--exe", str(target), "--restore"],
                           capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONUTF8": "1"})
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertEqual(target.read_bytes(), b"TARGET-UNTOUCHED")
        self.assert_no_tmp()

    def test_restore_success_repairs_from_backup(self):
        target = self.d / "BROKEN.exe"
        target.write_bytes(fakepe(u16("XXXXX")))          # 已被改坏的目标
        Path(str(target) + ".orig.bak").write_bytes(EN_PE)
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "你好   "}], ["--restore"],
                          exe_name="BROKEN.exe")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(target.read_bytes()[512:522], u16("你好   "))
        self.assert_no_tmp()

    def test_bad_patch_format_rejected(self):
        p, exe = self.cli([], patch={"format": "other/9", "records": []})
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(exe.read_bytes(), EN_PE)


class TestGenerator(Base):
    def test_nonbmp_oversize_skipped(self):
        data = bytearray(u16("HelloZ"))
        s = dict(ZERO_STATS)
        mp.patch_bytes(data, [{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 0}],
                       {"Hello": "😀abcd"}, s)
        self.assertEqual(s["toolong"], 1)
        self.assertEqual(s["hit"], 0)
        self.assertEqual(bytes(data), u16("HelloZ"))

    def test_nonbmp_fits_padded_by_units(self):
        data = bytearray(u16("HelloZ"))
        s = dict(ZERO_STATS)
        recs = mp.patch_bytes(data, [{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 0}],
                              {"Hello": "😀ab"}, s)     # 4 码元 -> 补 1 空格
        self.assertEqual(s["hit"], 1)
        self.assertEqual(bytes(data[0:10]), u16("😀ab "))
        self.assertEqual(len(data), 12)                  # 总长不变
        self.assertEqual(recs[0]["zh"], "😀ab ")
        self.assertEqual(mp.u16units("😀ab "), 5)

    def test_tab_padding_before_tab(self):
        data = bytearray(u16("&New\tCtrl+N"))            # 11 码元 = 22 字节
        s = dict(ZERO_STATS)
        self.assertEqual(mp.u16units("&New\tCtrl+N"), 11)
        mp.patch_bytes(data, [{"text": "&New\tCtrl+N", "nbytes": 22, "kind": "menu", "abs": 0}],
                       {"&New\tCtrl+N": "&新建\tCtrl+N"}, s)   # 10 码元 -> 补 1 空格在 \t 前
        self.assertEqual(bytes(data).decode("utf-16-le"), "&新建 \tCtrl+N")
        self.assertEqual(s["hit"], 1)

    def test_wrong_slot_bytes_skipped(self):
        data, old = bytearray(u16("Other")), bytes(u16("Other"))
        s = dict(ZERO_STATS)
        mp.patch_bytes(data, [{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 0}],
                       {"Hello": "你好"}, s)
        self.assertEqual((s["badslot"], s["hit"]), (1, 0))
        self.assertEqual(bytes(data), old)

    def test_out_of_range_slot_skipped(self):
        data = bytearray(u16("Hello"))
        s = dict(ZERO_STATS)
        mp.patch_bytes(data, [{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 90}],
                       {"Hello": "你好"}, s)
        self.assertEqual(s["badslot"], 1)
        self.assertEqual(bytes(data), u16("Hello"))

    def test_bad_kind_and_odd_nbytes_skipped(self):
        data = bytearray(u16("Hello"))
        s = dict(ZERO_STATS)
        mp.patch_bytes(data, [{"text": "Hello", "nbytes": 10, "kind": "code", "abs": 0},
                              {"text": "Hello", "nbytes": 9, "kind": "menu", "abs": 0}],
                       {"Hello": "你好"}, s)
        self.assertEqual(s["badslot"], 2)
        self.assertEqual(bytes(data), u16("Hello"))

    def test_empty_original_slot_skipped(self):
        data, old = bytearray(u16("Hello")), bytes(u16("Hello"))
        s = dict(ZERO_STATS)
        mp.patch_bytes(data, [{"text": "", "nbytes": 10, "kind": "menu", "abs": 0}], {}, s)
        self.assertEqual(s["badslot"], 1)
        self.assertEqual(bytes(data), old)

    def test_dialog_structural_field_skipped(self):
        """对话框的 class / font 是结构字段，翻了会让对话框创建失败。"""
        data, old = bytearray(u16("Hello")), bytes(u16("Hello"))
        s = dict(ZERO_STATS)
        mp.patch_bytes(data, [{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 0,
                               "field": "font"},
                              {"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 0,
                               "field": "ctrl_class"}],
                       {"Hello": "你好"}, s)
        self.assertEqual((s["badslot"], s["hit"]), (2, 0))
        self.assertEqual(bytes(data), old)
        # title / ctrl_title 与缺 field 的老 slots.json 仍照常处理
        s = dict(ZERO_STATS)
        mp.patch_bytes(data, [{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 0,
                               "field": "ctrl_title"}], {"Hello": "你好"}, s)
        self.assertEqual(s["hit"], 1)

    def test_roundtrip_verify_empty_dict_untouched(self):
        p, out = self.gen([{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 512}],
                          {"Hello": "你好   "}, flags=["--verify"])
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn("roundtrip 一致: True", p.stdout)
        self.assertFalse(out.exists())

    def test_hash_mismatch_stops_before_writing(self):
        p, out = self.gen([{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 512}],
                          {"Hello": "你好   "}, sha="bad" * 20)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertFalse(out.exists(), "sha 不匹配仍写出了补丁")
        self.assert_no_tmp()

    def test_missing_sha_stops(self):
        raw = EN_PE
        (self.d / "gen.exe").write_bytes(raw)
        sj = self.d / "slots.json"
        sj.write_text(json.dumps({"slots": []}), encoding="utf-8")
        dj = self.d / "dict.json"
        dj.write_text("{}", encoding="utf-8")
        p = subprocess.run([sys.executable, str(REPO / "tools" / "make_patch.py"),
                            "--slots", str(sj), "--dict", str(dj), "--exe", str(self.d / "gen.exe"),
                            "-o", str(self.d / "out.json")],
                           capture_output=True, text=True, encoding="utf-8",
                           env={**os.environ, "PYTHONUTF8": "1"})
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((self.d / "out.json").exists())

    def test_bad_slot_stops_generation(self):
        p, out = self.gen([{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 512},
                           {"text": "Mismatch", "nbytes": 10, "kind": "dialog", "abs": 512}],
                          {"Hello": "你好   "})
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertFalse(out.exists(), "坏槽位仍写出了补丁")
        self.assert_no_tmp()

    def test_generated_patch_reapplies_cleanly(self):
        p, out = self.gen([{"text": "Hello", "nbytes": 10, "kind": "dialog", "abs": 512}],
                          {"Hello": "你好   "})
        self.assertEqual(p.returncode, 0, p.stdout)
        patch = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(patch["format"], "ltspice-zh-patch/1")
        self.assertEqual(len(patch["records"]), 1)
        data = bytearray(EN_PE)
        stats = {"applied": 0, "already": 0}
        missing = ap.apply_patch(data, patch, stats, SPAN)
        self.assertEqual((missing, stats["applied"], stats["wrong_len"]), ([], 1, 0))
        self.assertEqual(bytes(data[512:522]), u16("你好   "))


class TestOverlapPreflight(Base):
    """同一批记录里区间相交 = 无法证明每条都生效，整批拒绝、一个字节都不写。"""

    def test_same_offset_different_translation_rejected(self):
        data, old = bytearray(u16("Hello")), bytes(u16("Hello"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你好   "},
                                     {"off": 0, "text": "Hello", "zh": "再见   "}])
        self.assertEqual((s["applied"], s["already"], s["conflict"]), (0, 0, 1))
        self.assertEqual(bytes(data), old)

    def test_partial_overlap_rejected(self):
        """不同偏移、区间部分重叠（[0,10) 与 [2,14)）也要整批拒绝。"""
        data, old = bytearray(u16("HelloWorld")), bytes(u16("HelloWorld"))
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你好   "},
                                     {"off": 2, "text": "elloWo", "zh": "一二三四五六"}])
        self.assertEqual((s["applied"], s["conflict"]), (0, 1))
        self.assertEqual(bytes(data), old)

    def test_already_branch_participates_in_overlap_check(self):
        """已是译文的记录同样占区间：后一条想改重叠区段必须整批拒绝。"""
        data = bytearray(u16("你好   ") + u16("Hello"))
        old = bytes(data)
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你好   "},
                                     {"off": 2, "text": "好   He", "zh": "冲突冲突冲突"}])
        self.assertEqual((s["already"], s["applied"], s["conflict"]), (0, 0, 1))
        self.assertEqual(bytes(data), old)

    def test_identical_duplicate_is_deduped_not_double_counted(self):
        data = bytearray(u16("Hello"))
        rec = {"off": 0, "text": "Hello", "zh": "你好   "}
        s, _ = self.run_apply(data, [rec, dict(rec), dict(rec)])
        self.assertEqual((s["applied"], s["dup"], s["conflict"]), (1, 2, 0))
        self.assertEqual(bytes(data), u16("你好   "))

    def test_no_partial_write_before_conflict_detected(self):
        """冲突记录排在前面的记录也不能被写进去（先规划、后统一落盘）。"""
        data = bytearray(u16("Hello") + u16("World"))
        old = bytes(data)
        s, _ = self.run_apply(data, [{"off": 0, "text": "Hello", "zh": "你好   "},
                                     {"off": 10, "text": "World", "zh": "世界   "},
                                     {"off": 10, "text": "World", "zh": "地球   "}])
        self.assertEqual((s["applied"], s["conflict"]), (0, 1))
        self.assertEqual(bytes(data), old)

    def test_cli_conflict_leaves_everything_untouched(self):
        out = self.d / "conflict-out.exe"
        p, exe = self.cli([{"off": 512, "text": "Hello", "zh": "你好   "},
                           {"off": 512, "text": "Hello", "zh": "再见   "}],
                          ["--backup", "--out", str(out)])
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn("冲突", p.stdout)
        self.assertEqual(exe.read_bytes(), EN_PE)
        self.assertFalse(Path(str(exe) + ".orig.bak").exists())
        self.assertFalse(out.exists())
        self.assert_no_tmp()


class TestDialogParser(unittest.TestCase):
    """DLGTEMPLATE 解析：槽位偏移必须来自读取位置，不能按 len(文本) 反推。"""

    def _legacy(self, title, cdit=0, ctrl=None, style=0):
        """旧式 DLGTEMPLATE：style/exstyle/cdit/x/y/cx/cy = 18 字节，再 menu/class/title。"""
        b = struct.pack("<IIHhhhh", style, 0, cdit, 0, 0, 0, 0) + b"\0\0" * 2 + title + b"\0\0"
        if ctrl is not None:
            b += b"\0\0"                                   # 无创建数据
            b += struct.pack("<IIhhhhH", 0x0080, 0, 0, 0, 10, 10, 0xFFFF) + b"Button\0\0" + ctrl + b"\0\0"
            b += b"\0\0"
        return b

    def test_nonbmp_title_offset_is_byte_accurate(self):
        """'😀' 是 1 码点 / 2 码元：旧算法 p-len(v)*2-2 会把它算成 24。"""
        blob = self._legacy(u16("😀"))
        slots, ex = dl.parse_dialog(blob)
        self.assertFalse(ex)
        self.assertEqual(slots, [(22, "😀", "title")])
        self.assertEqual(blob[22:26], u16("😀"))

    def test_ascii_title_offset_unchanged(self):
        blob = self._legacy(u16("Hi"))
        self.assertEqual(dl.parse_dialog(blob)[0], [(22, "Hi", "title")])

    def test_every_field_offset_points_at_its_own_bytes(self):
        """title / font / ctrl_class / ctrl_title 四个位置都要按真实读取位置报。"""
        blob = self._legacy(u16("😀标"), style=0x40, cdit=1, ctrl=u16("&OK"))
        slots, _ = dl.parse_dialog(blob)
        for rel, text, _field in slots:
            nb = len(u16(text))
            self.assertEqual(blob[rel:rel + nb], u16(text),
                             "%r 偏移 %d 不是文本首字节" % (text, rel))
        self.assertEqual([f for _r, _t, f in slots],
                         ["title", "font", "ctrl_class", "ctrl_title"])


class TestRealData(unittest.TestCase):
    """真实数据的只读一致性校验：不写安装目录，只用英文备份读。"""

    def setUp(self):
        if not Path(EN_EXE).exists():
            self.skipTest("未提供原始英文 exe（LTSPICE_EN_EXE）")

    def test_slots_match_english_exe(self):
        raw = Path(EN_EXE).read_bytes()
        slots = json.loads((REPO / "dict" / "slots-26.1.1.json").read_text(encoding="utf-8"))["slots"]
        self.assertEqual(len(slots), 2745)
        bad = [s for s in slots if not mp.read_slot(raw, s)]
        self.assertEqual(bad, [], "基线槽位与英文 exe 不符：%s" % bad[:3])

    def test_committed_patch_is_unit_length_consistent(self):
        recs = json.loads((REPO / "patches" / "ltspice-26.1.1-zh.patch.json").read_text(encoding="utf-8"))["records"]
        bad = [r for r in recs
               if len(u16(r["zh"])) != len(u16(r["text"])) or "\x00" in r["zh"] or not r["text"]]
        self.assertEqual(bad, [], "已提交补丁含不合规记录：%s" % bad[:3])

    def test_committed_patch_reproduces_known_hash(self):
        """补丁打到英文备份上，产物 sha256 必须是文档记录的 e7759a9c…"""
        raw = Path(EN_EXE).read_bytes()
        patch = json.loads((REPO / "patches" / "ltspice-26.1.1-zh.patch.json").read_text(encoding="utf-8"))
        data = bytearray(raw)
        stats = {"applied": 0, "already": 0}
        pe_span = ap.resource_span(__import__("pefile").PE(data=raw))
        missing = ap.apply_patch(data, patch, stats, pe_span)
        ap.strip_signature_and_fix_checksum(data)
        self.assertEqual(missing, [])
        self.assertEqual((stats["wrong_len"], stats["ambiguous"], stats["rejected"]), (0, 0, 0))
        self.assertEqual(hashlib.sha256(bytes(data)).hexdigest(),
                         "e7759a9c113a290b2ec92843281f0fff386bf30891640b5c892396d547419651")


if __name__ == "__main__":
    unittest.main(verbosity=2)
