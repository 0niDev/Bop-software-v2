"""
Database Layer for BOP Pharmaceutical ERP

This module provides optimized database operations for SQLite Cloud with:
- Connection pooling with health checking
- Query building with SQL injection protection
- Transaction management with retry logic
- Batch operations for network efficiency

Architecture: Network-first design assuming 50-200ms latency
"""

__version__ = "2.0.0"
__author__ = "BOP Software Team"
