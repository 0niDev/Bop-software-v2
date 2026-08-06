"""
Item Repository - Handles products, raw materials, and inventory items

Provides methods for item CRUD operations, stock tracking, and pricing.
"""

from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository


class ItemRepository(BaseRepository):
    """Repository for item-related database operations."""
    
    def __init__(self):
        super().__init__('items', 'id')
    
    def create_item(self, name: str, item_type: str, sku: str = None,
                    category_id: int = None, unit_id: int = None,
                    purchase_price: float = 0.0, sale_price: float = 0.0,
                    mrp: float = 0.0, gst_rate: float = 0.0,
                    min_stock: float = 0.0, max_stock: float = 0.0,
                    description: str = None, **kwargs) -> int:
        """Create a new item."""
        columns = [
            'name', 'item_type', 'sku', 'category_id', 'unit_id',
            'purchase_price', 'sale_price', 'mrp', 'gst_rate',
            'min_stock', 'max_stock', 'description'
        ]
        values = [
            name, item_type, sku, category_id, unit_id,
            purchase_price, sale_price, mrp, gst_rate,
            min_stock, max_stock, description
        ]
        
        for key, value in kwargs.items():
            if key not in ['name', 'item_type']:
                columns.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO items ({column_names}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def get_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get item by SKU."""
        query = "SELECT * FROM items WHERE sku = ?"
        return self.execute_single(query, (sku,))
    
    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get item by name."""
        query = "SELECT * FROM items WHERE name = ?"
        return self.execute_single(query, (name,))
    
    def get_items_by_type(self, item_type: str) -> List[Dict[str, Any]]:
        """Get all items of a specific type."""
        query = "SELECT * FROM items WHERE item_type = ? ORDER BY name"
        return self.execute_query(query, (item_type,))
    
    def get_items_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        """Get all items in a category."""
        query = "SELECT * FROM items WHERE category_id = ? ORDER BY name"
        return self.execute_query(query, (category_id,))
    
    def search_items(self, search_term: str, item_type: str = None) -> List[Dict[str, Any]]:
        """Search items by name, SKU, or description."""
        search_pattern = f"%{search_term}%"
        
        if item_type:
            query = """
                SELECT * FROM items 
                WHERE (name LIKE ? OR sku LIKE ? OR description LIKE ?)
                AND item_type = ?
                ORDER BY name
            """
            return self.execute_query(query, (search_pattern, search_pattern, search_pattern, item_type))
        else:
            query = """
                SELECT * FROM items 
                WHERE name LIKE ? OR sku LIKE ? OR description LIKE ?
                ORDER BY name
            """
            return self.execute_query(query, (search_pattern, search_pattern, search_pattern))
    
    def update_prices(self, item_id: int, purchase_price: float = None,
                      sale_price: float = None, mrp: float = None) -> bool:
        """Update item prices."""
        updates = []
        values = []
        
        if purchase_price is not None:
            updates.append("purchase_price = ?")
            values.append(purchase_price)
        if sale_price is not None:
            updates.append("sale_price = ?")
            values.append(sale_price)
        if mrp is not None:
            updates.append("mrp = ?")
            values.append(mrp)
        
        if not updates:
            return True
        
        set_clause = ', '.join(updates)
        values.append(item_id)
        
        query = f"UPDATE items SET {set_clause} WHERE id = ?"
        rows_affected = self.execute_update(query, tuple(values))
        return rows_affected > 0
    
    def get_low_stock_items(self) -> List[Dict[str, Any]]:
        """Get items below minimum stock level."""
        query = """
            SELECT i.*, COALESCE(SUM(s.quantity), 0) as current_stock
            FROM items i
            LEFT JOIN stock s ON i.id = s.item_id
            GROUP BY i.id
            HAVING current_stock <= i.min_stock
            ORDER BY current_stock ASC
        """
        return self.execute_query(query)
    
    # Abstract method implementations
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new item."""
        required_fields = ['name', 'item_type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        return self.create_item(**data)
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update an existing item."""
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE items SET {set_clause} WHERE id = ?"
        values.append(id_value)
        rows_affected = self.execute_update(query, tuple(values))
        return rows_affected > 0
    
    def delete(self, id_value: Any) -> bool:
        """Delete an item."""
        query = "UPDATE items SET is_active = 0 WHERE id = ?"
        rows_affected = self.execute_update(query, (id_value,))
        return rows_affected > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find items by arbitrary criteria."""
        if not kwargs:
            return self.get_all()
        conditions = []
        values = []
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM items WHERE {where_clause} ORDER BY name"
        return self.execute_query(query, tuple(values))
