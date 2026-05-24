"""编辑模块对话框。"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QHBoxLayout, QFileDialog, QLabel,
    QMessageBox, QListWidget, QListWidgetItem,
    QGroupBox, QAbstractItemView, QCheckBox,
)
from PySide6.QtCore import Qt


class EditModuleDialog(QDialog):
    def __init__(self, info: dict, categories: list[str],
                 existing_modules: list[str], library_alias: str,
                 parent=None):
        super().__init__(parent)
        self._info = info
        self._categories = categories
        self._existing = existing_modules
        self._alias = library_alias
        self._name = info["name"]
        self._current_file_names = (
            info.get("files", {}).get("source", []) +
            info.get("files", {}).get("header", [])
        )
        self._added_files: list[str] = []  # 用户新增的绝对路径
        self._removed_files: set[str] = set()  # 用户移除的文件名
        self._delete_requested = False

        self.setWindowTitle(f"编辑模块: {info['name']}")
        self.setMinimumSize(560, 640)
        self._init_ui()
        self._result = None

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # ── 表单 ──
        form = QFormLayout()

        self.name_edit = QLineEdit(self._info["name"])
        form.addRow("名称:", self.name_edit)

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(False)
        for c in self._categories:
            self.cat_combo.addItem(c)
        current_cat = self._info.get("category", "")
        if current_cat:
            idx = self.cat_combo.findText(current_cat)
            if idx >= 0:
                self.cat_combo.setCurrentIndex(idx)
                if idx > 0:
                    self.cat_combo.removeItem(idx)
                    self.cat_combo.insertItem(0, current_cat)
                    self.cat_combo.setCurrentIndex(0)
            else:
                self.cat_combo.insertItem(0, current_cat)
                self.cat_combo.setCurrentIndex(0)

        cat_row = QHBoxLayout()
        cat_row.addWidget(self.cat_combo)
        btn_manage_cat = QPushButton("管理分类...")
        btn_manage_cat.clicked.connect(self._on_manage_categories)
        cat_row.addWidget(btn_manage_cat)
        form.addRow("分类:", cat_row)

        from core.api import _get_library
        from core.library import LibraryContext
        lib_path = _get_library(self._alias)["path"]
        ctx = LibraryContext(lib_path)
        groups = ctx.list_groups()

        self.group_combo = QComboBox()
        self.group_combo.setEditable(False)
        self.group_combo.addItems(groups)
        g = self._info.get("group", "Hardware")
        idx = self.group_combo.findText(g)
        if idx >= 0:
            self.group_combo.setCurrentIndex(idx)
            if idx > 0:
                self.group_combo.removeItem(idx)
                self.group_combo.insertItem(0, g)
                self.group_combo.setCurrentIndex(0)
        elif g:
            self.group_combo.insertItem(0, g)
            self.group_combo.setCurrentIndex(0)

        group_row = QHBoxLayout()
        group_row.addWidget(self.group_combo)
        btn_manage_group = QPushButton("管理分组...")
        btn_manage_group.clicked.connect(self._on_manage_groups)
        group_row.addWidget(btn_manage_group)
        form.addRow("工程分组:", group_row)

        # 版本
        ver_layout = QHBoxLayout()
        self.lbl_current_ver = QLabel(self._info.get("version", "1.0"))
        ver_layout.addWidget(QLabel("当前版本:"))
        ver_layout.addWidget(self.lbl_current_ver)
        ver_layout.addWidget(QLabel("  新版本:"))
        self.version_edit = QLineEdit()
        self.version_edit.setMaximumWidth(100)
        self.version_edit.setEnabled(False)
        ver_layout.addWidget(self.version_edit)
        self.snapshot_check = QCheckBox("保存为新版本并创建快照")
        self.snapshot_check.toggled.connect(self._on_snapshot_toggled)
        ver_layout.addWidget(self.snapshot_check)
        ver_layout.addStretch()
        form.addRow("版本:", ver_layout)

        # 验证状态
        vlayout = QHBoxLayout()
        self.verified_check = QCheckBox("已验证")
        self.verified_check.setChecked(self._info.get("verified", False))
        vlayout.addWidget(self.verified_check)
        vlayout.addStretch()
        form.addRow("验证:", vlayout)

        # 引脚
        pins = self._info.get("pins", {})
        self.pins_edit = QTextEdit()
        self.pins_edit.setMaximumHeight(60)
        self.pins_edit.setPlaceholderText("每行一个，格式: PIN=功能\n例如: PA0=Servo_PWM")
        if pins:
            self.pins_edit.setPlainText("\n".join(f"{k}={v}" for k, v in pins.items()))
        form.addRow("引脚:", self.pins_edit)

        # 描述
        self.notes_edit = QLineEdit(self._info.get("description", ""))
        self.notes_edit.setPlaceholderText("模块功能描述...")
        form.addRow("描述:", self.notes_edit)

        layout.addLayout(form)

        # ── 文件管理 ──
        file_group = QGroupBox("模块文件")
        file_layout = QVBoxLayout()

        bar = QHBoxLayout()
        btn_import_dir = QPushButton("从文件夹导入...")
        btn_import_dir.clicked.connect(self._import_from_dir)
        btn_add = QPushButton("添加文件...")
        btn_add.clicked.connect(self._add_files)
        btn_remove = QPushButton("移除选中")
        btn_remove.clicked.connect(self._remove_files)
        bar.addWidget(btn_import_dir)
        bar.addWidget(btn_add)
        bar.addWidget(btn_remove)
        bar.addStretch()
        self.lbl_count = QLabel()
        bar.addWidget(self.lbl_count)
        file_layout.addLayout(bar)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setTextElideMode(Qt.ElideLeft)
        file_layout.addWidget(self.file_list)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)
        self._refresh_file_list()

        # ── 依赖选择 ──
        dep_group = QGroupBox("依赖模块")
        dep_layout = QVBoxLayout()
        self.dep_list = QListWidget()
        current_deps = [d.lower() for d in self._info.get("dependencies", [])]
        for m in self._existing:
            if m.lower() == self._name.lower():
                continue  # 不依赖自己
            item = QListWidgetItem(m)
            item.setCheckState(Qt.Checked if m.lower() in current_deps else Qt.Unchecked)
            self.dep_list.addItem(item)
        dep_layout.addWidget(self.dep_list)
        dep_group.setLayout(dep_layout)
        layout.addWidget(dep_group)

        # ── 底部按钮 ──
        bottom = QHBoxLayout()

        btn_delete = QPushButton("删除模块")
        btn_delete.setObjectName("btnDelete")
        btn_delete.clicked.connect(self._on_delete)
        bottom.addWidget(btn_delete)
        bottom.addStretch()

        btn_save = QPushButton("保存")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._validate_and_accept)
        btn_cancel = QPushButton("取消")
        btn_cancel.clicked.connect(self.reject)
        bottom.addWidget(btn_save)
        bottom.addWidget(btn_cancel)

        layout.addLayout(bottom)

    def _on_manage_categories(self):
        from .manage_categories import ManageCategoriesDialog
        dlg = ManageCategoriesDialog(self._alias, self)
        dlg.exec()
        from core.api import _get_library
        from core.library import LibraryContext
        lib_path = _get_library(self._alias)["path"]
        ctx = LibraryContext(lib_path)
        current = self.cat_combo.currentText()
        self.cat_combo.clear()
        for c in ctx.list_categories():
            self.cat_combo.addItem(c)
        idx = self.cat_combo.findText(current)
        if idx >= 0:
            self.cat_combo.setCurrentIndex(idx)

    def _on_manage_groups(self):
        from .manage_groups import ManageGroupsDialog
        dlg = ManageGroupsDialog(self._alias, self)
        dlg.exec()
        from core.api import list_groups
        current = self.group_combo.currentText()
        self.group_combo.clear()
        for g in list_groups(self._alias):
            self.group_combo.addItem(g)
        idx = self.group_combo.findText(current)
        if idx >= 0:
            self.group_combo.setCurrentIndex(idx)

    # ── 文件管理 ──

    def _refresh_file_list(self):
        self.file_list.clear()
        for f in sorted(self._current_file_names):
            if f not in self._removed_files:
                item = QListWidgetItem(f"📄 {f}")
                item.setData(Qt.UserRole, f)
                item.setToolTip(f)
                self.file_list.addItem(item)
        for p in self._added_files:
            f = os.path.basename(p)
            item = QListWidgetItem(f"🆕 {f}  —  {p}")
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            item.setForeground(Qt.darkGreen)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.file_list.addItem(item)
        self.lbl_count.setText(
            f"共 {len(self._current_file_names) - len(self._removed_files) + len(self._added_files)} 个文件"
        )

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 C/H 源文件", "",
            "C/H 文件 (*.c *.h);;所有文件 (*)"
        )
        if not paths:
            return
        existing_names = (
            {f for f in self._current_file_names if f not in self._removed_files}
            | {os.path.basename(p) for p in self._added_files}
        )
        skipped = []
        for p in paths:
            p = os.path.abspath(p)
            name = os.path.basename(p)
            # 已在添加列表中
            if p in self._added_files:
                continue
            if name in existing_names:
                # 替换：移除旧的，加入新的
                if name in {f for f in self._current_file_names if f not in self._removed_files}:
                    self._removed_files.add(name)
                self._added_files = [x for x in self._added_files if os.path.basename(x) != name]
                self._added_files.append(p)
                existing_names.add(name)
                skipped.append(f"已替换: {name}")
            else:
                self._added_files.append(p)
                existing_names.add(name)
        self._refresh_file_list()
        if skipped:
            QMessageBox.information(self, "文件替换", "\n".join(skipped))

    def _remove_files(self):
        for item in self.file_list.selectedItems():
            key = item.data(Qt.UserRole)
            if key in self._added_files:
                self._added_files.remove(key)
            else:
                # 是已有文件
                self._removed_files.add(key)
        self._refresh_file_list()

    def _import_from_dir(self):
        path = QFileDialog.getExistingDirectory(self, "选择包含 C/H 文件的目录")
        if not path:
            return
        try:
            dir_files = [f for f in os.listdir(path)
                         if f.lower().endswith(('.c', '.h'))]
        except OSError as e:
            QMessageBox.warning(self, "错误", f"无法读取目录: {e}")
            return
        if not dir_files:
            QMessageBox.information(self, "提示", "所选目录中没有 .c 或 .h 文件")
            return

        existing_names = {f for f in self._current_file_names if f not in self._removed_files}
        replaced = []
        added = []
        for f in dir_files:
            src = os.path.abspath(os.path.join(path, f))
            if f in existing_names:
                self._removed_files.add(f)
                self._added_files = [x for x in self._added_files if os.path.basename(x) != f]
                self._added_files.append(src)
                replaced.append(f)
            elif src not in self._added_files:
                self._added_files.append(src)
                added.append(f)

        self._refresh_file_list()
        msg_parts = []
        if replaced:
            msg_parts.append(f"已替换: {', '.join(replaced)}")
        if added:
            msg_parts.append(f"新增: {', '.join(added)}")
        if msg_parts:
            self.lbl_count.setToolTip("\n".join(msg_parts))

    def _on_snapshot_toggled(self, checked: bool):
        self.version_edit.setEnabled(checked)
        if checked:
            old_ver = self._info.get("version", "1.0")
            parts = old_ver.rsplit(".", 1)
            if len(parts) == 2 and parts[1].isdigit():
                new_ver = f"{parts[0]}.{int(parts[1]) + 1}"
            else:
                new_ver = old_ver + ".1"
            self.version_edit.setText(new_ver)
        else:
            self.version_edit.clear()

    # ── 保存 ──

    def _validate_and_accept(self):
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "验证失败", "模块名称不能为空")
            return
        new_cat = self.cat_combo.currentText().strip()
        if not new_cat:
            QMessageBox.warning(self, "验证失败", "请选择分类")
            return
        # 检查名称冲突（改名后与其他模块重名）
        if new_name.lower() != self._name.lower():
            for m in self._existing:
                if m.lower() == new_name.lower():
                    QMessageBox.warning(self, "验证失败", f"模块 '{new_name}' 已存在")
                    return

        if self.snapshot_check.isChecked():
            new_ver = self.version_edit.text().strip() or self._info.get("version", "1.0")
        else:
            new_ver = None

        # 解析引脚
        pins = {}
        pin_text = self.pins_edit.toPlainText().strip()
        if pin_text:
            for line in pin_text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    pins[k.strip()] = v.strip()

        deps = []
        for i in range(self.dep_list.count()):
            item = self.dep_list.item(i)
            if item.checkState() == Qt.Checked:
                deps.append(item.text())

        # 检查依赖回路
        effective_name = new_name if new_name != self._name else self._name
        cycle = self._detect_cycle(effective_name, deps)
        if cycle:
            QMessageBox.warning(self, "循环依赖",
                                f"依赖关系修改已自动撤销：所选依赖会形成循环引用。\n"
                                f"涉及模块: {' → '.join(cycle)}\n\n"
                                f"其他修改正常保留，可继续保存。")
            # 恢复依赖复选框为原始状态
            current_deps = {d.lower() for d in self._info.get("dependencies", [])}
            for i in range(self.dep_list.count()):
                item = self.dep_list.item(i)
                item.setCheckState(Qt.Checked if item.text().lower() in current_deps else Qt.Unchecked)
            deps = [d for d in self._info.get("dependencies", [])]

        self._result = {
            "new_name": new_name if new_name != self._name else None,
            "new_category": new_cat if new_cat != self._info.get("category", "") else None,
            "new_version": new_ver,
            "new_description": self.notes_edit.text().strip(),
            "new_group": self.group_combo.currentText().strip(),
            "new_pins": pins,
            "new_verified": self.verified_check.isChecked(),
            "new_dependencies": deps,
            "add_files": self._added_files if self._added_files else None,
            "remove_files": list(self._removed_files) if self._removed_files else None,
        }
        self.accept()

    def get_result(self) -> dict:
        return self._result

    def is_delete_requested(self) -> bool:
        return self._delete_requested

    # ── 回路检测 ──

    def _detect_cycle(self, new_name: str, new_deps: list[str]):
        """检测添加 new_deps 后是否形成回路。返回回路路径或 None。"""
        from core.library import LibraryContext
        from core.api import _get_library
        try:
            lib = _get_library(self._alias)
            ctx = LibraryContext(lib["path"])
            graph = {}
            for e in ctx.load_index():
                mod = ctx.load_module(e["name"])
                ename = e["name"].lower()
                if ename == self._name.lower():
                    graph[new_name.lower()] = [d.lower() for d in new_deps]
                else:
                    graph[ename] = [d.lower() for d in mod.get("dependencies", [])]

            WHITE, GRAY, BLACK = 0, 1, 2
            color = {}

            def dfs(n, path):
                if n not in graph:
                    return None
                color[n] = GRAY
                path.append(n)
                for nb in graph[n]:
                    if nb not in graph:
                        continue
                    if color.get(nb) == GRAY:
                        # 找到回路
                        cycle_start = path.index(nb)
                        return path[cycle_start:] + [nb]
                    if color.get(nb, WHITE) == WHITE:
                        result = dfs(nb, path)
                        if result:
                            return result
                path.pop()
                color[n] = BLACK
                return None

            for n in graph:
                color[n] = WHITE
            return dfs(new_name.lower(), [])
        except Exception as e:
            QMessageBox.warning(self, "回路检测失败",
                                f"无法检测循环依赖，依赖修改仍将保存。\n错误: {e}")
            return None

    # ── 删除 ──

    def _on_delete(self):
        try:
            from core.dependency import reverse_dependencies
            from core.library import LibraryContext
            from core.api import load_config, _get_library
            lib = _get_library(self._alias)
            ctx = LibraryContext(lib["path"])
            rdeps = reverse_dependencies(ctx, self._name)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"无法检查依赖关系: {e}")
            return

        msg = f"确定要将模块 '{self._name}' 从库 '{self._alias}' 中移除吗？\n\n"
        msg += "模块文件夹将移到 _trash/ 目录，可在文件系统中恢复。\n"

        if rdeps:
            msg += f"\n⚠ 以下 {len(rdeps)} 个模块依赖了 '{self._name}'：\n"
            msg += "  " + ", ".join(rdeps) + "\n"
            msg += "移除后将自动从这些模块的依赖列表中清除引用。\n"
            msg += "❗ 请确认这些模块的代码逻辑已经脱离对被删模块的真实依赖\n"
            msg += "（例如不再 #include 其头文件、不调用其函数），否则编译会失败。\n"
        else:
            msg += "\n无其他模块依赖此模块，可安全移除。"

        reply = QMessageBox.question(
            self, "确认删除", msg,
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._delete_requested = True
            self.reject()
