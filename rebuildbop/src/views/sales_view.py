"""Sales module view - Sales invoice management."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.views.base_widgets import PlaceholderView


class SalesView(QWidget):
    """Sales module view with boilerplate content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        """Build the sales UI with boilerplate content."""
        layout = QVBoxLayout(self)
        
        placeholder = PlaceholderView("Sales Module")
        layout.addWidget(placeholder)
        layout.addStretch()
