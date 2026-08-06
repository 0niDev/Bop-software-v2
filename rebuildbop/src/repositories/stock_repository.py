"""
Stock Repository - Handles inventory stock levels and movements

Provides methods for stock tracking, adjustments, and warehouse management.
"""

from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository


class StockRepository(BaseRepository):
    """Repository for stock-related database operations."""
    
    def __init__(self):
        super().__init__('stock', 'id')
    
    def get_inventory_value(self, company_id: int = 1) -> float:
        """
        Get total inventory value.
        
        Args:
            company_id: Company ID
            
        Returns:
            Total inventory value
        """
        query = """
            SELECT COALESCE(SUM(s.quantity * i.standard_cost), 0) as total_value
            FROM stock_batches s
            JOIN items i ON s.item_id = i.id
            WHERE s.quantity > 0 AND company_id = ?
        """
        try:
            result = self.execute_single(query, (company_id,))
            return float(result.get('total_value', 0)) if result else 0.0
        except Exception:
            return 0.0
    
    def get_low_stock_items(self, limit: int = 10, company_id: int = 1) -> List[Dict[str, Any]]:
        """
        Get items with low stock levels.
        
        Args:
            limit: Maximum number of items to return
            company_id: Company ID
            
        Returns:
            List of low stock items
        """
        query = """
            SELECT i.id, i.name, i.sku, SUM(s.quantity) as current_qty, i.reorder_level
            FROM items i
            LEFT JOIN stock_batches s ON i.id = s.item_id
            WHERE company_id = ?
            GROUP BY i.id
            HAVING current_qty <= i.reorder_level OR current_qty IS NULL
            ORDER BY current_qty ASC
            LIMIT ?
        """
        try:
            return self.execute_query(query, (company_id, limit))
        except Exception:
            return []
    
    def get_current_stock(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get current stock levels for all items."""
        # Check if stock table exists first
        try:
            query = """
                SELECT s.*, i.name as item_name, i.sku as item_sku
                FROM stock s
                JOIN items i ON s.item_id = i.id
                ORDER BY i.name
                LIMIT ?
            """
            return self.execute_query(query, (limit,))
        except Exception:
            # Table doesn't exist yet, return empty list
            return []
    
    def get_stock_for_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get current stock for an item."""
        query = "SELECT * FROM stock WHERE item_id = ?"
        return self.execute_single(query, (item_id,))
    
    def get_current_quantity(self, item_id: int) -> float:
        """Get current quantity for an item."""
        stock = self.get_stock_for_item(item_id)
        return stock.get('quantity', 0) if stock else 0
    
    def update_quantity(self, item_id: int, quantity: float, operation: str = 'set') -> bool:
        """Update stock quantity."""
        if operation == 'add':
            query = "UPDATE stock SET quantity = quantity + ? WHERE item_id = ?"
        elif operation == 'subtract':
            query = "UPDATE stock SET quantity = quantity - ? WHERE item_id = ?"
        else:
            query = "UPDATE stock SET quantity = ? WHERE item_id = ?"
        
        rows_affected = self.execute_update(query, (quantity, item_id) if operation == 'set' else (quantity, item_id))
        return rows_affected > 0
    
    def create_stock_record(self, item_id: int, quantity: float, warehouse_id: int = None) -> int:
        """Create a new stock record."""
        columns = ['item_id', 'quantity', 'warehouse_id']
        values = [item_id, quantity, warehouse_id]
        placeholders = ', '.join(['?' for _ in columns])
        query = f"INSERT INTO stock ({', '.join(columns)}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def get_all_stock(self) -> List[Dict[str, Any]]:
        """Get all stock records with item details."""
        query = """
            SELECT s.*, i.name as item_name, i.sku as item_sku
            FROM stock s
            JOIN items i ON s.item_id = i.id
            ORDER BY i.name
        """
        return self.execute_query(query)
    
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new stock record."""
        required_fields = ['item_id', 'quantity']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        return self.create_stock_record(**data)
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update stock record."""
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE stock SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        """Delete stock record."""
        query = "DELETE FROM stock WHERE id = ?"
        return self.execute_delete(query, (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find stock by criteria."""
        if not kwargs:
            return self.get_all()
        conditions = []
        values = []
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM stock WHERE {where_clause}"
        return self.execute_query(query, tuple(values))
