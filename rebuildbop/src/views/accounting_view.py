"""Accounting module view - Chart of accounts and journal entries."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.views.base_widgets import PlaceholderView


class AccountingView(QWidget):
    """Accounting module view with boilerplate content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        """Build the accounting UI with boilerplate content."""
        layout = QVBoxLayout(self)
        
        placeholder = PlaceholderView("Accounting Module")
        layout.addWidget(placeholder)
        layout.addStretch()
