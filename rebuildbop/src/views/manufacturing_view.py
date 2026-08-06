"""Manufacturing module view - Production and BOM management."""
from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from src.views.base_widgets import PlaceholderView


class ManufacturingView(QWidget):
    """Manufacturing module view with boilerplate content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        """Build the manufacturing UI with boilerplate content."""
        layout = QVBoxLayout(self)
        
        placeholder = PlaceholderView("Manufacturing Module")
        layout.addWidget(placeholder)
        layout.addStretch()
