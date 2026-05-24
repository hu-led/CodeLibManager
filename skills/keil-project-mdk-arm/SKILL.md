---
name: keil-project-mdk-arm
description: 管理 Keil MDK-ARM 工程文件结构，包括向 .uvprojx 添加/移除源文件、文件组管理和头文件路径配置。触发条件：在 Keil MDK-ARM 工程中新建源文件、调整工程结构时。
---

# Keil MDK-ARM 工程管理规范

## 工程文件结构

**一个工程文件夹下你主要工作在：**

`<ProjectDir>\User\main.c` 和 `<ProjectDir>\User\main.h`：项目主程序存放处

`<ProjectDir>\Hardware`：硬件驱动等程序存放处

`<ProjectDir>\System`：功能性程序存放处

使用时允许按需在 `<ProjectDir>` 下创建新文件夹（与 `Hardware`、`System` 同级），确保文件分类明确

**禁止修改：**

`<ProjectDir>\Library`：库函数文件

`<ProjectDir>\Start`：启动文件、寄存器描述文件等

`<ProjectDir>\User` 文件夹下除 `main.c` 和 `main.h` 外的其它文件

## 工程结构管理工具

所有工程结构操作统一通过 CodeLibManager CLI 完成，自动检测工程平台：

```bash
cd <CodeLibManager根目录> && python -m cli.main project-<命令> [参数...]
```

参数中使用**工程根目录路径**（而非 uvprojx 文件名），工具会自动扫描并定位 .uvprojx 文件。

## 从代码库添加模块

使用 **codelib-manager** 技能将已验证或待验证的硬件驱动、算法等模块从可复用代码库复制到工程。模块复制会自动完成：文件复制 → Keil 分组创建 → 文件注册 → Include 路径添加。

如需手动管理 Keil 工程文件结构，使用以下 project-* 命令。

## 创建和修改源文件

根据需求：

在`<ProjectDir>\Hardware` 中创建或修改硬件驱动等程序

在`<ProjectDir>\System` 中创建或修改功能性程序

在`<ProjectDir>\User` 中创建或修改主函数程序文件 `main.c` 和 `main.h` 

在`<ProjectDir>\<自定义文件夹>` 中创建或修改其它类型程序文件 

## 在 Keil 工程中创建新文件分组

当需要为工程创建新的逻辑分组（Group）时：

`python -m cli.main project-create-group <工程根目录路径> <GroupName>`

示例：`python -m cli.main project-create-group C:\...\VerifyTest Hardware`

## 从 Keil 工程中删除分组

当需要删除工程中的空分组（Group）时：

`python -m cli.main project-remove-group <工程根目录路径> <GroupName>`

示例：`python -m cli.main project-remove-group C:\...\VerifyTest TestGroup`

注意：分组内有文件时会拒绝删除并提示文件数量，需先移除文件。

## 将源文件纳入 Keil 工程

当需要将新创建的 `.c` 或 `.h` 文件注册到 Keil 工程时：

`python -m cli.main project-add-file <工程根目录路径> <GroupName> <文件路径>`

示例：`python -m cli.main project-add-file C:\...\VerifyTest Hardware ".\\Hardware\\LED.c"`

### 注册后必须验证

脚本执行后，**立即**用 grep 验证 XML 正确性，不要跳过此步骤直接编译：

```
grep -A 4 "FileName>文件名" <工程>.uvprojx
```

验证要点：
- `<FileName>` 不为空（空的会导致文件不被编译，产生 `Undefined symbol` 链接错误）
- `<FileType>` 正确：c=1, h=5, s/asm=2, cpp=8
- `<FilePath>` 路径正确

**Token 节约：** 验证时只 grep 目标文件条目（~5行），绝不整文件读取 uvprojx（~700行）。用 `grep "GroupName>" uvprojx` 可一览全部分组仅需 ~5 行输出。

## 从 Keil 工程中移除源文件

当需要将源文件从 Keil 工程中移除时：

`python -m cli.main project-remove-file <工程根目录路径> <GroupName> <文件路径>`

示例：`python -m cli.main project-remove-file C:\...\VerifyTest Hardware ".\\Hardware\\LED.c"`

## 将文件夹添加到 Include Paths

当需要将新创建的文件夹添加到 `Include Paths` 时：

