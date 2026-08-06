"""
Query Builder with SQL Injection Protection

Provides safe, optimized query building for SQLite Cloud with:
- Parameterized queries (no string concatenation)
- Batch operation support
- Query result caching
- Execution plan analysis

Performance Targets:
- Query building: < 1ms
- Batch operations: 80% reduction in round-trips
- Cache hit rate: > 70% for read operations
"""

import sqlite3
import hashlib
import json
import time
import logging
from typing import Optional, Dict, Any, List, Tuple, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import OrderedDict

logger = logging.getLogger(__name__)


class Operator(Enum):
    """SQL comparison operators"""
    EQ = '='
    NE = '!='
    LT = '<'
    LE = '<='
    GT = '>'
    GE = '>='
    LIKE = 'LIKE'
    IN = 'IN'
    NOT_IN = 'NOT IN'
    IS_NULL = 'IS NULL'
    IS_NOT_NULL = 'IS NOT NULL'
    BETWEEN = 'BETWEEN'


@dataclass
class QueryCondition:
    """Represents a WHERE condition"""
    column: str
    operator: Operator
    value: Any
    logical_op: str = 'AND'  # AND or OR
    
    def to_sql(self, param_offset: int = 0) -> Tuple[str, List[Any]]:
        """
        Convert condition to SQL with parameters
        
        Args:
            param_offset: Starting parameter index
            
        Returns:
            Tuple of (SQL fragment, parameter values)
        """
        if self.operator == Operator.IS_NULL:
            return f"{self.column} IS NULL", []
        elif self.operator == Operator.IS_NOT_NULL:
            return f"{self.column} IS NOT NULL", []
        elif self.operator == Operator.IN:
            placeholders = ','.join(['?' for _ in self.value])
            return f"{self.column} IN ({placeholders})", list(self.value)
        elif self.operator == Operator.NOT_IN:
            placeholders = ','.join(['?' for _ in self.value])
            return f"{self.column} NOT IN ({placeholders})", list(self.value)
        elif self.operator == Operator.BETWEEN:
            return f"{self.column} BETWEEN ? AND ?", [self.value[0], self.value[1]]
        else:
            return f"{self.column} {self.operator.value} ?", [self.value]


@dataclass
class OrderBy:
    """Represents an ORDER BY clause"""
    column: str
    ascending: bool = True


@dataclass
class QueryResult:
    """Wrapped query result with metadata"""
    rows: List[sqlite3.Row]
    columns: List[str]
    row_count: int
    execution_time_ms: float
    cached: bool = False
    query_hash: str = ""
    
    def to_dict_list(self) -> List[Dict[str, Any]]:
        """Convert rows to list of dictionaries"""
        return [dict(row) for row in self.rows]
    
    def first(self) -> Optional[Dict[str, Any]]:
        """Get first row as dictionary or None"""
        if self.rows:
            return dict(self.rows[0])
        return None
    
    def scalar(self) -> Any:
        """Get single scalar value from first row"""
        if self.rows and len(self.rows[0]) > 0:
            return self.rows[0][0]
        return None


