# LTspice 26.x 简体中文界面补丁

为 LTspice 的菜单、对话框和提示文字提供简体中文翻译。补丁在本机应用到已安装的 LTspice，仓库只分发文本补丁、词典和工具脚本。

当前补丁以 **Windows 版 LTspice 26.1.1** 为基准，覆盖 **2599 / 2745** 个可翻译槽位。其它版本需要重新生成补丁并验证。

[下载发布包](https://github.com/spdw666/LTspice-26.x-zh/releases/latest) · [更新日志](CHANGELOG.md) · [Agent 使用说明](docs/SKILL.md) · [反馈问题](https://github.com/spdw666/LTspice-26.x-zh/issues)

## 快速开始

准备 Windows 10 / 11、已安装的 LTspice，以及带有 `pip`、`venv` 的 Python 3。Git 用于拉取源码；也可以下载发布包后解压使用。

### 1. 获取工具

在 PowerShell 中执行。下面把工具放到 D 盘，不改变 LTspice 的安装位置：

```powershell
git clone https://github.com/spdw666/LTspice-26.x-zh.git D:\LTspice-zh
Set-Location D:\LTspice-zh

python -m venv .venv
$Python = Join-Path $PWD '.venv\Scripts\python.exe'
& $Python -m pip install pefile
```

如果使用下载的压缩包，从解压后的仓库目录执行创建环境及安装依赖的三条命令即可。后面的示例沿用 `$Python` 和当前仓库目录。

### 2. 确认目标程序

从桌面快捷方式读取实际路径：

```powershell
$Shortcut = Join-Path $env:USERPROFILE 'Desktop\LTspice.lnk'
$Exe = (New-Object -ComObject WScript.Shell).CreateShortcut($Shortcut).TargetPath
Get-Item -LiteralPath $Exe | Select-Object FullName, @{Name='Version'; Expression={$_.VersionInfo.FileVersion}}
```

如果快捷方式在别处，修改 `$Shortcut`；也可以直接设置 `$Exe` 为实际程序路径。常见位置是 `%LOCALAPPDATA%\Programs\ADI\LTspice\LTspice.exe` 和 `C:\Program Files\ADI\LTspice\LTspice.exe`。

应用补丁前，关闭 LTspice 及正在连接它的自动化桥接进程。安装目录需要具备写入权限。

### 3. 检查并应用

先检查匹配情况；退出码为 `0` 后再应用：

```powershell
$Patch = 'patches\ltspice-26.1.1-zh.patch.json'

& $Python tools\apply_patch.py --patch $Patch --exe $Exe --check
if ($LASTEXITCODE -ne 0) { throw '补丁检查失败，请核对程序版本和输出记录。' }

& $Python tools\apply_patch.py --patch $Patch --exe $Exe --backup
if ($LASTEXITCODE -ne 0) { throw '补丁应用失败，请查看命令输出。' }
```

首次应用会保存 `$Exe.orig.bak`，已有同名备份时不覆盖。保留这份原始英文备份。

### 4. 确认效果

重新启动 LTspice，检查菜单文字，并打开元件属性对话框。再运行一个熟悉的电路，确认仿真结果与应用补丁前一致。

对于基准版 26.1.1，可用哈希核对完整产物：

```powershell
Get-FileHash -LiteralPath $Exe -Algorithm SHA256
```

| 文件 | SHA-256 |
|---|---|
| 原始英文 26.1.1 | `3c144a2b3ec6a30baac6761c502d99b95aaa40b947ff5eca25b8fbd80d68af72` |
| 应用当前补丁后 | `e7759a9c113a290b2ec92843281f0fff386bf30891640b5c892396d547419651` |

## 重新应用与还原英文

**重新应用汉化**：已有同版本英文备份时，用备份作为基准重新生成汉化程序：

```powershell
& $Python tools\apply_patch.py --patch $Patch --exe $Exe --restore
if ($LASTEXITCODE -ne 0) { throw '重新应用失败，原目标文件保持原状。' }
```

`--restore` 表示“以备份为基准重新应用补丁”，不是单独恢复英文的开关。脚本识别 `.orig.bak` 和 `.orig-*.bak`；先在内存中检查，匹配成功后才写回目标。

**还原英文界面**：关闭程序，复制对应版本的原始备份：

```powershell
$Backup = "$Exe.orig.bak" # 使用其它备份名时，在这里填写实际路径
Copy-Item -LiteralPath $Backup -Destination $Exe -Force
```

LTspice 更新可能替换主程序。升级后保留新版本的英文文件，重新检查版本适配；不要用旧版本备份覆盖新版本程序。

## 翻译覆盖

| 内容 | 已译 / 可翻译槽位 | 说明 |
|---|---|---|
| 菜单 | 1031 / 1047 | 主菜单、右键菜单、下拉项 |
| 对话框 | 1096 / 1199 | 窗口标题、控件标题 |
| 字符串表 | 472 / 499 | 状态提示、工具提示、错误信息 |
| **合计** | **2599 / 2745（94.7%）** | 按资源槽位计数，同一文本可出现多次 |

元件型号、参数名、格式缩写等保留原文；仍有部分文字未翻译。帮助文档、示例电路、模型库和仿真表达式保持原样。

补丁保持字段的 UTF-16 字节长度，较短译文使用空格补齐，因此某些位置会有额外留白。窗口类名、字体名等结构字段保留原值。

## 命令参考

```powershell
& $Python tools\apply_patch.py --patch $Patch --exe $Exe --check
& $Python tools\apply_patch.py --patch $Patch --exe $Exe --backup
& $Python tools\apply_patch.py --patch $Patch --exe $Exe --out .\LTspice-zh.exe
```

| 参数 | 行为 |
|---|---|
| `--check` | 只读检查；同时传入的 `--backup`、`--restore` 被忽略 |
| `--backup` | 应用前保存原文件为 `<exe>.orig.bak`，已有同名备份时保留 |
| `--restore` | 从已有备份读取基准，检查成功后重新应用补丁 |
| `--out` | 写入指定输出文件，保留输入程序 |

退出码 `0` 表示检查或应用成功；非 `0` 时读取输出中的未定位、长度、歧义、不合规或区间冲突信息。**预检失败不会改动目标、输出和备份**；单个输出文件通过同目录临时文件与原子替换保存。

界面文本的定位与替换限定在 `.rsrc` 资源节，代码节保持不变。程序字节变化后，原厂数字签名不再有效；工具会清除 PE 头中的证书表目录项并重算校验和。

## 调整词条

编辑 [`dict/zh_dict.json`](dict/zh_dict.json) 的“英文原文 → 中文译文”映射，然后使用**原始英文程序**重新生成补丁。输出到新文件，便于先检查再使用：

```powershell
$Original = "$Exe.orig.bak" # 填写基准版本的原始英文备份路径
& $Python tools\make_patch.py --slots dict\slots-26.1.1.json --dict dict\zh_dict.json `
    --exe $Original --out .\custom.patch.json
if ($LASTEXITCODE -ne 0) { throw '补丁生成失败，请核对基准及槽位信息。' }

& $Python tools\apply_patch.py --patch .\custom.patch.json --exe $Original --check
```

译文按 UTF-16 码元数补齐，过长条目会跳过并计数。生成器核对槽位表记录的 SHA-256 和实际字段字节；基准不匹配或槽位不合规时停止生成。

为其它版本制作补丁时，先重新扫描该版本的原始英文程序，再生成对应补丁：

```powershell
$env:LTSPICE_EXE = $Original
$env:SLOTS_OUT = 'slots-new.json'
& $Python tools\scan_slots.py
& $Python tools\make_patch.py --slots .\slots-new.json --dict dict\zh_dict.json `
    --exe $Original --out .\new-version.patch.json
```

新版本需要另行验证资源结构、界面操作和仿真结果；文本匹配成功不等于完整兼容。

## 验证与项目结构

仓库提供 56 项工具链回归测试。真实程序用例读取 `LTSPICE_EN_EXE` 指定的原始英文程序；文件不存在时跳过相应用例。以下示例显式指定备份路径：

```powershell
$env:LTSPICE_EN_EXE = "$Exe.orig.bak" # 使用其它备份名时填写实际路径
& $Python tests\test_regression.py -v
```

26.1.1 的既有验收结果：130 个对话框模板全部解析；130 个原生创建状态与子控件结构逐项匹配英文版（两版各成功创建 116 个）；17 个菜单资源加载；10 V、两个 1 kΩ 电阻的分压仿真输出为 5.0 V。工具链回归通过不替代其它版本的界面与仿真验收。

| 路径 | 用途 |
|---|---|
| [`patches/`](patches/) | 可直接应用的文本补丁 |
| [`dict/`](dict/) | 翻译词典、基准槽位表 |
| [`tools/`](tools/) | 应用、扫描、生成和对话框解析脚本 |
| [`tests/`](tests/) | 工具链回归测试 |
| [`docs/SKILL.md`](docs/SKILL.md) | Agent 操作说明 |
| [`CHANGELOG.md`](CHANGELOG.md) | 版本变更记录 |

给 Agent 的可复用指令：

```text
读取仓库 docs/SKILL.md，定位快捷方式实际指向的 LTspice.exe，核对版本。
关闭目标程序，先运行 --check；成功后使用 --backup 应用对应版本补丁。
已有同版本英文备份且需要重置时使用 --restore；恢复英文则复制原始备份。
核对退出码、产物哈希、菜单、元件属性对话框与一个已知电路的仿真结果。
保留英文备份，不修改帮助文件、模型库或工程文件。
```

## 常见问题

**界面仍是英文？** 核对快捷方式指向的程序路径，关闭已有实例后重新启动。多个安装目录之间不要混用补丁目标和备份。

**检查失败或出现“未定位”？** 核对程序版本及原始文件，查看失败记录；其它版本按上面的扫描与生成流程制作补丁。

**程序被占用或目录写入失败？** 关闭 LTspice 和桥接进程，确认 `$Exe`、输出目录及写入权限后再执行。

**想反馈译文或界面问题？** 在 [Issues](https://github.com/spdw666/LTspice-26.x-zh/issues) 附上版本号、相关文字或目标窗口截图，以及命令输出中的失败记录。

## 许可证

本项目的工具和词典采用 [MIT 许可证](LICENSE)。这是社区维护的界面补丁；LTspice 软件本体归 Analog Devices 所有，仓库不分发其可执行文件。
