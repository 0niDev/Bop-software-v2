# BOP Pharmaceutical ERP - Database Schema Design

## Overview

This document defines the complete database schema for the rebuilt BOP Pharmaceutical ERP system, optimized for SQLite Cloud with comprehensive indexing for network performance.

## Design Principles

1. **Multi-Tenancy Ready**: All business tables include `company_id` for future multi-company support
2. **Soft Deletes**: Historical data preserved via `is_active` flags
3. **Audit Trail**: All modifications tracked with timestamps and user context
4. **Double-Entry Integrity**: Every financial transaction flows through journal_entries
5. **Network Optimized**: Comprehensive indexes to minimize query time over network
6. **Data Validation**: CHECK constraints enforce business rules at database level

## Schema Version

**Version**: 2.0 (Rebuild)  
**Database Engine**: SQLite Cloud  
**Compatibility**: SQLite 3.35+

---

## Table Definitions

### 1. Multi-Tenancy Foundation

#### companies
```sql
CREATE TABLE IF NOT EXISTS companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    address         TEXT,
    phone           TEXT,
    email           TEXT,
    ntn             TEXT,              -- National Tax Number
    logo_path       TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_companies_active ON companies(is_active);
```

#### warehouses
```sql
CREATE TABLE IF NOT EXISTS warehouses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    address         TEXT,
    is_default      INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_warehouses_company ON warehouses(company_id, is_active);
```

### 2. Authentication & Authorization

#### roles
```sql
CREATE TABLE IF NOT EXISTS roles (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### permissions
```sql
CREATE TABLE IF NOT EXISTS permissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT NOT NULL UNIQUE,
    description     TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

#### role_permissions
```sql
CREATE TABLE IF NOT EXISTS role_permissions (
    role_id         INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_permission ON role_permissions(permission_id);
```

#### users
```sql
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    password_salt   TEXT NOT NULL,
    full_name       TEXT NOT NULL,
    email           TEXT,
    role_id         INTEGER NOT NULL REFERENCES roles(id),
    is_active       INTEGER NOT NULL DEFAULT 1,
    last_login_at   TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role_id, is_active);
```

### 3. Chart of Accounts (Core Accounting)

#### accounts
```sql
CREATE TABLE IF NOT EXISTS accounts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    account_code        TEXT NOT NULL,
    account_name        TEXT NOT NULL,
    parent_account_id   INTEGER REFERENCES accounts(id),
    account_type        TEXT NOT NULL CHECK (account_type IN 
                          ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')),
    account_subtype     TEXT,
    opening_balance     REAL NOT NULL DEFAULT 0,
    is_system_account   INTEGER NOT NULL DEFAULT 0,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, account_code)
);

-- Indexes for chart of accounts queries
CREATE INDEX IF NOT EXISTS idx_accounts_company_code ON accounts(company_id, account_code);
CREATE INDEX IF NOT EXISTS idx_accounts_company_active ON accounts(company_id, is_active);
CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(account_type);
CREATE INDEX IF NOT EXISTS idx_accounts_parent ON accounts(parent_account_id);
CREATE INDEX IF NOT EXISTS idx_accounts_company_type ON accounts(company_id, account_type);
```

### 4. General Ledger (Double-Entry Core)

#### journal_entries
```sql
CREATE TABLE IF NOT EXISTS journal_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    voucher_number  TEXT NOT NULL,
    voucher_type    TEXT NOT NULL CHECK (voucher_type IN 
                      ('JOURNAL','SALES','SALES_RETURN','PURCHASE','PURCHASE_RETURN',
                       'PAYMENT','RECEIPT','MANUFACTURING','STOCK_ADJUSTMENT','OPENING')),
    entry_date      TEXT NOT NULL,
    reference_no    TEXT,
    narration       TEXT,
    source_table    TEXT,
    source_id       INTEGER,
    is_posted       INTEGER NOT NULL DEFAULT 1,
    created_by      INTEGER REFERENCES users(id),
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, voucher_number)
);

-- Critical indexes for journal entry queries
CREATE INDEX IF NOT EXISTS idx_je_company_date ON journal_entries(company_id, entry_date);
CREATE INDEX IF NOT EXISTS idx_je_company_type ON journal_entries(company_id, voucher_type);
CREATE INDEX IF NOT EXISTS idx_je_source ON journal_entries(source_table, source_id);
CREATE INDEX IF NOT EXISTS idx_je_posted_company ON journal_entries(is_posted, company_id);
CREATE INDEX IF NOT EXISTS idx_je_date_range ON journal_entries(entry_date DESC);
CREATE INDEX IF NOT EXISTS idx_je_voucher_lookup ON journal_entries(company_id, voucher_number);
```

