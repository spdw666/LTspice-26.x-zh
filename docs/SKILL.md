---
name: ltspice-zh-deploy
description: |
  在本机为 ADI LTspice 26.x 安装简体中文界面汉化。当用户说"汉化 LTspice""把 LTspice 变中文"
  "LTspice 装中文界面""LTspice Chinese"、或要求给 LTspice 部署汉化补丁时使用。也适用于
  重新生成 / 修改汉化词条、或把汉化补丁适配到 LTspice 其它小版本的场景。
  若用户要的是用 MCP 控制 LTspice 做仿真（不是汉化），不要使用本 skill。
---

# LTspice 26.x 汉化部署

对 `LTspice.exe` 的 PE 资源段做**原地等长字节替换**，把界面文本换成简体中文。
不改代码段，不动 PE 头，可随时用备份还原。

## 核心约束（违反会导致对话框无法创建或进程崩溃）

**三类资源的文本字段都以 NUL 结尾，字段边界由 NUL 位置决定。**

因此译文必须补空格到与原文字符数**完全相同**。绝不能"缩短后把剩余字节填 NUL" ——
那等于提前终止字段，紧随其后的字体名 / 控件类 / 控件字段全部错位，
`CreateDialogIndirectParamW` 直接失败（历史上 88 个对话框里 87 个打不开）。

长度按 **UTF-16 码元 / 字节**算，不是按 Python 码点数：一个 emoji 算 2 码元。
不合规输入（空原文、内嵌 NUL、非法 kind、越界偏移、孤立代理项）会被脚本拒绝并计入失败。

`tools/make_patch.py` 已内置补齐与槽位校验，不要绕过它手写替换。

**写入是事务性的**：预检有任一条不成功，目标 / `--out` / 备份一个字节都不改，退出码 1。
所以看到非 0 退出码时，磁盘状态仍然干净，修好补丁重跑即可。

**别在补丁里放重叠记录**：同一批记录里任意两条的写入区间 `[off, off+nbytes)` 相交
（同偏移两个不同译文、不同偏移部分重叠）时，无法证明每条都生效，整批作废、退出码 1。
完全相同的重复记录会被去重，只计一次成功。

## 部署步骤

1. 找安装目录（二选一）：
   `%LOCALAPPDATA%\Programs\ADI\LTspice` 或 `C:\Program Files\ADI\LTspice`。
   可用快捷方式解析确认：`(New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\LTspice.lnk").TargetPath`。
2. `pip install pefile`（唯一依赖，Python 3.8+，Windows）。
3. 首次部署（**不要加 `--restore`**）：

   ```
   python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json --exe "<目录>/LTspice.exe" --backup
   ```

   之后重装或重置时再加 `--restore`（会先从备份还原再打补丁）。

4. 验收：**退出码必须是 0**，且输出含 `未定位 0 处`、`长度不合规 0 处`、`歧义 0 处`、
   `不合规拒绝 0 处`。非 0 时磁盘完全没有改动，可以放心修。
5. 启动 LTspice，确认菜单为「文件 / 视图 / 工具 / 帮助」，并试着打开元件属性编辑器
   （选中元件按 Ctrl+右键 → Properties）。菜单文本也可以用 `GetMenuStringW` 直接读运行中窗口做机器校验。
6. 工具链改动后可跑 `python tests/test_regression.py -v`（56 项）确认防护未被削弱。

## 重新出补丁（换了版本或要改词条）

基准 `slots.json` **必须从原始英文 exe 扫描**；扫描已汉化的 exe 会得到中文原文，无法当基准。

```
$env:LTSPICE_EXE = "<原始英文 exe 路径>"
$env:SLOTS_OUT   = "slots.json"
python tools/scan_slots.py

python tools/make_patch.py --slots slots.json --dict zh_dict.json --exe "<原始英文 exe>" -o patches/xxx.patch.json
```

改 `dict/zh_dict.json` 里的 `"英文原文": "中文译文"` 即可调整词条；译文超长会被自动跳过并计数。
`make_patch.py` 会在 sha256 与 exe 不符时直接失败（偏移已失效），并逐个槽位校验边界与字节，
有坏槽位就不产出补丁 —— 遇到失败先重跑 `scan_slots.py`，不要绕过。

## 还原

```
Copy-Item "<安装目录>\LTspice.exe.orig.bak" "<安装目录>\LTspice.exe" -Force
```

脚本也兼容 `.orig-*.bak` 命名（例如 `.orig-26.1.1.bak`）。

## 注意

- 改字节后 ADI 签名失效，脚本会摘除证书表目录项并重算 PE 校验和（正常现象）。
- 不要用 LTspice 自带在线更新器覆盖主程序，会冲掉汉化；重跑 apply_patch.py 即可恢复。
- 帮助文档 `LTspiceHelp\*.htm` 不在范围内。
- 用 MCP 控制 LTspice 做仿真与汉化无关；LTspice 26.x 自带 `ltspice-mcp-bridge.exe`。
