---
name: codelib-manager
description: 管理可复用C代码库，包括模块浏览/导入/导出/链复制/编辑/验证、分类和工程分组管理。触发条件：需要查找、复用、导入、管理代码模块，或进行模块验证时。
---

# 代码库管理器

## 工具位置与调用方式

CLI 工具位于 `<CodeLibManager根目录>`：

```bash
cd <CodeLibManager根目录> && python -m cli.main <command> [args...]
```

所有命令支持 `--json` 输出结构化数据供 AI 解析。除 `add-library` 外，所有命令的 `--library` 参数可省略（默认使用活跃库）。

## 核心概念：分类 vs 工程分组（关键！容易混淆）

- **分类（category）**：模块在代码库中的逻辑归类，**同时是库文件系统中的物理文件夹名**。例如 `Communication`、`Display`、`Motor`、`Sensor`、`System`。同一分类下的所有模块存放在 `<库根>/<分类>/<模块名>/` 目录下。
- **工程分组（group）**：每个模块的元数据词条，表明该模块**复制到目标工程时应放入哪个子目录**。例如 `Hardware` 或 `System`。工程分组值由 `.codelib.json` 中的 `groups` 数组集中管理，目前只用两个：`Hardware` 和 `System`。

**禁止行为**：不要把分类名当作工程分组名写入 `--group` 参数，也不要把分类名加入 `.codelib.json` 的 groups 列表。两者完全独立，没有对应关系。

## 核心原则

- **先查询，不假设**：操作前用 `list-libraries --json` 发现可用库，用 `list-modules` 了解库内容。**绝不硬编码库路径或别名。**
- **干跑先行**：`chain-copy` 必须先 `--dry-run` 展示依赖链和冲突给用户确认，再正式执行。
- **用别名，不用路径**：AI 通过 `--library <别名>` 指定目标库，物理路径由 config.json 管理。

---

## 一、库发现与切换

```bash
# 列出所有已注册库（含 alias、path、active 状态）
python -m cli.main list-libraries --json

# 切换活跃库（后续命令可省略 --library）
python -m cli.main switch-library <别名>

# 注册新库
python -m cli.main add-library <别名> <路径>

# 注销库（不删除物理文件）
python -m cli.main remove-library <别名>

# 重命名库别名（不改物理路径）
python -m cli.main rename-library <旧别名> <新别名>

# 更新库物理路径（不移动文件）
python -m cli.main update-library-path <别名> <新路径>

# 完整性检测
python -m cli.main validate-library [--library <别名>]

# 清理无效模块索引条目
python -m cli.main cleanup-broken [--library <别名>]
```

---

## 二、模块浏览

```bash
# 列出模块（支持过滤）
python -m cli.main list-modules [--library <别名>] \
    [--category <分类>] [--status verified|unverified] \
    [--search <关键词>] [--summary] [--json]

# 查看模块详情（含依赖、引脚、文件等）
python -m cli.main info <模块名> [--library <别名>] [--json]

# 查看递归依赖树
python -m cli.main tree <模块名> [--library <别名>] [--json]
```

`--summary` 输出精简（名称/分类/状态/依赖数），节省 token。

---

## 三、模块导出到工程

### 单模块复制

```bash
python -m cli.main copy-to-project <模块名> <工程路径> [--library <别名>] \
    [--dry-run] [--json]
```

自动完成：复制 .c/.h → 创建工程分组目录 → 注册文件（Keil）/ 自动发现（MRS2）→ 添加 Include 路径。

### 链复制（含依赖）

```bash
# 第一步：干跑预览（必须！）
python -m cli.main chain-copy <入口模块> <工程路径> --dry-run --json

# 第二步：把依赖链和冲突列表展示给用户，确认选择范围和冲突处理方式

# 第三步：正式执行
python -m cli.main chain-copy <入口模块> <工程路径> [--library <别名>] \
    [--select <模块1,模块2>] \
    [--conflicts "<文件名>:skip|overwrite|rename,..."] \
    [--json]
```

- `--select`：只复制依赖链中的指定模块
- `--conflicts`：按文件名指定冲突处理策略
  - `skip`：跳过该文件
  - `overwrite`：覆盖并备份原文件为 .bak
  - `rename`：自动重命名（添加 _new 后缀）

**AI 执行链复制时必须先 --dry-run 给用户确认！**

---

## 四、模块导入

```bash
python -m cli.main import-module <源目录> [--library <别名>] \
    --name <模块名> --category <分类> \
    [--version 1.0] [--description "描述"] \
    [--deps "依赖A,依赖B"] [--group <工程分组>] \
    [--json]
```

从包含 .c/.h 文件的目录导入为新模块。源目录中所有 .c/.h 文件会被复制到库中。

---

## 五、模块编辑

```bash
python -m cli.main edit-module <模块名> [--library <别名>] \
    [--new-name <新名称>] [--new-category <新分类>] \
    [--new-version <版本号>] [--new-description "描述"] \
    [--new-group <工程分组>] [--pins "PA0=SERVO,PA1=LED"] \
    [--new-verified True|False] [--new-notes "备注"] \
    [--deps "模块A,模块B"] \
    [--add <文件路径1> <文件路径2>] \
    [--remove <文件名1> <文件名2>] \
    [--json]
```

