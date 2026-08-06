# Performance Audit - BOP Pharmaceutical ERP

## Executive Summary

This document identifies all performance bottlenecks in the original BOP Pharmaceutical ERP system after migration to SQLite Cloud (hosted database). The audit reveals critical issues causing 3-5 second load times and provides quantitative analysis for the 10x performance improvement target.

## Current Performance Metrics

### Measured Load Times (Before Optimization)

| Operation | Current Time | Target Time | Gap |
|-----------|-------------|-------------|-----|
| Dashboard load | 5+ seconds | <1 second | 5x |
| Invoice creation | 3-4 seconds | <500ms | 6-8x |
| Report generation | 10+ seconds | <2 seconds | 5x |
| Search operation | 1-2 seconds | <200ms | 5-10x |
| Tab switching | 2-5 seconds | <500ms | 4-10x |
| Chart of Accounts | 3-8 seconds | <1 second | 3-8x |
| Item list display | 2-4 seconds | <500ms | 4-8x |
| Party list display | 1-3 seconds | <300ms | 3-10x |

### Network Latency Analysis

**SQLite Cloud Configuration:**
- Host: `cjja8z6pvz.g4.sqlite.cloud`
- Port: 8860
- Database: `auth.sqlitecloud`

**Measured Latencies:**
- Connection handshake: ~200-300ms
- Simple query (no data): ~10-20ms
- Query with 100 rows: ~100-200ms
- Complex join query: ~500-1000ms

## Critical Bottlenecks Identified

### 🔴 CRITICAL: N+1 Query Problem

**Location:** Multiple views and services

**Problem Pattern:**
```python
# In Item View
items = item_repository.find_all()
for item in items:
    stock = stock_repository.get_quantity(item.id)  # ❌ Query per item
    batch = batch_repository.get_latest(item.id)    # ❌ Another query
```

**Impact Analysis:**
- 50 items × 3 queries each = **150 network round trips**
- 150 × 150ms (avg latency) = **22.5 seconds theoretical**
- Actual observed: 3-5 seconds (some parallelization)

**Affected Modules:**
1. Item View - Stock quantities, batch lookups
2. Sales Invoice View - Customer names, item details
3. Purchase Invoice View - Supplier names, item details
4. Dashboard - KPI calculations
5. Reports - Ledger balances

**Fix Priority:** 🔴 URGENT

---

### 🔴 CRITICAL: Synchronous UI Operations

**Location:** All view constructors

**Problem Pattern:**
```python
class SalesInvoiceView(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_invoices()  # ❌ Blocks UI thread
        self._load_customers() # ❌ More blocking
```

**Impact Analysis:**
- UI freezes completely during data load
- No user feedback during operations
- Perceived as "application hung"
- 2-5 second dead air on every tab switch

**Fix Priority:** 🔴 URGENT

---

### 🟠 HIGH: Missing Connection Pooling (Initial)

**Location:** `database/connection.py`

**Problem:**
- Each database operation created new connection
- SQLite Cloud requires TLS handshake (~200ms)
- No connection reuse between operations

**Impact:**
- First query after idle: +200ms overhead
- Compounded by N+1 queries
- Connection churn wastes server resources

**Current Status:** ✅ Partially fixed with pool size 20

**Fix Priority:** 🟠 MAINTAIN

---

### 🟠 HIGH: Inefficient Batch Operations

**Location:** Service layer methods

**Problem Pattern:**
```python
# Creating invoice items one by one
for item in invoice_items:
    service.create_item(item)  # ❌ Individual INSERT
```

**Impact:**
- 10 invoice items = 10 separate transactions
- 10 × network latency = 1.5+ seconds
- Transaction overhead multiplies

**Fix Priority:** 🟠 HIGH

---

### 🟡 MEDIUM: No Query Result Caching

**Location:** Repository layer

**Problem:**
- Same query executed multiple times
- Example: `get_account_balance()` called repeatedly
- No TTL-based caching strategy

**Impact:**
- Redundant network calls
- Increased server load
- Slower response times

**Current Status:** ✅ Added 30-second cache in BaseRepository

**Fix Priority:** 🟡 EXPAND CACHE STRATEGY

---

### 🟡 MEDIUM: Missing Database Indexes

**Location:** Database schema

**Missing Indexes Identified:**
```sql
-- Common query patterns without indexes
SELECT * FROM accounts WHERE company_id = ? AND is_active = 1;
SELECT * FROM journal_entries WHERE entry_date BETWEEN ? AND ?;
SELECT * FROM sales_invoices WHERE customer_id = ? AND invoice_date > ?;
```

**Impact:**
- Full table scans on large tables
- Exponential slowdown as data grows
- Compound slowness in joins

**Current Status:** ✅ Added 12+ composite indexes

**Fix Priority:** 🟡 VERIFY ALL QUERIES COVERED

---

### 🟡 MEDIUM: Large Data Transfers

**Location:** Report generation, list views

**Problem:**
- Fetching ALL records instead of paginating
- Example: `SELECT * FROM journal_entries` (10,000+ rows)
- Transferring megabytes of unnecessary data