#### journal_entry_lines
```sql
CREATE TABLE IF NOT EXISTS journal_entry_lines (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_entry_id    INTEGER NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE,
    account_id          INTEGER NOT NULL REFERENCES accounts(id),
    party_id            INTEGER REFERENCES parties(id),
    debit               REAL NOT NULL DEFAULT 0,
    credit              REAL NOT NULL DEFAULT 0,
    description         TEXT,
    line_order          INTEGER NOT NULL DEFAULT 0,
    CHECK (debit >= 0 AND credit >= 0),
    CHECK (NOT (debit > 0 AND credit > 0))
);

-- Indexes for ledger queries and balance calculations
CREATE INDEX IF NOT EXISTS idx_jel_journal_entry ON journal_entry_lines(journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_jel_account ON journal_entry_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_jel_party ON journal_entry_lines(party_id) WHERE party_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_jel_account_je ON journal_entry_lines(account_id, journal_entry_id);
CREATE INDEX IF NOT EXISTS idx_jel_account_period ON journal_entry_lines(account_id, debit, credit);
```

### 5. Party Management (Customers/Suppliers)

#### parties
```sql
CREATE TABLE IF NOT EXISTS parties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    party_type      TEXT NOT NULL CHECK (party_type IN ('CUSTOMER','SUPPLIER','BOTH')),
    customer_category TEXT CHECK (customer_category IN ('FARMER','INDIVIDUAL','BUSINESS')),
    phone           TEXT,
    address         TEXT,
    email           TEXT,
    opening_balance REAL NOT NULL DEFAULT 0,
    credit_limit    REAL NOT NULL DEFAULT 0,
    account_id      INTEGER REFERENCES accounts(id),
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, code)
);

-- Indexes for party lookups
CREATE INDEX IF NOT EXISTS idx_parties_company_code ON parties(company_id, code);
CREATE INDEX IF NOT EXISTS idx_parties_company_type ON parties(company_id, party_type);
CREATE INDEX IF NOT EXISTS idx_parties_company_active ON parties(company_id, is_active);
CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(name);
CREATE INDEX IF NOT EXISTS idx_parties_account ON parties(account_id);
```

### 6. Inventory Management

#### item_categories
```sql
CREATE TABLE IF NOT EXISTS item_categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    code            TEXT NOT NULL,
    name            TEXT NOT NULL,
    parent_id       INTEGER REFERENCES item_categories(id),
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, code)
);

CREATE INDEX IF NOT EXISTS idx_item_categories_company ON item_categories(company_id, is_active);
```

#### items
```sql
CREATE TABLE IF NOT EXISTS items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    item_code           TEXT NOT NULL,
    item_name           TEXT NOT NULL,
    category_id         INTEGER REFERENCES item_categories(id),
    unit_of_measure     TEXT NOT NULL DEFAULT 'PCS',
    sale_price          REAL NOT NULL DEFAULT 0,
    purchase_price      REAL NOT NULL DEFAULT 0,
    reorder_level       REAL NOT NULL DEFAULT 0,
    tax_rate            REAL NOT NULL DEFAULT 0,
    is_batch_tracked    INTEGER NOT NULL DEFAULT 1,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, item_code)
);

-- Indexes for item lookups
CREATE INDEX IF NOT EXISTS idx_items_company_code ON items(company_id, item_code);
CREATE INDEX IF NOT EXISTS idx_items_company_active ON items(company_id, is_active);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);
CREATE INDEX IF NOT EXISTS idx_items_company_category ON items(company_id, category_id);
```

