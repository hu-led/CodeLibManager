---
name: keil-build
description: 为 Keil项目提供编译、错误解析与烧录流程。触发条件：用户要求编译、构建、下载、烧录 Keil 工程时。
---

# Keil 工程编译与烧录规范

**注意：**命令行工具为`C:\Keil_v5\UV4\UV4.exe`，已添加到系统环境变量。UV4 命令行完全依赖项目文件（.uvprojx/.uvoptx），GUI 中的修改必须点 OK 按钮保存才会写入文件，否则命令行读不到。

## Token 节约规则

排查烧录/编译问题时，**禁止**整文件读取大文件。始终先用 grep 定位关键 section，再精确读取：

```
# 读取 uvoptx 的调试配置（只需要这两个 section）
grep -A 15 "<DebugOpt>" <工程>.uvoptx
grep -A 10 "TargetDriverDllRegistry" <工程>.uvoptx

# 读取 uvprojx 的关键编译配置
grep -A 5 "VariousControls\|Define\|IncludePath" <工程>.uvprojx
```

**禁止**读取 `.uvguix.*` 文件——那是 GUI 窗口布局数据，对命令行操作无任何作用。

## 验证前静态审查清单

编译烧录之前，按以下清单逐项审查 main.c 及新增/修改的模块代码。

### 执行方式：Subagent 串行检查（Token 优先）

主 agent 收集以下文件后，**启动 1 个 subagent 串行完成全部 6 项检查**，代码只发一次：

- `main.c` 和新增/修改的模块 `.c/.h` 文件
- `.uvprojx` 工程文件（用 grep 提取 Files/IncludePath，不读全文件）
- `stm32f10x_conf.h`（如有）
- 启动文件（如有 IRQHandler 的新模块才需要）

Subagent 提示词："执行 Keil 工程编译前静态审查，逐项完成下方 6 项检查并输出结果。"

要求 subagent 按以下格式返回：

```
| # | 检查项 | 结果 | 问题详情 |
|---|--------|------|---------|
| 1 | printf/semihosting | ✅/⚠️/❌ | ... |
| 2 | 依赖完整性 | ✅/❌ | ... |
| ... | ... | ... | ... |
```

主 agent 根据检查结果决策：全部 ✅ 或仅 ⚠️ → 继续编译；有 ❌ → 先修复再继续。

### 6 项检查清单（供 subagent 参考）

| # | 检查项 | 要点 |
|---|--------|------|
| 1 | **printf/semihosting 隐患** | 搜索 `printf`、`scanf`、`putchar`。若使用了这些函数，必须启用 MicroLIB（Project → Options → Target → Use MicroLIB）或改用 `Serial_Printf`。不检查则烧录后芯片卡死在启动阶段 |
| 2 | **依赖完整性** | 检查模块 `#include` 的头文件是否都在工程中可用，module.json 声明的依赖是否都已添加。缺失依赖会导致 `Undefined symbol` 链接错误 |
| 3 | **头文件包含** | 确认 `stm32f10x_conf.h` 中对应外设头文件已取消注释（如用 GPIO 需 `stm32f10x_gpio.h` 等） |
| 4 | **uvprojx 注册** | 新增的 `.c` 文件必须在 uvprojx 中注册（FileType=1），且 Include Paths 包含其头文件所在目录 |
| 5 | **中断函数** | 搜索 `IRQHandler`，确认中断函数名与启动文件中的向量表一致（如 `TIM2_IRQHandler` 而非 `TIM2_IRQn`） |
| 6 | **Doxygen 注释规范** | 检查新增/修改的函数注释是否符合 c-cpp-coding-guide：有参数才写 `@param`，有返回值才写 `@retval`，禁止 `@param 无`/`@retval 无` |

## 编译流程

