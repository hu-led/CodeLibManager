---
name: mrs-project
description: 管理 MounRiver Studio 2 工程文件结构，包括目录/分组管理、include 路径配置和预处理器定义。触发条件：在 MRS2 工程中新建源文件、调整工程结构时。
---

# MRS2 工程管理规范

## 核心原则

- **AI 负责推理 + 调用工具，能固化的脚本已固化** — 编译用 `mrs_build.py`，工程结构用 CodeLibManager CLI
- **新增 .c 文件后必须更新 subdir.mk** — MRS2 不会自动检测新文件
- **用 grep 验证，不整文件读取** — .cproject 很大，只 grep 关键节

## 工程文件结构

MRS2 基于 Eclipse CDT，文件系统目录结构即工程分组：

| 目录 | 用途 | 是否可修改 |
|------|------|-----------|
| `User/` | main.c、ch32v30x_it.c、中断服务 | 可修改 main.c |
| `Hardware/` | 硬件驱动（LED、I2C、传感器等） | 可新增 |
| `System/` | 系统级功能（Delay、Timer 等） | 可新增 |
| `Core/` | RISC-V 内核相关 | **禁止修改** |
| `Debug/` | debug.c/h、printf 重定向 | **禁止修改** |
| `Ld/` | 链接脚本 Link.ld | **谨慎修改** |
| `Peripheral/` | 官方外设库（inc/ + src/） | **禁止修改** |
| `Startup/` | 启动汇编文件 | **禁止修改** |
| `SRC/` | 共享源码（链接资源，在工程外） | **禁止修改** |

## 新增 .c 文件后的必做操作

**Eclipse CDT 不会自动检测新文件！** 每次 `copy-to-project` 后，必须更新 `obj/<目录>/subdir.mk`。

### 自动更新 subdir.mk（推荐）

`copy-to-project` / `chain-copy` 会自动将文件复制到工程并添加 Include 路径，但 MRS2 平台的 subdir.mk **仍需手动更新**。用以下命令快速追加：

```bash
# 在 subdir.mk 的 C_SRCS/OBJS/C_DEPS 三个列表中各加一行
# 位置：C_SRCS += \ ...  C_DEPS += \ ...  OBJS += \ ...
```

更新模式（在最后一个已有条目后追加新条目，保持字母序）：

```
C_SRCS += \
../Hardware/AHT_10.c \
../Hardware/AP3216C.c \
../Hardware/新文件.c \     ← 追加在这里
```

**注意**：OBJS 和 C_DEPS 列表也要同步追加对应的 .o 和 .d 条目。

### 验证更新

```bash
grep "新模块名" obj/Hardware/subdir.mk
```

### 为什么不刷新 Makefile？

Eclipse CDT 的 Makefile 由 GUI 生成。命令行无法触发重新生成。当前方案是手动编辑 subdir.mk，下次用 MRS2 GUI 打开工程时会自动覆盖为正确版本。

## 从代码库添加模块

使用 **codelib-manager** 技能。默认已完成：目录创建 → 文件复制 → Include 路径添加。之后按上方流程更新 subdir.mk。

```bash
cd <CodeLibManager根目录> && python -m cli.main copy-to-project <模块名> <工程根目录路径>
```

## 平台适配器工具

```bash
cd <CodeLibManager根目录> && python -m cli.main project-<命令> [参数...]
```

| 命令 | 用途 |
|------|------|
| `project-create-group` | 创建目录分组 |
| `project-add-include` | 添加 Include 路径 |
| `project-remove-include` | 移除 Include 路径 |
| `project-add-define` | 添加预处理器定义 |
| `project-remove-define` | 移除预处理器定义 |
| `project-init --template MRS2_CH32V307` | 从模板创建新工程 |

## 验证 Include 路径

```bash
grep "c.compiler.include.paths" .cproject | head -20
```

## 验证 Defines

```bash
grep -A 10 "c.compiler.defs" .cproject
```

## Token 节约

- `.cproject` 不要整文件读 — 用 `grep` 提取关键节（include paths / defines / sourceEntries）
- 验证工程结构用 `ls` 列出目录，不递归遍历
- 编译用 `mrs_build.py`，不要手写 PATH + make 命令

