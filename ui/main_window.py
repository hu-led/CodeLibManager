"""主窗口。"""

import sys
import os

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QComboBox, QToolBar, QStatusBar,
    QMessageBox, QFileDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QApplication,
)
from PySide6.QtCore import Qt, QTimer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.api import (
    list_modules, get_module_info, get_dependency_tree,
    copy_module_to_project, chain_copy_to_project,
    import_module, edit_module, verify_module, remove_module,
    add_library, remove_library, list_libraries,
    validate_library, cleanup_broken_modules,
    load_config, save_config,
    topological_sort, LibraryContext,
    LibraryError, PlatformError,
    CircularDependencyError, MissingDependencyError,
)

from .module_list import ModuleListWidget
from .module_detail import ModuleDetailWidget
from .dialogs.import_module import ImportModuleDialog
from .dialogs.chain_copy import ChainCopyDialog
from .dialogs.edit_module import EditModuleDialog
from .dialogs.manage_library import ManageLibraryDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._config = load_config()
        self._refresh_guard = False
        self.setWindowTitle("CodeLib Manager — 复用代码库管理器")
        self._init_ui()
        self._refresh_libraries()
        QTimer.singleShot(100, self._refresh_all)

    def _init_ui(self):
        # 工具栏
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel(" 库: "))
        self.library_combo = QComboBox()
        self.library_combo.setMinimumWidth(180)
        self.library_combo.currentIndexChanged.connect(self._on_library_changed)
        toolbar.addWidget(self.library_combo)
        toolbar.addSeparator()

        btn_import = QPushButton("导入模块")
        btn_import.clicked.connect(self._on_import_module)
        toolbar.addWidget(btn_import)

        btn_add_lib = QPushButton("添加库")
        btn_add_lib.clicked.connect(self._on_add_library)
        toolbar.addWidget(btn_add_lib)

        btn_manage_lib = QPushButton("管理库")
        btn_manage_lib.clicked.connect(self._on_manage_library)
        toolbar.addWidget(btn_manage_lib)

        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self._refresh_all)
        toolbar.addWidget(btn_refresh)

        # 中央分割器
        splitter = QSplitter(Qt.Horizontal)
        self.module_list = ModuleListWidget()
        self.module_detail = ModuleDetailWidget()
        splitter.addWidget(self.module_list)
        splitter.addWidget(self.module_detail)
        self.module_list.setMinimumWidth(250)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        self.setCentralWidget(splitter)

        # 信号
        self.module_list.module_selected.connect(self._on_module_selected)
        self.module_list.copy_requested.connect(self._on_copy_module)
        self.module_list.chain_copy_requested.connect(self._on_chain_copy)
        self.module_list.edit_requested.connect(self._on_edit_module)
        self.module_detail.copy_requested.connect(self._on_copy_module)
        self.module_detail.chain_copy_requested.connect(self._on_chain_copy)
        self.module_detail.edit_requested.connect(self._on_edit_module)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    # ── 数据刷新 ────────────────────────────────────────

    def _refresh_libraries(self):
        self._config = load_config()
        libs = self._config.get("libraries", [])
        active = self._config.get("active_library", "")
        self.library_combo.blockSignals(True)
        self.library_combo.clear()
        # 活跃库排首位，其余按名称排序
        sorted_libs = sorted(libs, key=lambda l: l["alias"].lower())
        active_entry = None
        others = []
        for l in sorted_libs:
            if l["alias"] == active:
                active_entry = l
            else:
                others.append(l)
        items = [active_entry] + others if active_entry else others
        for l in items:
            self.library_combo.addItem(l["alias"], l["path"])
        if active_entry:
            self.library_combo.setCurrentIndex(0)
        self.library_combo.blockSignals(False)

    def _refresh_all(self):
        if self._refresh_guard:
            return
        self._refresh_guard = True
        try:
            self._refresh_libraries()
            alias = self.library_combo.currentText()
            if not alias:
                self.status_bar.showMessage("请先添加一个库")
                self.module_detail.clear()
                return
            try:
                mods = list_modules(alias)
                self.module_detail.clear()
                self.module_list.load_modules(mods)
                # 完整性检测
                issues = validate_library(alias)
                broken_count = sum(1 for m in mods if m.get("broken"))
                if issues:
                    cleanable = [i for i in issues if i["type"] in ("missing_dir", "missing_metadata")]
                    file_only = [i for i in issues if i["type"] == "missing_file"]
                    self._show_integrity_warning(alias, issues, cleanable, file_only)
                # 状态栏
                verified = sum(1 for m in mods if m.get("verified") and not m.get("broken"))
                parts = [
                    f"库: {alias}",
                    f"模块: {len(mods)}",
                    f"已验证: {verified}",
                    f"未验证: {len(mods) - verified - broken_count}",
                ]
                if broken_count:
                    parts.append(f"⚠ 损坏: {broken_count}")
                self.status_bar.showMessage("  |  ".join(parts))
            except LibraryError as e:
                self.status_bar.showMessage(f"库加载失败: {e}")
        finally:
            self._refresh_guard = False

    def _show_integrity_warning(self, alias, issues, cleanable, file_only):
        lines = [f"检测到 {len(issues)} 个完整性问题："]
        for iss in issues[:8]:
            lines.append(f"  • {iss['message']}")
        if len(issues) > 8:
            lines.append(f"  ... 还有 {len(issues) - 8} 个问题")

        if cleanable:
            lines.append("")
            lines.append(f"其中 {len(cleanable)} 个模块的文件夹或元数据已丢失，可以自动清理索引条目。")
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("库完整性问题")
            msg_box.setText("\n".join(lines))
            msg_box.setIcon(QMessageBox.Warning)
            btn_clean = msg_box.addButton("清理无效条目", QMessageBox.ActionRole)
            msg_box.addButton("稍后处理", QMessageBox.RejectRole)
            msg_box.exec()
            if msg_box.clickedButton() == btn_clean:
                result = cleanup_broken_modules(alias)
                self.status_bar.showMessage(
                    f"已清理 {result['count']} 个无效模块条目"
                )
                QTimer.singleShot(0, self._refresh_all)
        else:
            lines.append("")
            lines.append(f"{len(file_only)} 个文件缺失，请在编辑模块中手动补充。")
            QMessageBox.warning(self, "库完整性问题", "\n".join(lines))

    def _on_library_changed(self):
        alias = self.library_combo.currentText()
        if alias:
            self._config["active_library"] = alias
            save_config(self._config)
            self._refresh_all()

    def _on_module_selected(self, name: str):
        alias = self.library_combo.currentText()
        try:
            info = get_module_info(alias, name)
            tree = get_dependency_tree(alias, name)
            self.module_detail.show_module(info)
            self.module_detail.show_dependency_tree(tree)
            self.module_detail.show_reverse_deps(info.get("reverse_dependencies", []))
        except LibraryError as e:
            QMessageBox.warning(self, "错误", str(e))

    # ── 操作 ────────────────────────────────────────────

    def _on_import_module(self):
        alias = self.library_combo.currentText()
        if not alias:
            QMessageBox.warning(self, "提示", "请先选择一个库")
            return

        lib_path = self._current_lib_path()
        if not lib_path:
            return

        ctx = LibraryContext(lib_path)
        categories = ctx.list_categories()
        existing = [m["name"] for m in ctx.load_index()]

        dlg = ImportModuleDialog(lib_path, categories, existing, self)
        if dlg.exec():
            data = dlg.get_result()
            try:
                import_module(
                    alias,
                    file_paths=data["file_paths"],
                    name=data["name"],
                    category=data["category"],
                    version=data["version"],
                    description=data["description"],
                    dependencies=data["dependencies"],
                    group=data["group"],
                )
                self.status_bar.showMessage(f"模块 '{data['name']}' 导入成功")
                self._refresh_all()
            except LibraryError as e:
                QMessageBox.warning(self, "导入失败", str(e))

    def _on_copy_module(self, name: str):
        alias = self.library_combo.currentText()
        if not alias:
            QMessageBox.warning(self, "提示", "请先选择一个库")
            return
        project = QFileDialog.getExistingDirectory(self, "选择工程目录")
        if not project:
            return
        try:
            # 检查工程是否被支持的平台识别
            from core.platform import get_adapter, PlatformError as PE
            adapter = get_adapter(project)
            adapter.find_project_file(project)
        except PE as e:
            QMessageBox.warning(self, "错误", str(e))
            return

        try:
            result = copy_module_to_project(alias, name, project)
            self.status_bar.showMessage(
                f"已复制 '{name}' 到 {project}，注册 {len(result.get('registered', []))} 个文件"
            )
            QMessageBox.information(self, "完成",
                                    f"模块 '{name}' 已复制到工程\n"
                                    f"分组: {result.get('group', '—')}\n"
                                    f"文件: {len(result.get('copied', []))} 个")
        except (LibraryError, PlatformError) as e:
            QMessageBox.warning(self, "错误", str(e))

    def _on_chain_copy(self, name: str):
        alias = self.library_combo.currentText()
        lib_path = self._current_lib_path()
        if not lib_path:
            return

        try:
            ctx = LibraryContext(lib_path)
            chain = topological_sort(ctx, name)
        except CircularDependencyError as e:
            QMessageBox.warning(self, "循环依赖", f"无法执行链复制:\n{e}")
            return
        except MissingDependencyError as e:
            QMessageBox.warning(self, "缺失依赖", f"无法执行链复制:\n{e}")
            return

        dlg = ChainCopyDialog(chain, [], alias, self)
        if dlg.exec():
            project = dlg.get_project_path()
            selected = dlg.get_selected_modules()
            resolutions = dlg.get_conflict_resolutions()

            try:
                result = chain_copy_to_project(
                    alias, name, project,
                    selected_modules=selected,
                    conflict_resolutions=resolutions,
                )
                count = len(result.get("chain", []))
                self.status_bar.showMessage(
                    f"链复制完成: {count} 个模块 → {project}"
                )
                QMessageBox.information(self, "完成",
                                        f"模块链复制完成\n"
                                        f"共复制 {count} 个模块到 {project}")
            except (LibraryError, PlatformError) as e:
                QMessageBox.warning(self, "错误", str(e))

    def _on_edit_module(self, name: str):
        alias = self.library_combo.currentText()
        lib_path = self._current_lib_path()
        if not lib_path:
            return

        try:
            info = get_module_info(alias, name)
        except LibraryError as e:
            QMessageBox.warning(self, "错误", str(e))
            return

        ctx = LibraryContext(lib_path)
        categories = ctx.list_categories()
        existing = [m["name"] for m in ctx.load_index()]

        dlg = EditModuleDialog(info, categories, existing, alias, self)
        if dlg.exec():
            data = dlg.get_result()
            if data is None:
                return
            try:
                result = edit_module(
                    alias, name,
                    new_name=data["new_name"],
                    new_category=data["new_category"],
                    new_version=data["new_version"],
                    new_description=data["new_description"],
                    new_group=data["new_group"],
                    new_pins=data["new_pins"],
                    new_verified=data["new_verified"],
                    new_dependencies=data["new_dependencies"],
                    add_files=data["add_files"],
                    remove_files=data["remove_files"],
                )
                msg = f"模块 '{result['name']}' 已保存"
                if result.get("old_name"):
                    msg += f"（已重命名: {result['old_name']} → {result['name']}）"
                if result.get("snapshot"):
                    msg += f"  |  快照: {result['snapshot']}"
                self.status_bar.showMessage(msg)
                self._refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "编辑失败", str(e))
        elif dlg.is_delete_requested():
            try:
                result = remove_module(alias, name, cleanup_deps=True)
                cleaned = result.get("reverse_deps_cleaned", [])
                msg = f"模块 '{name}' 已移除 → {result['moved_to']}"
                if cleaned:
                    msg += f"\n已清理 {len(cleaned)} 个模块的依赖引用: {', '.join(cleaned)}"
                self.status_bar.showMessage(msg)
                self._refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "移除失败", str(e))

    def _on_add_library(self):
        path = QFileDialog.getExistingDirectory(self, "选择新代码库根目录")
        if not path:
            return

        # 询问别名
        from PySide6.QtWidgets import QInputDialog
        alias, ok = QInputDialog.getText(
            self, "库别名", "为这个库输入一个别名:",
            text=os.path.basename(path)
        )
        if ok and alias:
            try:
                add_library(alias, path)
                self._refresh_all()
                self.status_bar.showMessage(f"库 '{alias}' 已添加")
            except LibraryError as e:
                QMessageBox.warning(self, "添加失败", str(e))

    def _on_manage_library(self):
        alias = self.library_combo.currentText()
        if not alias:
            QMessageBox.warning(self, "提示", "请先选择一个库")
            return
        lib_path = self._current_lib_path()
        if not lib_path:
            return
        dlg = ManageLibraryDialog(alias, lib_path, self)
        dlg.exec()
        result = dlg.get_result()
        if result["action"] in ("renamed", "removed"):
            self._refresh_libraries()
            self._refresh_all()
        elif result["action"] == "path_updated":
            self._refresh_all()

    def _current_lib_path(self) -> str:
        idx = self.library_combo.currentIndex()
        if idx < 0:
            return ""
        return self.library_combo.itemData(idx)

    def closeEvent(self, event):
        try:
            self._config["window"] = {
                "width": self.width(),
                "height": self.height(),
            }
            save_config(self._config)
        except Exception:
            pass
        super().closeEvent(event)