#### stock_batches
```sql
CREATE TABLE IF NOT EXISTS stock_batches (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    item_id             INTEGER NOT NULL REFERENCES items(id),
    warehouse_id        INTEGER NOT NULL REFERENCES warehouses(id),
    batch_number        TEXT NOT NULL,
    manufacture_date    TEXT,
    expiry_date         TEXT,
    quantity_in_stock   REAL NOT NULL DEFAULT 0,
    unit_cost           REAL NOT NULL DEFAULT 0,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, item_id, batch_number, warehouse_id)
);

-- Critical indexes for stock queries
CREATE INDEX IF NOT EXISTS idx_stock_item_warehouse ON stock_batches(item_id, warehouse_id);
CREATE INDEX IF NOT EXISTS idx_stock_item_active ON stock_batches(item_id, is_active);
CREATE INDEX IF NOT EXISTS idx_stock_company_item ON stock_batches(company_id, item_id);
CREATE INDEX IF NOT EXISTS idx_stock_expiry ON stock_batches(expiry_date);
```

#### stock_movements
```sql
CREATE TABLE IF NOT EXISTS stock_movements (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    item_id             INTEGER NOT NULL REFERENCES items(id),
    batch_id            INTEGER REFERENCES stock_batches(id),
    warehouse_id        INTEGER NOT NULL REFERENCES warehouses(id),
    movement_type       TEXT NOT NULL CHECK (movement_type IN 
                          ('RECEIPT','ISSUE','ADJUSTMENT','TRANSFER','RETURN')),
    quantity            REAL NOT NULL,
    unit_cost           REAL NOT NULL DEFAULT 0,
    total_value         REAL NOT NULL DEFAULT 0,
    reference_type      TEXT,
    reference_id        INTEGER,
    notes               TEXT,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for stock movement tracking
CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id, created_at);
CREATE INDEX IF NOT EXISTS idx_stock_movements_batch ON stock_movements(batch_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_reference ON stock_movements(reference_type, reference_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_company ON stock_movements(company_id, created_at);
```

### 7. Sales Management

#### sales_invoices
```sql
CREATE TABLE IF NOT EXISTS sales_invoices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    invoice_number      TEXT NOT NULL,
    customer_id         INTEGER NOT NULL REFERENCES parties(id),
    invoice_date        TEXT NOT NULL,
    payment_type        TEXT NOT NULL CHECK (payment_type IN ('CASH','BANK','CHEQUE','CREDIT')),
    bank_account_id     INTEGER REFERENCES bank_accounts(id),
    warehouse_id        INTEGER NOT NULL REFERENCES warehouses(id),
    subtotal            REAL NOT NULL DEFAULT 0,
    discount_amount     REAL NOT NULL DEFAULT 0,
    tax_amount          REAL NOT NULL DEFAULT 0,
    total_amount        REAL NOT NULL DEFAULT 0,
    notes               TEXT,
    status              TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, invoice_number)
);

-- Indexes for sales queries
CREATE INDEX IF NOT EXISTS idx_sales_company_customer ON sales_invoices(company_id, customer_id);
CREATE INDEX IF NOT EXISTS idx_sales_company_date ON sales_invoices(company_id, invoice_date);
CREATE INDEX IF NOT EXISTS idx_sales_company_status ON sales_invoices(company_id, status);
CREATE INDEX IF NOT EXISTS idx_sales_customer_date ON sales_invoices(customer_id, invoice_date);
CREATE INDEX IF NOT EXISTS idx_sales_invoice_lookup ON sales_invoices(company_id, invoice_number);
```

#### sales_invoice_items
```sql
CREATE TABLE IF NOT EXISTS sales_invoice_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id          INTEGER NOT NULL REFERENCES sales_invoices(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL REFERENCES items(id),
    batch_id            INTEGER REFERENCES stock_batches(id),
    quantity            REAL NOT NULL DEFAULT 0,
    unit_price          REAL NOT NULL DEFAULT 0,
    discount_amount     REAL NOT NULL DEFAULT 0,
    tax_amount          REAL NOT NULL DEFAULT 0,
    line_total          REAL NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for invoice item queries
CREATE INDEX IF NOT EXISTS idx_sii_invoice ON sales_invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_sii_item ON sales_invoice_items(item_id);
CREATE INDEX IF NOT EXISTS idx_sii_batch ON sales_invoice_items(batch_id);
```

#### sales_returns
```sql
CREATE TABLE IF NOT EXISTS sales_returns (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    return_number       TEXT NOT NULL,
    invoice_id          INTEGER NOT NULL REFERENCES sales_invoices(id),
    customer_id         INTEGER NOT NULL REFERENCES parties(id),
    return_date         TEXT NOT NULL,
    reason              TEXT,
    total_amount        REAL NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, return_number)
);

CREATE INDEX IF NOT EXISTS idx_sales_return_company ON sales_returns(company_id, return_date);
CREATE INDEX IF NOT EXISTS idx_sales_return_invoice ON sales_returns(invoice_id);
```