class QueryCache:
    """
    LRU cache for query results with TTL
    
    Features:
    - Automatic expiration
    - Size limiting
    - Cache invalidation patterns
    """
    
    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = 60):
        """
        Initialize query cache
        
        Args:
            max_size: Maximum number of cached results
            default_ttl_seconds: Default time-to-live for cache entries
        """
        self.max_size = max_size
        self.default_ttl = timedelta(seconds=default_ttl_seconds)
        self._cache: OrderedDict[str, Tuple[Any, datetime]] = OrderedDict()
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, sql: str, params: tuple) -> str:
        """Generate cache key from SQL and parameters"""
        key_data = f"{sql}:{json.dumps(params, sort_keys=True, default=str)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, sql: str, params: tuple) -> Optional[QueryResult]:
        """
        Get cached result if available and not expired
        
        Args:
            sql: SQL query
            params: Query parameters
            
        Returns:
            Cached QueryResult or None
        """
        key = self._generate_key(sql, params)
        
        if key in self._cache:
            result, expires_at = self._cache[key]
            if datetime.now() < expires_at:
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                logger.debug(f"Cache hit for query: {key[:16]}...")
                return result
            else:
                # Expired, remove it
                del self._cache[key]
        
        self._misses += 1
        return None
    
    def set(self, sql: str, params: tuple, result: QueryResult, 
            ttl: Optional[timedelta] = None):
        """
        Cache a query result
        
        Args:
            sql: SQL query
            params: Query parameters
            result: QueryResult to cache
            ttl: Custom TTL (uses default if not specified)
        """
        key = self._generate_key(sql, params)
        expires_at = datetime.now() + (ttl or self.default_ttl)
        
        # Remove oldest if at capacity
        if len(self._cache) >= self.max_size:
            self._cache.popitem(last=False)
        
        self._cache[key] = (result, expires_at)
        logger.debug(f"Cached query: {key[:16]}...")
    
    def invalidate(self, pattern: Optional[str] = None):
        """
        Invalidate cache entries
        
        Args:
            pattern: Optional pattern to match keys (invalidates all if None)
        """
        if pattern is None:
            self._cache.clear()
            logger.info("Cache completely invalidated")
        else:
            # Remove matching keys
            to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in to_remove:
                del self._cache[key]
            logger.info(f"Invalidated {len(to_remove)} cache entries matching '{pattern}'")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        return {
            'size': len(self._cache),
            'max_size': self.max_size,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate_percent': round(hit_rate, 2),
            'default_ttl_seconds': self.default_ttl.total_seconds()
        }


