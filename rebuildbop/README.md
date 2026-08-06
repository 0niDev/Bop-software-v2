# BOP Pharmaceutical ERP System - Rebuilt

A complete rebuild of the BOP Pharmaceutical ERP system with **SQLite Cloud** as the primary database.

## 🚀 Performance Targets (10x Improvement)

| Operation | Current | Target |
|-----------|---------|--------|
| Dashboard Load | 5+ seconds | <1 second |
| Invoice Creation | 3-4 seconds | <500ms |
| Report Generation | 10+ seconds | <2 seconds |
| Search | 1-2 seconds | <200ms |

## 📁 Project Structure

```
rebuildbop/
├── docs/
│   └── analysis/          # Analysis documentation
├── src/
│   ├── views/            # UI components (Phase 0 - COMPLETE)
│   │   ├── login_window.py
│   │   ├── main_window.py
│   │   ├── dashboard_view.py
│   │   ├── sales_view.py
│   │   ├── purchases_view.py
│   │   ├── manufacturing_view.py
│   │   ├── inventory_view.py
│   │   ├── accounting_view.py
│   │   ├── banking_view.py
│   │   ├── reports_view.py
│   │   ├── settings_view.py
│   │   ├── party_management_view.py
│   │   ├── item_management_view.py
│   │   └── base_widgets.py
│   ├── config/           # Configuration
│   │   ├── app_config.py
│   │   └── database_config.py  # ⚠️ NEEDS API KEY
│   ├── database/         # Phase 2: Connection pooling, etc.
│   ├── repositories/     # Phase 3: Data access layer
│   ├── services/         # Phase 4: Business logic
│   ├── controllers/      # Phase 5: View controllers
│   └── utils/            # Utilities
├── tests/                # Phase 7: Test suite
└── main.py              # Application entry point
```

## ⚙️ Setup Instructions

### 1. Install Dependencies

```bash
pip install PySide6 sqlitecloud
```

### 2. Configure SQLite Cloud Connection

**CRITICAL**: You need to provide your SQLite Cloud API key from the old BOP system.

Edit `src/config/database_config.py`:

```python
SQLITE_CLOUD_API_KEY = "your_api_key_here"
SQLITE_CLOUD_HOST = "your_host.sqlite.cloud"
SQLITE_CLOUD_DATABASE = "your_database_name"
```

Or set environment variables:

```bash
export SQLITE_CLOUD_API_KEY="your_api_key_here"
export SQLITE_CLOUD_HOST="your_host.sqlite.cloud"
export SQLITE_CLOUD_DATABASE="your_database_name"
```

### 3. Run the Application

```bash
python main.py
```

## 🎯 Current Status

### ✅ Phase 0: Main Window Framework (COMPLETE)

The main application structure has been rebuilt matching the old application layout:

- **Login Window**: Modern login screen with background thread for authentication
- **Main Window**: Sidebar navigation with stacked widget for module views
- **All Module Views**: Boilerplate placeholders for all 11 modules:
  - Dashboard (with KPI cards)
  - Sales
  - Purchases
  - Manufacturing
  - Inventory
  - Accounting
  - Banking
  - Reports
  - Party Management
  - Item Management
  - Settings

### 🔧 Next Steps

**Please provide your SQLite Cloud API key** from the old system so I can properly configure the database connection in `src/config/database_config.py`.

Once configured, the following phases will be implemented:

- **Phase 1**: Analysis Documentation
- **Phase 2**: Database Layer (Connection Pooling, Query Optimization)
- **Phase 3**: Repository Layer (Data Access)
- **Phase 4**: Service Layer (Business Logic)
- **Phase 5**: Controller Layer (View Controllers)
- **Phase 6**: Replace Boilerplate with Real Functionality
- **Phase 7**: Testing (90%+ Coverage)
- **Phase 8**: Complete Documentation

## 🏗️ Architecture

### Layered Architecture

```
Views → Controllers → Services → Repositories → Database
```

### Core Infrastructure

- **Connection Pooling**: Min 10, Max 50 connections
- **Three-tier Caching**: L1 (memory), L2 (session), L3 (global)
- **Async Operations**: QThreads for all database operations
- **Transaction Management**: Savepoints, rollback, deadlock detection
- **Retry Logic**: Exponential backoff (100ms, 500ms, 2000ms)
- **Batch Operations**: Reduce round-trips by 80%

## 📊 Success Criteria

- [x] Main window matches old application layout
- [x] All modules visible with boilerplate content
- [ ] API key configured for database connection
- [ ] 10x performance improvement achieved
- [ ] No UI freezes, all operations async
- [ ] 100% business logic accuracy from old system
- [ ] 90%+ test coverage
- [ ] Complete documentation
- [x] SQLite Cloud as primary database from day one

## 📝 License

Proprietary - BOP Pharmaceutical