#### sales_return_items
```sql
CREATE TABLE IF NOT EXISTS sales_return_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id           INTEGER NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL REFERENCES items(id),
    batch_id            INTEGER REFERENCES stock_batches(id),
    quantity            REAL NOT NULL DEFAULT 0,
    unit_price          REAL NOT NULL DEFAULT 0,
    line_total          REAL NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_sri_return ON sales_return_items(return_id);
CREATE INDEX IF NOT EXISTS idx_sri_item ON sales_return_items(item_id);
```

### 8. Purchase Management

#### purchase_invoices
```sql
CREATE TABLE IF NOT EXISTS purchase_invoices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    invoice_number      TEXT NOT NULL,
    supplier_id         INTEGER NOT NULL REFERENCES parties(id),
    invoice_date        TEXT NOT NULL,
    payment_type        TEXT NOT NULL CHECK (payment_type IN ('CASH','BANK','CHEQUE','CREDIT')),
    bank_account_id     INTEGER REFERENCES bank_accounts(id),
    warehouse_id        INTEGER NOT NULL REFERENCES warehouses(id),
    subtotal            REAL NOT NULL DEFAULT 0,
    discount_amount     REAL NOT NULL DEFAULT 0,
    tax_amount          REAL NOT NULL DEFAULT 0,
    total_amount        REAL NOT NULL DEFAULT 0,
    notes               TEXT,
    status              TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, invoice_number)
);

-- Indexes for purchase queries
CREATE INDEX IF NOT EXISTS idx_purchase_company_supplier ON purchase_invoices(company_id, supplier_id);
CREATE INDEX IF NOT EXISTS idx_purchase_company_date ON purchase_invoices(company_id, invoice_date);
CREATE INDEX IF NOT EXISTS idx_purchase_company_status ON purchase_invoices(company_id, status);
CREATE INDEX IF NOT EXISTS idx_purchase_supplier_date ON purchase_invoices(supplier_id, invoice_date);
```

#### purchase_invoice_items
```sql
CREATE TABLE IF NOT EXISTS purchase_invoice_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id          INTEGER NOT NULL REFERENCES purchase_invoices(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL REFERENCES items(id),
    quantity            REAL NOT NULL DEFAULT 0,
    unit_price          REAL NOT NULL DEFAULT 0,
    discount_amount     REAL NOT NULL DEFAULT 0,
    tax_amount          REAL NOT NULL DEFAULT 0,
    line_total          REAL NOT NULL DEFAULT 0,
    batch_number        TEXT,
    manufacture_date    TEXT,
    expiry_date         TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pii_invoice ON purchase_invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_pii_item ON purchase_invoice_items(item_id);
```

#### purchase_returns
```sql
CREATE TABLE IF NOT EXISTS purchase_returns (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    return_number       TEXT NOT NULL,
    invoice_id          INTEGER NOT NULL REFERENCES purchase_invoices(id),
    supplier_id         INTEGER NOT NULL REFERENCES parties(id),
    return_date         TEXT NOT NULL,
    reason              TEXT,
    total_amount        REAL NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, return_number)
);

CREATE INDEX IF NOT EXISTS idx_purchase_return_company ON purchase_returns(company_id, return_date);
```

#### purchase_return_items
```sql
CREATE TABLE IF NOT EXISTS purchase_return_items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id           INTEGER NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL REFERENCES items(id),
    quantity            REAL NOT NULL DEFAULT 0,
    unit_price          REAL NOT NULL DEFAULT 0,
    line_total          REAL NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pri_return ON purchase_return_items(return_id);
```

### 9. Banking & Payments

#### bank_accounts
```sql
CREATE TABLE IF NOT EXISTS bank_accounts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    account_name        TEXT NOT NULL,
    bank_name           TEXT NOT NULL,
    account_number      TEXT NOT NULL,
    branch_code         TEXT,
    account_type        TEXT CHECK (account_type IN ('CURRENT','SAVINGS')),
    opening_balance     REAL NOT NULL DEFAULT 0,
    account_id          INTEGER NOT NULL REFERENCES accounts(id),
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, account_number)
);

CREATE INDEX IF NOT EXISTS idx_bank_company ON bank_accounts(company_id, is_active);
CREATE INDEX IF NOT EXISTS idx_bank_account ON bank_accounts(account_id);
```

