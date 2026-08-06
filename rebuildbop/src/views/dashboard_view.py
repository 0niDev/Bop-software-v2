"""Dashboard view - Main home screen with KPIs."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.views.base_widgets import KPICard, PlaceholderView


class DashboardView(QWidget):
    """Main dashboard view with boilerplate content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        """Build the dashboard UI with boilerplate content."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(100)
        header_layout.addWidget(refresh_btn)
        
        main_layout.addWidget(header_widget)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(10, 10, 10, 10)

        # KPI Cards Grid
        kpi_grid = QGridLayout()
        kpi_grid.setSpacing(15)
        
        # Boilerplate KPI cards
        self.receivables_card = KPICard("Accounts Receivable", "PKR 0.00")
        self.payables_card = KPICard("Accounts Payable", "PKR 0.00")
        self.sales_card = KPICard("Sales This Month", "PKR 0.00")
        self.purchases_card = KPICard("Purchases This Month", "PKR 0.00")
        
        kpi_grid.addWidget(self.receivables_card, 0, 0)
        kpi_grid.addWidget(self.payables_card, 0, 1)
        kpi_grid.addWidget(self.sales_card, 1, 0)
        kpi_grid.addWidget(self.purchases_card, 1, 1)
        
        content_layout.addLayout(kpi_grid)

        # Placeholder message
        placeholder = PlaceholderView("Dashboard Module")
        content_layout.addWidget(placeholder)

        content_layout.addStretch()
        
        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)
