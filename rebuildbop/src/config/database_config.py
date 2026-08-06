"""
Database configuration placeholder for SQLite Cloud.

CRITICAL: This file needs your SQLite Cloud API key to connect to the database.

TO CONFIGURE:
1. Get your API key from the old BOP system
2. Replace the empty string below with your actual API key
3. Or set environment variable: SQLITE_CLOUD_API_KEY=your_key_here

Example:
    SQLITE_CLOUD_API_KEY = "bmJZ0l1RTFCoxS0Au17c0iofzZmrDn2Db94v0YtV9Uw"
    SQLITE_CLOUD_HOST = "cjja8z6pvz.g4.sqlite.cloud"
    SQLITE_CLOUD_PORT = 8860
    SQLITE_CLOUD_DATABASE = "cool-depot.sqlite"
"""

# SQLite Cloud Configuration
SQLITE_CLOUD_API_KEY = ""  # ← INSERT YOUR API KEY HERE
SQLITE_CLOUD_HOST = ""  # ← INSERT YOUR HOST HERE (e.g., cjja8z6pvz.g4.sqlite.cloud)
SQLITE_CLOUD_PORT = 8860
SQLITE_CLOUD_DATABASE = ""  # ← INSERT YOUR DATABASE NAME HERE

# Connection String (will be built from above values if API key is provided)
SQLITE_CLOUD_URL = ""

# If you have a complete connection URL, you can use it directly:
# Example: sqlitecloud://cjja8z6pvz.g4.sqlite.cloud:8860/cool-depot.sqlite?apikey=bmJZ0l1RTFCoxS0Au17c0iofzZmrDn2Db94v0YtV9Uw
# SQLITE_CLOUD_URL = "sqlitecloud://YOUR_HOST:8860/YOUR_DB?apikey=YOUR_API_KEY"


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