`python -m cli.main project-add-include <工程根目录路径> <文件夹路径>`

示例：`python -m cli.main project-add-include C:\...\VerifyTest ".\\Hardware"`

## 从 Include Paths 中移除文件夹

当需要将文件夹从 `Include Paths` 中移除时：

`python -m cli.main project-remove-include <工程根目录路径> <文件夹路径>`

示例：`python -m cli.main project-remove-include C:\...\VerifyTest ".\\Hardware"`

## 预处理器 Define 管理

工程级别的预处理器 Define（如 `USE_STDPERIPH_DRIVER`、`STM32F10X_HD` 等）通常在创建工程时一次性配置好，日常开发中极少变动。如需修改，请直接在 Keil IDE 中操作：`Project → Options for Target → C/C++ → Preprocessor Symbols → Define`。

## 新建工程后初始化调试器

通过 Keil IDE 新建工程后，`.uvoptx` 中的调试器配置默认为空，会导致命令行烧录失败。应在工程创建完成后，按以下步骤初始化：

1. 在 Keil GUI 中打开工程：`Project → Options for Target → Debug`
2. 右侧选择所用调试器（如 "ST-Link Debugger"）
3. 点击 **Settings** → 确认 SWD 模式 → 确认 **SW Device** 列表中显示芯片
4. 切换到 **Flash Download** 标签页 → 点击 **Add** → 选择匹配芯片的 Flash 算法（如 STM32F10x 128KB Flash）→ 点击 **OK** 保存所有设置
5. 执行一次 `UV4.exe -j0 -f <工程>.uvprojx -o flash.log` 验证烧录可用

**为什么必须在 GUI 中配置：** Keil 命令行 UV4.exe 完全依赖 `.uvoptx` 中的调试器配置。GUI 里选了调试器但没点 OK 不会持久化，命令行读到的仍是空配置。烧录失败的首个排查点就是检查 `.uvoptx` 中的 `<tDll>` 和 `<TargetDriverDllRegistry>` 是否为空。

如果已有同芯片的其他可用项目，更快的做法是直接复制其 uvoptx 中的 `<DebugOpt>` 和 `<TargetDriverDllRegistry>` 到新项目——参数由设备包自动生成，手动拼写极易出错。

## 新模块创建完整流程

当需要创建新的功能模块（如 LED 驱动、延时函数）时，遵循以下标准流程：

### 步骤

1. **创建源文件**：在对应文件夹创建 `.c` 和 `.h`（如 `Hardware/LED.c` + `LED.h`）
2. **创建分组**（如不存在）：
   `python -m cli.main project-create-group <工程根目录> Hardware`
3. **注册 .c 文件**：
   `python -m cli.main project-add-file <工程根目录> Hardware ".\\Hardware\\LED.c"`
4. **注册 .h 文件**：
   `python -m cli.main project-add-file <工程根目录> Hardware ".\\Hardware\\LED.h"`
5. **添加 Include 路径**：
   `python -m cli.main project-add-include <工程根目录> ".\\Hardware"`
6. **验证注册结果**（关键步骤，不可跳过）：
   `grep -A 4 "FileName>LED" <工程>.uvprojx`
   确认 FileName 不为空、FileType 为 1（.c）或 5（.h）
7. **编译验证**：执行增量编译确认 0 Error

### Token 效率

- 步骤 2-5 的命令可**合并**为单条 `&&` 链式命令并行执行
- 步骤 6 的验证使用 grep（~5 行输出），代替整文件读取 uvprojx（~700 行），节省 ~99% token
- 如需查看参考实现，不要读取参考项目的完整 uvprojx，用 `grep -A 10 "GroupName>目标分组" 参考项目.uvprojx` 即可

### 常见出错模式

| 现象 | 原因 | 检查命令 |
|------|------|---------|
| `Undefined symbol` 链接错误 | .c 文件未被编译（FileName 空或 FileType=0） | `grep -A 4 "FileName>文件名" uvprojx` |
| `cannot open source file` | Include 路径未添加 | `grep "IncludePath" uvprojx` |
| 文件重复添加 | 脚本自动检测并提示"已存在，跳过" | 无需处理 |

### 模块验证与入库

新模块经编译 + 硬件测试验证后，如需加入可复用代码库，使用 **codelib-manager** 技能完成入库和验证标记。
