# CodeLibManager — 嵌入式 C 可复用代码库管理器

一款面向嵌入式开发者的桌面工具，用于管理跨平台（Keil MDK-ARM / MounRiver Studio 2等）的可复用 C 代码模块库。支持 GUI 和 CLI（供 AI Agent 调用）两种操作方式。设计理念是作为一个跨嵌入式平台、进行个人嵌入式工程的管理助手，GUI和CLI具有同等功能和权限，因此可以适配AI agent进行智能工程管理。

该项目是我第二次 `Vibe coding` 尝试，我负责提出需求、设计框架、管理整个项目、验证和提出修改意见等。AI agent 负责编写基础代码，debug等。截至项目完成时我还是大一，尚未接触很多现代大型工程管理的内容，整体功能结构均是独立构思，可能存在诸多问题或缺陷，代码可能存在不完善的地方，非常欢迎大家的指点和交流，我将虚心听取大家的意见和建议。

项目进行测试时使用的开发板分别是 $STM32F103C8T6$ 和 $CH32V307VCT6$ ，对应 $Keil MDK-ARM$  和 $MounRiver Studio 2$ 两种开发平台。如希望使用更多平台，请参考本文档“平台支持--添加新平台”一栏。同时，我也会在后续更新中在仓库加入对更多常用嵌入式开发平台的适配。

## 核心功能

- **模块管理**：导入、浏览、编辑、验证、删除可复用 C 代码模块（.c/.h），支持搜索、分类过滤、状态筛选
- **依赖解析**：自动拓扑排序，检测循环依赖，构建依赖树，展示反向依赖
- **链复制**：将一个模块及其全部传递依赖按拓扑顺序批量复制到工程，自动处理分组创建、文件复制/注册、Include 路径配置
- **多平台适配**：Keil MDK-ARM（.uvprojx）和 MounRiver Studio 2（.cproject）自动检测与适配，可通过适配器接口自由扩展新平台
- **双接口**：GUI（PySide6）供用户操作，CLI（JSON 输出）供 AI Agent 调用
- **库管理**：支持多个代码库并存、切换，可对库做重命名、更新路径、管理分类/分组等操作

## 运行环境

| 项目 | 说明 |
|------|------|
| 操作系统 | Windows 11 中文版 |
| Python | 3.12.9 |
| 源码编码 | UTF-8 |
| GUI 框架 | PySide6 6.11.0 |
| 打包工具 | PyInstaller |
| 终端编码 | GBK（CLI 输出需注意中文兼容） |

## 项目结构

```
CodeLibManager/
├── main.py              # GUI 入口
├── cli/                 # CLI 命令行接口（供 AI Agent 调用）
├── core/                # 业务逻辑：API、依赖解析、库 I/O、平台适配器
├── ui/                  # PySide6 用户界面
├── resources/           # QSS 样式表
├── skills/              # AI Agent 操作指示（Claude Code skill 文件）
├── example-libs/        # 示例代码库
│   ├── STM32F1/         # 6 个已验证 STM32F103 模块
│   └── CH32V307/        # 6 个已验证 CH32V307 模块
└── .gitignore
```

## 新用户上手指南

### 第一步：环境准备

- 安装 Python 3.9 或更高版本
- `pip install PySide6`

### 第二步：克隆并启动

```bash
git clone <本仓库>
cd CodeLibManager
python main.py
```

首次启动界面空白是正常的——因为你还没有注册任何代码库。

### 第三步：添加示例库体验功能

1. 工具栏点击 **"添加库"**
2. 选择 `example-libs/STM32F1/` 目录，输入别名（如 `STM32F1示例`）
3. 左侧列表即刻出现 6 个示例模块
4. 重复操作添加 `example-libs/CH32V307/`

### 第四步：试试核心功能

**浏览**：左侧点击任意模块 → 右侧查看详情、依赖树、引脚映射

**复制到工程**：右键模块 → "复制到工程" → 选择你的 Keil/MRS2 工程目录 → 自动完成：创建分组目录 → 复制 .c/.h → 注册文件（Keil）/ 自动发现（MRS2）→ 添加 Include 路径

