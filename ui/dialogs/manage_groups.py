"""管理工程分组对话框。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QInputDialog,
)
from PySide6.QtCore import Qt, Signal


class ManageGroupsDialog(QDialog):
    """管理库的工程分组。"""

    groups_changed = Signal()

    def __init__(self, library_alias: str, parent=None):
        super().__init__(parent)
        self._alias = library_alias
        self.setWindowTitle(f"管理工程分组 — {library_alias}")
        self.setMinimumSize(400, 380)
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("工程分组（Keil: .uvprojx 分组 / MRS2: 文件系统目录）："))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("新增:"))
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("输入新分组名...")
        self.add_edit.returnPressed.connect(self._add)
        add_layout.addWidget(self.add_edit)
        btn_add = QPushButton("添加")
        btn_add.clicked.connect(self._add)
        add_layout.addWidget(btn_add)
        layout.addLayout(add_layout)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _refresh_list(self):
        from core.api import list_groups
        groups = list_groups(self._alias)

        self.list_widget.clear()
        for g in groups:
            self.list_widget.addItem(g)

    def _add(self):
        from core.api import add_group, LibraryError
        name = self.add_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入分组名")
            return
        try:
            add_group(self._alias, name)
            self.add_edit.clear()
            self._refresh_list()
            self.groups_changed.emit()
        except LibraryError as e:
            QMessageBox.warning(self, "添加失败", str(e))

    def contextMenuEvent(self, event):
        item = self.list_widget.currentItem()
        if item is None:
            return
        name = item.text()

        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("改名", lambda: self._rename(name))
        menu.addAction("删除", lambda: self._delete(name))
        menu.exec(event.globalPos())

    def _rename(self, old_name: str):
        new_name, ok = QInputDialog.getText(
            self, "重命名分组", f"将 '{old_name}' 重命名为:",
            text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        try:
            from core.api import rename_group, LibraryError
            result = rename_group(self._alias, old_name, new_name.strip())
            self._refresh_list()
            self.groups_changed.emit()
            if result["affected_modules"]:
                QMessageBox.information(
                    self, "完成",
                    f"分组已重命名，影响 {len(result['affected_modules'])} 个模块"
                )
        except LibraryError as e:
            QMessageBox.warning(self, "改名失败", str(e))

    def _delete(self, name: str):
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除分组 '{name}' 吗？\n\n"
            f"只能删除未被模块使用的分组。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            from core.api import delete_group, LibraryError
            delete_group(self._alias, name)
            self._refresh_list()
            self.groups_changed.emit()
        except LibraryError as e:
            QMessageBox.warning(self, "删除失败", str(e))
