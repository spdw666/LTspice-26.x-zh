# 给 agent 的仓库约定

本仓库是 **LTspice 26.x 界面汉化**（PE 资源原地等长替换）。部署方式见
[docs/SKILL.md](docs/SKILL.md) 与 README。

## 你要做的事

用户要求"汉化 LTspice"时：

1. 定位安装目录：`%LOCALAPPDATA%\Programs\ADI\LTspice` 或 `C:\Program Files\ADI\LTspice`。
2. `pip install pefile`。
3. 首次部署（**不要加 `--restore`，本机还没有备份**）：

   ```
   python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json --exe "<目录>/LTspice.exe" --backup
   ```

   重复部署或想重置时，才加上 `--restore`（会先从备份还原再打补丁）。

4. 验收：退出码必须是 **0**，且输出含 `未定位 0 处`、`长度不合规 0 处`。
5. 启动后确认菜单为「文件 / 视图 / 工具 / 帮助」；对话框能正常打开（元件属性编辑器等）。

## 绝对不能做

- **不要手写替换逻辑绕过 `make_patch.py`**。三类资源的字段都以 NUL 结尾，
  **字段边界由 NUL 位置决定**：译文短于原文后再填 NUL，等于提前终止字段，
  紧随其后的字体名 / 控件类 / 控件字段会全部错位，`CreateDialogIndirectParamW` 直接失败。
  正确做法是一律补空格到与原文字符数**完全相同**。
- **不要把"已汉化的 exe"当基准去扫 `slots.json`**，那会得到中文原文，基准就废了。
  基准必须来自原始英文 exe。
- 不要提交任何 ADI 二进制文件（`*.exe` 已在 `.gitignore` 中）。
- 不要动 `LTspiceHelp\*.htm`。

## 验证基线

- `patches/ltspice-26.1.1-zh.patch.json` 打完后产物 sha256 应为
  `e7759a9c113a290b2ec92843281f0fff386bf30891640b5c892396d547419651`
- `tools/scan_slots.py` 对 26.1.1 原始 exe 应扫出 **2745** 个槽位
  （菜单 1047 / 对话框 1199 可翻译字段 / 字符串表 499）
- 130 个对话框模板必须 **全部可解析**；88 个实际存在的对话框资源，
  其 `CreateDialogIndirectParamW` 成/败状态必须与原始英文版**逐一相同**
