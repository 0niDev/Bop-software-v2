"""Main application window with sidebar navigation."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from src.config.app_config import get_config
from src.views.dashboard_view import DashboardView
from src.views.sales_view import SalesView
from src.views.purchases_view import PurchasesView
from src.views.manufacturing_view import ManufacturingView
from src.views.inventory_view import InventoryView
from src.views.accounting_view import AccountingView
from src.views.banking_view import BankingView
from src.views.reports_view import ReportsView
from src.views.settings_view import SettingsView
from src.views.party_management_view import PartyManagementView
from src.views.item_management_view import ItemManagementView


class MainWindow(QMainWindow):
    """Main application window with role-based navigation."""
    
    # All available navigation items matching old application structure
    ALL_NAV_ITEMS = [
        ("Dashboard", "dashboard", DashboardView),
        ("Sales", "sales", SalesView),
        ("Purchases", "purchases", PurchasesView),
        ("Manufacturing", "manufacturing", ManufacturingView),
        ("Inventory", "inventory", InventoryView),
        ("Accounting", "accounting", AccountingView),
        ("Banking", "banking", BankingView),
        ("Reports", "reports", ReportsView),
        ("Party Management", "party_management", PartyManagementView),
        ("Item Management", "item_management", ItemManagementView),
        ("Settings", "settings", SettingsView),
    ]

    def __init__(self, user_data: dict = None, parent=None):
        super().__init__(parent)
        self.user_data = user_data or {"username": "admin", "full_name": "Admin User", "role": "Admin"}
        self._pages: dict[str, QWidget] = {}
        self._nav_items = self.ALL_NAV_ITEMS  # Could be filtered by role in future
        
        # Build UI
        self._build_ui()
        
    def _build_ui(self) -> None:
        """Build the main window UI matching old application layout."""
        cfg = get_config()
        self.setWindowTitle(f"{cfg.app_name} — {self.user_data['full_name']} ({self.user_data['role']})")
        self.resize(1400, 900)

        central = QWidget()
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # -- Sidebar --------------------------------------------------
        sidebar = QWidget()
        sidebar.setFixedWidth(240)
        sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Brand header
        brand = QLabel("BOP Pharmaceutical ERP")
        brand.setWordWrap(True)
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
            padding: 16px 8px;
            color: #ffffff;
            background: rgba(255, 255, 255, 0.05);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        """)
        brand.setFixedHeight(60)
        sidebar_layout.addWidget(brand)

        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setFrameShape(QListWidget.NoFrame)
        self.nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.nav_list.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.nav_list.setStyleSheet("""
            QListWidget::item {
                padding: 10px 16px;
                margin: 2px 8px;
                border-radius: 8px;
                min-height: 36px;
            }
            QListWidget::item:hover {
                background: rgba(255, 255, 255, 0.08);
                color: #ffffff;
            }
            QListWidget::item:selected {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #e94560,
                    stop:1 #ff6b6b);
                color: #ffffff;
            }
        """)

        # Add navigation items
        for label, key, _ in self._nav_items:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, key)
            self.nav_list.addItem(item)
        
        self.nav_list.currentItemChanged.connect(self._on_nav_changed)

        sidebar_layout.addWidget(self.nav_list, 1)

        # User info at bottom of sidebar
        user_info = QLabel(f"👤 {self.user_data['full_name']}\n{self.user_data['role']}")
        user_info.setWordWrap(True)
        user_info.setAlignment(Qt.AlignCenter)
        user_info.setStyleSheet("""
            color: #a8b2d1;
            padding: 8px 16px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            font-size: 11px;
        """)
        sidebar_layout.addWidget(user_info)

        # Logout button
        logout_btn = QPushButton("Logout")
        logout_btn.setFixedHeight(40)
        logout_btn.clicked.connect(self._on_logout)
        sidebar_layout.addWidget(logout_btn)

        # -- Content stack ---------------------------------------------
        self.stack = QStackedWidget()

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)
        
        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Logged in as {self.user_data['username']} ({self.user_data['role']})")

        # Select first item (Dashboard)
        if self.nav_list.count() > 0:
            self.nav_list.setCurrentRow(0)

    def _on_nav_changed(self, current: QListWidgetItem, previous) -> None:
        """Handle navigation item change."""
        if current is None:
            return
        key = current.data(Qt.UserRole)
        page = self._get_or_create_page(key)
        self.stack.setCurrentWidget(page)
        self.statusBar().showMessage(f"Viewing: {current.text()}")

    def _get_or_create_page(self, key: str) -> QWidget:
        """Get existing page or create new one."""
        if key in self._pages:
            return self._pages[key]

        # Find the view class for this key
        view_class = None
        for label, k, vc in self._nav_items:
            if k == key:
                view_class = vc
                break

        if view_class:
            page = view_class()
        else:
            # Fallback placeholder
            page = QWidget()
            layout = QVBoxLayout(page)
            layout.setAlignment(Qt.AlignCenter)
            label = QLabel(f"'{key.replace('_', ' ').title()}' module")
            label.setStyleSheet("color: #888; font-size: 13px;")
            layout.addWidget(label)

        self._pages[key] = page
        self.stack.addWidget(page)
        return page

    def _on_logout(self) -> None:
        """Handle logout button click."""
        confirm = QMessageBox.question(self, "Logout", "Are you sure you want to logout?")
        if confirm == QMessageBox.Yes:
            self.close()