1.  **进入工程目录：** 首先 `cd` 到 `.uvprojx` 文件所在的项目根目录，后续所有命令均在此目录下执行。
2.  **识别工程：** 确认当前目录下的 `.uvprojx` 文件。
3.  **执行编译：** 使用命令 `UV4.exe -j0 -b [工程文件].uvprojx -o build.log` 进行编译，输出重定向到日志文件。编译后立即检查退出码：`%ERRORLEVEL%` 非零则编译环境异常（如 UV4 启动失败、License 问题），不再继续后续步骤。
    - `-j0`：抑制 GUI 弹窗，避免编译被对话框阻塞。
    - `-b`：增量编译，**首选此模式**。
    - `-c`：全量重编（clean + rebuild）。**注意**：`-c` 先清空所有中间文件再编译，若清空后编译失败（如新增源文件未正确注册），日志可能只显示 "Clean started" 而无后续编译错误信息，造成误判。因此 `-c` 仅在前一轮 `-b` 提示修改未生效或依赖遗漏时才使用，使用后若日志不完整，立刻再用 `-b` 查看实际错误。
4.  **精简编译日志：** 编译完成后，用以下命令过滤 `build.log`，只保留关键信息并写入 `build-filtered.log`：
    `powershell -Command "Select-String -Path build.log -Pattern 'Error:|Warning:|\.axf.*not created|0 Error\(s\)|\.axf|Program Size:' -Context 0,1 | Select-Object -ExpandProperty Line | Out-File -Encoding UTF8 build-filtered.log"`
    过滤内容包括错误、警告、编译产物信息以及 **RAM/ROM 用量**（Program Size），之后只需读取 `build-filtered.log` 即可定位问题并了解内存占用，大幅节省 token。
5.  **解析错误：** 读取 `build-filtered.log`（如不存在则回退到 `build.log`），寻找错误和警告并据此修复代码。常见编译/链接错误的速查见下方"编译错误排查"表。
6.  **编译成功验证：** `build-filtered.log` 中出现 `0 Error(s), 0 Warning(s)` 即为编译成功。编译成功时向用户汇报 RAM/ROM 用量（从 `Program Size:` 行提取 Code/RO-data/RW-data/ZI-data，并计算 RAM = RW + ZI）。不要依赖检查 `Objects` 目录下的 `.hex`/`.axf` 文件，增量编译可能不重新生成这些文件。

## 编译/链接错误排查

编译失败时，按以下模式匹配：

| 错误输出特征 | 原因 | 排查步骤 |
|-------------|------|---------|
| `Undefined symbol <函数名> (referred from main.o)` | 链接器找不到函数定义——源文件未被编译 | ①grep uvprojx 检查该函数所在 .c 文件的注册：`grep -A 4 "FileName>文件名" <工程>.uvprojx` ②确认 FileName 不为空、FileType 为 1（不是 0）③确认 Include Path 包含该文件所在目录 |
| `warning: #5-D: cannot open source file "xxx.h"` | 头文件路径未加入 Include Paths | `grep "IncludePath" <工程>.uvprojx` 确认路径存在 |
| `error: #20: identifier "xxx" is undefined` | 宏未定义或头文件未包含 | 检查 `stm32f10x_conf.h` 中对应外设头文件是否取消注释 |
| `Warning: #940-D: missing return statement` | 函数缺少 return | 在 Keil 编译器中通常无害，但建议补上 |
| `Target not created` | 存在 Error 导致链接失败 | 向上滚动寻找具体 Error，先解决 Error 再管 Warning |

**Token 节约：** 排查链接错误时，不要整文件读取 uvprojx。先用 `grep -A 4 "FileName>文件名"` 精确查看文件注册条目，或用 `grep "GroupName>" uvprojx` 列出所有分组概览。

## 烧录流程

### 烧录前校验（必须执行）

执行烧录前，先检查 `.uvoptx` 的调试器配置是否有效：

1. 用 grep 检查 `<DebugOpt>` 中的 `<tDll>` 是否为空：
   ```
   grep "<tDll>" <工程>.uvoptx
   ```
   若为 `<tDll></tDll>`（空），说明调试器未配置，按下方"调试器配置修复"处理后再烧录。