- 只传需要修改的字段，未传的保持不变
- `--new-version`：版本变化时自动创建快照（旧版 zip 入 .snapshots/）
- `--new-name`：重命名模块会联动更新索引和其他模块的依赖引用
- `--add` / `--remove`：管理模块文件

---

## 六、模块更新

```bash
python -m cli.main update-module <模块名> <源目录> [--library <别名>] \
    [--from-project] [--no-verify] [--json]
```

- 用源目录中的 .c/.h 替换模块文件，自动创建快照
- 默认自动标记为已验证
- `--from-project`：从 Keil 工程目录反向同步（源目录 = 工程根路径，自动定位 `<Group>/<file>`）
- `--no-verify`：跳过自动验证标记

---

## 七、模块验证与删除

```bash
# 标记验证状态
python -m cli.main verify <模块名> --status passed|failed \
    [--notes "验证说明"] [--library <别名>] [--json]

# 删除模块（移入 _trash/，清理依赖引用）
python -m cli.main remove-module <模块名> [--library <别名>] [--json]
```

---

## 八、分类管理

分类 = 库根目录下的物理文件夹，重命名/删除会联动更新索引和所有受影响的 module.json。

```bash
python -m cli.main add-category <分类名> [--library <别名>] [--json]
python -m cli.main rename-category <旧名> <新名> [--library <别名>] [--json]
python -m cli.main delete-category <分类名> [--library <别名>] [--json]
```

- `delete-category`：只能删除空分类，有模块时失败并列出模块名
- `rename-category`：重命名物理文件夹 + 更新所有模块的 category/path + 更新所有 module.json

---

## 九、工程分组管理

分组 = `.codelib.json` 中的 `groups` 数组，每个库独立维护。目前只用 `Hardware` 和 `System` 两个值。

```bash
python -m cli.main list-groups [--library <别名>] [--json]
python -m cli.main add-group <分组名> [--library <别名>] [--json]
python -m cli.main rename-group <旧名> <新名> [--library <别名>] [--json]
python -m cli.main delete-group <分组名> [--library <别名>] [--json]
```

- `delete-group`：只能删除未被任何模块使用的分组
- `rename-group`：重命名时会联动更新使用该分组的所有 module.json

---

## 十、模块验证工作流

代码库中的模块初始标记为"未验证"。验证需按依赖关系**从底层到上层**逐步进行。

### 固定验证工程

- 位置：`<Keil工程目录>\Programs\VerifyTest`（由用户自行配置）
- 预配置 STM32F103C8 模板，长期复用
- 每次验证新模块前确保 main.c 已清理为最小模板

### 每次验证对话步骤（跨技能协作）

> **技能链**：codelib-manager（步骤 1-5）→ c-cpp-coding-guide（步骤 6）→ keil-build（步骤 7）→ codelib-manager（步骤 9）
> 步骤切换时，AI 应自动激活对应技能。

1. **查看进度**：`list-modules --status unverified`
2. **筛选可测模块**：在未验证中，找出依赖全部已验的模块，展示给用户
3. **用户选择**：由用户决定本次验证哪个模块
4. **讨论标准**：与用户讨论验证标准（需覆盖哪些接口、边界条件）
5. **添加到验证工程**：`copy-to-project <模块> VerifyTest`
6. **编写测试 main.c**：覆盖模块所有公开接口 → 触发 **c-cpp-coding-guide** 技能
7. **编译烧录**：执行 `UV4.exe -j0 -b ... && UV4.exe -j0 -f ...` → 触发 **keil-build** 技能
8. **硬件验证**：用户确认功能正常
9. **反向同步**：`update-module <模块> VerifyTest --from-project` → 回到 **codelib-manager**
   - 从工程复制文件回库（覆盖原文件）
   - 自动标记 verified + 记录日期
   - `--no-verify` 可跳过自动标记

### 验证优先级（按依赖排序）

| 优先级 | 模块 | 依赖 |
|--------|------|------|
| P0 | Delay | 无 |
| P0 | LED | 无 |
| P1 | Key, Timer, Serial | Delay |
| P2 | OLED, PWM, IIC_Hardware | Timer |
| P3 | ADC, MPU6050, IC, Servo, stepmotor, 其他 | 各依赖 |

### 贡献已验证模块到代码库

新模块经代码审查 + 编译 + 硬件测试验证后入库：

1. 将 .c/.h 文件复制到库的 `<Category>/<ModuleName>/`
2. 创建 `module.json`（参照现有模块格式）
3. 在 `modules.json` 中添加条目
4. 标记验证：`verify <模块名> --status passed`
5. 提醒用户考虑将已验证模块入库

---

## Token 节约技巧

- `list-modules --summary`：精简输出，每模块一行
- `list-modules --json`：结构化数据，AI 直接解析关键字段
- `info <模块> --field dependencies,pins --json`：按需取字段，省 80% 输出
- `chain-copy --dry-run --json`：预览完整依赖链，避免无效交互
- `tree --json`：获取完整依赖树，避免递归查询
