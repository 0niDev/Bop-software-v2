"""
Party Repository - Handles customers, suppliers, and other business partners

Provides methods for party CRUD operations, categorization, and relationship management.
"""

from typing import Any, Dict, List, Optional
from .base_repository import BaseRepository


class PartyRepository(BaseRepository):
    """
    Repository for party-related database operations.
    
    Handles customers, suppliers, vendors, and other business entities.
    """
    
    def __init__(self):
        super().__init__('parties', 'id')
    
    def create_party(self, name: str, party_type: str, contact_person: str = None,
                     phone: str = None, email: str = None, address: str = None,
                     city: str = None, country: str = None, gst_number: str = None,
                     pan_number: str = None, opening_balance: float = 0.0,
                     **kwargs) -> int:
        """
        Create a new party (customer/supplier/vendor).
        
        Args:
            name: Party name
            party_type: Type of party (customer, supplier, vendor, etc.)
            contact_person: Contact person name
            phone: Phone number
            email: Email address
            address: Street address
            city: City
            country: Country
            gst_number: GST/VAT number
            pan_number: PAN/Tax ID number
            opening_balance: Opening balance amount
            **kwargs: Additional fields
            
        Returns:
            ID of the newly created party
        """
        columns = [
            'name', 'party_type', 'contact_person', 'phone', 'email',
            'address', 'city', 'country', 'gst_number', 'pan_number',
            'opening_balance'
        ]
        values = [
            name, party_type, contact_person, phone, email,
            address, city, country, gst_number, pan_number,
            opening_balance
        ]
        
        # Add additional fields
        for key, value in kwargs.items():
            if key not in ['name', 'party_type']:
                columns.append(key)
                values.append(value)
        
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        
        query = f"INSERT INTO parties ({column_names}) VALUES ({placeholders})"
        return self.execute_insert(query, tuple(values))
    
    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a party by name."""
        query = "SELECT * FROM parties WHERE name = ?"
        return self.execute_single(query, (name,))
    
    def get_by_type(self, party_type: str, order_by: str = 'name') -> List[Dict[str, Any]]:
        """
        Get all parties of a specific type.
        
        Args:
            party_type: Type of party (customer, supplier, etc.)
            order_by: Column to order by
            
        Returns:
            List of party dictionaries
        """
        query = f"SELECT * FROM parties WHERE party_type = ? ORDER BY {order_by}"
        return self.execute_query(query, (party_type,))
    
    def get_all_customers(self) -> List[Dict[str, Any]]:
        """Get all customers."""
        return self.get_by_type('customer')
    
    def get_all_suppliers(self) -> List[Dict[str, Any]]:
        """Get all suppliers."""
        return self.get_by_type('supplier')
    
    def get_all_vendors(self) -> List[Dict[str, Any]]:
        """Get all vendors."""
        return self.get_by_type('vendor')
    
    def search_parties(self, search_term: str, party_type: str = None) -> List[Dict[str, Any]]:
        """
        Search parties by name, contact person, or phone.
        
        Args:
            search_term: Search term
            party_type: Filter by party type (optional)
            
        Returns:
            List of matching parties
        """
        search_pattern = f"%{search_term}%"
        
        if party_type:
            query = """
                SELECT * FROM parties 
                WHERE (name LIKE ? OR contact_person LIKE ? OR phone LIKE ?)
                AND party_type = ?
                ORDER BY name
            """
            return self.execute_query(query, (search_pattern, search_pattern, search_pattern, party_type))
        else:
            query = """
                SELECT * FROM parties 
                WHERE name LIKE ? OR contact_person LIKE ? OR phone LIKE ?
                ORDER BY name
            """
            return self.execute_query(query, (search_pattern, search_pattern, search_pattern))
    
    def update_balance(self, party_id: int, amount: float, operation: str = 'add') -> bool:
        """
        Update party's balance.
        
        Args:
            party_id: Party ID
            amount: Amount to add/subtract
            operation: 'add' or 'subtract'
            
        Returns:
            True if update was successful
        """
        if operation == 'add':
            query = "UPDATE parties SET opening_balance = opening_balance + ? WHERE id = ?"
        elif operation == 'subtract':
            query = "UPDATE parties SET opening_balance = opening_balance - ? WHERE id = ?"
        else:
            query = "UPDATE parties SET opening_balance = ? WHERE id = ?"
            amount = abs(amount)
        
        rows_affected = self.execute_update(query, (amount, party_id))
        return rows_affected > 0
    
    def get_party_with_balance(self, party_id: int) -> Optional[Dict[str, Any]]:
        """
        Get party with current balance including transactions.
        
        Args:
            party_id: Party ID
            
        Returns:
            Party dictionary with calculated balance
        """
        party = self.get_by_id(party_id)
        if not party:
            return None
        
        # Calculate balance from transactions
        query = """
            SELECT 
                COALESCE(SUM(CASE WHEN debit > 0 THEN debit ELSE 0 END), 0) as total_debit,
                COALESCE(SUM(CASE WHEN credit > 0 THEN credit ELSE 0 END), 0) as total_credit
            FROM transactions 
            WHERE party_id = ?
        """
        result = self.execute_single(query, (party_id,))
        
        if result:
            opening = party.get('opening_balance', 0) or 0
            total_debit = result.get('total_debit', 0) or 0
            total_credit = result.get('total_credit', 0) or 0
            party['current_balance'] = opening + total_debit - total_credit
        
        return party
    
    def get_parties_with_outstanding(self, party_type: str = None) -> List[Dict[str, Any]]:
        """
        Get parties with outstanding balances.
        
        Args:
            party_type: Filter by party type (optional)
            
        Returns:
            List of parties with their outstanding balances
        """
        where_clause = ""
        params = []
        
        if party_type:
            where_clause = "WHERE p.party_type = ?"
            params.append(party_type)
        
        query = f"""
            SELECT 
                p.*,
                p.opening_balance + 
                COALESCE((SELECT SUM(debit) FROM transactions t WHERE t.party_id = p.id), 0) -
                COALESCE((SELECT SUM(credit) FROM transactions t WHERE t.party_id = p.id), 0) 
                as current_balance
            FROM parties p
            {where_clause}
            HAVING current_balance != 0
            ORDER BY current_balance DESC
        """
        
        return self.execute_query(query, tuple(params))
    
    def check_duplicate(self, name: str, phone: str = None, email: str = None) -> bool:
        """Check if a party already exists with same details."""
        conditions = ["name = ?"]
        values = [name]
        
        if phone:
            conditions.append("phone = ?")
            values.append(phone)
        
        if email:
            conditions.append("email = ?")
            values.append(email)
        
        where_clause = " AND ".join(conditions)
        return self.exists(where_clause, tuple(values))
    
    # Abstract method implementations
    def create(self, data: Dict[str, Any]) -> int:
        """Create a new party."""
        required_fields = ['name', 'party_type']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        return self.create_party(**data)
    
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """Update an existing party."""
        if not data:
            return True
        
        columns = list(data.keys())
        values = list(data.values())
        set_clause = ', '.join([f"{col} = ?" for col in columns])
        
        query = f"UPDATE parties SET {set_clause} WHERE id = ?"
        values.append(id_value)
        
        rows_affected = self.execute_update(query, tuple(values))
        return rows_affected > 0
    
    def delete(self, id_value: Any) -> bool:
        """Delete a party (soft delete by setting is_active to 0)."""
        query = "UPDATE parties SET is_active = 0 WHERE id = ?"
        rows_affected = self.execute_update(query, (id_value,))
        return rows_affected > 0
    
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """Find parties by arbitrary criteria."""
        if not kwargs:
            return self.get_all()
        
        conditions = []
        values = []
        
        for key, value in kwargs.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        
        where_clause = ' AND '.join(conditions)
        query = f"SELECT * FROM parties WHERE {where_clause} ORDER BY name"
        
        return self.execute_query(query, tuple(values))