#### cheques
```sql
CREATE TABLE IF NOT EXISTS cheques (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    cheque_number       TEXT NOT NULL,
    bank_account_id     INTEGER NOT NULL REFERENCES bank_accounts(id),
    party_id            INTEGER REFERENCES parties(id),
    amount              REAL NOT NULL DEFAULT 0,
    issue_date          TEXT NOT NULL,
    maturity_date       TEXT,
    status              TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN 
                          ('PENDING','CLEARED','BOUNCED','LOST','CANCELLED')),
    reference_type      TEXT,
    reference_id        INTEGER,
    notes               TEXT,
    cleared_at          TEXT,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for cheque tracking
CREATE INDEX IF NOT EXISTS idx_cheque_company ON cheques(company_id, status);
CREATE INDEX IF NOT EXISTS idx_cheque_bank ON cheques(bank_account_id);
CREATE INDEX IF NOT EXISTS idx_cheque_party ON cheques(party_id);
CREATE INDEX IF NOT EXISTS idx_cheque_maturity ON cheques(maturity_date);
CREATE INDEX IF NOT EXISTS idx_cheque_reference ON cheques(reference_type, reference_id);
```

#### payments
```sql
CREATE TABLE IF NOT EXISTS payments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    payment_number      TEXT NOT NULL,
    payment_date        TEXT NOT NULL,
    payee_id            INTEGER NOT NULL REFERENCES parties(id),
    payment_type        TEXT NOT NULL CHECK (payment_type IN ('CASH','BANK','CHEQUE')),
    bank_account_id     INTEGER REFERENCES bank_accounts(id),
    cheque_id           INTEGER REFERENCES cheques(id),
    total_amount        REAL NOT NULL DEFAULT 0,
    notes               TEXT,
    status              TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, payment_number)
);

CREATE INDEX IF NOT EXISTS idx_payment_company ON payments(company_id, payment_date);
CREATE INDEX IF NOT EXISTS idx_payment_payee ON payments(payee_id);
```

#### payment_allocations
```sql
CREATE TABLE IF NOT EXISTS payment_allocations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id          INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
    invoice_type        TEXT NOT NULL CHECK (invoice_type IN ('SALES','PURCHASE')),
    invoice_id          INTEGER NOT NULL,
    allocated_amount    REAL NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_payment_alloc_payment ON payment_allocations(payment_id);
CREATE INDEX IF NOT EXISTS idx_payment_alloc_invoice ON payment_allocations(invoice_type, invoice_id);
```

#### receipts
```sql
CREATE TABLE IF NOT EXISTS receipts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    receipt_number      TEXT NOT NULL,
    receipt_date        TEXT NOT NULL,
    payer_id            INTEGER NOT NULL REFERENCES parties(id),
    payment_type        TEXT NOT NULL CHECK (payment_type IN ('CASH','BANK','CHEQUE')),
    bank_account_id     INTEGER REFERENCES bank_accounts(id),
    cheque_id           INTEGER REFERENCES cheques(id),
    total_amount        REAL NOT NULL DEFAULT 0,
    notes               TEXT,
    status              TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, receipt_number)
);

CREATE INDEX IF NOT EXISTS idx_receipt_company ON receipts(company_id, receipt_date);
CREATE INDEX IF NOT EXISTS idx_receipt_payer ON receipts(payer_id);
```

#### receipt_allocations
```sql
CREATE TABLE IF NOT EXISTS receipt_allocations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id          INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    invoice_id          INTEGER NOT NULL REFERENCES sales_invoices(id),
    allocated_amount    REAL NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_receipt_alloc_receipt ON receipt_allocations(receipt_id);
CREATE INDEX IF NOT EXISTS idx_receipt_alloc_invoice ON receipt_allocations(invoice_id);
```

### 10. Manufacturing

#### bill_of_materials
```sql
CREATE TABLE IF NOT EXISTS bill_of_materials (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    bom_code            TEXT NOT NULL,
    finished_good_id    INTEGER NOT NULL REFERENCES items(id),
    version             INTEGER NOT NULL DEFAULT 1,
    is_active           INTEGER NOT NULL DEFAULT 1,
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, bom_code, version)
);

CREATE INDEX IF NOT EXISTS idx_bom_company ON bill_of_materials(company_id, is_active);
CREATE INDEX IF NOT EXISTS idx_bom_finished_good ON bill_of_materials(finished_good_id);
```

