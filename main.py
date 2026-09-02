"""
Entry point for Monkey Tracker Pro.
"""
import sys
import os

# Ensure the project root is on sys.path so `app.*` imports work
sys.path.insert(0, os.path.dirname(__file__))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from app.main_window import MainWindow


def main() -> None:
    # HiDPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Monkey Tracker Pro")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("MonkeyTracker")

    # Use system font with a size that works well on Windows
    font = app.font()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
