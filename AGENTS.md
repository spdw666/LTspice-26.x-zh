# 给 agent 的仓库约定

本仓库是 **LTspice 26.x 界面汉化**（PE 资源原地等长替换）。部署方式见
[docs/SKILL.md](docs/SKILL.md) 与 README。

## 你要做的事

用户要求"汉化 LTspice"时：

1. 定位安装目录：`%LOCALAPPDATA%\Programs\ADI\LTspice` 或 `C:\Program Files\ADI\LTspice`。
2. `pip install pefile`。
3. `python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json --exe "<目录>/LTspice.exe" --backup --restore`
4. 验收：`未定位 0 处`；启动后再用 `GetMenuStringW` 读运行中窗口的菜单文本确认是中文。

## 绝对不能做

- **不要手写替换逻辑绕过 `make_patch.py`**。LTspice 对条目长度极敏感，译文短于原文会让
  进程启动即崩溃。补齐空格到原文字符数是硬要求。
- **不要把"已汉化的 exe"当基准去扫 `slots.json`**，那会得到中文原文，基准就废了。
  基准必须来自原始英文 exe。
- 不要提交任何 ADI 二进制文件（`*.exe` 已在 `.gitignore` 中）。
- 不要动 `LTspiceHelp\*.htm`。

## 验证基线

- `patches/ltspice-26.1.1-zh.patch.json` 打完后产物 sha256 应为
  `6bd0de084f0643cf8656041765271fe3f9af62d272b2182898cce09989962d7b`
- `tools/scan_slots.py` 对 26.1.1 原始 exe 应扫出 **2920** 个槽位
  （菜单 1047 / 对话框 1374 / 字符串表 499）。
