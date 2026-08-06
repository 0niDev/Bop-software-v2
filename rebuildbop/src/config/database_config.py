"""
Database configuration for SQLite Cloud.

CRITICAL: This file contains your SQLite Cloud API key to connect to the database.

Configuration:
    SQLITE_CLOUD_API_KEY = "bmJZ0l1RTFCoxS0Au17c0iofzZmrDn2Db94v0YtV9Uw"
    SQLITE_CLOUD_HOST = "cjja8z6pvz.g4.sqlite.cloud"
    SQLITE_CLOUD_PORT = 8860
    SQLITE_CLOUD_DATABASE = "cool-depot.sqlite"  # Main ERP database from old system
"""

# SQLite Cloud Configuration - FROM OLD SYSTEM
SQLITE_CLOUD_API_KEY = "bmJZ0l1RTFCoxS0Au17c0iofzZmrDn2Db94v0YtV9Uw"
SQLITE_CLOUD_HOST = "cjja8z6pvz.g4.sqlite.cloud"
SQLITE_CLOUD_PORT = 8860
SQLITE_CLOUD_DATABASE = "cool-depot.sqlite"  # Main database from old BOP system

# Connection String (built from above values)
SQLITE_CLOUD_URL = ""


def get_sqlite_cloud_url() -> str:
    """Build SQLite Cloud connection URL from configuration."""
    global SQLITE_CLOUD_URL
    
    if SQLITE_CLOUD_URL:
        return SQLITE_CLOUD_URL
    
    if SQLITE_CLOUD_API_KEY and SQLITE_CLOUD_HOST and SQLITE_CLOUD_DATABASE:
        return f"sqlitecloud://{SQLITE_CLOUD_HOST}:{SQLITE_CLOUD_PORT}/{SQLITE_CLOUD_DATABASE}?apikey={SQLITE_CLOUD_API_KEY}"
    
    return ""


def is_configured() -> bool:
    """Check if SQLite Cloud is properly configured."""
    return bool(get_sqlite_cloud_url())
