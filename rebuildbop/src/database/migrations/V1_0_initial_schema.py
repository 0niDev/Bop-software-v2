"""
V1_0: Initial Schema Creation

Creates all core tables for BOP ERP v2.0 with SQLite Cloud optimization
Includes indexes for all foreign keys and common search fields
"""

UP = """
-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================
-- CORE TABLES
-- ============================================

-- Users table for authentication
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT UNIQUE,
    full_name TEXT,
    role_id INTEGER,
    is_active INTEGER DEFAULT 1,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER
);

-- Roles for RBAC
CREATE TABLE IF NOT EXISTS roles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    permissions TEXT, -- JSON array of permission strings
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Parties (customers, vendors, suppliers)
CREATE TABLE IF NOT EXISTS parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- CUSTOMER, VENDOR, SUPPLIER, BOTH
    email TEXT,
    phone TEXT,
    mobile TEXT,
    address TEXT,
    city TEXT,
    country TEXT,
    tax_number TEXT,
    credit_limit DECIMAL(15,2) DEFAULT 0,
    balance DECIMAL(15,2) DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER
);

-- Chart of Accounts
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    parent_id INTEGER,
    level INTEGER DEFAULT 1,
    is_header INTEGER DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    balance DECIMAL(15,2) DEFAULT 0,
    opening_balance_dr DECIMAL(15,2) DEFAULT 0,
    opening_balance_cr DECIMAL(15,2) DEFAULT 0,
    current_balance_dr DECIMAL(15,2) DEFAULT 0,
    current_balance_cr DECIMAL(15,2) DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES accounts(id)
);

-- Journal Entries (header)
CREATE TABLE IF NOT EXISTS journal_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_no TEXT UNIQUE NOT NULL,
    date DATE NOT NULL,
    type TEXT NOT NULL, -- SALES, PURCHASE, PAYMENT, RECEIPT, JOURNAL
    party_id INTEGER,
    narration TEXT,
    reference_no TEXT,
    total_dr DECIMAL(15,2) DEFAULT 0,
    total_cr DECIMAL(15,2) DEFAULT 0,
    is_posted INTEGER DEFAULT 0,
    posted_at TIMESTAMP,
    posted_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER,
    FOREIGN KEY (party_id) REFERENCES parties(id)
);

-- Journal Entry Lines
CREATE TABLE IF NOT EXISTS journal_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    description TEXT,
    debit DECIMAL(15,2) DEFAULT 0,
    credit DECIMAL(15,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (entry_id) REFERENCES journal_entries(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

-- Items (products, raw materials)
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    type TEXT NOT NULL, -- PRODUCT, RAW_MATERIAL, SERVICE
    category_id INTEGER,
    unit_of_measure TEXT DEFAULT 'PCS',
    sale_price DECIMAL(15,2) DEFAULT 0,
    purchase_price DECIMAL(15,2) DEFAULT 0,
    cost_price DECIMAL(15,2) DEFAULT 0,
    reorder_level INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER,
    FOREIGN KEY (category_id) REFERENCES item_categories(id)
);

-- Item Categories
CREATE TABLE IF NOT EXISTS item_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_id) REFERENCES item_categories(id)
);

-- Inventory/Stock
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    quantity DECIMAL(15,2) DEFAULT 0,
    reserved_quantity DECIMAL(15,2) DEFAULT 0,
    available_quantity DECIMAL(15,2) GENERATED ALWAYS AS (quantity - reserved_quantity) VIRTUAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(item_id, warehouse_id),
    FOREIGN KEY (item_id) REFERENCES items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

-- Warehouses
CREATE TABLE IF NOT EXISTS warehouses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    address TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Stock Movements (audit trail)
CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    movement_type TEXT NOT NULL, -- IN, OUT, ADJUSTMENT, TRANSFER
    quantity DECIMAL(15,2) NOT NULL,
    reference_type TEXT, -- INVOICE, PURCHASE, MANUFACTURING
    reference_id INTEGER,
    narration TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (item_id) REFERENCES items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

-- Sales Invoices (header)
CREATE TABLE IF NOT EXISTS sales_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT UNIQUE NOT NULL,
    date DATE NOT NULL,
    party_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    subtotal DECIMAL(15,2) DEFAULT 0,
    discount DECIMAL(15,2) DEFAULT 0,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) DEFAULT 0,
    paid_amount DECIMAL(15,2) DEFAULT 0,
    balance_amount DECIMAL(15,2) DEFAULT 0,
    status TEXT DEFAULT 'DRAFT', -- DRAFT, POSTED, CANCELLED
    narration TEXT,
    is_posted INTEGER DEFAULT 0,
    posted_at TIMESTAMP,
    posted_by INTEGER,
    journal_entry_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER,
    FOREIGN KEY (party_id) REFERENCES parties(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id)
);

-- Sales Invoice Lines
CREATE TABLE IF NOT EXISTS sales_invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity DECIMAL(15,2) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    discount DECIMAL(15,2) DEFAULT 0,
    tax_rate DECIMAL(5,2) DEFAULT 0,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    line_total DECIMAL(15,2) NOT NULL,
    cost_price DECIMAL(15,2) DEFAULT 0,
    FOREIGN KEY (invoice_id) REFERENCES sales_invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Purchase Invoices (header)
CREATE TABLE IF NOT EXISTS purchase_invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT UNIQUE NOT NULL,
    date DATE NOT NULL,
    party_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    subtotal DECIMAL(15,2) DEFAULT 0,
    discount DECIMAL(15,2) DEFAULT 0,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    total_amount DECIMAL(15,2) DEFAULT 0,
    paid_amount DECIMAL(15,2) DEFAULT 0,
    balance_amount DECIMAL(15,2) DEFAULT 0,
    status TEXT DEFAULT 'DRAFT',
    narration TEXT,
    is_posted INTEGER DEFAULT 0,
    posted_at TIMESTAMP,
    posted_by INTEGER,
    journal_entry_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER,
    FOREIGN KEY (party_id) REFERENCES parties(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id),
    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id)
);

-- Purchase Invoice Lines
CREATE TABLE IF NOT EXISTS purchase_invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity DECIMAL(15,2) NOT NULL,
    unit_price DECIMAL(15,2) NOT NULL,
    discount DECIMAL(15,2) DEFAULT 0,
    tax_rate DECIMAL(5,2) DEFAULT 0,
    tax_amount DECIMAL(15,2) DEFAULT 0,
    line_total DECIMAL(15,2) NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES purchase_invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(id)
);

-- Manufacturing/Production Orders
CREATE TABLE IF NOT EXISTS manufacturing_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE NOT NULL,
    date DATE NOT NULL,
    product_item_id INTEGER NOT NULL,
    quantity_to_produce DECIMAL(15,2) NOT NULL,
    quantity_produced DECIMAL(15,2) DEFAULT 0,
    status TEXT DEFAULT 'PLANNED', -- PLANNED, IN_PROGRESS, COMPLETED, CANCELLED
    warehouse_id INTEGER,
    notes TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER,
    FOREIGN KEY (product_item_id) REFERENCES items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

-- Bill of Materials (BOM)
CREATE TABLE IF NOT EXISTS bill_of_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_item_id INTEGER NOT NULL,
    component_item_id INTEGER NOT NULL,
    quantity_required DECIMAL(15,2) NOT NULL,
    unit_of_measure TEXT,
    waste_percentage DECIMAL(5,2) DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_item_id, component_item_id),
    FOREIGN KEY (product_item_id) REFERENCES items(id),
    FOREIGN KEY (component_item_id) REFERENCES items(id)
);

-- Manufacturing Order Components (consumed materials)
CREATE TABLE IF NOT EXISTS manufacturing_order_components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    item_id INTEGER NOT NULL,
    quantity_required DECIMAL(15,2) NOT NULL,
    quantity_consumed DECIMAL(15,2) DEFAULT 0,
    warehouse_id INTEGER,
    issued_at TIMESTAMP,
    issued_by INTEGER,
    FOREIGN KEY (order_id) REFERENCES manufacturing_orders(id),
    FOREIGN KEY (item_id) REFERENCES items(id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
);

-- Payments
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_no TEXT UNIQUE NOT NULL,
    date DATE NOT NULL,
    type TEXT NOT NULL, -- PAYMENT, RECEIPT
    party_id INTEGER NOT NULL,
    amount DECIMAL(15,2) NOT NULL,
    payment_method TEXT, -- CASH, BANK, CHEQUE
    reference_no TEXT,
    narration TEXT,
    journal_entry_id INTEGER,
    is_posted INTEGER DEFAULT 0,
    posted_at TIMESTAMP,
    posted_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    updated_by INTEGER,
    FOREIGN KEY (party_id) REFERENCES parties(id),
    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id)
);

-- Payment Allocations (linking payments to invoices)
CREATE TABLE IF NOT EXISTS payment_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id INTEGER NOT NULL,
    invoice_type TEXT NOT NULL, -- SALES, PURCHASE
    invoice_id INTEGER NOT NULL,
    allocated_amount DECIMAL(15,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (payment_id) REFERENCES payments(id),
    UNIQUE(payment_id, invoice_type, invoice_id)
);

-- Banks
CREATE TABLE IF NOT EXISTS banks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    account_no TEXT,
    bank_name TEXT,
    branch_name TEXT,
    ifsc_code TEXT,
    balance DECIMAL(15,2) DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Bank Transactions
CREATE TABLE IF NOT EXISTS bank_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_id INTEGER NOT NULL,
    transaction_date DATE NOT NULL,
    type TEXT NOT NULL, -- DEPOSIT, WITHDRAWAL, TRANSFER
    amount DECIMAL(15,2) NOT NULL,
    balance_after DECIMAL(15,2),
    reference_no TEXT,
    narration TEXT,
    party_id INTEGER,
    is_reconciled INTEGER DEFAULT 0,
    reconciled_at TIMESTAMP,
    journal_entry_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (bank_id) REFERENCES banks(id),
    FOREIGN KEY (party_id) REFERENCES parties(id),
    FOREIGN KEY (journal_entry_id) REFERENCES journal_entries(id)
);

-- Tax Configuration
CREATE TABLE IF NOT EXISTS tax_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    rate DECIMAL(5,2) NOT NULL,
    type TEXT NOT NULL, -- SALES, PURCHASE, BOTH
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settings/Configuration
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_name TEXT UNIQUE NOT NULL,
    value TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER
);

-- Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL, -- CREATE, UPDATE, DELETE, POST, CANCEL
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    old_values TEXT, -- JSON
    new_values TEXT, -- JSON
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================
-- STRATEGIC INDEXES FOR NETWORK PERFORMANCE
-- ============================================

-- Foreign key indexes (critical for JOIN performance)
CREATE INDEX IF NOT EXISTS idx_accounts_parent ON accounts(parent_id);
CREATE INDEX IF NOT EXISTS idx_journal_entries_party ON journal_entries(party_id);
CREATE INDEX IF NOT EXISTS idx_journal_lines_entry ON journal_lines(entry_id);
CREATE INDEX IF NOT EXISTS idx_journal_lines_account ON journal_lines(account_id);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category_id);
CREATE INDEX IF NOT EXISTS idx_inventory_item ON inventory(item_id);
CREATE INDEX IF NOT EXISTS idx_inventory_warehouse ON inventory(warehouse_id);
CREATE INDEX IF NOT EXISTS idx_stock_movements_item ON stock_movements(item_id);
CREATE INDEX IF NOT EXISTS idx_sales_invoices_party ON sales_invoices(party_id);
CREATE INDEX IF NOT EXISTS idx_sales_invoice_lines_invoice ON sales_invoice_lines(invoice_id);
CREATE INDEX IF NOT EXISTS idx_purchase_invoices_party ON purchase_invoices(party_id);
CREATE INDEX IF NOT EXISTS idx_purchase_invoice_lines_invoice ON purchase_invoice_lines(invoice_id);
CREATE INDEX IF NOT EXISTS idx_manufacturing_orders_product ON manufacturing_orders(product_item_id);
CREATE INDEX IF NOT EXISTS idx_bom_product ON bill_of_materials(product_item_id);
CREATE INDEX IF NOT EXISTS idx_payments_party ON payments(party_id);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_bank ON bank_transactions(bank_id);

-- Search/performance indexes
CREATE INDEX IF NOT EXISTS idx_parties_code ON parties(code);
CREATE INDEX IF NOT EXISTS idx_parties_name ON parties(name);
CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(type);
CREATE INDEX IF NOT EXISTS idx_accounts_code ON accounts(code);
CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(type);
CREATE INDEX IF NOT EXISTS idx_journal_entries_date ON journal_entries(date);
CREATE INDEX IF NOT EXISTS idx_journal_entries_type ON journal_entries(type);
CREATE INDEX IF NOT EXISTS idx_journal_entries_posted ON journal_entries(is_posted);
CREATE INDEX IF NOT EXISTS idx_items_code ON items(code);
CREATE INDEX IF NOT EXISTS idx_items_name ON items(name);
CREATE INDEX IF NOT EXISTS idx_sales_invoices_date ON sales_invoices(date);
CREATE INDEX IF NOT EXISTS idx_sales_invoices_status ON sales_invoices(status);
CREATE INDEX IF NOT EXISTS idx_purchase_invoices_date ON purchase_invoices(date);
CREATE INDEX IF NOT EXISTS idx_manufacturing_orders_status ON manufacturing_orders(status);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(date);
CREATE INDEX IF NOT EXISTS idx_bank_transactions_date ON bank_transactions(transaction_date);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sales_invoice_party_date ON sales_invoices(party_id, date);
CREATE INDEX IF NOT EXISTS idx_purchase_invoice_party_date ON purchase_invoices(party_id, date);
CREATE INDEX IF NOT EXISTS idx_journal_entry_party_date ON journal_entries(party_id, date);
CREATE INDEX IF NOT EXISTS idx_inventory_item_warehouse ON inventory(item_id, warehouse_id);
"""

DOWN = """
-- Drop all tables in reverse dependency order
DROP TABLE IF EXISTS audit_log;
DROP TABLE IF EXISTS settings;
DROP TABLE IF EXISTS tax_rates;
DROP TABLE IF EXISTS bank_transactions;
DROP TABLE IF EXISTS banks;
DROP TABLE IF EXISTS payment_allocations;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS manufacturing_order_components;
DROP TABLE IF EXISTS bill_of_materials;
DROP TABLE IF EXISTS manufacturing_orders;
DROP TABLE IF EXISTS purchase_invoice_lines;
DROP TABLE IF EXISTS purchase_invoices;
DROP TABLE IF EXISTS sales_invoice_lines;
DROP TABLE IF EXISTS sales_invoices;
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS warehouses;
DROP TABLE IF EXISTS item_categories;
DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS journal_lines;
DROP TABLE IF EXISTS journal_entries;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS parties;
DROP TABLE IF EXISTS roles;
DROP TABLE IF EXISTS users;
"""
