"""
Invoice Repository - Handles sales and purchase invoices

Provides methods for invoice CRUD operations, line items, and status tracking.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime
from .base_repository import BaseRepository


class InvoiceRepository(BaseRepository):
    """Repository for invoice-related database operations."""
    
    def __init__(self):
        super().__init__('invoices', 'id')
    
    def get_sales_summary(self, start_date: str, end_date: str, company_id: int = 1) -> Dict[str, Any]:
        """
        Get sales summary for a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            company_id: Company ID
            
        Returns:
            Dictionary with total and count
        """
        query = """
            SELECT 
                COALESCE(SUM(total_amount), 0) as total,
                COUNT(*) as count
            FROM sales_invoices
            WHERE date(invoice_date) BETWEEN date(?) AND date(?)
            AND company_id = ?
            AND status != 'CANCELLED'
        """
        result = self.execute_single(query, (start_date, end_date, company_id))
        return result if result else {'total': 0.0, 'count': 0}
    
    def get_purchase_summary(self, start_date: str, end_date: str, company_id: int = 1) -> Dict[str, Any]:
        """
        Get purchase summary for a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            company_id: Company ID
            
        Returns:
            Dictionary with total and count
        """
        query = """
            SELECT 
                COALESCE(SUM(total_amount), 0) as total,
                COUNT(*) as count
            FROM purchase_invoices
            WHERE date(invoice_date) BETWEEN date(?) AND date(?)
            AND company_id = ?
            AND status != 'CANCELLED'
        """
        result = self.execute_single(query, (start_date, end_date, company_id))
        return result if result else {'total': 0.0, 'count': 0}
    
    def create_invoice(self, invoice_number: str, invoice_type: str, party_id: int,
                       invoice_date: str = None, due_date: str = None,
                       subtotal: float = 0.0, tax_amount: float = 0.0,
                       discount_amount: float = 0.0, total_amount: float = 0.0,
                       status: str = 'draft', notes: str = None, **kwargs) -> int:
        """Create a new invoice."""
        if not invoice_date:
            invoice_date = datetime.now().strftime('%Y-%m-%d')
        
        columns = [
            'invoice_number', 'invoice_type', 'party_id', 'invoice_date',
            'due_date', 'subtotal', 'tax_amount', 'discount_amount',
            'total_amount', 'status', 'notes'
        ]
        values = [
            invoice_number, invoice_type, party_id, invoice_date,
            due_date, subtotal, tax_amount, discount_amount,
            total_amount, status, notes
        ]
        
        for key, value in kwargs.items():
            if key not in ['invoice_number', 'invoice_type']:
                columns.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        query = f"INSERT INTO invoices ({column_names}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def get_by_number(self, invoice_number: str) -> Optional[Dict[str, Any]]:
        """Get invoice by number."""
        query = "SELECT * FROM invoices WHERE invoice_number = ?"
        return self.execute_single(query, (invoice_number,))
    
    def get_invoices_by_type(self, invoice_type: str, status: str = None) -> List[Dict[str, Any]]:
        """Get invoices by type (sales/purchase)."""
        if status:
            query = "SELECT * FROM invoices WHERE invoice_type = ? AND status = ? ORDER BY invoice_date DESC"
            return self.execute_query(query, (invoice_type, status))
        else:
            query = "SELECT * FROM invoices WHERE invoice_type = ? ORDER BY invoice_date DESC"
            return self.execute_query(query, (invoice_type,))
    
    def get_sales_invoices(self, status: str = None) -> List[Dict[str, Any]]:
        """Get all sales invoices."""
        return self.get_invoices_by_type('sales', status)
    
    def get_purchase_invoices(self, status: str = None) -> List[Dict[str, Any]]:
        """Get all purchase invoices."""
        return self.get_invoices_by_type('purchase', status)
    
    def get_invoices_by_party(self, party_id: int, invoice_type: str = None) -> List[Dict[str, Any]]:
        """Get invoices for a specific party."""
        if invoice_type:
            query = "SELECT * FROM invoices WHERE party_id = ? AND invoice_type = ? ORDER BY invoice_date DESC"
            return self.execute_query(query, (party_id, invoice_type))
        else:
            query = "SELECT * FROM invoices WHERE party_id = ? ORDER BY invoice_date DESC"
            return self.execute_query(query, (party_id,))
    
    def get_overdue_invoices(self, invoice_type: str = None) -> List[Dict[str, Any]]:
        """Get overdue invoices."""
        today = datetime.now().strftime('%Y-%m-%d')
        if invoice_type:
            query = """
                SELECT * FROM invoices 
                WHERE due_date < ? AND status != 'paid' AND invoice_type = ?
                ORDER BY due_date ASC
            """
            return self.execute_query(query, (today, invoice_type))
        else:
            query = """
                SELECT * FROM invoices 
                WHERE due_date < ? AND status != 'paid'
                ORDER BY due_date ASC
            """
            return self.execute_query(query, (today,))
    
    def update_status(self, invoice_id: int, status: str) -> bool:
        """Update invoice status."""
        query = "UPDATE invoices SET status = ? WHERE id = ?"
        rows_affected = self.execute_update(query, (status, invoice_id))
        return rows_affected > 0
    
    def get_invoice_with_items(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        """Get invoice with its line items."""
        invoice = self.get_by_id(invoice_id)
        if not invoice:
            return None
        
        items_query = "SELECT * FROM invoice_items WHERE invoice_id = ?"
        invoice['items'] = self.execute_query(items_query, (invoice_id,))
        return invoice
    
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new invoice."""
        required_fields = ['invoice_number', 'invoice_type', 'party_id']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        return self.create_invoice(**data)
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update an existing invoice."""
        if not data:
            return True
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        query = f"UPDATE invoices SET {set_clause} WHERE id = ?"
        values.append(id_value)
        rows_affected = self.execute_update(query, tuple(values))
        return rows_affected > 0
    
    def delete(self, id_value: Any) -> bool:
        """Delete an invoice."""
        query = "UPDATE invoices SET status = 'cancelled' WHERE id = ?"
        rows_affected = self.execute_update(query, (id_value,))
        return rows_affected > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find invoices by arbitrary criteria."""
        if not kwargs:
            return self.get_all()
        conditions = []
        values = []
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM invoices WHERE {where_clause} ORDER BY invoice_date DESC"
        return self.execute_query(query, tuple(values))