**链复制（核心特色）**：右键模块 → "链复制到工程" → 预览该模块的完整依赖链和文件冲突 → 勾选需要的模块 → 确认 → 所有模块按拓扑顺序批量复制

**导入自己的模块**：工具栏"导入模块" → 选择 .c/.h 文件 → 填写名称、分类（库中的文件夹名）、工程分组（Hardware 或 System）、依赖 → 入库

**编辑/验证模块**：右键模块 → "编辑模块" → 可改元数据、增删文件、标记验证状态

### 第五步：构建自己的代码库

理解了功能后，新建一个文件夹作为你自己的代码库根目录，用"添加库"注册。之后：
- 把你在工程中写好的硬件驱动、算法模块逐个"导入模块"入库
- 新工程直接"链复制"已有模块，减少重复造轮子
- 验证过的模块标记 `已验证`，未验证的标记 `未验证`，便于后续追踪质量

### 进阶：AI Agent 辅助

如果你使用 Claude Code等AI agent，`skills/` 目录下的技能文件可让 AI 直接操作 CLI：

- 将 `skills/` 下的 `.md` 文件复制到 `C:\Users\<你的用户名>\.claude\skills\`
- 将文件中的 `<CodeLibManager根目录>` 替换为你的实际路径
- 之后在对话中说"帮我把 LED 模块复制到 MRS2 工程"即可

### 自行打包（可选）

```bash
pip install PyInstaller
build.bat
# 产物在 dist/CodeLibManager/CodeLibManager.exe
# 也可前往 Releases 页面下载预编译版本
```

## 模块详情字段说明

| 字段 | 含义 |
|------|------|
| 名称 | 模块唯一标识（英文），在库内不可重复 |
| 版本 | 模块版本号，更新时可保存快照 |
| 分类 | 模块在代码库中的逻辑归类，**同时也是库文件系统中的物理文件夹名**（如 Communication、System） |
| 状态 | `已验证` 表示该模块已通过编译+硬件实测；`未验证` 表示尚未测试 |
| 工程分组 | 模块复制到目标工程时放入的**子目录名**，当前只用 `Hardware` 和 `System` 两个值 |
| 文件 | 模块包含的 .c/.h 文件列表 |
| 引脚 | 模块用到的 MCU 引脚映射（如 `PA0=LED`） |
| 描述 | 模块功能的简要说明 |
| 依赖关系 | 递归展示该模块依赖的所有模块（拓扑顺序）；下方显示哪些模块依赖了它 |

> **关键区分**：分类（category）是库中的文件夹名，工程分组（group）是复制到工程时的子目录名。两者完全独立——不要把分类名当作工程分组名使用。

### 自定义分类与分组

分类和分组均可自由增删改，没有限制。示例库中的分类名（Communication、System 等）和分组名（Hardware、System）只是作者的个人习惯，你可以按自己的风格调整。

| 操作 | 分类（category） | 工程分组（group） |
|------|-----------------|-------------------|
| 添加 | GUI: 管理库 → 管理分类 → 新建 | GUI: 管理库 → 管理工程分组 → 新建 |
| 改名 | 会联动更新该分类下所有模块的路径和元数据 | 会联动更新使用该分组的所有模块 |
| 删除 | 仅空分类可删（有模块时报错并列出模块名） | 仅未被引用的分组可删（有模块使用时同样报错） |
| CLI | `add-category` / `rename-category` / `delete-category` | `list-groups` / `add-group` / `rename-group` / `delete-group` |

分类名和分组名互不冲突——一个模块的 `category` 是 `Communication`（存在 `Communication/LED/` 下），`group` 是 `Hardware`（复制到工程时放入 `Hardware/` 目录），完全合理。

## AI Agent 支持

`skills/` 目录包含 Claude Code 可直接使用的技能文件，AI 通过 CLI 的 `--json` 输出来操作代码库：

| 技能 | 功能 |
|------|------|
| `codelib-manager` | 模块浏览、导入、导出、链复制、编辑、验证 |
| `mrs-project` | MRS2 工程结构管理 |
| `keil-project-mdk-arm` | Keil MDK 工程结构管理 |
| `keil-build` | Keil 工程编译与烧录 |

**使用方式**：在 Claude Code 中直接描述需求（如"帮我把 LED 模块复制到 MRS2 工程"），AI 会自动通过 CLI 调用相应功能。

## 平台支持

| 平台 | 工程文件 | 编译工具链 |
|------|----------|------------|
| STM32F103 (Keil MDK-ARM) | .uvprojx | ARMCC / ARMClang |
| CH32V307 (MounRiver Studio 2) | .cproject | RISC-V GCC |

### 添加新平台

如需支持其他 IDE（如 TI CCS、ESP-IDF、IAR 等），只需新增一个平台适配器，放在 `core/platforms/` 下，继承 `PlatformAdapter`（`core/platform.py`），并在 `core/api.py` 中注册：

```python
# core/platform.py —— 抽象基类
class PlatformAdapter:
    def find_project_file(self, project_path: str) -> str:
        """定位工程文件（如 .uvprojx、.cproject、.ewp 等），找不到抛出 PlatformError。"""
        ...

    def register_module(self, project_file: str, module_meta: dict, project_path: str) -> None:
        """将模块注册到工程：创建分组 → 校验文件 → 添加 include 路径。"""
        ...
