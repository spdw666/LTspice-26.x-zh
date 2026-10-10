# LTspice 26.x 汉化

把 Analog Devices **LTspice 26.x** 的界面换成简体中文：主菜单、右键菜单、工具栏下拉、对话框标题与控件、
状态栏与错误提示。给 agent 一键部署，也给人手动部署。

**不改动任何可执行代码** —— 只替换 PE 资源段里的界面文本，代码段、PE 头、节表零改动，随时可还原。

> **关于"是不是唯一一个"**：本仓库创建时做过一轮检索 —— GitHub 仓库搜索（12 组关键词：
> `ltspice chinese` / `ltspice 汉化` / `ltspice 中文` / `ltspice localization` 等）、
> GitHub 代码搜索（4 组）、全网搜索 —— **未发现其它可用的 LTspice 26.x 界面汉化项目**。
> 全网唯一在做的中文汉化只覆盖 26.0.2 且走网盘，无公开镜像。
> 这是"本次检索未发现"，不是对全网的绝对断言。

> **2026-10-10 重要修复**：早期版本（产物 sha256 `6bd0de08…`）的对话框资源存在结构错位，
> 46/130 个对话框模板无法解析、绝大多数对话框无法打开。根因与修复见
> [第五节](#五原理文本字段的边界由-nul-决定)。当前版本产物为 `e7759a9c…`，已通过逐对话框对照验证。
> 如果你装过旧版，用下面的命令重装即可。

---

## 目录

- [一、60 秒部署（给 agent 的指令）](#一60-秒部署给-agent-的指令)
- [二、手动部署](#二手动部署)
- [三、还原英文](#三还原英文)
- [四、覆盖范围](#四覆盖范围)
- [五、原理：文本字段的边界由 NUL 决定](#五原理文本字段的边界由-nul-决定)
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
3. 首次部署（本机还没有备份，不要加 --restore）：
   python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json --exe "<安装目录>/LTspice.exe" --backup
   LTspice 默认安装在 %LOCALAPPDATA%\Programs\ADI\LTspice 或 C:\Program Files\ADI\LTspice
4. 验收标准：退出码为 0，且输出含「未定位 0 处」「长度不合规 0 处」
5. 启动 LTspice，确认菜单栏是「文件 / 视图 / 工具 / 帮助」，并能打开元件属性编辑器
6. 提醒用户不要用 LTspice 自带的在线更新器覆盖主程序
```

依赖：Python 3.8+ / Windows / `pefile`（唯一第三方包）。补丁本体 257 KB。

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

# 不确定就顺着桌面快捷方式解析目标
(New-Object -ComObject WScript.Shell).CreateShortcut("$env:USERPROFILE\Desktop\LTspice.lnk").TargetPath
```

### 2.3 打补丁

```powershell
# 首次部署
python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json `
    --exe "C:\Program Files\ADI\LTspice\LTspice.exe" --backup

# 之后每次重装 / 想重置（会先从备份还原再打）
python tools/apply_patch.py --patch patches/ltspice-26.1.1-zh.patch.json `
    --exe "C:\Program Files\ADI\LTspice\LTspice.exe" --backup --restore
```

参数含义：

| 参数 | 作用 |
|---|---|
| `--patch` | 补丁文件路径 |
| `--exe` | 目标 `LTspice.exe` |
| `--backup` | 备份成 `LTspice.exe.orig.bak`（已存在同名备份时不覆盖；仅在整次替换会成功时才写） |
| `--restore` | 以备份为基准重打补丁，使命令幂等。**首次部署不要加**，没有备份时会明确报错退出 |
| `--out` | 输出到新文件而不原地覆盖（失败时不创建、不覆盖已存在的文件） |
| `--check` | 无条件只读：试算并报告，绝不写盘（此时 `--backup`/`--restore` 被忽略） |

正常输出（退出码 0）：

```text
目标就是补丁针对的原始版本 ✔  3c144a2b3ec6a30b…
资源段 .rsrc: 0x37ed400 - 0x4310c00
替换 2599/2599 处（0 处已是译文），未定位 0 处，长度不合规 0 处，歧义 0 处
已备份 -> C:\Program Files\ADI\LTspice\LTspice.exe.orig.bak
证书表目录项已摘除
PE 校验和已重算
已写出 C:\Program Files\ADI\LTspice\LTspice.exe  (70571120 bytes, sha256=e7759a9c…)
全部替换成功。
```

**退出码语义**：0 = 全部替换成功；1 = 有未定位 / 长度不合规 / 歧义 / 不合规记录的条目，或命令出错。
agent 应当把非 0 退出码视为部署失败。

**写入是事务性的**：先在内存里做完整预检，**全部记录都成功才允许落盘**。
只要有一条不成功，目标文件、`--out`、备份一律保持原样（`--restore` 也只把备份读进内存比对，
不会再"先还原再发现打不上"）。落盘用同目录临时文件 + 原子替换，中断不会留下半个文件。

**区间冲突也会整体拒绝**：一批记录里任意两条的写入区间 `[off, off+nbytes)` 相交
（同偏移不同译文，或不同偏移部分重叠，含"已是译文"的记录占用的区间），
就无法证明每条都真正生效 —— 此时整批取消、一个字节都不写，退出码 1。
完全相同的重复记录（同偏移、同译文）按去重处理：只写一次，也只计一次成功。

> 想先不动手只看看：把参数换成 `--check`。它是无条件只读的，连备份都不写。

---

## 三、还原英文

```powershell
Copy-Item "C:\Program Files\ADI\LTspice\LTspice.exe.orig.bak" `
          "C:\Program Files\ADI\LTspice\LTspice.exe" -Force
```

或重跑带 `--restore` 的部署命令（先还原再打补丁，等于重置）。

> 本机（DSH 维护的那台）原始备份名为 `LTspice.exe.orig-26.1.1.bak`，
> 脚本同时兼容 `.orig.bak` 与 `.orig-*.bak` 两种命名。

---

## 四、覆盖范围

2745 个可翻译槽位中命中 **2599 处**（94.7%），涉及 17 个菜单资源、130 个对话框资源、60 个字符串表块。

| 资源类型 | 资源个数 | 已译 / 槽位 | 命中率 | 典型内容 |
|---|---|---|---|---|
| 菜单模板 `RT_MENU` | 17 | 1031 / 1047 | 98.5% | 主菜单、全部右键菜单、工具栏下拉项 |
| 对话框 `RT_DIALOG` | 130 | 1096 / 1199 | 91.4% | 标题 119 条、控件标题 977 条 |
| 字符串表 `RT_STRING` | 60 | 472 / 499 | 94.6% | 状态栏、工具提示、错误消息、文件类型过滤器 |
| **合计** | **207** | **2599 / 2745** | **94.7%** | 1507 条唯一文本中译出 1403 条 |

> 对话框槽位数从早期的 1374 降到 1199，是因为**只收可翻译字段**（标题与控件标题）。
> 窗口类名（`SysListView32`）、字体名（`MS Shell Dlg`）是结构字段，翻了会让对话框创建失败。

未翻译的条目全部是**不该翻**的东西：

| 类别 | 例子 |
|---|---|
| 内部键 | `IDX_MRU_FILE1..16`（菜单内部 ID，翻了会错位） |
| 格式缩写 | `ASC` `ASY` `RAW` `FFT` `CAP` `COM` |
| 电气 / 参数名 | `Abstol:` `Chgtol:` `RelTol` `F0` `F1` |
| 结构字段 | 对话框的 `class` / `ctrl_class` / `font`（代码主动跳过，不是遗漏） |

> `LTspiceHelp\*.htm`（752 个 HTML 帮助页）**不在范围内**，保持英文。

---

## 五、原理：文本字段的边界由 NUL 决定

这是本项目最关键、也最容易踩错的一点。

### 5.1 字段长什么样

三类资源的模板里，文本字段都是 **`sz_Or_Ord`**：一串 UTF-16 字符，后跟一个 NUL 结束符。
**字段占用多少字节，是由 NUL 的位置决定的**，不是由"你写了多少字节"决定的。

```text
对话框模板（DLGTEMPLATEEX）:
  [18 字节头][menu][class][title ← NUL 结尾][字体][控件0][控件1]…

菜单模板:
  [option][submenu id][文本 ← NUL 结尾][下一个 option]…
```

### 5.2 错误做法（早期版本，已修复）

把中文写进去、剩余位置**填 NUL**：

```text
title: "Select Standard Resistor" (24 码元) → "选择标准电阻" (6 码元) + 18 个 NUL
                                            ↑ 解析器在这里就认为字段结束了
```

于是紧接其后的字体名字段从**错误的位置**开始读 —— 字体名读成 `l Dlg`，
控件类读成 `sListView32`，再往后整个控件表全错位。
表现就是：**模板能"读完"，但 `CreateDialogIndirectParamW` 直接失败**。

实测对比（同一台机器，逐资源调用 Win32 API）：

| 检查 | 原始英文 | 旧汉化版 `6bd0de08…` | 当前版 `e7759a9c…` |
|---|---:|---:|---:|
| 130 个对话框模板解析成功 | 130 | **84**（46 个抛异常） | 130 |
| 结构字段（font/class）与原文一致的模板 | 130 | 52 | **130** |
| 88 个实际存在的对话框，`CreateDialogIndirectParamW` 成功 | 87 | **1** | **87** |
| 与英文版成/败状态逐一相同的对话框 | — | 1 | **88 / 88** |

### 5.3 正确做法

**一律补空格到与原文完全相同的 UTF-16 码元数。**

```text
"Select Standard Resistor" (24 码元)
→ "选择标准电阻" + 18 个空格 (24 码元)   ✔ NUL 位置不变，后续字段全部对齐
```

菜单项含 `\t`（快捷键提示分隔符，共 238 条）时，空格补在 `\t` **之前**，避免污染快捷键列：

```text
原文  &New Schematic\tCtrl+N        (21 码元)
译文  &新建原理图       \tCtrl+N      (21 码元，补 7 个空格)
```

### 5.4 改动边界

| 部位 | 是否改动 |
|---|---|
| `.rsrc` 段内的界面文本字节 | ✅ 唯一的改动点 |
| PE 头 / 节表 / 资源目录 | ❌ 零改动 |
| `.text` 代码段 / `.rdata` / `.data` | ❌ 零改动 |
| 文件总长度 | ❌ 完全不变（70571120 字节） |

定位搜索也**硬限制在 `.rsrc` 段内**，且当某条原文在段内出现多次时判定为歧义、跳过不改，
绝不猜。唯二被迫动的"非文本"是 Authenticode 证书表目录项（改了字节签名必然失效，
留着无效签名不如摘掉）与随其重算的 PE 校验和，由脚本自动完成。

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
│  └─ slots-26.1.1.json                26.1.1 基准槽位表（2745 条）
├─ docs/
│  └─ SKILL.md                         给 agent 的精简版 skill 说明
├─ tests/
│  └─ test_regression.py               工具链回归测试（47 项，含真实数据只读校验）
├─ AGENTS.md                           agent 自动读取的仓库约定
└─ README.md
```

### `apply_patch.py` —— 部署

按**原文文本**匹配，仅在 `.rsrc` 段内定位：

- 同版本：优先用记录里的精确偏移；
- 跨小版本（26.1.1 → 26.1.2）：偏移对不上时在 `.rsrc` 内搜索原文，**多处命中则跳过**（歧义即失败，不猜）；
- 应用前强制校验每条译文的 **UTF-16 码元数**与原文一致（按 UTF-16LE 字节长度算，不是 Python 码点数），不符则整条拒绝写入；
- 拒绝不合规记录：空原文、原文或译文含内嵌 NUL、非字符串字段、未知 `kind`、孤立代理项；
- **区间冲突预检**：一批记录里任意两条的 `[off, off+nbytes)` 相交（同偏移不同译文、
  不同偏移部分重叠，含"已是译文"记录占用的区间）就无法证明每条都生效 ——
  整批拒绝、一个字节都不写、退出码 1；完全相同的重复记录去重，只写一次也只计一次成功；
- 预检全过才落盘：目标 / `--out` / 备份要么全改，要么一个字节都不动；
- 退出码反映真实结果：有任何一条没成功（未定位 / 长度不合规 / 歧义 / 不合规 / 区间冲突）就是 1。

```powershell
python tools/apply_patch.py --patch <补丁> --exe <目标 exe> [--backup] [--restore] [--out <输出>] [--check]
```

### `scan_slots.py` —— 扫描

三类资源各用其原生格式精确定位，**不做模糊全文扫描**，因此不会误改二进制数据：

- `RT_MENU`：用 Win32 `user32` 读出权威文本顺序，再在 blob 内按字节顺序定位（需 Windows GUI 环境）；
- `RT_STRING`：长度前缀自描述，直接解析；
- `RT_DIALOG`：按 `DLGTEMPLATE` / `DLGTEMPLATEEX` 逐字段解析，**只收 `title` 与 `ctrl_title`**
  （`class` / `ctrl_class` / `font` 是结构字段，收了会让对话框创建失败）。
  槽位偏移由解析过程直接给出，**不按 `len(文本)` 反推** —— `len()` 数的是码点，
  含 emoji 等非 BMP 字符的标题会少算 2 字节/字符，导致 `abs` 偏大、改错位置。

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

`--verify` 做 roundtrip 自检：用空词典跑一遍，结果必须与输入**逐字节相同**。
译文超长的条目会被拒绝并计入 `超长跳过`，不会写进补丁。

安全约束（生成器与部署器一致）：

- `slots.json` 记录的 sha256 与 `--exe` 不一致时**直接失败退出，不创建任何输出** ——
  偏移已失效，按偏移改就是改坏数据；
- 每个槽位先校验：`kind` 白名单、`nbytes` 为正偶数、`abs` 不越界、exe 内该偏移的字节
  确实等于 `text`、对话框槽位的 `field` 必须是 `title` / `ctrl_title`；
  任一不符即为**坏槽位**，跳过不写并计数，CLI 层面有坏槽位就拒绝产出补丁；
- 译文补齐按 **UTF-16 码元数**（非 BMP 字符算 2 码元），补齐后字节数必须与槽位完全相等，
  否则丢弃该条 —— 绝不截断代理对，也绝不写出超长内容覆盖原字段之后的字节；
- 补丁先在内存里生成完整内容，最后用同目录临时文件 + 原子替换写出。

### 回归测试

```powershell
python tests/test_regression.py -v              # 47 项，含真实数据只读校验
python -m unittest discover -s tests -v
```

真实数据的用例读 `LTSPICE_EN_EXE`（默认本机 `LTspice.exe.orig-26.1.1.bak`），
只读比对槽位、补丁记录，并重放补丁验产物哈希 `e7759a9c…`；**不写安装目录、不启动 LTspice**。

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

3. 译文放不下会自动跳过并打印 `超长跳过 N` —— 看着改短即可。

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

> **⚠️ 最容易踩的坑**：扫基准必须用**原始英文 exe**。拿已汉化的 exe 去扫，得到的"原文"
> 是中文，基准就废了，后续所有版本都对不上。

---

## 八、验证记录

以下均为实测，不是推断：

| 验证项 | 方法 | 结果 |
|---|---|---|
| 补丁自洽性 | 空词典 roundtrip | 与原文件**逐字节一致** ✔ |
| 补丁正确性 | 全新 clone → 打补丁 → 比对 sha256 | 可复现，产物稳定 ✔ |
| 模板可解析性 | 仓库解析器遍历 130 个对话框模板 | 130/130 全部解析成功 ✔ |
| 结构字段保真 | 逐模板比对 `font` / `ctrl_class` 与英文版 | **0 个不一致** ✔ |
| 对话框可用性 | 对 88 个实际存在的对话框调用 `CreateDialogIndirectParamW` | 成/败状态与英文版 **88/88 逐一相同** ✔ |
| 写入范围 | 合成样本（把原文塞进 `.text`、清空 `.rsrc` 内的对应串） | 拒绝写入，`.text` **未被改动** ✔ |
| 超长译文 | 向词典塞入超过原文的译文 | 被拒绝，补丁中 0 条超长记录 ✔ |
| 非 BMP 字符 | `😀abc`(5 码元) 收进 5 码元槽位、`😀abcd`(6 码元) 拒收 | 按 UTF-16 字节长度判定，槽位总长不变 ✔ |
| 失败事务性 | 补丁含 1 条未定位条目 | 目标 / `--out` / 备份**全部未改动**，无临时文件残留 ✔ |
| 区间冲突 | 补丁含同偏移不同译文 / 部分重叠记录 | 退出码 1，目标 / `--out` / 备份**全部未改动** ✔ |
| 对话框槽位偏移 | 旧式模板标题含非 BMP 字符 | 偏移取自读取位置（22），不按码点反推 ✔ |
| 生成器哈希 | `slots.json` 的 sha256 与 exe 不符 | 退出码 1，**未创建输出文件** ✔ |
| 工具链回归 | `python tests/test_regression.py` | 56 项全过 ✔ |
| 运行时正确性 | 启动后读运行中窗口的菜单文本 | `&文件 / &视图 / &工具 / &帮助` ✔ |
| 进程存活 | 部署后连续观察 | 进程存活，主窗口正常 ✔ |

可复现的验收脚本（PowerShell）：

```powershell
$exe = "$env:LOCALAPPDATA\Programs\ADI\LTspice\LTspice.exe"
# 1) 菜单文本
Add-Type -TypeDefinition @"
using System;using System.Text;using System.Runtime.InteropServices;
public class C {
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr GetMenu(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetMenuItemCount(IntPtr m);
  [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetMenuStringW(IntPtr m,uint i,StringBuilder s,int n,uint f);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc f,IntPtr l);
  public delegate bool EnumWindowsProc(IntPtr h,IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint p);
  public static IntPtr Find(uint pid){IntPtr r=IntPtr.Zero;EnumWindows((h,l)=>{uint p;GetWindowThreadProcessId(h,out p);if(p==pid&&GetMenu(h)!=IntPtr.Zero){r=h;return false;}return true;},IntPtr.Zero);return r;}
}
"@
$p = Start-Process $exe -PassThru; Start-Sleep 8
if (-not (Get-Process -Id $p.Id -ErrorAction SilentlyContinue)) { "✘ 启动崩溃"; exit }
$h = [C]::Find([uint32]$p.Id); $m = [C]::GetMenu($h)
0..([C]::GetMenuItemCount($m)-1) | ForEach-Object {
  $sb = New-Object System.Text.StringBuilder 256
  [void][C]::GetMenuStringW($m,[uint32]$_,$sb,256,0x400); "  菜单项 $_ : $($sb.ToString())"
}
```

---

## 九、常见问题

**Q：启动后界面还是英文？**
A：确认你改的是**正在运行的那个安装**。同时装了逐用户和全用户两版时，快捷方式指向哪个就改哪个。
用 2.2 节的快捷方式解析命令确认路径。

**Q：弹「未定位 N 处」或退出码 1？**
A：版本差异过大。按 7.2 重新扫基准出补丁；`--check` 的输出会列出前 10 条未定位的原文。

**Q：对话框打不开 / 界面有空白？**
A：那是旧版（`6bd0de08…`）的已知缺陷，根因见[第五节](#五原理文本字段的边界由-nul-决定)。
重新部署当前版本（产物 `e7759a9c…`）即可。用 `Get-FileHash` 确认产物哈希。

**Q：菜单里出现了多余的空格？**
A：那是补齐用的填充空格，**必需**，删掉就会破坏资源结构。视觉上菜单项左对齐，不影响功能与快捷键。

**Q：LTspice 提示更新，更新完汉化没了？**
A：正常 —— 更新器会覆盖 `LTspice.exe`。重跑部署命令即可；建议关掉 LTspice 的自动更新。

**Q：Windows Defender / 杀软报毒？**
A：改过签名的 exe 常见误报。源码全在仓库里可自行审计；也可先用 `--out` 输出到别的路径试跑。

**Q：能汉化帮助文档吗？**
A：`LTspiceHelp\*.htm` 有 752 个文件，涉及索引与交叉引用，本仓库不处理。

**Q：这是官方汉化吗？**
A：不是。ADI 没有出过中文界面。本仓库是社区对官方 exe 的资源替换，不修改任何逻辑代码。

---

## 十、已知限制

- 改过字节后 ADI 的 Authenticode 签名必然失效，脚本会摘除证书表目录项并重算 PE 校验和（正常现象）。
- 不要用 LTspice 自带的在线更新器覆盖主程序。
- 只覆盖 26.x 的 PE 资源；帮助文档与示例电路不在范围内。
- 菜单与对话框文案最长只能与英文等长（补齐空格），个别长句中文会偏紧凑。
- 与英文版相比，汉化版多占用若干空格填充字节，界面排版在个别控件上可能略有差异。
- 长度上限按 **UTF-16 码元**算：一个 emoji / 生僻字占 2 码元，比中文汉字更"贵"。
- 只要有一条记录没成功，整次写入就被取消（宁可不动，也不留下半汉化的 exe）。
- 术语如有不同意见，改 `dict/zh_dict.json` 重出补丁即可，欢迎提 PR。

---

## 许可证

工具与词典采用 **MIT**。LTspice 本体版权归 Analog Devices, Inc.，
本仓库**不含任何 ADI 二进制文件** —— 只有文本补丁（原文 → 译文对照）与脚本。
LTspice 是 Analog Devices, Inc. 的商标。
