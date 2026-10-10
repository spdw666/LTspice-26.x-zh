# LTspice 26.x 汉化

把 Analog Devices **LTspice 26.x** 的界面换成简体中文：主菜单、右键菜单、工具栏下拉、130 个对话框、
状态栏与错误提示全部覆盖。给 agent 一键部署，也给人手动部署。

**不改动任何可执行代码** —— 只替换 PE 资源段里的界面文本，代码段、PE 头、节表零改动，随时可还原。

![汉化后的 LTspice 主界面](docs/screenshot.png)

---

## 目录

- [一、60 秒部署（给 agent 的指令）](#一60-秒部署给-agent-的指令)
- [二、手动部署](#二手动部署)
- [三、还原英文](#三还原英文)
- [四、覆盖范围](#四覆盖范围)
- [五、原理：为什么必须"等长替换"](#五原理为什么必须等长替换)
- [六、工具链详解](#六工具链详解)
- [七、自己出补丁 / 改词条](#七自己出补丁--改词条)
- [八、验证记录](#八验证记录)
- [九、常见问题](#九常见问题)
- [十、已知限制](#十已知限制)

---

## 一、60 秒部署（给 agent 的指令）

把下面这段直接丢给能跑命令的 agent（Claude Code / Codex / Cursor / DeepSeek Harness / Windsurf 等）：

```text
在本机安装 LTspice 26.x 汉化：
1. git clone https://github.com/spdw666/LTspice-26.x-zh 到工作区
2. pip install pefile
3. 运行 apply_patch.py（--exe 换成实际安装路径）：
   python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json --exe "<安装目录>/LTspice.exe" --backup --restore
   LTspice 默认安装在 %LOCALAPPDATA%\Programs\ADI\LTspice 或 C:\Program Files\ADI\LTspice
4. 验收标准：输出里必须是「替换 2599/2599 处（…），未定位 0 处」
5. 启动 LTspice，确认菜单栏显示「文件 / 视图 / 工具 / 帮助」
6. 提醒用户不要用 LTspice 自带的在线更新器覆盖主程序
```

依赖：Python 3.8+ / Windows / `pefile`（唯一第三方包）。补丁本体 200 KB。

---

## 二、手动部署

### 2.1 环境

| 项 | 要求 |
|---|---|
| 系统 | Windows 10 / 11（64 位） |
| Python | 3.8 及以上 |
| 第三方包 | `pefile` |
| LTspice | 26.x（26.1.1 为补丁基准版本） |

```powershell
pip install pefile
git clone https://github.com/spdw666/LTspice-26.x-zh
cd LTspice-26.x-zh
```

### 2.2 找到 LTspice 安装目录

两种常见位置，用哪个取决于安装时的选择：

```powershell
# 逐用户安装（最常见）
"$env:LOCALAPPDATA\Programs\ADI\LTspice\LTspice.exe"

# 全用户安装
"C:\Program Files\ADI\LTspice\LTspice.exe"

# 不确定就用这条自动定位（顺着桌面快捷方式解析目标）
(New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\LTspice.lnk").TargetPath
```

### 2.3 打补丁

```powershell
python tools/apply_patch.py `
    --patch patches/ltspice-26.1.1-zh.patch.json `
    --exe "C:\Program Files\ADI\LTspice\LTspice.exe" `
    --backup --restore
```

参数含义：

| 参数 | 作用 |
|---|---|
| `--patch` | 补丁文件路径 |
| `--exe` | 目标 `LTspice.exe` |
| `--backup` | 把原件另存为 `LTspice.exe.orig.bak`（只在不存在时创建，不会覆盖已有备份） |
| `--restore` | 先从这个备份还原，再打补丁 —— **加上它，命令就变成幂等的，可以反复执行** |
| `--out` | 输出到新文件而不原地覆盖（想留一份原件时用） |
| `--check` | 只试算不写盘，用来预检版本是否匹配 |

正常输出：

```text
目标就是补丁针对的原始版本 ✔  3c144a2b3ec6a30b…
替换 2599/2599 处（0 处已是译文），未定位 0 处
证书表目录项已摘除
PE 校验和已重算
已写出 C:\Program Files\ADI\LTspice\LTspice.exe  (70571120 bytes, sha256=6bd0de08…)
```

看到 **「未定位 0 处」** 才算完全成功。如果不是 0，说明目标版本与补丁基准差异较大，
见 [第七节](#七自己出补丁--改词条) 重新出补丁。

> 想先不动手，只看看能不能打：把 `--backup --restore` 换成 `--check`。

---

## 三、还原英文

```powershell
Copy-Item "C:\Program Files\ADI\LTspice\LTspice.exe.orig.bak" `
          "C:\Program Files\ADI\LTspice\LTspice.exe" -Force
```

或者直接重跑一次带 `--restore` 的部署命令（它会先还原再打补丁，等于"重置"）。

---

## 四、覆盖范围

2920 个可翻译槽位中命中 **2599 处**（89.0%），涉及 17 个菜单资源、130 个对话框资源、60 个字符串表块。

| 资源类型 | 资源个数 | 已译 / 槽位 | 命中率 | 典型内容 |
|---|---|---|---|---|
| 菜单模板 `RT_MENU` | 17 | 1031 / 1047 | 98.5% | 主菜单、全部右键菜单、工具栏下拉项 |
| 对话框 `RT_DIALOG` | 130 | 1096 / 1374 | 79.8% | 窗口标题、标签、按钮、复选框、提示语 |
| 字符串表 `RT_STRING` | 60 | 472 / 499 | 94.6% | 状态栏、工具提示、错误消息、文件类型过滤器 |
| **合计** | **207** | **2599 / 2920** | **89.0%** | 1514 条唯一文本中译出 1403 条 |

未翻译的 64 条唯一文本，全部是**不该翻**的东西：

| 类别 | 数量 | 例子 |
|---|---|---|
| 内部键 | 16 | `IDX_MRU_FILE1..16`（菜单内部 ID，翻了会错位） |
| 格式缩写 | 19 | `ASC` `ASY` `RAW` `FFT` `CAP` `COM` |
| 电气 / 参数名 | 20 | `Abstol:` `Chgtol:` `RelTol` `F0` `F1` |
| 其它 | 9 | `MS Shell Dlg`（Windows 字体名）、`<descr>` 之类占位符 |

> `LTspiceHelp\*.htm`（752 个 HTML 帮助页）**不在范围内**，保持英文 —— 动它容易破坏索引与交叉引用。

---

## 五、原理：为什么必须"等长替换"

LTspice 的资源加载器对每个条目的 **UTF-16 码元数**做边界校验。这不是猜的，是实测出来的：

> 把一条字符串表条目的译文改短（例如 `Paste BOM onto ASCII clipboard` → 中文 19 字符），
> 进程在启动后 **8 秒内直接退出**，Windows 事件日志留下
> `Faulting application name: LTspice.exe` —— 因为紧随其后的结构字段读到了旧字符残渣。

所以本项目的硬约束是：

**1. 菜单 / 字符串表 —— 补空格补齐**

译文右侧补空格，直到 **UTF-16 码元数与原文完全相同**。含 `\t` 的菜单项（共 238 条）
补在 `\t` **之前**，否则会把空格塞进快捷键列：

```text
原文  &New Schematic\tCtrl+N        (21 码元)
译文  &新建原理图       \tCtrl+N      (21 码元，补 7 个空格)
```

**2. 对话框 —— 严格等长**

对话框文案本来就短，直接严格等长；万一译文放不下，**跳过并保留英文**，绝不截断结构字段。

**3. 结果：原地等长字节写入**

| 部位 | 是否改动 |
|---|---|
| `.rsrc` 段内的界面文本字节 | ✅ 唯一的改动点 |
| PE 头 / 节表 / 资源目录 | ❌ 零改动 |
| `.text` 代码段 / `.rdata` / `.data` | ❌ 零改动 |
| 文件总长度 | ❌ 完全不变（70571120 字节） |

唯一被迫动的"非文本"是：**Authenticode 证书表目录项被摘除**（改了字节签名必然失效，
留着无效签名不如摘掉干净），以及随之 **重算的 PE 校验和**。这两处由脚本自动完成。

---

## 六、工具链详解

```text
LTspice-26.x-zh/
├─ patches/
│  └─ ltspice-26.1.1-zh.patch.json    ★ 核心：2599 条「原文 → 译文」替换
├─ tools/
│  ├─ apply_patch.py                   ★ 部署用：把补丁打进目标 exe
│  ├─ scan_slots.py                    扫描 exe 里所有可翻译槽位 → slots.json
│  ├─ make_patch.py                    基准 slots + 词典 + 原始 exe → 新补丁
│  └─ dlg.py                           DLGTEMPLATE / DLGTEMPLATEEX 解析器
├─ dict/
│  ├─ zh_dict.json                     1466 条人工校对词典（含专业术语）
│  └─ slots-26.1.1.json                26.1.1 基准槽位表（2920 条）
├─ docs/
│  ├─ screenshot.png
│  └─ SKILL.md                         给 agent 的精简版 skill 说明
├─ AGENTS.md                           agent 自动读取的仓库约定
└─ README.md
```

### `apply_patch.py` —— 部署

按**原文文本**匹配，不依赖绝对偏移。所以：

- 同版本：偏移精确命中，快且准；
- 跨小版本（26.1.1 → 26.1.2）：偏移对不上时自动全文搜索原文再定位；
- 定位不到的条目**跳过并计数**，不会写坏文件。

```powershell
python tools/apply_patch.py --patch <补丁> --exe <目标 exe> [--backup] [--restore] [--out <输出>] [--check]
```

### `scan_slots.py` —— 扫描

三类资源各用其原生格式精确定位，**不做模糊全文扫描**，因此不会误改二进制数据：

- `RT_MENU`：用 Win32 `user32` 读出权威文本顺序，再在 blob 内按字节顺序定位（需要 Windows GUI 环境）；
- `RT_STRING`：长度前缀自描述，直接解析；
- `RT_DIALOG`：按 `DLGTEMPLATE` / `DLGTEMPLATEEX` 逐字段解析。

```powershell
$env:LTSPICE_EXE = "C:\Program Files\ADI\LTspice\LTspice.exe.orig.bak"
$env:SLOTS_OUT   = "slots.json"
python tools/scan_slots.py
```

### `make_patch.py` —— 出补丁

```powershell
python tools/make_patch.py --slots slots.json --dict zh_dict.json --exe <原始 exe> -o my.patch.json
python tools/make_patch.py --slots slots.json --dict zh_dict.json --exe <原始 exe> --verify   # 只自检
```

`--verify` 会做 roundtrip 自检：用空词典跑一遍，结果必须与输入**逐字节相同**。

---

## 七、自己出补丁 / 改词条

### 7.1 只想改几个词

1. 打开 `dict/zh_dict.json`，格式是 `"英文原文": "中文译文"`：

   ```json
   {
     "Place a bus tap": "放置总线分支",
     "&New Schematic\tCtrl+N": "&新建原理图\tCtrl+N"
   }
   ```

2. 重出补丁（**`--exe` 必须是原始英文 exe**）：

   ```powershell
   python tools/make_patch.py --slots dict/slots-26.1.1.json --dict dict/zh_dict.json `
       --exe "C:\Program Files\ADI\LTspice\LTspice.exe.orig.bak" `
       -o patches/ltspice-26.1.1-zh.patch.json
   ```

3. 译文放不下会自动跳过并打印 `译文超长(NB>MB)` —— 看着改短即可。

### 7.2 换了 LTspice 版本（26.1.2 / 26.2 / 27…）

```powershell
# ① 先确认目标版本能不能直接套用现有补丁
python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json --exe "<新版本 exe>" --check

# ② 差异太大就重扫基准（必须用**原始英文** exe！）
$env:LTSPICE_EXE = "<新版本原始 exe>"
$env:SLOTS_OUT   = "slots-26.1.2.json"
python tools/scan_slots.py

# ③ 用同一份词典重出补丁
python tools/make_patch.py --slots slots-26.1.2.json --dict dict/zh_dict.json --exe "<新版本原始 exe>" -o patches/ltspice-26.1.2-zh.patch.json
```

> **⚠️ 最常踩的坑**：扫基准必须用**原始英文 exe**。拿已汉化的 exe 去扫，得到的"原文"
> 是中文，基准就废了，后续所有版本都对不上。上一版的备份就在 `LTspice.exe.orig.bak`。

---

## 八、验证记录

以下都是在本机真实跑出来的结果，不是推断：

| 验证项 | 方法 | 结果 |
|---|---|---|
| 补丁自洽性 | 空词典 roundtrip | 与原文件**逐字节一致** ✔ |
| 补丁正确性 | 从 GitHub 全新 clone → 打补丁 → 比对 sha256 | 产物 `6bd0de08…` 与手工构建的汉化版**完全一致** ✔ |
| 扫描器正确性 | 仓库版 `scan_slots.py` vs 人工基准 | 2920 条槽位**逐条相同**（差异 0）✔ |
| 资源完整性 | 用 Win32 API 加载全部菜单资源 | 17 个全部可加载，**项数与英文版逐一相同** ✔ |
| 运行时正确性 | 启动后实时读取运行中窗口的菜单文本 | `&文件 / &视图 / &工具 / &帮助`，子项 `&新建原理图 Ctrl+N`、`&打开... Ctrl+O`、`退出` ✔ |
| 进程存活 | 打补丁后连续观察 30 秒 | 进程存活，主窗口正常显示 ✔ |

可复现的验收脚本（PowerShell），部署完可以直接跑：

```powershell
Add-Type -AssemblyName System.Drawing
$p = Start-Process "$env:LOCALAPPDATA\Programs\ADI\LTspice\LTspice.exe" -PassThru
Start-Sleep 8
if (Get-Process -Id $p.Id -ErrorAction SilentlyContinue) { "进程存活 ✔" } else { "启动崩溃 ✘" }
```

---

## 九、常见问题

**Q：启动后界面还是英文？**
A：确认你改的是**正在运行的那个安装**。如果同时装了逐用户和全用户两版，快捷方式指向哪个就改哪个。
用第二节的快捷方式解析命令确认路径。

**Q：提示「未定位 N 处」，N 很大？**
A：版本差异过大。按 7.2 重新扫基准出补丁；也可以直接看 `--check` 的输出，它会列出前 10 条未定位的原文。

**Q：菜单里出现了多余的空格？**
A：那是补齐用的填充空格（见第五节）。它是**必需的**，删掉就会启动崩溃。视觉上菜单项左对齐，
不影响任何功能，也不影响快捷键。

**Q：LTspice 提示更新，更新完汉化没了？**
A：正常 —— 更新器会覆盖 `LTspice.exe`。重跑一次部署命令即可；建议在 LTspice 里关掉自动更新。

**Q：Windows Defender / 杀软报毒？**
A：改过签名的 exe 常见误报。源码全在仓库里，可以自己审计；也可以先用 `--out` 输出到别的路径试跑。

**Q：能汉化帮助文档吗？**
A：`LTspiceHelp\*.htm` 有 752 个文件，涉及索引与交叉引用，本仓库不处理。

**Q：这是官方汉化吗？**
A：不是。ADI 没有出过中文界面。本仓库是社区对官方 exe 的资源替换，不修改任何逻辑代码。

---

## 十、已知限制

- 改过字节后 ADI 的 Authenticode 签名必然失效，脚本会主动摘除证书表目录项并重算 PE 校验和（正常现象）。
- 不要用 LTspice 自带的在线更新器覆盖主程序，会冲掉汉化；重跑 `apply_patch.py` 即可恢复。
- 只覆盖 26.x 的 PE 资源；帮助文档与示例电路不在范围内。
- 菜单文本最长只能与英文等长（补齐空格），所以个别长句中文会偏紧凑。
- 术语如有不同意见，改 `dict/zh_dict.json` 重出补丁即可，欢迎提 PR。

---

## 许可证

工具与词典采用 **MIT**。LTspice 本体版权归 Analog Devices, Inc.，
本仓库**不含任何 ADI 二进制文件** —— 只有文本补丁（原文 → 译文对照）、脚本和截图。
LTspice 是 Analog Devices, Inc. 的商标。
