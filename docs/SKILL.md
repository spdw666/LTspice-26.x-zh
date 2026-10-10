---
name: ltspice-zh-deploy
description: |
  在本机为 ADI LTspice 26.x 安装简体中文界面汉化。当用户说"汉化 LTspice""把 LTspice 变中文"
  "LTspice 装中文界面""LTspice Chinese"、或要求给 LTspice 部署汉化补丁时使用。也适用于
  需要重新生成 / 修改汉化词条、或把汉化补丁适配到 LTspice 其它小版本的场景。
  若用户要的是用 MCP 控制 LTspice 做仿真（不是汉化），不要使用本 skill。
---

# LTspice 26.x 汉化部署

对 `LTspice.exe` 的 PE 资源段做**原地等长字节替换**，把界面文本换成简体中文。
不改代码段，不动 PE 头，可随时用备份还原。

## 硬约束（违反会导致 LTspice 启动即崩溃）

LTspice 资源加载器按条目的 **UTF-16 码元数**做边界校验。译文比原文**短**时，
后续结构字段会读到旧字符残渣，进程 8 秒内退出。所以：

- 菜单项、字符串表：译文必须**补空格**到与原文字符数相同；含 `\t` 的项补在 `\t` 之前。
- 对话框：严格等长，译文超长就跳过（保留英文），绝不截断结构。

`tools/make_patch.py` 已内置这套补齐逻辑，不要绕过它手写替换。

## 部署步骤

1. 找安装目录（二选一）：
   `%LOCALAPPDATA%\Programs\ADI\LTspice` 或 `C:\Program Files\ADI\LTspice`。
   用 `Get-Command` / 桌面快捷方式解析 / 直接 `Test-Path` 都可以，确认目录里有 `LTspice.exe`。
2. `pip install pefile`（唯一依赖，Python 3.8+，Windows）。
3. 打补丁（`--backup` 存原件，`--restore` 先还原再打，两者一起用可重复执行）：

   ```
   python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json \
       --exe "<安装目录>\LTspice.exe" --backup --restore
   ```

4. 验收：输出必须是 `替换 N/N 处（...），未定位 0 处`。未定位不是 0 时，
   说明目标版本与补丁基准差异较大，改用下方"重新出补丁"。
5. 启动 LTspice，确认菜单栏是「文件 / 视图 / 工具 / 帮助」。可用
   `GetMenuStringW` 直接读运行中窗口的菜单文本做机器校验，比截图更可靠。

## 重新出补丁（换了版本或要改词条）

基准 `slots.json` **必须从原始英文 exe 扫描**；扫描已汉化的 exe 会得到中文原文，无法当基准。

```
$env:LTSPICE_EXE = "<原始英文 exe 路径>"
$env:SLOTS_OUT   = "slots.json"
python tools/scan_slots.py

python tools/make_patch.py --slots slots.json --dict zh_dict.json --exe "<原始英文 exe>" -o patches/xxx.patch.json
```

改 `zh_dict.json` 里的 `"英文原文": "中文译文"` 即可调整词条；译文超长会被自动跳过并计数。

## 还原

```
Copy-Item "<安装目录>\LTspice.exe.orig.bak" "<安装目录>\LTspice.exe" -Force
```

## 注意

- 改字节后 ADI 签名失效，脚本会摘除证书表目录项并重算 PE 校验和（正常现象）。
- 不要用 LTspice 自带在线更新器覆盖主程序，会冲掉汉化；重跑 apply_patch.py 即可恢复。
- 帮助文档 `LTspiceHelp\*.htm` 不在范围内。
- 用 MCP 控制 LTspice 做仿真与汉化无关；LTspice 26.x 自带 `ltspice-mcp-bridge.exe`。