2. 用 grep 检查 `<TargetDriverDllRegistry>` 中是否存在当前调试器的 `<Key>` 条目（如 ST-Link 应有 `ST-LINKIII-KEIL_SWO`）。若无有效条目，同样按"调试器配置修复"处理。

3. 确认 Flash 算法参数存在：grep `Flash\` 在 TargetDriverDllRegistry 的输出中应能找到如 `STM32F10x_128.FLM` 的算法引用。若缺失则会导致 `No Algorithm found` 错误。

### 执行烧录

校验通过后，使用 `UV4.exe -j0 -f [工程文件].uvprojx -o flash.log` 命令进行程序烧录。

### 烧录结果确认

烧录完成后读取 `flash.log`。成功标志：`Erase Done.  Programming Done.  Verify OK.`

**必须**询问用户芯片是否正常运行。若用户反馈异常则进入烧录失败排查。

## 烧录失败排查

烧录失败时，仔细阅读 `flash.log` 中的错误信息，按以下模式匹配排查：

| 错误输出特征 | 原因 | 排查步骤 |
|-------------|------|---------|
| `No ST-Link detected` / `ST-Link USB communication error` | 调试器未连接或驱动问题 | ①检查 USB 线是否插好 ②设备管理器中确认 ST-Link 设备出现 ③重新插拔后再试 |
| `No Cortex-M device found` / `No target connected` | 芯片未上电或复位电路异常 | ①确认开发板供电正常 ②检查 BOOT0 是否拉低 ③按一下复位键后重试 |
| `Cannot enter Debug Mode` / `Cannot access target` | SWD 接线问题或芯片处于低功耗/锁死 | ①检查 SWCLK/SWDIO/GND 三条线连接 ②按住复位键 → 点烧录 → 瞬间松开复位 |
| `Internal DLL Error` + `Flash Download failed - Target DLL cancelled` | uvoptx 中调试器 DLL 未配置（GUI 修改未保存） | ①执行"烧录前校验"步骤 ②按"调试器配置修复"补全 uvoptx ③参考同目录下其他正常工作的 Keil 项目的 uvoptx 配置 |
| `No Algorithm found for: <地址范围>` | ST-Link 已连接芯片，但 Flash 编程算法未配置 | ①grep 检查 TargetDriverDllRegistry 中 ST-LINKIII-KEIL_SWO 条目的 Name 是否包含 `-FF0<芯片>.FLM -FS<地址> -FL<长度>` ②缺失时从同目录其他成功项目的 uvoptx 复制参数 ③常见参数：`-FD20000000 -FC1000 -FN1 -FF0STM32F10x_128.FLM -FS08000000 -FL020000` |
| `Flash Download Failed - Target DLL cancelled` | Flash 写保护或 Programming Algorithm 配置错误 | ①检查 Keil Flash Download 设置页的 Programming Algorithm 是否匹配芯片 ②如芯片被读保护，在 Keil 中用 Flash → Erase 全片擦除 |
| `Cannot Load Flash Programming Algorithm` | 芯片型号不匹配 | 核对 `Project → Options → Device` 中的芯片型号与实际芯片一致 |
| `Error: Flash Timeout` / `Verify Failed` | SWD 速度过高或 Flash 擦除不完整 | ①在 Debug 设置中将 SWD Max Clock 降到 1MHz 以下 ②先用 `-c` 全量重编再烧录 |
| 无任何错误但烧录后芯片不运行 | 烧录后未复位、Option Byte 配置异常或 Flash 算法与实际芯片 Flash 大小不匹配 | ①检查 Debug 设置中 `Reset and Run` 是否勾选 ②检查 Flash Download 页的 Programming Algorithm 地址范围是否超出芯片实际 Flash 大小 ③检查 Option Byte 页（如有）中 BOR 阈值、看门狗硬件使能等配置是否符合预期 |

## 调试器配置修复

**注意：** 通过 `F1_STDL` 模板创建的工程已预配置 ST-Link 调试器和 Flash 算法，通常无需手动修复此步骤。

当 uvoptx 缺失调试器配置时（如非模板创建的旧工程），按以下步骤修复：

### 1. 修复 DebugOpt 中的 DLL 设置

在 `<DebugOpt>` 中补全目标调试器 DLL（以 ST-Link 为例）：

```xml
<tDll>SARMCM3.DLL</tDll>
<tDllPa></tDllPa>
<tDlgDll>TCM.DLL</tDlgDll>
<tDlgPa>-pCM3</tDlgPa>
```

### 2. 修复 TargetDriverDllRegistry（含 Flash 算法）

需要同时保留**两条**条目——当前调试器条目 + UL2CM3 条目。以下为已验证可用的配置：

**ST-Link (TDRV5)：**
```xml
<TargetDriverDllRegistry>
  <SetRegEntry>
    <Number>0</Number>
    <Key>ST-LINKIII-KEIL_SWO</Key>
    <Name>-U2 -O206 -SF4000 -C0 -A0 -I0 -HNlocalhost -HP7184 -P2 -N00("ARM CoreSight SW-DP") -D00(1BA01477) -L00(0) -TO18 -TC10000000 -TP21 -TDS8007 -TDT0 -TDC1F -TIEFFFFFFFF -TIP8 -FO15 -FD20000000 -FC1000 -FN1 -FF0STM32F10x_128.FLM -FS08000000 -FL020000 -FP0($$Device:STM32F103C8$Flash\STM32F10x_128.FLM)</Name>
  </SetRegEntry>
  <SetRegEntry>
    <Number>0</Number>
    <Key>UL2CM3</Key>
    <Name>UL2CM3(-S0 -C0 -P0 -FD20000000 -FC1000 -FN1 -FF0STM32F10x_128 -FS08000000 -FL020000 -FP0($$Device:STM32F103C8$Flash\STM32F10x_128.FLM))</Name>
  </SetRegEntry>
