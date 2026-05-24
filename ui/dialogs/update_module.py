"""更新模块对话框。"""

import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QDialogButtonBox, QMessageBox,
    QTextEdit,
)
from PySide6.QtCore import Qt


class UpdateModuleDialog(QDialog):
    def __init__(self, module_name: str, module_info: dict, parent=None):
        super().__init__(parent)
        self._module_name = module_name
        self._module_info = module_info
        self.setWindowTitle(f"更新模块 — {module_name}")
        self.setMinimumWidth(450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 当前信息
        layout.addWidget(QLabel(f"<b>当前模块:</b> {self._module_name}"))
        layout.addWidget(QLabel(f"版本: {self._module_info.get('version', '—')}"))
        old_files = (self._module_info.get("files", {}).get("source", []) +
                     self._module_info.get("files", {}).get("header", []))
        layout.addWidget(QLabel(f"现有文件: {', '.join(old_files) if old_files else '—'}"))

        layout.addWidget(QLabel("<hr>"))

        # 新源目录
        layout.addWidget(QLabel("<b>选择新版本源目录:</b>"))
        src_layout = QHBoxLayout()
        self.src_edit = QLineEdit()
        self.src_edit.setPlaceholderText("包含更新后 .c/.h 文件的目录...")
        btn_browse = QPushButton("浏览...")
        btn_browse.clicked.connect(self._browse)
        src_layout.addWidget(self.src_edit)
        src_layout.addWidget(btn_browse)
        layout.addLayout(src_layout)

        self.lbl_preview = QLabel("(未选择目录)")
        self.lbl_preview.setStyleSheet("color: #9AA0A6;")
        layout.addWidget(self.lbl_preview)

        # 备注
        layout.addWidget(QLabel("更新说明（可选）:"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(60)
        layout.addWidget(self.notes_edit)

        # 按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.button(QDialogButtonBox.Ok).setText("确认更新")
        btn_box.accepted.connect(self._validate)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "选择新版本源目录")
        if path:
            self.src_edit.setText(path)
            try:
                cfiles = [f for f in os.listdir(path) if f.endswith('.c')]
                hfiles = [f for f in os.listdir(path) if f.endswith('.h')]
                preview = []
                if cfiles:
                    preview.append(f".c: {', '.join(cfiles)}")
                if hfiles:
                    preview.append(f".h: {', '.join(hfiles)}")
                self.lbl_preview.setText(" | ".join(preview) if preview else "(目录为空)")
            except OSError as e:
                self.lbl_preview.setText(f"(无法读取目录: {e})")
                self.lbl_preview.setStyleSheet("color: #C5221F;")

    def _validate(self):
        src = self.src_edit.text().strip()
        if not src or not os.path.isdir(src):
            QMessageBox.warning(self, "验证失败", "请选择有效的源目录")
            return
        self._source_dir = src
        self._notes = self.notes_edit.toPlainText().strip()
        self.accept()

    def get_source_dir(self) -> str:
        return self._source_dir

    def get_notes(self) -> str:
        return self._notes
