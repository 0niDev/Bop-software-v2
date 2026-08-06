"""
Base Repository - Abstract base class for all repositories

Provides common CRUD operations and database connection management.
All repositories should inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, TypeVar, Generic
import sqlitecloud
from src.database.sqlitecloud_connection import SQLiteCloudConnection

T = TypeVar('T')


class BaseRepository(ABC):
    """
    Abstract base class for all repository classes.
    
    Provides common database operations and connection management.
    All repositories should inherit from this class and implement
    entity-specific methods.
    
    Attributes:
        table_name (str): Name of the database table
        primary_key (str): Name of the primary key column
    """
    
    def __init__(self, table_name: str, primary_key: str = 'id'):
        """
        Initialize the base repository.
        
        Args:
            table_name: Name of the database table
            primary_key: Name of the primary key column
        """
        self.table_name = table_name
        self.primary_key = primary_key
        self._connection = None
    
    def _get_connection(self):
        """Get a database connection."""
        if self._connection is None:
            self._connection = SQLiteCloudConnection()
        return self._connection
    
    def _close_connection(self):
        """Close the connection if open."""
        if self._connection:
            try:
                self._connection.close()
            except:
                pass
            self._connection = None
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return results as list of dictionaries.
        
        Args:
            query: SQL query string with placeholders
            params: Parameters for the query
            
        Returns:
            List of dictionaries representing rows
        """
        conn = None
        try:
            conn = SQLiteCloudConnection()
            cursor = conn.execute(query, params)
            columns = [description[0] for description in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
        except Exception as e:
            raise Exception(f"Query execution failed: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def execute_single(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """Execute a query and return a single result."""
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def execute_insert(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT query and return the last inserted ID."""
        conn = None
        try:
            conn = SQLiteCloudConnection()
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"Insert operation failed: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an UPDATE query and return number of affected rows."""
        conn = None
        try:
            conn = SQLiteCloudConnection()
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"Update operation failed: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def execute_delete(self, query: str, params: tuple = ()) -> int:
        """Execute a DELETE query and return number of affected rows."""
        conn = None
        try:
            conn = SQLiteCloudConnection()
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"Delete operation failed: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def execute_batch(self, query: str, params_list: List[tuple]) -> int:
        """Execute a batch operation efficiently."""
        conn = None
        try:
            conn = SQLiteCloudConnection()
            cursor = conn.executemany(query, params_list)
            conn.commit()
            return cursor.rowcount
        except Exception as e:
            if conn:
                conn.rollback()
            raise Exception(f"Batch operation failed: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def get_by_id(self, id_value: Any) -> Optional[Dict[str, Any]]:
        """
        Get a single record by its primary key.
        
        Args:
            id_value: The primary key value
            
        Returns:
            Dictionary representing the row or None if not found
        """
        query = f"SELECT * FROM {self.table_name} WHERE {self.primary_key} = ?"
        return self.execute_single(query, (id_value,))
    
    def get_all(self, order_by: str = None, limit: int = None) -> List[Dict[str, Any]]:
        """
        Get all records from the table.
        
        Args:
            order_by: Column to order by (optional)
            limit: Maximum number of records to return (optional)
            
        Returns:
            List of dictionaries representing rows
        """
        query = f"SELECT * FROM {self.table_name}"
        if order_by:
            query += f" ORDER BY {order_by}"
        if limit:
            query += f" LIMIT {limit}"
        return self.execute_query(query)
    
    def count(self, where_clause: str = None, params: tuple = (), company_id: int = None) -> int:
        """
        Count records in the table with optional company filter.
        
        Args:
            where_clause: WHERE clause (without 'WHERE' keyword)
            params: Parameters for the WHERE clause
            company_id: Optional company ID to filter
            
        Returns:
            Count of records
        """
        if company_id is not None:
            if where_clause:
                where_clause += f" AND company_id = ?"
                params = params + (company_id,)
            else:
                where_clause = "company_id = ?"
                params = (company_id,)
        
        query = f"SELECT COUNT(*) as count FROM {self.table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        result = self.execute_single(query, params)
        return result.get('count', 0) if result else 0
    
    def exists(self, where_clause: str, params: tuple = ()) -> bool:
        """
        Check if any records match the given condition.
        
        Args:
            where_clause: WHERE clause (without 'WHERE' keyword)
            params: Parameters for the WHERE clause
            
        Returns:
            True if at least one record matches, False otherwise
        """
        count = self.count(where_clause, params)
        return count > 0
    
    @abstractmethod
    def create(self, data: Dict[str, Any]) -> int:
        """
        Create a new record.
        
        Args:
            data: Dictionary of column names and values
            
        Returns:
            ID of the newly created record
        """
        pass
    
    @abstractmethod
    def update(self, id_value: Any, data: Dict[str, Any]) -> bool:
        """
        Update an existing record.
        
        Args:
            id_value: Primary key value
            data: Dictionary of column names and values to update
            
        Returns:
            True if update was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def delete(self, id_value: Any) -> bool:
        """
        Delete a record.
        
        Args:
            id_value: Primary key value
            
        Returns:
            True if deletion was successful, False otherwise
        """
        pass
    
    @abstractmethod
    def find_by(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Find records by arbitrary criteria.
        
        Args:
            **kwargs: Column name and value pairs
            
        Returns:
            List of matching records
        """
        pass
