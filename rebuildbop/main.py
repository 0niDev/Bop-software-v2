"""Application entry point for BOP Pharmaceutical ERP System."""
from __future__ import annotations

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from src.config.app_config import get_config
from src.views.login_window import LoginView
from src.views.main_window import MainWindow


# Application stylesheet matching old application design
APP_STYLESHEET = """
/* ============================================================
   GLOBAL STYLES
   ============================================================ */
QWidget {
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
    font-size: 14px;
    color: #1a1a2e;
}

QMainWindow {
    background: #f0f2f5;
}

/* ============================================================
   SIDEBAR
   ============================================================ */
#sidebar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1a2e,
        stop:1 #16213e);
    border-right: 1px solid #0f3460;
}

#sidebar QLabel {
    color: #ffffff;
}

#sidebar QListWidget {
    background: transparent;
    color: #a8b2d1;
    border: none;
    outline: none;
    font-size: 13px;
}

#sidebar QListWidget::item {
    padding: 10px 16px;
    border-radius: 8px;
    margin: 2px 8px;
}

#sidebar QListWidget::item:hover {
    background: rgba(255, 255, 255, 0.08);
    color: #ffffff;
}

#sidebar QListWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e94560,
        stop:1 #ff6b6b);
    color: #ffffff;
}

#sidebar QPushButton {
    background: rgba(255, 255, 255, 0.08);
    color: #a8b2d1;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 10px 16px;
    margin: 4px 12px 12px 12px;
    font-weight: 500;
}

#sidebar QPushButton:hover {
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
}

/* ============================================================
   LOGIN CARD
   ============================================================ */
#loginCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #ffffff,
        stop:1 #f8f9fa);
    border: none;
    border-radius: 16px;
}

#loginCard QLabel {
    color: #1a1a2e;
}

#loginCard QLineEdit {
    background: #f8f9fa;
    border: 2px solid #e9ecef;
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 13px;
}

#loginCard QLineEdit:focus {
    border-color: #e94560;
    background: #ffffff;
}

#loginCard QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #e94560,
        stop:1 #ff6b6b);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    padding: 12px 24px;
    font-size: 14px;
    font-weight: bold;
}

#loginCard QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #c73652,
        stop:1 #e94560);
}

/* ============================================================
   BUTTONS
   ============================================================ */
QPushButton {
    background: #e94560;
    color: #ffffff;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 500;
}

QPushButton:hover {
    background: #c73652;
}

QPushButton:pressed {
    background: #a82d45;
}

QPushButton:disabled {
    background: #ced4da;
    color: #6c757d;
}

/* ============================================================
   TABLES
   ============================================================ */
QTableWidget {
    background: #ffffff;
    border: 1px solid #e9ecef;
    border-radius: 12px;
    gridline-color: #f1f3f5;
    selection-background-color: #e94560;
    selection-color: #ffffff;
    alternate-background-color: #f8f9fa;
}

QTableWidget::item {
    padding: 8px 12px;
}

QHeaderView::section {
    background: #f8f9fa;
    color: #495057;
    padding: 10px 12px;
    border: none;
    border-bottom: 2px solid #e9ecef;
    font-weight: 600;
    font-size: 12px;
}

/* ============================================================
   INPUTS
   ============================================================ */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {
    background: #ffffff;
    border: 2px solid #e9ecef;
    border-radius: 8px;
    padding: 8px 12px;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #e94560;
}

/* ============================================================
   STATUS BAR
   ============================================================ */
QStatusBar {
    background: #ffffff;
    border-top: 1px solid #e9ecef;
    color: #6c757d;
    padding: 4px 12px;
}
"""


class Application:
    """Main application class."""
    
    def __init__(self) -> None:
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setStyleSheet(APP_STYLESHEET)
        
        # Set application font
        font = QFont("Segoe UI", 14)
        self.qt_app.setFont(font)
        
        self.login_view: LoginView | None = None
        self.main_window: MainWindow | None = None
        
    def run(self) -> int:
        """Run the application."""
        try:
            self._show_login()
            return self.qt_app.exec()
        except Exception as e:
            print(f"Fatal error: {e}")
            return 1

    def _show_login(self) -> None:
        """Show login window."""
        self.login_view = LoginView()
        self.login_view.login_successful.connect(self._on_login_successful)
        self.login_view.show()
    
    def _on_login_successful(self, user_data: dict) -> None:
        """Handle successful login."""
        # Create and show main window
        self.main_window = MainWindow(user_data)
        self.main_window.show()
        
        # Close login window
        if self.login_view:
            self.login_view.close()
            self.login_view = None


def main() -> int:
    """Application entry point."""
    app = Application()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