</TargetDriverDllRegistry>
```

**CMSIS-DAP (TDRV2)：**
```xml
<TargetDriverDllRegistry>
  <SetRegEntry>
    <Number>0</Number>
    <Key>CMSIS_AGDI</Key>
    <Name></Name>
  </SetRegEntry>
  <SetRegEntry>
    <Number>0</Number>
    <Key>UL2CM3</Key>
    <Name>UL2CM3(-S0 -C0 -P0 -FD20000000 -FC1000 -FN1 -FF0STM32F10x_128 -FS08000000 -FL020000 -FP0($$Device:STM32F103C8$Flash\STM32F10x_128.FLM))</Name>
  </SetRegEntry>
</TargetDriverDllRegistry>
```

**J-Link (TDRV3)：**
- tDlgDll 改为 `Segger\JL2CM3.dll`
- TargetDriverDllRegistry Key 改为 `JL2CM3`

### 3. 快速修复策略

如果同目录下有其他正常工作的 Keil 项目，直接用 grep 提取其 uvoptx 的 `<DebugOpt>` 和 `<TargetDriverDllRegistry>` 配置，复制到当前项目，速度最快且参数最可靠。

### 各调试器对应的 TOOLS.INI 参数

| 调试器 | TDRV | DLL 路径 |
|--------|------|---------|
| ULINK2 | TDRV0 | BIN\UL2CM3.DLL |
| ULINK Pro | TDRV1 | BIN\ULP2CM3.DLL |
| CMSIS-DAP | TDRV2 | BIN\CMSIS_AGDI.dll |
| J-Link | TDRV3 | Segger\JL2CM3.dll |
| ST-Link | TDRV5 | STLink\ST-LINKIII-KEIL_SWO.dll |

以上信息来自 `C:\Keil_v5\TOOLS.INI` 的 `[ARM]` 部分，需要时 grep `TDRV<编号>` 即可获取。
