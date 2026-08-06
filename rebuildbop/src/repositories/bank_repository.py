"""
Bank Repository - Handles bank accounts and transactions

Provides methods for bank account management, reconciliation, and payment processing.
"""

from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository


class BankRepository(BaseRepository):
    """Repository for bank-related database operations."""
    
    def __init__(self):
        super().__init__('bank_accounts', 'id')
    
    def create_bank_account(self, account_name: str, bank_name: str, account_number: str,
                            ifsc_code: str = None, branch: str = None,
                            opening_balance: float = 0.0, **kwargs) -> int:
        """Create a new bank account."""
        columns = ['account_name', 'bank_name', 'account_number', 'ifsc_code', 
                   'branch', 'opening_balance']
        values = [account_name, bank_name, account_number, ifsc_code, 
                  branch, opening_balance]
        
        for key, value in kwargs.items():
            if key not in ['account_name', 'bank_name']:
                columns.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        query = f"INSERT INTO bank_accounts ({column_names}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def get_by_account_number(self, account_number: str) -> Optional[Dict[str, Any]]:
        """Get bank account by number."""
        query = "SELECT * FROM bank_accounts WHERE account_number = ?"
        return self.execute_single(query, (account_number,))
    
    def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Get all bank accounts."""
        query = "SELECT * FROM bank_accounts ORDER BY bank_name, account_name"
        return self.execute_query(query)
    
    def update_balance(self, account_id: int, amount: float, operation: str = 'add') -> bool:
        """Update bank account balance."""
        if operation == 'add':
            query = "UPDATE bank_accounts SET current_balance = current_balance + ? WHERE id = ?"
        elif operation == 'subtract':
            query = "UPDATE bank_accounts SET current_balance = current_balance - ? WHERE id = ?"
        else:
            query = "UPDATE bank_accounts SET current_balance = ? WHERE id = ?"
        rows_affected = self.execute_update(query, (amount, account_id) if operation != 'set' else (amount, account_id))
        return rows_affected > 0
    
    def get_account_balance(self, account_id: int) -> float:
        """Get current balance for a bank account."""
        account = self.get_by_id(account_id)
        return account.get('current_balance', 0) if account else 0
    
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new bank account."""
        required_fields = ['account_name', 'bank_name', 'account_number']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        return self.create_bank_account(**data)
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update bank account."""
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE bank_accounts SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        """Delete bank account."""
        query = "UPDATE bank_accounts SET is_active = 0 WHERE id = ?"
        return self.execute_update(query, (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find bank accounts by criteria."""
        if not kwargs:
            return self.get_all()
        conditions = []
        values = []
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM bank_accounts WHERE {where_clause}"
        return self.execute_query(query, tuple(values))
