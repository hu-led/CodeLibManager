"""模块详情面板。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout,
    QTreeWidget, QTreeWidgetItem, QPushButton, QHBoxLayout,
    QTextEdit, QSplitter, QHeaderView,
)
from PySide6.QtCore import Qt, Signal


class ModuleDetailWidget(QWidget):
    copy_requested = Signal(str)
    chain_copy_requested = Signal(str)
    edit_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_module = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 基本信息
        self.info_group = QGroupBox("模块信息")
        self.info_form = QFormLayout()
        self.lbl_name = QLabel("—")
        self.lbl_version = QLabel("—")
        self.lbl_category = QLabel("—")
        self.lbl_status = QLabel("—")
        self.lbl_group = QLabel("—")
        self.lbl_files = QLabel("—")
        self.lbl_files.setWordWrap(True)
        self.lbl_files.setMinimumWidth(0)
        self.lbl_pins = QLabel("—")
        self.lbl_pins.setWordWrap(True)
        self.lbl_pins.setMinimumWidth(0)
        self.lbl_notes = QLabel("—")
        self.lbl_notes.setWordWrap(True)
        self.lbl_notes.setMinimumWidth(0)

        self.info_form.addRow("名称:", self.lbl_name)
        self.info_form.addRow("版本:", self.lbl_version)
        self.info_form.addRow("分类:", self.lbl_category)
        self.info_form.addRow("状态:", self.lbl_status)
        self.info_form.addRow("工程分组:", self.lbl_group)
        self.info_form.addRow("文件:", self.lbl_files)
        self.info_form.addRow("引脚:", self.lbl_pins)
        self.info_form.addRow("描述:", self.lbl_notes)
        self.info_group.setLayout(self.info_form)
        layout.addWidget(self.info_group)

        # 操作按钮（高频操作，放在信息区下方）
        btn_layout = QHBoxLayout()
        self.btn_copy = QPushButton("复制到工程")
        self.btn_copy.clicked.connect(self._on_copy)
        self.btn_chain = QPushButton("链复制到工程")
        self.btn_chain.clicked.connect(self._on_chain_copy)
        self.btn_edit = QPushButton("编辑模块")
        self.btn_edit.clicked.connect(self._on_edit)
        btn_layout.addWidget(self.btn_copy)
        btn_layout.addWidget(self.btn_chain)
        btn_layout.addWidget(self.btn_edit)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # 依赖树
        self.dep_group = QGroupBox("依赖关系")
        dep_layout = QVBoxLayout()
        self.dep_tree = QTreeWidget()
        self.dep_tree.setHeaderLabels(["模块", "分组", "状态"])
        self.dep_tree.setRootIsDecorated(True)
        self.dep_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.dep_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.dep_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        dep_layout.addWidget(self.dep_tree)

        self.lbl_reverse = QLabel("")
        self.lbl_reverse.setWordWrap(True)
        self.lbl_reverse.setMinimumWidth(0)
        dep_layout.addWidget(self.lbl_reverse)
        self.dep_group.setLayout(dep_layout)
        layout.addWidget(self.dep_group)

        self.setEnabled(False)

    def clear(self):
        self._current_module = None
        self.lbl_name.setText("—")
        self.lbl_version.setText("—")
        self.lbl_category.setText("—")
        self.lbl_status.setText("—")
        self.lbl_group.setText("—")
        self.lbl_files.setText("—")
        self.lbl_pins.setText("—")
        self.lbl_notes.setText("—")
        self.dep_tree.clear()
        self.lbl_reverse.setText("")
        self.setEnabled(False)

    def show_module(self, info: dict):
        self._current_module = info
        self.setEnabled(True)

        name = info.get("name", "—")
        self.lbl_name.setText(name)
        self.lbl_version.setText(info.get("version", "—"))
        self.lbl_category.setText(info.get("category", "—"))

        v = info.get("verified", False)
        vd = info.get("verified_date")
        status_text = "✓ 已验证" if v else "✗ 未验证"
        if v and vd:
            status_text += f" ({vd})"
        self.lbl_status.setText(status_text)

        self.lbl_group.setText(info.get("group", "—"))
        all_files = (info.get("files", {}).get("source", []) +
                     info.get("files", {}).get("header", []))
        self.lbl_files.setText(", ".join(all_files) if all_files else "—")

        pins = info.get("pins", {})
        self.lbl_pins.setText(", ".join(f"{k}={v}" for k, v in pins.items()) if pins else "—")
        self.lbl_notes.setText(info.get("description", "") or "—")

        # 更新按钮文本
        self.btn_copy.setText(f"复制 '{name}' 到工程")
        self.btn_chain.setText(f"链复制 '{name}' 到工程")
        self.btn_edit.setText(f"编辑 '{name}'")

    def show_dependency_tree(self, tree: dict):
        self.dep_tree.clear()
        self._add_tree_node(self.dep_tree.invisibleRootItem(), tree)

    def _add_tree_node(self, parent, node: dict):
        status = "✓" if node.get("verified") else "✗"
        item = QTreeWidgetItem([
            node.get("name", "?"),
            node.get("group", ""),
            status,
        ])
        parent.addChild(item)
        for child in node.get("dependencies", []):
            self._add_tree_node(item, child)
        item.setExpanded(True)

    def show_reverse_deps(self, rdeps: list[str]):
        if rdeps:
            self.lbl_reverse.setText(f"被以下模块依赖: {', '.join(rdeps)}")
        else:
            self.lbl_reverse.setText("无模块依赖此模块")

    def _on_copy(self):
        if self._current_module:
            self.copy_requested.emit(self._current_module["name"])

    def _on_chain_copy(self):
        if self._current_module:
            self.chain_copy_requested.emit(self._current_module["name"])

    def _on_edit(self):
        if self._current_module:
            self.edit_requested.emit(self._current_module["name"])
