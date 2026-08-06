"""
Dashboard Service - Provides dashboard KPIs and statistics

This service aggregates data from multiple repositories to provide
dashboard metrics and key performance indicators.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.services.base_service import BaseService
from src.repositories.account_repository import AccountRepository
from src.repositories.party_repository import PartyRepository
from src.repositories.item_repository import ItemRepository
from src.repositories.invoice_repository import InvoiceRepository
from src.repositories.stock_repository import StockRepository
from src.repositories.bank_repository import BankRepository

logger = logging.getLogger(__name__)


class DashboardService(BaseService):
    """
    Service for fetching dashboard data with caching support.
    
    Provides KPIs, statistics, and summary data for the dashboard view.
    Uses caching to improve performance for frequently accessed data.
    """
    
    def __init__(self):
        """Initialize dashboard service with repositories."""
        super().__init__("DashboardService")
        
        # Initialize repositories
        self.account_repo = AccountRepository()
        self.party_repo = PartyRepository()
        self.item_repo = ItemRepository()
        self.invoice_repo = InvoiceRepository()
        self.stock_repo = StockRepository()
        self.bank_repo = BankRepository()
        
        # Cache configuration
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, float] = {}
        self._cache_ttl = 60  # 60 seconds cache TTL
    
    def _get_cached(self, key: str, loader, force: bool = False) -> Any:
        """
        Get cached data or load if expired.
        
        Args:
            key: Cache key
            loader: Function to load data if cache miss
            force: Force refresh regardless of cache
            
        Returns:
            Cached or freshly loaded data
        """
        if not force and key in self._cache:
            if (datetime.now().timestamp() - self._cache_time.get(key, 0)) < self._cache_ttl:
                logger.debug(f"Cache hit for {key}")
                return self._cache[key]
        
        try:
            data = loader()
            self._cache[key] = data
            self._cache_time[key] = datetime.now().timestamp()
            logger.debug(f"Cache miss, loaded {key}")
            return data
        except Exception as e:
            logger.error(f"Error loading {key}: {e}")
            return self._cache.get(key, None)
    
    def invalidate_cache(self) -> None:
        """Clear all cached dashboard data."""
        self._cache.clear()
        self._cache_time.clear()
        logger.info("Dashboard cache cleared")
    
    def get_dashboard_data(self, company_id: int = 1, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data.
        
        Args:
            company_id: Company ID to filter data
            force_refresh: Force refresh from database
            
        Returns:
            Dictionary containing all dashboard KPIs and data
        """
        cache_key = f"dashboard_{company_id}"
        
        return self._get_cached(cache_key, lambda: self._load_dashboard_data(company_id), force_refresh)
    
    def _load_dashboard_data(self, company_id: int) -> Dict[str, Any]:
        """
        Load dashboard data from repositories.
        
        Args:
            company_id: Company ID to filter data
            
        Returns:
            Dictionary with dashboard metrics
        """
        today = datetime.now().date()
        month_start = today.replace(day=1)
        
        try:
            # Sales metrics
            today_sales = self.invoice_repo.get_sales_summary(
                start_date=today.isoformat(),
                end_date=today.isoformat(),
                company_id=company_id
            )
            
            month_sales = self.invoice_repo.get_sales_summary(
                start_date=month_start.isoformat(),
                end_date=today.isoformat(),
                company_id=company_id
            )
            
            # Purchase metrics
            today_purchases = self.invoice_repo.get_purchase_summary(
                start_date=today.isoformat(),
                end_date=today.isoformat(),
                company_id=company_id
            )
            
            # Inventory metrics
            inventory_value = self.stock_repo.get_inventory_value(company_id=company_id)
            low_stock_items = self.stock_repo.get_low_stock_items(limit=10, company_id=company_id)
            
            # Party metrics
            total_parties = self.party_repo.count(company_id=company_id)
            total_customers = self.party_repo.count_by_type('CUSTOMER', company_id=company_id)
            total_suppliers = self.party_repo.count_by_type('SUPPLIER', company_id=company_id)
            
            # Account metrics
            total_accounts = self.account_repo.count(company_id=company_id)
            
            # Bank balance
            bank_balance = self.bank_repo.get_total_balance(company_id=company_id)
            
            return {
                'sales': {
                    'today': today_sales.get('total', 0.0),
                    'today_count': today_sales.get('count', 0),
                    'month': month_sales.get('total', 0.0),
                    'month_count': month_sales.get('count', 0),
                },
                'purchases': {
                    'today': today_purchases.get('total', 0.0),
                    'today_count': today_purchases.get('count', 0),
                },
                'inventory': {
                    'total_value': inventory_value,
                    'low_stock_count': len(low_stock_items),
                    'low_stock_items': low_stock_items,
                },
                'parties': {
                    'total': total_parties,
                    'customers': total_customers,
                    'suppliers': total_suppliers,
                },
                'accounts': {
                    'total': total_accounts,
                },
                'bank': {
                    'total_balance': bank_balance,
                },
                'generated_at': datetime.now().isoformat(),
            }
            
        except Exception as e:
            logger.exception(f"Error loading dashboard data: {e}")
            # Return empty structure on error
            return {
                'sales': {'today': 0.0, 'today_count': 0, 'month': 0.0, 'month_count': 0},
                'purchases': {'today': 0.0, 'today_count': 0},
                'inventory': {'total_value': 0.0, 'low_stock_count': 0, 'low_stock_items': []},
                'parties': {'total': 0, 'customers': 0, 'suppliers': 0},
                'accounts': {'total': 0},
                'bank': {'total_balance': 0.0},
                'generated_at': datetime.now().isoformat(),
                'error': str(e),
            }
    
    def get_kpi_cards(self, company_id: int = 1) -> List[Dict[str, Any]]:
        """
        Get KPI card data for dashboard display.
        
        Args:
            company_id: Company ID to filter data
            
        Returns:
            List of KPI card dictionaries
        """
        data = self.get_dashboard_data(company_id)
        
        return [
            {
                'title': "Today's Sales",
                'value': self.format_currency(data['sales']['today']),
                'icon': '💰',
                'color': '#2ecc71',
            },
            {
                'title': "Month's Sales",
                'value': self.format_currency(data['sales']['month']),
                'icon': '📈',
                'color': '#3498db',
            },
            {
                'title': 'Inventory Value',
                'value': self.format_currency(data['inventory']['total_value']),
                'icon': '📦',
                'color': '#e94560',
            },
            {
                'title': 'Total Parties',
                'value': str(data['parties']['total']),
                'icon': '👥',
                'color': '#f39c12',
            },
        ]
    
    # Abstract method implementations (required by BaseService)
    def get_by_id(self, id_value: Any) -> Optional[Dict[str, Any]]:
        """Not applicable for dashboard service."""
        return None
    
    def get_all(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Not applicable for dashboard service."""
        return []
    
    def create(self, data: Dict[str, Any]) -> int:
        """Not applicable for dashboard service."""
        raise NotImplementedError("Dashboard service does not support create operations")
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Not applicable for dashboard service."""
        raise NotImplementedError("Dashboard service does not support update operations")
    
    def delete(self, id_value: Any) -> bool:
        """Not applicable for dashboard service."""
        raise NotImplementedError("Dashboard service does not support delete operations")
