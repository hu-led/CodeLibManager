"""导入新模块对话框（跨文件夹多选文件）。"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QTextEdit, QPushButton, QHBoxLayout, QFileDialog, QLabel,
    QDialogButtonBox, QMessageBox, QListWidget, QListWidgetItem,
    QGroupBox, QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class ImportModuleDialog(QDialog):
    def __init__(self, library_path: str, categories: list[str],
                 existing_modules: list[str], parent=None):
        super().__init__(parent)
        self._library_path = library_path
        self._existing = existing_modules
        self._file_paths: list[str] = []  # 累积选中的文件绝对路径
        self.setWindowTitle("导入新模块")
        self.setMinimumSize(550, 620)
        self._init_ui(categories)
        self._result = None

    def _init_ui(self, categories: list[str]):
        layout = QVBoxLayout(self)

        # ── 文件选择区域 ──
        file_group = QGroupBox("选择要导入的文件 (.c / .h)")
        file_layout = QVBoxLayout()

        sel_bar = QHBoxLayout()
        btn_add = QPushButton("添加文件...")
        btn_add.clicked.connect(self._add_files)
        btn_remove = QPushButton("移除选中")
        btn_remove.clicked.connect(self._remove_selected)
        btn_clear = QPushButton("清空")
        btn_clear.clicked.connect(self._clear_files)
        sel_bar.addWidget(btn_add)
        sel_bar.addWidget(btn_remove)
        sel_bar.addWidget(btn_clear)
        sel_bar.addStretch()
        self.lbl_count = QLabel("已选: 0 个文件")
        sel_bar.addWidget(self.lbl_count)
        file_layout.addLayout(sel_bar)

        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.file_list.setTextElideMode(Qt.ElideLeft)
        file_layout.addWidget(self.file_list)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # ── 表单 ──
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("模块名称（英文）")
        form.addRow("名称 *:", self.name_edit)

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(True)
        for c in categories:
            self.cat_combo.addItem(c)
        form.addRow("分类 *:", self.cat_combo)

        self.version_edit = QLineEdit("1.0")
        form.addRow("版本:", self.version_edit)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(60)
        self.desc_edit.setPlaceholderText("简要描述模块功能...")
        form.addRow("描述:", self.desc_edit)

        from core.library import LibraryContext
        ctx = LibraryContext(self._library_path)
        groups = ctx.list_groups()

        self.group_combo = QComboBox()
        self.group_combo.addItems(groups)
        self.group_combo.setEditable(True)
        form.addRow("工程分组:", self.group_combo)

        layout.addLayout(form)

        # ── 依赖选择 ──
        dep_group = QGroupBox("依赖模块（勾选需要的）")
        dep_layout = QVBoxLayout()
        self.dep_list = QListWidget()
        for m in self._existing:
            item = QListWidgetItem(m)
            item.setCheckState(Qt.Unchecked)
            self.dep_list.addItem(item)
        dep_layout.addWidget(self.dep_list)
        dep_group.setLayout(dep_layout)
        layout.addWidget(dep_group)

        # ── 按钮 ──
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._validate)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择 C/H 源文件", "",
            "C/H 文件 (*.c *.h);;所有文件 (*)"
        )
        if not paths:
            return
        existing_paths = set(self._file_paths)
        existing_names = {os.path.basename(x) for x in self._file_paths}
        skipped = []
        for p in paths:
            p = os.path.abspath(p)
            if p in existing_paths:
                continue
            name = os.path.basename(p)
            if name in existing_names:
                skipped.append(f"{name}\n  (已有: {[x for x in self._file_paths if os.path.basename(x) == name][0]})")
                continue
            existing_names.add(name)
            existing_paths.add(p)
            self._file_paths.append(p)
            item = QListWidgetItem(f"📄 {name}  —  {p}")
            item.setData(Qt.UserRole, p)
            item.setToolTip(p)
            item.setForeground(QColor("#1A73E8"))
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            self.file_list.addItem(item)
        self._update_count()
        if skipped:
            QMessageBox.warning(self, "同名文件", "以下文件与已选文件重名，已跳过:\n" + "\n".join(skipped))

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            path = item.data(Qt.UserRole)
            if path in self._file_paths:
                self._file_paths.remove(path)
            self.file_list.takeItem(self.file_list.row(item))
        self._update_count()

    def _clear_files(self):
        self._file_paths.clear()
        self.file_list.clear()
        self._update_count()

    def _update_count(self):
        self.lbl_count.setText(f"已选: {len(self._file_paths)} 个文件")

    def _validate(self):
        name = self.name_edit.text().strip()
        cat = self.cat_combo.currentText().strip()

        if not name:
            QMessageBox.warning(self, "验证失败", "请输入模块名称")
            return
        if not cat:
            QMessageBox.warning(self, "验证失败", "请选择或输入分类")
            return
        if name.lower() in [m.lower() for m in self._existing]:
            QMessageBox.warning(self, "验证失败", f"模块 '{name}' 已存在")
            return
        if not self._file_paths:
            QMessageBox.warning(self, "验证失败", "请至少选择一个文件")
            return

        deps = []
        for i in range(self.dep_list.count()):
            item = self.dep_list.item(i)
            if item.checkState() == Qt.Checked:
                deps.append(item.text())

        self._result = {
            "file_paths": self._file_paths,
            "name": name,
            "category": cat,
            "version": self.version_edit.text().strip() or "1.0",
            "description": self.desc_edit.toPlainText().strip(),
            "dependencies": deps,
            "group": self.group_combo.currentText().strip() or "Hardware",
        }
        self.accept()

    def get_result(self) -> dict:
        return self._result
