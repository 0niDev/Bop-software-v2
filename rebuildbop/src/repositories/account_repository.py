"""
Account Repository - Handles chart of accounts and general ledger

Provides methods for account CRUD operations, hierarchy management, and balance tracking.
"""

from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository


class AccountRepository(BaseRepository):
    """Repository for account-related database operations."""
    
    def __init__(self):
        super().__init__('accounts', 'id')
    
    def create_account(self, account_code: str, account_name: str, account_type: str,
                       parent_id: int = None, description: str = None, 
                       opening_balance: float = 0.0, **kwargs) -> int:
        """Create a new account."""
        columns = ['account_code', 'account_name', 'account_type', 'parent_id', 
                   'description', 'opening_balance']
        values = [account_code, account_name, account_type, parent_id, 
                  description, opening_balance]
        
        for key, value in kwargs.items():
            if key not in ['account_code', 'account_name']:
                columns.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        query = f"INSERT INTO accounts ({column_names}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def get_by_code(self, account_code: str) -> Optional[Dict[str, Any]]:
        """Get account by code."""
        query = "SELECT * FROM accounts WHERE account_code = ?"
        return self.execute_single(query, (account_code,))
    
    def get_accounts_by_type(self, account_type: str) -> List[Dict[str, Any]]:
        """Get all accounts of a specific type."""
        query = "SELECT * FROM accounts WHERE account_type = ? ORDER BY account_code"
        return self.execute_query(query, (account_type,))
    
    def get_child_accounts(self, parent_id: int) -> List[Dict[str, Any]]:
        """Get all child accounts of a parent."""
        query = "SELECT * FROM accounts WHERE parent_id = ? ORDER BY account_code"
        return self.execute_query(query, (parent_id,))
    
    def get_root_accounts(self) -> List[Dict[str, Any]]:
        """Get all root level accounts."""
        query = "SELECT * FROM accounts WHERE parent_id IS NULL ORDER BY account_code"
        return self.execute_query(query)
    
    def search_accounts(self, search_term: str, account_type: str = None) -> List[Dict[str, Any]]:
        """Search accounts by code or name."""
        search_pattern = f"%{search_term}%"
        if account_type:
            query = """
                SELECT * FROM accounts 
                WHERE (account_code LIKE ? OR account_name LIKE ?) AND account_type = ?
                ORDER BY account_code
            """
            return self.execute_query(query, (search_pattern, search_pattern, account_type))
        else:
            query = """
                SELECT * FROM accounts 
                WHERE account_code LIKE ? OR account_name LIKE ?
                ORDER BY account_code
            """
            return self.execute_query(query, (search_pattern, search_pattern))
    
    def get_account_balance(self, account_id: int) -> float:
        """Calculate account balance from transactions."""
        query = """
            SELECT 
                COALESCE(SUM(debit), 0) as total_debit,
                COALESCE(SUM(credit), 0) as total_credit
            FROM transactions WHERE account_id = ?
        """
        result = self.execute_single(query, (account_id,))
        if result:
            opening = self.get_by_id(account_id).get('opening_balance', 0) or 0
            return opening + (result['total_debit'] or 0) - (result['total_credit'] or 0)
        return 0
    
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new account."""
        required_fields = ['account_code', 'account_name', 'account_type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        return self.create_account(**data)
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update an existing account."""
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE accounts SET {set_clause} WHERE id = ?"
        values.append(id_value)
        rows_affected = self.execute_update(query, tuple(values))
        return rows_affected > 0
    
    def delete(self, id_value: Any) -> bool:
        """Delete an account."""
        query = "UPDATE accounts SET is_active = 0 WHERE id = ?"
        rows_affected = self.execute_update(query, (id_value,))
        return rows_affected > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find accounts by arbitrary criteria."""
        if not kwargs:
            return self.get_all()
        conditions = []
        values = []
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM accounts WHERE {where_clause} ORDER BY account_code"
        return self.execute_query(query, tuple(values))