#### bom_components
```sql
CREATE TABLE IF NOT EXISTS bom_components (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    bom_id              INTEGER NOT NULL REFERENCES bill_of_materials(id) ON DELETE CASCADE,
    component_id        INTEGER NOT NULL REFERENCES items(id),
    quantity_required   REAL NOT NULL DEFAULT 0,
    unit_of_measure     TEXT NOT NULL,
    waste_percentage    REAL NOT NULL DEFAULT 0,
    line_order          INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bom_comp_bom ON bom_components(bom_id);
CREATE INDEX IF NOT EXISTS idx_bom_comp_component ON bom_components(component_id);
```

#### production_orders
```sql
CREATE TABLE IF NOT EXISTS production_orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    order_number        TEXT NOT NULL,
    bom_id              INTEGER NOT NULL REFERENCES bill_of_materials(id),
    warehouse_id        INTEGER NOT NULL REFERENCES warehouses(id),
    planned_quantity    REAL NOT NULL DEFAULT 0,
    produced_quantity   REAL NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'PLANNED' CHECK (status IN 
                          ('PLANNED','IN_PROGRESS','COMPLETED','CANCELLED')),
    start_date          TEXT,
    completion_date     TEXT,
    notes               TEXT,
    created_by          INTEGER REFERENCES users(id),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (company_id, order_number)
);

CREATE INDEX IF NOT EXISTS idx_prod_order_company ON production_orders(company_id, status);
CREATE INDEX IF NOT EXISTS idx_prod_order_bom ON production_orders(bom_id);
CREATE INDEX IF NOT EXISTS idx_prod_order_status ON production_orders(status);
```

#### production_consumption
```sql
CREATE TABLE IF NOT EXISTS production_consumption (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    production_order_id INTEGER NOT NULL REFERENCES production_orders(id),
    item_id             INTEGER NOT NULL REFERENCES items(id),
    batch_id            INTEGER REFERENCES stock_batches(id),
    quantity_consumed   REAL NOT NULL DEFAULT 0,
    unit_cost           REAL NOT NULL DEFAULT 0,
    total_cost          REAL NOT NULL DEFAULT 0,
    consumed_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          INTEGER REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_prod_cons_order ON production_consumption(production_order_id);
CREATE INDEX IF NOT EXISTS idx_prod_cons_item ON production_consumption(item_id);
```

#### production_output
```sql
CREATE TABLE IF NOT EXISTS production_output (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    production_order_id INTEGER NOT NULL REFERENCES production_orders(id),
    item_id             INTEGER NOT NULL REFERENCES items(id),
    batch_id            INTEGER NOT NULL REFERENCES stock_batches(id),
    quantity_produced   REAL NOT NULL DEFAULT 0,
    unit_cost           REAL NOT NULL DEFAULT 0,
    total_cost          REAL NOT NULL DEFAULT 0,
    produced_at         TEXT NOT NULL DEFAULT (datetime('now')),
    created_by          INTEGER REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_prod_output_order ON production_output(production_order_id);
CREATE INDEX IF NOT EXISTS idx_prod_output_item ON production_output(item_id);
CREATE INDEX IF NOT EXISTS idx_prod_output_batch ON production_output(batch_id);
```

### 11. Audit Trail

#### audit_log
```sql
CREATE TABLE IF NOT EXISTS audit_log (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id          INTEGER NOT NULL REFERENCES companies(id),
    user_id             INTEGER REFERENCES users(id),
    action              TEXT NOT NULL CHECK (action IN 
                          ('CREATE','UPDATE','DELETE','POST','CANCEL','LOGIN','LOGOUT')),
    entity_type         TEXT NOT NULL,
    entity_id           INTEGER,
    old_values          TEXT,  -- JSON
    new_values          TEXT,  -- JSON
    ip_address          TEXT,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_audit_company ON audit_log(company_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action, created_at);
```

---

## Default Data Seeding

### System Accounts (Chart of Accounts)