class QueryBuilder:
    """
    Fluent query builder with SQL injection protection
    
    Features:
    - Method chaining
    - Parameterized queries
    - Batch operations
    - Result caching
    
    Usage:
        qb = QueryBuilder(conn)
        result = (qb
            .select('id', 'name', 'balance')
            .from_table('accounts')
            .where('party_id', Operator.EQ, party_id)
            .and_where('is_active', Operator.EQ, True)
            .order_by('name')
            .limit(100)
            .execute())
    """
    
    def __init__(self, connection: sqlite3.Connection, cache: Optional[QueryCache] = None):
        """
        Initialize query builder
        
        Args:
            connection: Database connection
            cache: Optional query cache
        """
        self.conn = connection
        self.cache = cache or QueryCache()
        self._reset()
    
    def _reset(self):
        """Reset builder state"""
        self._select_columns: List[str] = []
        self._from_table: Optional[str] = None
        self._joins: List[str] = []
        self._conditions: List[QueryCondition] = []
        self._order_by: List[OrderBy] = []
        self._limit: Optional[int] = None
        self._offset: Optional[int] = None
        self._params: List[Any] = []
        self._use_cache = True
        self._cache_ttl: Optional[timedelta] = None
    
    def select(self, *columns: str) -> 'QueryBuilder':
        """
        Set columns to select
        
        Args:
            columns: Column names or expressions
            
        Returns:
            Self for chaining
        """
        self._select_columns = list(columns)
        return self
    
    def select_all(self) -> 'QueryBuilder':
        """Select all columns"""
        self._select_columns = ['*']
        return self
    
    def from_table(self, table: str) -> 'QueryBuilder':
        """
        Set source table
        
        Args:
            table: Table name
            
        Returns:
            Self for chaining
        """
        self._from_table = table
        return self
    
    def join(self, table: str, on_condition: str, 
             join_type: str = 'INNER') -> 'QueryBuilder':
        """
        Add JOIN clause
        
        Args:
            table: Table to join
            on_condition: ON condition (e.g., "a.id = b.a_id")
            join_type: Type of join (INNER, LEFT, RIGHT, FULL)
            
        Returns:
            Self for chaining
        """
        self._joins.append(f"{join_type} JOIN {table} ON {on_condition}")
        return self
    
    def where(self, column: str, operator: Operator, value: Any) -> 'QueryBuilder':
        """
        Add WHERE condition with AND
        
        Args:
            column: Column name
            operator: Comparison operator
            value: Value to compare
            
        Returns:
            Self for chaining
        """
        self._conditions.append(QueryCondition(column, operator, value, 'AND'))
        return self
    
    def or_where(self, column: str, operator: Operator, value: Any) -> 'QueryBuilder':
        """
        Add WHERE condition with OR
        
        Args:
            column: Column name
            operator: Comparison operator
            value: Value to compare
            
        Returns:
            Self for chaining
        """
        self._conditions.append(QueryCondition(column, operator, value, 'OR'))
        return self
    
    def where_in(self, column: str, values: List[Any]) -> 'QueryBuilder':
        """Add WHERE IN condition"""
        self._conditions.append(QueryCondition(column, Operator.IN, values, 'AND'))
        return self
    
    def where_between(self, column: str, start: Any, end: Any) -> 'QueryBuilder':
        """Add WHERE BETWEEN condition"""
        self._conditions.append(QueryCondition(column, Operator.BETWEEN, (start, end), 'AND'))
        return self
    
    def where_null(self, column: str) -> 'QueryBuilder':
        """Add WHERE IS NULL condition"""
        self._conditions.append(QueryCondition(column, Operator.IS_NULL, None, 'AND'))
        return self
    
    def where_not_null(self, column: str) -> 'QueryBuilder':
        """Add WHERE IS NOT NULL condition"""
        self._conditions.append(QueryCondition(column, Operator.IS_NOT_NULL, None, 'AND'))
        return self
    
    def order_by(self, column: str, ascending: bool = True) -> 'QueryBuilder':
        """
        Add ORDER BY clause
        
        Args:
            column: Column to sort by
            ascending: True for ASC, False for DESC
            
        Returns:
            Self for chaining
        """
        self._order_by.append(OrderBy(column, ascending))
        return self
    
    def limit(self, limit: int) -> 'QueryBuilder':
        """Set LIMIT clause"""
        self._limit = limit
        return self
    
    def offset(self, offset: int) -> 'QueryBuilder':
        """Set OFFSET clause"""
        self._offset = offset
        return self
    
    def paginate(self, page: int, page_size: int) -> 'QueryBuilder':
        """
        Set pagination
        
        Args:
            page: Page number (1-indexed)
            page_size: Rows per page
            
        Returns:
            Self for chaining
        """
        self._limit = page_size
        self._offset = (page - 1) * page_size
        return self
    
    def disable_cache(self) -> 'QueryBuilder':
        """Disable query caching for this query"""
        self._use_cache = False
        return self
    
    def cache_ttl(self, seconds: int) -> 'QueryBuilder':
        """
        Set custom cache TTL
        
        Args:
            seconds: TTL in seconds
            
        Returns:
            Self for chaining
        """
        self._cache_ttl = timedelta(seconds=seconds)
        return self
    
    def _build_sql(self) -> Tuple[str, List[Any]]:
        """
        Build SQL query string and parameters
        
        Returns:
            Tuple of (SQL string, parameter list)
        """
        if not self._from_table:
            raise ValueError("Must specify table with from_table()")
        
        # SELECT clause
        columns = ', '.join(self._select_columns) if self._select_columns else '*'
        sql = f"SELECT {columns} FROM {self._from_table}"
        
        # JOIN clauses
        for join in self._joins:
            sql += f" {join}"
        
        # WHERE clause
        if self._conditions:
            where_parts = []
            params = []
            
            for i, cond in enumerate(self._conditions):
                cond_sql, cond_params = cond.to_sql(len(params))
                
                if i == 0:
                    where_parts.append(f"WHERE {cond_sql}")
                else:
                    where_parts.append(f"{cond.logical_op} {cond_sql}")
                
                params.extend(cond_params)
            
            sql += " " + " ".join(where_parts)
            self._params = params
        
        # ORDER BY clause
        if self._order_by:
            order_parts = []
            for order in self._order_by:
                direction = "ASC" if order.ascending else "DESC"
                order_parts.append(f"{order.column} {direction}")
            sql += " ORDER BY " + ", ".join(order_parts)
        
        # LIMIT clause
        if self._limit is not None:
            sql += f" LIMIT {self._limit}"
        
        # OFFSET clause
        if self._offset is not None:
            sql += f" OFFSET {self._offset}"
        
        return sql, self._params
    
    def execute(self, use_master: bool = False) -> QueryResult:
        """
        Execute the SELECT query
        
        Args:
            use_master: Force execution on master (for reads after writes)
            
        Returns:
            QueryResult with rows and metadata
            
        Raises:
            ValueError: If query is incomplete
        """
        sql, params = self._build_sql()
        
        # Try cache first
        if self._use_cache and not use_master:
            cached = self.cache.get(sql, tuple(params))
            if cached:
                cached.cached = True
                return cached
        
        # Execute query
        start_time = time.time()
        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        execution_time = (time.time() - start_time) * 1000
        
        # Fetch results
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        
        result = QueryResult(
            rows=rows,
            columns=columns,
            row_count=len(rows),
            execution_time_ms=execution_time,
            query_hash=hashlib.md5(f"{sql}:{params}".encode()).hexdigest()[:16]
        )
        
        # Cache result for SELECT queries
        if self._use_cache and sql.strip().upper().startswith('SELECT'):
            self.cache.set(sql, tuple(params), result, self._cache_ttl)
        
        logger.debug(f"Query executed in {execution_time:.2f}ms, {len(rows)} rows")
        
        # Reset builder for reuse
        self._reset()
        
        return result
    
    def execute_scalar(self) -> Any:
        """Execute and return single scalar value"""
        result = self.execute()
        return result.scalar()
    
    def execute_first(self) -> Optional[Dict[str, Any]]:
        """Execute and return first row as dict"""
        result = self.execute(limit=1)
        return result.first()
    
    def count(self, column: str = '*') -> int:
        """
        Execute COUNT query
        
        Args:
            column: Column to count (default *)
            
        Returns:
            Count value
        """
        original_select = self._select_columns.copy()
        self._select_columns = [f"COUNT({column})"]
        
        result = self.execute()
        
        # Restore original select
        self._select_columns = original_select
        
        return result.scalar() or 0
    
    def exists(self) -> bool:
        """Check if any rows match the criteria"""
        original_limit = self._limit
        self._limit = 1
        
        result = self.execute()
        
        # Restore original limit
        self._limit = original_limit
        
        return result.row_count > 0


