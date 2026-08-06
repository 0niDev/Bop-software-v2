"""Login window for BOP Pharmaceutical ERP System."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.config.app_config import get_config


class LoginThread(QThread):
    """Background thread for login to prevent UI freezing."""
    
    login_result = Signal(object, str)  # user_data, error_message
    
    def __init__(self, username: str, password: str):
        super().__init__()
        self.username = username
        self.password = password
    
    def run(self):
        """Execute login logic in background thread."""
        try:
            # TODO: Implement actual authentication when database is configured
            # For now, simulate successful login for demo purposes
            if self.username and self.password:
                user_data = {
                    "username": self.username,
                    "full_name": self.username.title(),
                    "role": "Admin"
                }
                self.login_result.emit(user_data, "")
            else:
                self.login_result.emit(None, "Invalid credentials")
        except Exception as e:
            self.login_result.emit(None, str(e))


class LoginView(QWidget):
    """Login window shown at application startup."""

    login_successful = Signal(object)  # Emits user data on successful login

    def __init__(self, parent=None):
        super().__init__(parent)
        self._login_thread = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the login UI."""
        self.setWindowTitle(get_config().app_name)
        self.setMinimumSize(420, 460)

        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)

        # Card container
        card = QFrame()
        card.setObjectName("loginCard")
        card.setFixedWidth(340)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setContentsMargins(32, 32, 32, 32)

        # Title
        title = QLabel(get_config().app_name)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont("Segoe UI", 14, QFont.Bold)
        title.setFont(title_font)
        card_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Sign in to continue")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #666;")
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(10)

        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        card_layout.addWidget(self.username_input)

        # Password input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.returnPressed.connect(self._on_login_clicked)
        card_layout.addWidget(self.password_input)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #c0392b;")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        card_layout.addWidget(self.error_label)

        # Login button
        self.login_button = QPushButton("Login")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._on_login_clicked)
        card_layout.addWidget(self.login_button)

        outer.addWidget(card, alignment=Qt.AlignCenter)

    def _on_login_clicked(self) -> None:
        """Handle login button click."""
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self._show_error("Please enter both username and password.")
            return

        # Disable UI during login
        self.login_button.setEnabled(False)
        self.login_button.setText("Logging in...")
        self.error_label.hide()
        
        # Start login in background thread
        if self._login_thread and self._login_thread.isRunning():
            self._login_thread.terminate()
        
        self._login_thread = LoginThread(username, password)
        self._login_thread.login_result.connect(self._on_login_result)
        self._login_thread.start()
    
    def _on_login_result(self, user_data, error):
        """Handle login result from background thread."""
        self.login_button.setEnabled(True)
        self.login_button.setText("Login")
        
        if error:
            self._show_error(error)
            self.password_input.clear()
            self.password_input.setFocus()
            return
        
        self.error_label.hide()
        self.login_successful.emit(user_data)

    def _show_error(self, message: str) -> None:
        """Display error message."""
        self.error_label.setText(message)
        self.error_label.show()