```sql
-- Insert default chart of accounts
INSERT INTO accounts (company_id, account_code, account_name, account_type, is_system_account) VALUES
-- Assets (1000-1999)
(1, '1000', 'Cash', 'ASSET', 1),
(1, '1010', 'Bank', 'ASSET', 1),
(1, '1100', 'Accounts Receivable', 'ASSET', 1),
(1, '1200', 'Inventory - Raw Materials', 'ASSET', 1),
(1, '1210', 'Inventory - Work in Progress', 'ASSET', 1),
(1, '1220', 'Inventory - Finished Goods', 'ASSET', 1),
(1, '1300', 'Prepaid Expenses', 'ASSET', 1),
(1, '1400', 'Fixed Assets', 'ASSET', 1),

-- Liabilities (2000-2999)
(1, '2000', 'Accounts Payable', 'LIABILITY', 1),
(1, '2100', 'Sales Tax Payable', 'LIABILITY', 1),
(1, '2200', 'Income Tax Payable', 'LIABILITY', 1),
(1, '2300', 'Accrued Expenses', 'LIABILITY', 1),

-- Equity (3000-3999)
(1, '3000', 'Share Capital', 'EQUITY', 1),
(1, '3100', 'Retained Earnings', 'EQUITY', 1),

-- Revenue (4000-4999)
(1, '4000', 'Sales Revenue', 'REVENUE', 1),
(1, '4100', 'Service Revenue', 'REVENUE', 1),

-- Expenses (5000-5999)
(1, '5000', 'Cost of Goods Sold', 'EXPENSE', 1),
(1, '5100', 'Salaries Expense', 'EXPENSE', 1),
(1, '5200', 'Rent Expense', 'EXPENSE', 1),
(1, '5300', 'Utilities Expense', 'EXPENSE', 1),
(1, '5400', 'Depreciation Expense', 'EXPENSE', 1);
```

### Default Roles

```sql
INSERT INTO roles (name, description) VALUES
('ADMIN', 'System Administrator - Full Access'),
('ACCOUNTANT', 'Accounting Manager - Full Accounting Access'),
('SALES', 'Sales Staff - Sales Module Only'),
('PURCHASE', 'Purchase Staff - Purchase Module Only'),
('INVENTORY', 'Store Keeper - Inventory Only'),
('VIEWER', 'Read-Only Access');
```

### Default Permissions

```sql
INSERT INTO permissions (code, description) VALUES
('ACCOUNT_CREATE', 'Create Chart of Accounts'),
('ACCOUNT_VIEW', 'View Chart of Accounts'),
('ACCOUNT_EDIT', 'Edit Chart of Accounts'),
('ACCOUNT_DELETE', 'Delete Chart of Accounts'),
('SALES_CREATE', 'Create Sales Invoices'),
('SALES_VIEW', 'View Sales Invoices'),
('SALES_POST', 'Post Sales Invoices'),
('PURCHASE_CREATE', 'Create Purchase Invoices'),
('PURCHASE_VIEW', 'View Purchase Invoices'),
('PURCHASE_POST', 'Post Purchase Invoices'),
('INVENTORY_VIEW', 'View Inventory'),
('INVENTORY_ADJUST', 'Adjust Inventory'),
('REPORT_VIEW', 'View Reports'),
('USER_MANAGE', 'Manage Users');
```

---

## Migration Notes

### From Old Schema (v1.0) to New Schema (v2.0)

1. **New Columns Added**:
   - `updated_at` timestamp on all business tables
   - `status` field on invoices for better workflow tracking
   - `bank_account_id` on sales/purchase invoices for proper bank reconciliation

2. **Index Optimization**:
   - Added composite indexes for common query patterns
   - Added partial indexes for active records only
   - Removed redundant single-column indexes

3. **Data Migration Script**:
   ```python
   # See docs/migration/data_migration.py
   ```

---

## Performance Considerations

### Query Optimization Guidelines

1. **Always filter by company_id first** - All queries should start with `WHERE company_id = ?`
2. **Use covering indexes** - Select only needed columns when possible
3. **Avoid SELECT *** - Especially on tables with TEXT/JSON columns
4. **Batch operations** - Use INSERT/UPDATE with multiple values
5. **Limit result sets** - Always use LIMIT for list queries

### Network Optimization

1. **Reduce round-trips** - Batch related operations
2. **Use prepared statements** - Cache frequently used queries
3. **Compress large result sets** - For reports with many rows
4. **Implement client-side caching** - LRU cache for reference data

---

*Schema Version: 2.0*  
*Last Updated: Based on analysis of BOP ERP v1.0*  
*Maintainer: Senior Full-Stack Python Architect*