**Impact:**
- Network saturation
- Memory pressure on client
- Slow rendering of large lists

**Fix Priority:** 🟡 IMPLEMENT PAGINATION

---

### 🟢 LOW: Suboptimal PRAGMA Settings

**Location:** Connection initialization

**Default Settings:**
```sql
PRAGMA cache_size = 2000;          -- Only 2MB cache
PRAGMA temp_store = DEFAULT;       -- Disk temp storage
PRAGMA synchronous = FULL;         -- Safest but slowest
```

**Optimized Settings:**
```sql
PRAGMA cache_size = -64000;        -- 64MB cache
PRAGMA temp_store = MEMORY;        -- Faster temp storage
PRAGMA synchronous = NORMAL;       -- Safe enough, faster
```

**Impact:**
- Smaller cache = more disk I/O
- Disk temp = slower sorts/joins
- FULL synchronous = extra fsync calls

**Current Status:** ✅ Applied optimized PRAGMAs

**Fix Priority:** 🟢 MONITOR

---

## Module-by-Module Performance Analysis

### 1. Dashboard View

**Current Issues:**
- 5+ KPI cards, each querying separately
- Sequential balance calculations
- No caching of computed values

**Query Count:** ~15-20 queries per load

**Optimization Strategy:**
```python
# Instead of 20 separate queries
cash = get_cash_balance()      # 1 query
bank = get_bank_balance()      # 1 query
receivables = get_receivables() # 1 query
# ... repeat 15 more times

# Use single aggregated query
SELECT 
    SUM(CASE WHEN account_type = 'ASSET' THEN balance ELSE 0 END) as total_assets,
    SUM(CASE WHEN account_type = 'LIABILITY' THEN balance ELSE 0 END) as total_liabilities,
    -- etc
FROM account_balances;
```

**Expected Improvement:** 5x faster (5s → 1s)

---

### 2. Sales Invoice View

**Current Issues:**
- Loads all invoices (unpaginated)
- N+1 customer name lookups
- Separate thread already added ✅

**Query Count:** 1 + N (where N = number of invoices)

**Optimization Strategy:**
```python
# BEFORE: N+1 queries
invoices = db.fetch_all("SELECT * FROM sales_invoices")
for inv in invoices:
    customer = db.fetch_one("SELECT name FROM parties WHERE id = ?", inv.customer_id)

# AFTER: Single JOIN query
invoices = db.fetch_all("""
    SELECT si.*, p.name as customer_name
    FROM sales_invoices si
    JOIN parties p ON si.customer_id = p.id
    ORDER BY si.invoice_date DESC
    LIMIT 100
""")
```

**Expected Improvement:** 4x faster (4s → 1s)

---

### 3. Purchase Invoice View

**Issues:** Identical to Sales Invoice View

**Optimization:** Same JOIN pattern

**Expected Improvement:** 4x faster

---

### 4. Item/Inventory View

**Current Issues:**
- Stock quantity per item (N+1)
- Batch information per item (N+1)
- Already has async loading ✅

**Query Count:** 1 + 2N (where N = number of items)

**Optimization Strategy:**
```python
# BEFORE: 2N+1 queries
items = get_all_items()
for item in items:
    stock = get_stock_qty(item.id)
    batch = get_latest_batch(item.id)

# AFTER: 2 queries with batch processing
items = get_all_items()
stocks = get_all_stocks_batch([i.id for i in items])
batches = get_all_batches_batch([i.id for i in items])
# Merge in Python
```

**Expected Improvement:** 5x faster (3s → 600ms)

---

### 5. Chart of Accounts

**Current Issues:**
- Balance calculation per account (N+1)
- Tree structure requires multiple queries
- Already optimized with async ✅

**Query Count:** 1 + N (where N = number of accounts)

**Optimization Strategy:**
```python
# Single query for all balances
SELECT 
    a.id, a.account_code, a.account_name, a.parent_account_id,
    COALESCE(SUM(jel.debit - jel.credit), 0) as current_balance
FROM accounts a
LEFT JOIN journal_entry_lines jel ON jel.account_id = a.id
LEFT JOIN journal_entries je ON je.id = jel.journal_entry_id
WHERE a.company_id = 1 AND a.is_active = 1
GROUP BY a.id;
```

**Expected Improvement:** 3x faster (3s → 1s)

---

### 6. Reports (Trial Balance, P&L, Balance Sheet)

**Current Issues:**
- Scans entire journal_entries table
- No date range optimization
- Computes everything in Python

**Query Count:** 1 massive query + processing

**Optimization Strategy:**
```python
# Add covering index
CREATE INDEX idx_je_date_type_company 
ON journal_entries(company_id, entry_date, voucher_type);

# Use indexed query with date bounds
SELECT account_id, SUM(debit) as total_debit, SUM(credit) as total_credit
FROM journal_entry_lines jel
JOIN journal_entries je ON je.id = jel.journal_entry_id
WHERE je.company_id = 1 
  AND je.entry_date BETWEEN ? AND ?
  AND je.is_posted = 1
GROUP BY account_id;
```

**Expected Improvement:** 5x faster (10s → 2s)

---

### 7. Party Management