```

**必须实现**（被 `copy-module` / `chain-copy` 核心流程调用）：

| 方法 | 作用 |
|------|------|
| `find_project_file(path)` | 返回工程文件绝对路径，用于自动检测平台类型 |
| `register_module(file, meta, path)` | 注册一个模块到工程中 |

**建议实现**（被 `project-*` CLI 子命令调用，用于手动工程管理）：

| 方法 | 作用 | 备注 |
|------|------|------|
| `create_group(file, name)` | 创建工程分组 | 已存在则跳过 |
| `add_file(file, group, path)` | 注册源文件到分组 | 已注册则跳过 |
| `remove_file(file, group, path)` | 移除源文件 | |
| `add_include_path(file, folder)` | 添加头文件搜索路径 | |
| `remove_include_path(file, folder)` | 移除头文件搜索路径 | |
| `remove_group(file, name)` | 删除空分组 | 非空则报错 |
| `add_define(file, define)` | 添加预处理器宏 | 可选，IDE 不支持则抛 AttributeError |
| `remove_define(file, define)` | 移除预处理器宏 | 可选 |

如有使用AI agent，建议为新平台写一份skill文档，便于AI工作

**注意事项**：

1. `find_project_file` 是平台自动检测的唯一依据——确保能可靠区分你的平台与其他平台
2. 所有文件路径操作前做 `os.path.exists` 校验，出错抛出 `PlatformError`
3. 写工程文件前先 `shutil.copy2` 做 `.bak` 备份，保留修改历史
4. 在 `core/api.py` 调用 `register_adapter(YourAdapter)` 注册（参考 Keil/MRS2 的注册方式）
5. CLI 的 `project-*` 命令通过 `get_adapter()` 自动分发到匹配的适配器，无需修改 CLI 代码
6. 如果平台支持文件系统自动发现源文件（如 Eclipse CDT），`add_file` / `remove_file` 可为空操作

## 示例库

`example-libs/` 下有两个示例库，各含 6 个已验证模块：

### STM32F1-ExampleLib（STM32F103C8）

| 模块 | 分类 | 工程分组 | 依赖 |
|------|------|----------|------|
| Delay | System | System | — |
| Timer | System | System | — |
| PWM | System | System | Timer |
| LED | Display | Hardware | — |
| Key | Input | Hardware | Delay |
| Serial | Communication | Hardware | — |

### CH32V307-ExampleLib（CH32V307VCT6）

| 模块 | 分类 | 工程分组 | 依赖 |
|------|------|----------|------|
| Timer | System | System | — |
| LED | Display | Hardware | — |
| Key | Input | Hardware | Timer |
| USART | Communication | Hardware | — |
| ADC_DMA | Analog | Hardware | — |
| IIC_Hardware | Communication | Hardware | — |
