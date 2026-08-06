"""Tests for QueryBuilder and related components."""
import pytest
from src.database.query_builder import QueryBuilder, QueryCache, BulkOperations


class TestQueryBuilder:
    """Test QueryBuilder functionality."""
    
    def test_select_basic(self):
        """Test basic SELECT query."""
        qb = QueryBuilder().select('*').from_('accounts')
        sql, params = qb.build()
        
        assert 'SELECT * FROM accounts' in sql
        assert params == []
    
    def test_select_with_where(self):
        """Test SELECT with WHERE clause."""
        qb = (QueryBuilder()
              .select('code', 'name')
              .from_('accounts')
              .where('account_type', '=', 'ASSET')
              .where('is_active', '=', True))
        sql, params = qb.build()
        
        assert 'SELECT code, name FROM accounts' in sql
        assert 'WHERE account_type = ? AND is_active = ?' in sql
        assert params == ['ASSET', True]
    
    def test_insert_query(self):
        """Test INSERT query."""
        qb = QueryBuilder().insert('accounts', {
            'code': '1001',
            'name': 'Cash',
            'account_type': 'ASSET'
        })
        sql, params = qb.build()
        
        assert 'INSERT INTO accounts' in sql
        assert len(params) == 3
    
    def test_update_query(self):
        """Test UPDATE query."""
        qb = (QueryBuilder()
              .update('accounts')
              .set({'name': 'Updated Cash'})
              .where('code', '=', '1001'))
        sql, params = qb.build()
        
        assert 'UPDATE accounts SET name = ?' in sql
        assert 'WHERE code = ?' in sql
        assert params == ['Updated Cash', '1001']
    
    def test_delete_query(self):
        """Test DELETE query."""
        qb = (QueryBuilder()
              .delete('accounts')
              .where('code', '=', '1001'))
        sql, params = qb.build()
        
        assert 'DELETE FROM accounts' in sql
        assert params == ['1001']
    
    def test_join_query(self):
        """Test JOIN query."""
        qb = (QueryBuilder()
              .select('a.code', 'a.name', 'p.name')
              .from_('accounts a')
              .join('parties p', 'a.party_id', '=', 'p.id')
              .where('a.is_active', '=', True))
        sql, params = qb.build()
        
        assert 'JOIN parties p ON a.party_id = p.id' in sql
    
    def test_order_by_limit_offset(self):
        """Test ORDER BY, LIMIT, OFFSET."""
        qb = (QueryBuilder()
              .select('*')
              .from_('accounts')
              .order_by('code', 'ASC')
              .limit(10)
              .offset(20))
        sql, params = qb.build()
        
        assert 'ORDER BY code ASC' in sql
        assert 'LIMIT 10' in sql
        assert 'OFFSET 20' in sql
    
    def test_sql_injection_protection(self):
        """Test SQL injection protection."""
        malicious_input = "'; DROP TABLE accounts; --"
        qb = (QueryBuilder()
              .select('*')
              .from_('accounts')
              .where('name', '=', malicious_input))
        sql, params = qb.build()
        
        # Should use parameterized query, not string concatenation
        assert '?' in sql
        assert params == [malicious_input]
        assert 'DROP TABLE' not in sql


class TestQueryCache:
    """Test QueryCache functionality."""
    
    def test_cache_set_get(self):
        """Test basic cache operations."""
        cache = QueryCache(max_size=100, ttl_seconds=60)
        
        cache.set('test_key', 'test_value')
        result = cache.get('test_key')
        
        assert result == 'test_value'
    
    def test_cache_ttl_expiration(self):
        """Test cache TTL expiration."""
        cache = QueryCache(max_size=100, ttl_seconds=1)
        
        cache.set('short_lived', 'value')
        
        import time
        time.sleep(1.1)  # Wait for expiration
        
        result = cache.get('short_lived')
        assert result is None
    
    def test_cache_max_size_eviction(self):
        """Test LRU eviction when max size reached."""
        cache = QueryCache(max_size=3, ttl_seconds=60)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        cache.set('key3', 'value3')
        
        # Add one more, should evict key1 (oldest)
        cache.set('key4', 'value4')
        
        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert cache.get('key4') == 'value4'
    
    def test_cache_clear(self):
        """Test cache clearing."""
        cache = QueryCache(max_size=100, ttl_seconds=60)
        
        cache.set('key1', 'value1')
        cache.set('key2', 'value2')
        
        cache.clear()
        
        assert cache.get('key1') is None
        assert cache.get('key2') is None
        assert cache.stats()['hits'] == 0
        assert cache.stats()['misses'] == 0


class TestBulkOperations:
    """Test bulk operation functionality."""
    
    def test_bulk_insert_sql_generation(self):
        """Test bulk INSERT SQL generation."""
        records = [
            {'code': '1001', 'name': 'Cash'},
            {'code': '1002', 'name': 'Bank'},
            {'code': '1003', 'name': 'Receivables'}
        ]
        
        sql, params = BulkOperations.bulk_insert('accounts', records)
        
        assert 'INSERT INTO accounts' in sql
        assert sql.count('?') == 6  # 2 fields × 3 records
        assert len(params) == 6
    
    def test_bulk_update_sql_generation(self):
        """Test bulk UPDATE SQL generation."""
        records = [
            {'id': 1, 'name': 'Updated1'},
            {'id': 2, 'name': 'Updated2'}
        ]
        
        sql, params = BulkOperations.bulk_update('accounts', records, 'id')
        
        assert 'UPDATE accounts' in sql
        assert 'WHERE id IN (?, ?)' in sql
    
    def test_bulk_delete_sql_generation(self):
        """Test bulk DELETE SQL generation."""
        ids = [1, 2, 3, 4, 5]
        
        sql, params = BulkOperations.bulk_delete('accounts', 'id', ids)
        
        assert 'DELETE FROM accounts' in sql
        assert 'WHERE id IN (?, ?, ?, ?, ?)' in sql
        assert len(params) == 5
    
    def test_empty_records_handling(self):
        """Test handling of empty record lists."""
        sql, params = BulkOperations.bulk_insert('accounts', [])
        
        assert sql == ''
        assert params == []
