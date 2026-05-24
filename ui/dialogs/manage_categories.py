"""管理分类对话框。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox, QInputDialog,
)
from PySide6.QtCore import Qt, Signal


class ManageCategoriesDialog(QDialog):
    """管理库的分类（文件夹）。"""

    categories_changed = Signal()  # 关闭后通知调用方刷新

    def __init__(self, library_alias: str, parent=None):
        super().__init__(parent)
        self._alias = library_alias
        self.setWindowTitle(f"管理分类 — {library_alias}")
        self.setMinimumSize(400, 380)
        self._init_ui()
        self._refresh_list()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("分类（库根目录下的文件夹）："))

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # 新增
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel("新增:"))
        self.add_edit = QLineEdit()
        self.add_edit.setPlaceholderText("输入新分类名...")
        self.add_edit.returnPressed.connect(self._add)
        add_layout.addWidget(self.add_edit)
        btn_add = QPushButton("添加")
        btn_add.clicked.connect(self._add)
        add_layout.addWidget(btn_add)
        layout.addLayout(add_layout)

        # 关闭
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _refresh_list(self):
        from core.api import _get_library
        from core.library import LibraryContext
        lib = _get_library(self._alias)
        ctx = LibraryContext(lib["path"])
        categories = ctx.list_categories()

        self.list_widget.clear()
        for cat in categories:
            item = QListWidgetItem(cat)
            self.list_widget.addItem(item)

    def _add(self):
        from core.api import add_category, LibraryError
        name = self.add_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入分类名")
            return
        try:
            add_category(self._alias, name)
            self.add_edit.clear()
            self._refresh_list()
            self.categories_changed.emit()
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
            self, "重命名分类", f"将 '{old_name}' 重命名为:",
            text=old_name
        )
        if not ok or not new_name.strip() or new_name.strip() == old_name:
            return
        try:
            from core.api import rename_category, LibraryError
            result = rename_category(self._alias, old_name, new_name.strip())
            self._refresh_list()
            self.categories_changed.emit()
            QMessageBox.information(
                self, "完成",
                f"分类已重命名，影响 {len(result['affected_modules'])} 个模块"
            )
        except LibraryError as e:
            QMessageBox.warning(self, "改名失败", str(e))

    def _delete(self, name: str):
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除分类 '{name}' 吗？\n\n"
            f"只能删除空的分类文件夹。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            from core.api import delete_category, LibraryError
            delete_category(self._alias, name)
            self._refresh_list()
            self.categories_changed.emit()
        except LibraryError as e:
            QMessageBox.warning(self, "删除失败", str(e))
