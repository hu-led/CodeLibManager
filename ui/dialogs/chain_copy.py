"""模块链复制预览对话框。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QFileDialog, QLineEdit, QLabel, QMessageBox,
    QDialogButtonBox, QGroupBox, QFormLayout, QComboBox, QScrollArea,
)
from PySide6.QtCore import Qt


class ChainCopyDialog(QDialog):
    def __init__(self, chain: list[dict], conflicts: list[dict],
                 library_alias: str, parent=None):
        super().__init__(parent)
        self._chain = chain
        self._conflicts = {c["file"]: c for c in conflicts}
        self._library_alias = library_alias
        self._selected_names = set(m["name"] for m in chain)  # 默认全选
        self._conflict_resolutions = {}
        self.setWindowTitle(f"模块链复制预览 — {library_alias}")
        self.setMinimumSize(650, 450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 依赖链树
        lbl = QLabel(f"选中模块的依赖链（{len(self._chain)} 个模块，拓扑顺序）：")
        layout.addWidget(lbl)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", "模块", "分组", "文件", "状态"])
        self.tree.setRootIsDecorated(True)
        # 构建树
        roots = [m for m in self._chain if not self._is_dep_of_any(m, self._chain)]
        for r in roots:
            self._add_chain_node(self.tree.invisibleRootItem(), r)
        self.tree.expandAll()
        self.tree.setColumnWidth(0, 50)
        layout.addWidget(self.tree, 3)

        # 冲突警告（默认隐藏，选择工程路径后检测到冲突时显示）
        self.conflict_scroll = QScrollArea()
        self.conflict_scroll.setWidgetResizable(True)
        self.conflict_scroll.setMaximumHeight(180)
        self.conflict_group = QGroupBox("")
        self.conflict_layout = QFormLayout()
        self.conflict_group.setLayout(self.conflict_layout)
        self.conflict_scroll.setWidget(self.conflict_group)
        self.conflict_scroll.hide()
        layout.addWidget(self.conflict_scroll)

        # 工程路径
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("目标工程:"))
        self.project_edit = QLineEdit()
        self.project_edit.setPlaceholderText("选择工程目录...")
        path_layout.addWidget(self.project_edit)
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse_project)
        path_layout.addWidget(btn_browse)
        layout.addLayout(path_layout)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText("确认复制")
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _add_chain_node(self, parent, mod: dict):
        name = mod.get("name", "?")
        files = (mod.get("files", {}).get("source", []) +
                 mod.get("files", {}).get("header", []))
        v = "✓" if mod.get("verified") else "✗"
        item = QTreeWidgetItem(["", name, mod.get("group", ""),
                                 ", ".join(files), v])
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(0, Qt.Checked)
        item.setData(0, Qt.UserRole, name)
        parent.addChild(item)

        # 添加依赖子节点
        for dep_name in mod.get("dependencies", []):
            dep_mod = next((m for m in self._chain if m["name"].lower() == dep_name.lower()), None)
            if dep_mod:
                self._add_chain_node(item, dep_mod)

    def _is_dep_of_any(self, mod: dict, all_mods: list[dict]) -> bool:
        name_lower = mod["name"].lower()
        for m in all_mods:
            deps_lower = [d.lower() for d in m.get("dependencies", [])]
            if name_lower in deps_lower:
                return True
        return False

    def _on_conflict_resolve(self, filename: str, index: int):
        actions = ["skip", "overwrite", "rename"]
        self._conflict_resolutions[filename] = actions[index]

    def _browse_project(self):
        path = QFileDialog.getExistingDirectory(self, "选择工程目录")
        if path:
            self.project_edit.setText(path)
            self._update_conflicts(path)

    def _update_conflicts(self, project_path):
        from core.file_ops import check_file_conflicts
        conflicts = check_file_conflicts(self._chain, project_path)
        self._conflicts = {c["file"]: c for c in conflicts}
        self._conflict_resolutions.clear()

        # 清空旧内容
        while self.conflict_layout.rowCount():
            self.conflict_layout.removeRow(0)

        if conflicts:
            self.conflict_group.setTitle(f"⚠ 文件冲突 ({len(conflicts)} 个)")
            for fname, c in self._conflicts.items():
                row = QHBoxLayout()
                lbl_conflict = QLabel(f"{fname}: 由 '{c['module_a']}' 已有，'{c['module_b']}' 也将添加")
                lbl_conflict.setStyleSheet("color: #E37400;")
                combo = QComboBox()
                combo.addItems(["跳过", "覆盖(备份)", "重命名"])
                combo.setCurrentIndex(0)
                combo.currentIndexChanged.connect(
                    lambda idx, f=fname: self._on_conflict_resolve(f, idx)
                )
                row.addWidget(lbl_conflict, 1)
                row.addWidget(combo)
                self.conflict_layout.addRow(row)
            self.conflict_scroll.show()
        else:
            self.conflict_scroll.hide()

    def _validate_and_accept(self):
        project = self.project_edit.text().strip()
        if not project:
            QMessageBox.warning(self, "验证失败", "请选择目标工程目录")
            return

        # 收集勾选的模块
        self._selected_names = set()
        for i in range(self.tree.topLevelItemCount()):
            self._collect_checked(self.tree.topLevelItem(i))

        if not self._selected_names:
            QMessageBox.warning(self, "验证失败", "请至少勾选一个模块")
            return

        # 给未设置的冲突加默认 skip
        for fname in self._conflicts:
            if fname not in self._conflict_resolutions:
                self._conflict_resolutions[fname] = "skip"

        self._project = project
        self.accept()

    def _collect_checked(self, item):
        if item.checkState(0) == Qt.Checked:
            self._selected_names.add(item.data(0, Qt.UserRole))
        for i in range(item.childCount()):
            self._collect_checked(item.child(i))

    def get_selected_modules(self) -> list[str]:
        return list(self._selected_names)

    def get_project_path(self) -> str:
        return self._project

    def get_conflict_resolutions(self) -> dict:
        return self._conflict_resolutions
