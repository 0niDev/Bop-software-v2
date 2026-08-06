"""Purchases module view - Purchase invoice management."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.views.base_widgets import PlaceholderView


class PurchasesView(QWidget):
    """Purchases module view with boilerplate content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        """Build the purchases UI with boilerplate content."""
        layout = QVBoxLayout(self)
        
        placeholder = PlaceholderView("Purchases Module")
        layout.addWidget(placeholder)
        layout.addStretch()
