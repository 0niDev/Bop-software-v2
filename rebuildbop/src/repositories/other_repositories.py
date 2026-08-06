"""
Remaining Repositories - Report, Settings, Audit, Tax, Unit, Category, Batch

Provides repository classes for supporting entities.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from .base_repository import BaseRepository


class ReportRepository(BaseRepository):
    """Repository for report-related operations."""
    
    def __init__(self):
        super().__init__('reports', 'id')
    
    def create(self, data: Dict[str, Any]) -> int:
        required_fields = ['report_name', 'report_type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['?' for _ in columns])
        query = f"INSERT INTO reports ({', '.join(columns)}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE reports SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        return self.execute_delete("DELETE FROM reports WHERE id = ?", (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        if not kwargs:
            return self.get_all()
        conditions = [f"{k} = ?" for k in kwargs]
        query = f"SELECT * FROM reports WHERE {' AND '.join(conditions)}"
        return self.execute_query(query, tuple(kwargs.values()))


class SettingsRepository(BaseRepository):
    """Repository for system settings."""
    
    def __init__(self):
        super().__init__('settings', 'id')
    
    def get_setting(self, key: str) -> Optional[str]:
        result = self.execute_single("SELECT value FROM settings WHERE setting_key = ?", (key,))
        return result['value'] if result else None
    
    def set_setting(self, key: str, value: str) -> bool:
        existing = self.get_setting(key)
        if existing:
            return self.execute_update("UPDATE settings SET value = ? WHERE setting_key = ?", (value, key)) > 0
        else:
            return self.execute_insert("INSERT INTO settings (setting_key, value) VALUES (?, ?)", (key, value)) > 0
    
    def create(self, data: Dict[str, Any]) -> int:
        return self.set_setting(data.get('setting_key', ''), data.get('value', ''))
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        if 'value' in data:
            return self.execute_update("UPDATE settings SET value = ? WHERE id = ?", (data['value'], id_value)) > 0
        return True
    
    def delete(self, id_value: Any) -> bool:
        return self.execute_delete("DELETE FROM settings WHERE id = ?", (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        if not kwargs:
            return self.get_all()
        conditions = [f"{k} = ?" for k in kwargs]
        query = f"SELECT * FROM settings WHERE {' AND '.join(conditions)}"
        return self.execute_query(query, tuple(kwargs.values()))


class AuditRepository(BaseRepository):
    """Repository for audit trail logging."""
    
    def __init__(self):
        super().__init__('audit_log', 'id')
    
    def log_action(self, user_id: int, action: str, entity_type: str, 
                   entity_id: int = None, details: str = None) -> int:
        timestamp = datetime.now().isoformat()
        return self.execute_insert(
            "INSERT INTO audit_log (user_id, action, entity_type, entity_id, details, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, action, entity_type, entity_id, details, timestamp)
        )
    
    def get_logs_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        return self.execute_query("SELECT * FROM audit_log WHERE user_id = ? ORDER BY timestamp DESC", (user_id,))
    
    def get_logs_by_entity(self, entity_type: str, entity_id: int = None) -> List[Dict[str, Any]]:
        if entity_id:
            return self.execute_query(
                "SELECT * FROM audit_log WHERE entity_type = ? AND entity_id = ? ORDER BY timestamp DESC",
                (entity_type, entity_id)
            )
        return self.execute_query(
            "SELECT * FROM audit_log WHERE entity_type = ? ORDER BY timestamp DESC",
            (entity_type,)
        )
    
    def create(self, data: Dict[str, Any]) -> int:
        return self.log_action(
            data.get('user_id', 0), data.get('action', ''), data.get('entity_type', ''),
            data.get('entity_id'), data.get('details')
        )
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        return False  # Audit logs should not be updated
    
    def delete(self, id_value: Any) -> bool:
        return False  # Audit logs should not be deleted
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        if not kwargs:
            return self.get_all(order_by='timestamp DESC')
        conditions = [f"{k} = ?" for k in kwargs]
        query = f"SELECT * FROM audit_log WHERE {' AND '.join(conditions)} ORDER BY timestamp DESC"
        return self.execute_query(query, tuple(kwargs.values()))


class TaxRepository(BaseRepository):
    """Repository for tax rates and configurations."""
    
    def __init__(self):
        super().__init__('tax_rates', 'id')
    
    def get_by_rate(self, rate: float) -> Optional[Dict[str, Any]]:
        return self.execute_single("SELECT * FROM tax_rates WHERE rate = ?", (rate,))
    
    def get_active_taxes(self) -> List[Dict[str, Any]]:
        return self.execute_query("SELECT * FROM tax_rates WHERE is_active = 1 ORDER BY rate")
    
    def create(self, data: Dict[str, Any]) -> int:
        columns = ['name', 'rate', 'description']
        values = [data.get('name', ''), data.get('rate', 0), data.get('description', '')]
        query = f"INSERT INTO tax_rates ({', '.join(columns)}) VALUES ({', '.join(['?']*3)})"
        return self.execute_insert(query, tuple(values))
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE tax_rates SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        return self.execute_update("UPDATE tax_rates SET is_active = 0 WHERE id = ?", (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        if not kwargs:
            return self.get_active_taxes()
        conditions = [f"{k} = ?" for k in kwargs]
        query = f"SELECT * FROM tax_rates WHERE {' AND '.join(conditions)}"
        return self.execute_query(query, tuple(kwargs.values()))


class UnitRepository(BaseRepository):
    """Repository for units of measurement."""
    
    def __init__(self):
        super().__init__('units', 'id')
    
    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self.execute_single("SELECT * FROM units WHERE unit_name = ?", (name,))
    
    def get_all_units(self) -> List[Dict[str, Any]]:
        return self.execute_query("SELECT * FROM units ORDER BY unit_name")
    
    def create(self, data: Dict[str, Any]) -> int:
        return self.execute_insert("INSERT INTO units (unit_name, symbol) VALUES (?, ?)",
                                   (data.get('unit_name', ''), data.get('symbol', '')))
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE units SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        return self.execute_delete("DELETE FROM units WHERE id = ?", (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        if not kwargs:
            return self.get_all_units()
        conditions = [f"{k} = ?" for k in kwargs]
        query = f"SELECT * FROM units WHERE {' AND '.join(conditions)}"
        return self.execute_query(query, tuple(kwargs.values()))


class CategoryRepository(BaseRepository):
    """Repository for item/party categories."""
    
    def __init__(self):
        super().__init__('categories', 'id')
    
    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        return self.execute_single("SELECT * FROM categories WHERE category_name = ?", (name,))
    
    def get_categories_by_type(self, category_type: str) -> List[Dict[str, Any]]:
        return self.execute_query("SELECT * FROM categories WHERE category_type = ? ORDER BY category_name",
                                  (category_type,))
    
    def create(self, data: Dict[str, Any]) -> int:
        return self.execute_insert(
            "INSERT INTO categories (category_name, category_type, parent_id) VALUES (?, ?, ?)",
            (data.get('category_name', ''), data.get('category_type', ''), data.get('parent_id'))
        )
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE categories SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        return self.execute_delete("DELETE FROM categories WHERE id = ?", (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        if not kwargs:
            return self.get_all()
        conditions = [f"{k} = ?" for k in kwargs]
        query = f"SELECT * FROM categories WHERE {' AND '.join(conditions)}"
        return self.execute_query(query, tuple(kwargs.values()))


class BatchRepository(BaseRepository):
    """Repository for batch/lot tracking (pharmaceutical)."""
    
    def __init__(self):
        super().__init__('batches', 'id')
    
    def create_batch(self, item_id: int, batch_number: str, manufacture_date: str,
                     expiry_date: str, quantity: float) -> int:
        return self.execute_insert(
            "INSERT INTO batches (item_id, batch_number, manufacture_date, expiry_date, quantity) VALUES (?, ?, ?, ?, ?)",
            (item_id, batch_number, manufacture_date, expiry_date, quantity)
        )
    
    def get_by_batch_number(self, batch_number: str) -> Optional[Dict[str, Any]]:
        return self.execute_single("SELECT * FROM batches WHERE batch_number = ?", (batch_number,))
    
    def get_expiring_batches(self, days: int = 30) -> List[Dict[str, Any]]:
        query = """
            SELECT * FROM batches 
            WHERE expiry_date <= date('now', '+{} days') AND quantity > 0
            ORDER BY expiry_date ASC
        """.format(days)
        return self.execute_query(query)
    
    def get_batches_for_item(self, item_id: int) -> List[Dict[str, Any]]:
        return self.execute_query("SELECT * FROM batches WHERE item_id = ? AND quantity > 0 ORDER BY expiry_date",
                                  (item_id,))
    
    def create(self, data: Dict[str, Any]) -> int:
        return self.create_batch(
            data.get('item_id'), data.get('batch_number', ''),
            data.get('manufacture_date', ''), data.get('expiry_date', ''),
            data.get('quantity', 0)
        )
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE batches SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        return self.execute_delete("DELETE FROM batches WHERE id = ?", (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        if not kwargs:
            return self.get_all()
        conditions = [f"{k} = ?" for k in kwargs]
        query = f"SELECT * FROM batches WHERE {' AND '.join(conditions)}"
        return self.execute_query(query, tuple(kwargs.values()))
