"""CodeLibManager GUI 入口。

用法:
  python main.py                  # 启动 GUI
  python -m CodeLibManager.cli.main  # CLI 模式
"""

import sys
import os
import pathlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor
from ui.main_window import MainWindow


class ComboPopupBelowStyle(QProxyStyle):
    """强制所有 QComboBox 下拉菜单始终向下展开，不对齐到选中项位置。"""
    def __init__(self, key="Fusion"):
        super().__init__(key)

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, option, widget, returnData)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CodeLibManager")
    app.setOrganizationName("CodeLibManager")

    # 全局样式：Fusion + 下拉始终向下
    app.setStyle(ComboPopupBelowStyle("Fusion"))

    # 加载 QSS 样式表
    _qss_path = pathlib.Path(__file__).parent / "resources" / "style.qss"
    if _qss_path.exists():
        app.setStyleSheet(_qss_path.read_text(encoding="utf-8"))

    # 全局调色板
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F0F2F5"))
    palette.setColor(QPalette.WindowText, QColor("#1F1F1F"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F7F8FA"))
    palette.setColor(QPalette.Text, QColor("#1F1F1F"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#1F1F1F"))
    palette.setColor(QPalette.Highlight, QColor("#1A73E8"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor("#9AA0A6"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#9AA0A6"))
    app.setPalette(palette)

    window = MainWindow()
    window.showMaximized()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
