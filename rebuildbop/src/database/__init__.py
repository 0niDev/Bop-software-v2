"""
Database package for BOP Pharmaceutical ERP.

This package provides SQLite Cloud database connectivity with:
- Connection pooling for performance
- Transaction management
- Async query execution support
"""

from src.database.connection import get_db, close_db
from src.database.sqlitecloud_connection import SQLiteCloudConnection

__all__ = [
    'get_db',
    'close_db',
    'SQLiteCloudConnection',
]
