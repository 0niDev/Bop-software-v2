"""
Transaction Repository - Handles accounting transactions (double-entry bookkeeping)

Provides methods for transaction CRUD operations, ledger entries, and balance calculations.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from .base_repository import BaseRepository


class TransactionRepository(BaseRepository):
    """Repository for accounting transaction operations."""
    
    def __init__(self):
        super().__init__('transactions', 'id')
    
    def create_transaction(self, transaction_date: str, account_id: int, 
                           debit: float = 0.0, credit: float = 0.0,
                           party_id: int = None, invoice_id: int = None,
                           description: str = None, reference_number: str = None,
                           **kwargs) -> int:
        """Create a new transaction entry."""
        if not transaction_date:
            transaction_date = datetime.now().strftime('%Y-%m-%d')
        
        columns = [
            'transaction_date', 'account_id', 'debit', 'credit',
            'party_id', 'invoice_id', 'description', 'reference_number'
        ]
        values = [
            transaction_date, account_id, debit, credit,
            party_id, invoice_id, description, reference_number
        ]
        
        for key, value in kwargs.items():
            if key not in ['account_id', 'debit', 'credit']:
                columns.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        query = f"INSERT INTO transactions ({column_names}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def create_double_entry(self, debit_account_id: int, credit_account_id: int,
                            amount: float, transaction_date: str = None,
                            party_id: int = None, invoice_id: int = None,
                            description: str = None) -> tuple:
        """
        Create a double-entry transaction (debit and credit).
        
        Returns tuple of (debit_transaction_id, credit_transaction_id)
        """
        debit_id = self.create_transaction(
            transaction_date=transaction_date,
            account_id=debit_account_id,
            debit=amount,
            credit=0.0,
            party_id=party_id,
            invoice_id=invoice_id,
            description=description
        )
        
        credit_id = self.create_transaction(
            transaction_date=transaction_date,
            account_id=credit_account_id,
            debit=0.0,
            credit=amount,
            party_id=party_id,
            invoice_id=invoice_id,
            description=description
        )
        
        return (debit_id, credit_id)
    
    def get_transactions_by_account(self, account_id: int, start_date: str = None,
                                    end_date: str = None) -> List[Dict[str, Any]]:
        """Get transactions for an account within date range."""
        conditions = ["account_id = ?"]
        values = [account_id]
        
        if start_date:
            conditions.append("transaction_date >= ?")
            values.append(start_date)
        if end_date:
            conditions.append("transaction_date <= ?")
            values.append(end_date)
        
        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM transactions WHERE {where_clause} ORDER BY transaction_date DESC"
        return self.execute_query(query, tuple(values))
    
    def get_transactions_by_party(self, party_id: int) -> List[Dict[str, Any]]:
        """Get all transactions for a party."""
        query = "SELECT * FROM transactions WHERE party_id = ? ORDER BY transaction_date DESC"
        return self.execute_query(query, (party_id,))
    
    def get_transactions_by_invoice(self, invoice_id: int) -> List[Dict[str, Any]]:
        """Get all transactions for an invoice."""
        query = "SELECT * FROM transactions WHERE invoice_id = ? ORDER BY transaction_date DESC"
        return self.execute_query(query, (invoice_id,))
    
    def get_account_balance(self, account_id: int, as_of_date: str = None) -> float:
        """Calculate account balance up to a specific date."""
        if as_of_date:
            query = """
                SELECT 
                    COALESCE(SUM(debit), 0) as total_debit,
                    COALESCE(SUM(credit), 0) as total_credit
                FROM transactions 
                WHERE account_id = ? AND transaction_date <= ?
            """
            result = self.execute_single(query, (account_id, as_of_date))
        else:
            query = """
                SELECT 
                    COALESCE(SUM(debit), 0) as total_debit,
                    COALESCE(SUM(credit), 0) as total_credit
                FROM transactions 
                WHERE account_id = ?
            """
            result = self.execute_single(query, (account_id,))
        
        if result:
            return (result['total_debit'] or 0) - (result['total_credit'] or 0)
        return 0.0
    
    def get_trial_balance(self, as_of_date: str = None) -> List[Dict[str, Any]]:
        """Get trial balance for all accounts."""
        date_filter = f"AND transaction_date <= '{as_of_date}'" if as_of_date else ""
        
        query = f"""
            SELECT 
                a.id,
                a.account_code,
                a.account_name,
                a.account_type,
                COALESCE(SUM(t.debit), 0) as total_debit,
                COALESCE(SUM(t.credit), 0) as total_credit,
                COALESCE(SUM(t.debit), 0) - COALESCE(SUM(t.credit), 0) as balance
            FROM accounts a
            LEFT JOIN transactions t ON a.id = t.account_id {date_filter}
            GROUP BY a.id, a.account_code, a.account_name, a.account_type
            HAVING balance != 0
            ORDER BY a.account_code
        """
        return self.execute_query(query)
    
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new transaction."""
        required_fields = ['account_id']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        return self.create_transaction(**data)
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update a transaction."""
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE transactions SET {set_clause} WHERE id = ?"
        values.append(id_value)
        return self.execute_update(query, tuple(values)) > 0
    
    def delete(self, id_value: Any) -> bool:
        """Delete a transaction."""
        query = "DELETE FROM transactions WHERE id = ?"
        return self.execute_delete(query, (id_value,)) > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find transactions by criteria."""
        if not kwargs:
            return self.get_all()
        conditions = []
        values = []
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM transactions WHERE {where_clause} ORDER BY transaction_date DESC"
        return self.execute_query(query, tuple(values))
