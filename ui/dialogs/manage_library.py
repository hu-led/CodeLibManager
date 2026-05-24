"""管理库对话框。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QMessageBox, QInputDialog, QFileDialog, QGroupBox,
)
from PySide6.QtCore import Qt


class ManageLibraryDialog(QDialog):
    """管理当前库：重命名、更新路径、管理分类/分组、移除库。"""

    def __init__(self, alias: str, library_path: str, parent=None):
        super().__init__(parent)
        self._alias = alias
        self._library_path = library_path
        self._result = {"action": None}
        self.setWindowTitle(f"管理库: {alias}")
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # ── 基本信息 ──
        info_group = QGroupBox("库信息")
        info_layout = QVBoxLayout()

        alias_layout = QHBoxLayout()
        alias_layout.addWidget(QLabel(f"别名:  {self._alias}"))
        alias_layout.addStretch()
        btn_rename = QPushButton("重命名库...")
        btn_rename.clicked.connect(self._rename_library)
        alias_layout.addWidget(btn_rename)
        info_layout.addLayout(alias_layout)

        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel(f"路径:  {self._library_path}"))
        path_layout.addStretch()
        btn_path = QPushButton("更新路径...")
        btn_path.clicked.connect(self._update_path)
        path_layout.addWidget(btn_path)
        info_layout.addLayout(path_layout)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # ── 管理按钮 ──
        mgmt_group = QGroupBox("管理")
        mgmt_layout = QVBoxLayout()

        btn_cats = QPushButton("管理分类...")
        btn_cats.clicked.connect(self._manage_categories)
        mgmt_layout.addWidget(btn_cats)

        btn_groups = QPushButton("管理工程分组...")
        btn_groups.clicked.connect(self._manage_groups)
        mgmt_layout.addWidget(btn_groups)

        mgmt_group.setLayout(mgmt_layout)
        layout.addWidget(mgmt_group)

        # ── 危险操作 ──
        danger_group = QGroupBox("危险操作")
        danger_layout = QVBoxLayout()
        btn_remove = QPushButton("移除库")
        btn_remove.setObjectName("btnRemove")
        btn_remove.clicked.connect(self._remove_library)
        danger_layout.addWidget(btn_remove)
        danger_group.setLayout(danger_layout)
        layout.addWidget(danger_group)

        # ── 关闭 ──
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

    def _rename_library(self):
        from core.api import rename_library, LibraryError
        new_alias, ok = QInputDialog.getText(
            self, "重命名库", "新别名:",
            text=self._alias
        )
        if not ok or not new_alias.strip() or new_alias.strip() == self._alias:
            return
        new_alias = new_alias.strip()
        # 检查是否与其他库重名
        from core.api import load_config
        cfg = load_config()
        if any(l["alias"] == new_alias for l in cfg.get("libraries", [])):
            QMessageBox.warning(self, "重命名失败", f"别名 '{new_alias}' 已被其他库使用")
            return
        try:
            result = rename_library(self._alias, new_alias)
            self._alias = result["new_alias"]
            self._result["action"] = "renamed"
            self._result["new_alias"] = result["new_alias"]
            QMessageBox.information(self, "完成", f"库已重命名为 '{result['new_alias']}'")
            self.accept()
        except LibraryError as e:
            QMessageBox.warning(self, "重命名失败", str(e))

    def _update_path(self):
        from core.api import update_library_path, LibraryError
        path = QFileDialog.getExistingDirectory(self, "选择库的新路径", self._library_path)
        if not path:
            return
        try:
            result = update_library_path(self._alias, path)
            self._library_path = result["path"]
            self._result["action"] = "path_updated"
            QMessageBox.information(self, "完成", f"路径已更新为:\n{path}")
        except LibraryError as e:
            QMessageBox.warning(self, "更新失败", str(e))

    def _manage_categories(self):
        from .manage_categories import ManageCategoriesDialog
        dlg = ManageCategoriesDialog(self._alias, self)
        dlg.exec()

    def _manage_groups(self):
        from .manage_groups import ManageGroupsDialog
        dlg = ManageGroupsDialog(self._alias, self)
        dlg.exec()

    def _remove_library(self):
        from core.api import remove_library, LibraryError
        reply = QMessageBox.question(
            self, "确认移除库",
            f"确定要移除库 '{self._alias}' 吗？\n\n"
            f"此操作仅从管理器中注销该库，不会删除硬盘上的任何文件。",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            remove_library(self._alias)
            self._result["action"] = "removed"
            QMessageBox.information(self, "完成", f"库 '{self._alias}' 已从管理器注销")
            self.accept()
        except LibraryError as e:
            QMessageBox.warning(self, "移除失败", str(e))

    def get_result(self) -> dict:
        return self._result