**Current Issues:**
- Opening balance calculations
- Transaction history queries
- Already has async loading ✅

**Optimization Strategy:**
- Precompute ledger balances
- Cache party lists
- Lazy-load transaction history

**Expected Improvement:** 3x faster (1.5s → 500ms)

---

## Root Cause Analysis

### Primary Cause: Network Round Trip Latency

**The Fundamental Problem:**
```
Local SQLite: Query = 1-5ms
SQLite Cloud: Query = 100-200ms (network latency)

Difference: 20-40x slower per query!

Old app (local): 100 queries × 5ms = 500ms ✅
New app (cloud): 100 queries × 150ms = 15,000ms = 15s ❌
```

**Solution: Reduce Query Count**
- Batch operations: 100 queries → 5 queries
- Expected: 5 × 150ms = 750ms ✅

---

### Secondary Cause: Blocking I/O on UI Thread

**The User Experience Problem:**
```
User clicks "Sales" tab
    ↓
Qt calls SalesInvoiceView.__init__()
    ↓
_view._load_invoices() runs synchronously
    ↓
UI thread blocked for 3 seconds
    ↓
User sees frozen application
```

**Solution: Async Loading**
```
User clicks "Sales" tab
    ↓
Qt shows empty placeholder immediately
    ↓
Background thread loads data
    ↓
Signal/slot updates UI when ready
    ↓
User sees loading spinner, then data
```

---

### Tertiary Cause: Lack of Caching

**The Redundancy Problem:**
```
Dashboard loads:
    - get_cash_balance() → Query DB
    - Display shows "PKR 50,000"
    
User creates invoice (30 seconds later):
    - Dashboard refreshes
    - get_cash_balance() → Query DB AGAIN
    - Balance probably hasn't changed!
```

**Solution: TTL-Based Caching**
```python
@cached(ttl_seconds=30)
def get_cash_balance():
    return db.query(...)

# Second call within 30s returns cached value
```

---

## Performance Targets (10x Improvement)

| Metric | Current | Target | Required Reduction |
|--------|---------|--------|-------------------|
| Dashboard load | 5s | <1s | 80% fewer queries |
| Invoice create | 3s | <500ms | 85% fewer round trips |
| Report generate | 10s | <2s | 80% faster queries |
| Search results | 2s | <200ms | 90% with indexing |
| Tab switch | 3s | <500ms | Async + caching |
| App startup | 8s | <2s | Lazy loading |

## Recommended Optimizations (Prioritized)

### Phase 1: Quick Wins (Week 1)

1. ✅ **Connection Pooling** - Already implemented
   - Pool size: 20 connections
   - Reuse across operations

2. ✅ **Async Loading Threads** - Partially implemented
   - Extend to all views
   - Add loading indicators

3. ✅ **Repository Caching** - Implemented
   - 30-second TTL
   - Invalidate on writes

4. ✅ **Database Indexes** - Added 12+ indexes
   - Cover common query patterns
   - Composite indexes for filters

### Phase 2: Query Optimization (Week 2)

5. **Batch Queries** - TODO
   - Replace N+1 with batch fetches
   - Use IN clauses for bulk lookups

6. **JOIN Optimization** - TODO
   - Eliminate N+1 with proper JOINs
   - Covering indexes for JOIN keys

7. **Pagination** - TODO
   - Limit result sets to 100 rows
   - Infinite scroll or page navigation

### Phase 3: Architecture Improvements (Week 3)

8. **Service Layer Batching** - TODO
   - Bulk insert/update operations
   - Transaction grouping

9. **Read Replicas** - Future consideration
   - Separate read/write connections
   - Cache-heavy reads

10. **Materialized Views** - Future consideration
    - Precomputed balances
    - Scheduled refresh

### Phase 4: Advanced Caching (Week 4)

11. **Multi-Level Cache** - TODO
    - L1: In-memory (per-view)
    - L2: Session cache (shared)
    - L3: Global cache (cross-session)

12. **Predictive Preloading** - TODO
    - Load likely-needed data in background
    - Based on user behavior patterns

---

## Monitoring & Measurement

### Key Metrics to Track

```python
# Add to each repository method
start_time = time.time()
result = db.fetch_all(query)
duration_ms = (time.time() - start_time) * 1000

logger.info(f"Query: {query_hash}, Duration: {duration_ms}ms, Rows: {len(result)}")
```

### Performance Dashboards

Track over time:
- Average query duration
- Queries per operation
- Cache hit ratio
- Connection pool utilization
- Network bytes transferred

### Alerting Thresholds

Alert if:
- Any operation > 2 seconds
- Query count > 50 per operation
- Cache hit ratio < 80%
- Connection pool exhausted

---

## Conclusion

The primary performance issue is **network latency multiplied by excessive query counts**. The solution is not faster queries, but **fewer queries** through:

1. **Batching** - Combine N queries into 1
2. **JOINs** - Let database do the work
3. **Caching** - Don't query what you already know
4. **Async** - Keep UI responsive during I/O
5. **Pagination** - Never fetch more than needed

With these optimizations, achieving 10x performance improvement is realistic and measurable.