class BulkOperations:
    """
    Batch operations for network efficiency
    
    Reduces round-trips by executing multiple operations in single batch
    """
    
    def __init__(self, connection: sqlite3.Connection, batch_size: int = 100):
        """
        Initialize bulk operations
        
        Args:
            connection: Database connection
            batch_size: Number of records per batch
        """
        self.conn = connection
        self.batch_size = batch_size
        self.logger = logging.getLogger(__name__)
    
    def bulk_insert(self, table: str, rows: List[Dict[str, Any]], 
                    ignore_duplicates: bool = False) -> int:
        """
        Insert multiple rows in a single batch
        
        Args:
            table: Target table name
            rows: List of dictionaries with column->value mappings
            ignore_duplicates: Use INSERT OR IGNORE instead of INSERT
            
        Returns:
            Number of rows inserted
            
        Example:
            rows = [
                {'name': 'Account1', 'type': 'Asset'},
                {'name': 'Account2', 'type': 'Liability'}
            ]
            count = bulk_ops.bulk_insert('accounts', rows)
        """
        if not rows:
            return 0
        
        # Get columns from first row
        columns = list(rows[0].keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_names = ', '.join(columns)
        
        insert_keyword = "INSERT OR IGNORE" if ignore_duplicates else "INSERT"
        sql = f"{insert_keyword} INTO {table} ({column_names}) VALUES ({placeholders})"
        
        # Prepare parameter tuples
        params = [tuple(row[col] for col in columns) for row in rows]
        
        # Execute in batches
        total_inserted = 0
        cursor = self.conn.cursor()
        
        for i in range(0, len(params), self.batch_size):
            batch = params[i:i + self.batch_size]
            cursor.executemany(sql, batch)
            total_inserted += cursor.rowcount
        
        self.conn.commit()
        self.logger.info(f"Bulk inserted {total_inserted} rows into {table}")
        
        return total_inserted
    
    def bulk_update(self, table: str, rows: List[Dict[str, Any]], 
                    key_column: str) -> int:
        """
        Update multiple rows in a single batch
        
        Args:
            table: Target table name
            rows: List of dictionaries with column->value mappings (must include key_column)
            key_column: Primary key column for WHERE clause
            
        Returns:
            Number of rows updated
            
        Example:
            rows = [
                {'id': 1, 'balance': 1000, 'updated_at': '2024-01-01'},
                {'id': 2, 'balance': 2000, 'updated_at': '2024-01-01'}
            ]
            count = bulk_ops.bulk_update('accounts', rows, key_column='id')
        """
        if not rows:
            return 0
        
        # Get columns to update (excluding key column)
        update_columns = [col for col in rows[0].keys() if col != key_column]
        
        if not update_columns:
            self.logger.warning("No columns to update")
            return 0
        
        # Build SET clause
        set_clause = ', '.join([f"{col} = ?" for col in update_columns])
        sql = f"UPDATE {table} SET {set_clause} WHERE {key_column} = ?"
        
        # Prepare parameter tuples (update values + key value)
        params = []
        for row in rows:
            update_values = tuple(row[col] for col in update_columns)
            key_value = row[key_column]
            params.append(update_values + (key_value,))
        
        # Execute in batches
        total_updated = 0
        cursor = self.conn.cursor()
        
        for i in range(0, len(params), self.batch_size):
            batch = params[i:i + self.batch_size]
            cursor.executemany(sql, batch)
            total_updated += cursor.rowcount
        
        self.conn.commit()
        self.logger.info(f"Bulk updated {total_updated} rows in {table}")
        
        return total_updated
    
    def bulk_delete(self, table: str, key_values: List[Any], 
                    key_column: str = 'id') -> int:
        """
        Delete multiple rows by key values
        
        Args:
            table: Target table name
            key_values: List of key values to delete
            key_column: Primary key column
            
        Returns:
            Number of rows deleted
            
        Example:
            deleted = bulk_ops.bulk_delete('accounts', [1, 2, 3], key_column='id')
        """
        if not key_values:
            return 0
        
        total_deleted = 0
        cursor = self.conn.cursor()
        
        # Execute in batches to avoid SQL parameter limits
        for i in range(0, len(key_values), self.batch_size):
            batch = key_values[i:i + self.batch_size]
            placeholders = ', '.join(['?' for _ in batch])
            sql = f"DELETE FROM {table} WHERE {key_column} IN ({placeholders})"
            
            cursor.execute(sql, batch)
            total_deleted += cursor.rowcount
        
        self.conn.commit()
        self.logger.info(f"Bulk deleted {total_deleted} rows from {table}")
        
        return total_deleted
    
    def find_all_by_ids(self, table: str, ids: List[Any], 
                        key_column: str = 'id',
                        columns: Optional[List[str]] = None) -> QueryResult:
        """
        Fetch multiple rows by ID in a single query
        
        Args:
            table: Target table name
            ids: List of IDs to fetch
            key_column: Primary key column
            columns: Columns to select (default: all)
            
        Returns:
            QueryResult with matching rows
        """
        if not ids:
            return QueryResult(rows=[], columns=[], row_count=0, execution_time_ms=0)
        
        # Split into batches to avoid SQL parameter limits
        all_rows = []
        columns_list = columns if columns else ['*']
        
        for i in range(0, len(ids), self.batch_size):
            batch = ids[i:i + self.batch_size]
            placeholders = ', '.join(['?' for _ in batch])
            column_names = ', '.join(columns_list)
            sql = f"SELECT {column_names} FROM {table} WHERE {key_column} IN ({placeholders})"
            
            cursor = self.conn.cursor()
            start_time = time.time()
            cursor.execute(sql, batch)
            execution_time = (time.time() - start_time) * 1000
            
            all_rows.extend(cursor.fetchall())
        
        # Build result
        columns = columns_list if columns_list != ['*'] else None
        if columns is None and all_rows:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [info[1] for info in cursor.fetchall()]
        
        return QueryResult(
            rows=all_rows,
            columns=columns or [],
            row_count=len(all_rows),
            execution_time_ms=execution_time
        )


class QueryOptimizer:
    """
    Analyze and optimize query performance
    
    Features:
    - Execution plan analysis
    - Index recommendations
    - Query rewriting suggestions
    """
    
    def __init__(self, connection: sqlite3.Connection):
        """
        Initialize query optimizer
        
        Args:
            connection: Database connection
        """
        self.conn = connection
        self.logger = logging.getLogger(__name__)
    
    def analyze_query(self, sql: str, params: tuple = ()) -> Dict[str, Any]:
        """
        Analyze query execution plan
        
        Args:
            sql: SQL query to analyze
            params: Query parameters
            
        Returns:
            Analysis results with recommendations
        """
        try:
            # Get EXPLAIN QUERY PLAN
            cursor = self.conn.cursor()
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}", params)
            plan_rows = cursor.fetchall()
            
            # Analyze plan
            uses_index = False
            full_scan = False
            temp_tables = False
            sorts = False
            
            for row in plan_rows:
                detail = str(row[-1]).upper()
                if 'USING INDEX' in detail or 'USING COVERING INDEX' in detail:
                    uses_index = True
                if 'SCAN TABLE' in detail or 'SCAN CURSOR' in detail:
                    full_scan = True
                if 'TEMP' in detail:
                    temp_tables = True
                if 'SORT' in detail:
                    sorts = True
            
            # Generate recommendations
            recommendations = []
            if full_scan and not uses_index:
                recommendations.append("Consider adding an index to avoid full table scan")
            if sorts:
                recommendations.append("Consider adding an index on ORDER BY columns")
            if temp_tables:
                recommendations.append("Query uses temporary tables - consider optimization")
            
            return {
                'sql': sql,
                'plan': [dict(zip(['id', 'parent', 'notused', 'detail'], row)) for row in plan_rows],
                'uses_index': uses_index,
                'full_scan': full_scan,
                'temp_tables': temp_tables,
                'sorts': sorts,
                'recommendations': recommendations,
                'performance_score': self._calculate_score(uses_index, full_scan, temp_tables, sorts)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze query: {e}")
            return {
                'sql': sql,
                'error': str(e),
                'performance_score': 0
            }
    
    def _calculate_score(self, uses_index: bool, full_scan: bool, 
                         temp_tables: bool, sorts: bool) -> int:
        """Calculate performance score (0-100)"""
        score = 100
        
        if full_scan:
            score -= 40
        if not uses_index and full_scan:
            score -= 20
        if temp_tables:
            score -= 15
        if sorts:
            score -= 10
        
        return max(0, min(100, score))
    
    def recommend_indexes(self, table: str) -> List[str]:
        """
        Recommend indexes for a table based on common query patterns
        
        Args:
            table: Table name to analyze
            
        Returns:
            List of recommended CREATE INDEX statements
        """
        recommendations = []
        cursor = self.conn.cursor()
        
        # Get table columns
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [info[1] for info in cursor.fetchall()]
        
        # Check for foreign key columns (common pattern: *_id)
        fk_columns = [col for col in columns if col.endswith('_id')]
        for col in fk_columns:
            idx_name = f"idx_{table}_{col}"
            recommendations.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({col})")
        
        # Check for common filter columns
        common_filter_cols = ['created_at', 'updated_at', 'status', 'type', 'date']
        for col in columns:
            if col in common_filter_cols or col.endswith('_at'):
                idx_name = f"idx_{table}_{col}"
                recommendations.append(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({col})")
        
        return recommendations
