"""模块列表表格组件。"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QComboBox, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLabel,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor


class ModuleListWidget(QWidget):
    module_selected = Signal(str)  # 模块名
    chain_copy_requested = Signal(str)
    copy_requested = Signal(str)
    edit_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modules = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 工具栏
        toolbar = QHBoxLayout()

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索模块...")
        self.search_box.setMaximumWidth(180)
        self.search_box.textChanged.connect(self._apply_filter)

        self.category_filter = QComboBox()
        self.category_filter.setMinimumWidth(160)
        self.category_filter.setSizeAdjustPolicy(self.category_filter.SizeAdjustPolicy.AdjustToContents)
        self.category_filter.addItem("全部分类", "")
        self.category_filter.currentIndexChanged.connect(self._apply_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItem("全部状态", "all")
        self.status_filter.addItem("已验证", "verified")
        self.status_filter.addItem("未验证", "unverified")
        self.status_filter.currentIndexChanged.connect(self._apply_filter)

        toolbar.addWidget(QLabel("搜索:"))
        toolbar.addWidget(self.search_box)
        toolbar.addWidget(QLabel("分类:"))
        toolbar.addWidget(self.category_filter)
        toolbar.addWidget(QLabel("状态:"))
        toolbar.addWidget(self.status_filter)
        toolbar.addStretch()

        layout.addLayout(toolbar)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["状态", "名称", "分类", "版本", "依赖数"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

        # 状态栏
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def load_modules(self, modules: list[dict]):
        self._modules = modules
        # 更新分类过滤器
        cats = sorted(set(m.get("category", "") for m in modules))
        current = self.category_filter.currentData()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("全部分类", "")
        # 当前分类在新库中存在则排首位，其余按名称排序
        in_new_set = current and current in cats
        ordered = []
        for c in cats:
            if c and c != current:
                ordered.append(c)
        if in_new_set:
            ordered.insert(0, current)
        for c in ordered:
            self.category_filter.addItem(c, c)
        self.category_filter.setCurrentIndex(1 if in_new_set else 0)
        self.category_filter.blockSignals(False)
        self._apply_filter()

    def _apply_filter(self):
        # 记住当前选中的模块名
        current_name = None
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item:
                current_name = item.data(Qt.UserRole)

        search = self.search_box.text().lower()
        cat = self.category_filter.currentData()
        status = self.status_filter.currentData()

        filtered = []
        for m in self._modules:
            if cat and m.get("category", "") != cat:
                continue
            if status == "verified" and not m.get("verified"):
                continue
            if status == "unverified" and m.get("verified"):
                continue
            if search:
                if search not in m.get("name", "").lower() and search not in m.get("description", "").lower():
                    continue
            filtered.append(m)

        self.table.blockSignals(True)
        self.table.setRowCount(len(filtered))
        for row, m in enumerate(filtered):
            broken = m.get("broken", False)
            v = m.get("verified", False)
            if broken:
                item = QTableWidgetItem("⚠")
                item.setForeground(QColor("#E37400"))
            elif v:
                item = QTableWidgetItem("✓")
                item.setForeground(QColor("#188038"))
            else:
                item = QTableWidgetItem("✗")
                item.setForeground(QColor("#C5221F"))
            item.setData(Qt.UserRole, m["name"])
            self.table.setItem(row, 0, item)
            self.table.setItem(row, 1, QTableWidgetItem(m["name"]))
            self.table.setItem(row, 2, QTableWidgetItem(m.get("category", "")))
            self.table.setItem(row, 3, QTableWidgetItem(m.get("version", "1.0")))
            self.table.setItem(row, 4, QTableWidgetItem(str(m.get("dep_count", 0))))

        self.table.blockSignals(False)
        self.table.clearSelection()
        if self.table.rowCount() > 0:
            target_row = 0
            if current_name:
                for row in range(self.table.rowCount()):
                    item = self.table.item(row, 0)
                    if item and item.data(Qt.UserRole) == current_name:
                        target_row = row
                        break
            self.table.selectRow(target_row)

        total = len(self._modules)
        if len(filtered) != total:
            self.status_label.setText(f"筛选结果: {len(filtered)} / {total} 个模块")
        else:
            self.status_label.setText("")

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item is not None:
                self.module_selected.emit(item.data(Qt.UserRole))

    def _show_context_menu(self, pos):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            if item is None:
                return
            name = item.data(Qt.UserRole)
            menu.addAction("复制到工程", lambda: self.copy_requested.emit(name))
            menu.addAction("链复制到工程", lambda: self.chain_copy_requested.emit(name))
            menu.addSeparator()
            menu.addAction("编辑模块", lambda: self.edit_requested.emit(name))
            menu.exec(self.table.viewport().mapToGlobal(pos))
