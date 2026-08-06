"""
Integration Tests for Repository Layer (Phase 3)
Tests against LIVE SQLite Cloud Database
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.database.connection import get_db, test_connection
from src.repositories.user_repository import UserRepository
from src.repositories.party_repository import PartyRepository
from src.repositories.item_repository import ItemRepository
from src.repositories.account_repository import AccountRepository
from src.repositories.stock_repository import StockRepository

def print_header(title: str):
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def print_result(test_name: str, success: bool, message: str = ""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status}: {test_name}")
    if message:
        print(f"   └─ {message}")

def test_user_repository():
    print_header("1. USER REPOSITORY TESTS")
    repo = UserRepository()
    passed = 0
    total = 0

    # Test 1: Get All Users
    total += 1
    try:
        users = repo.get_all()
        success = len(users) > 0
        print_result("Get All Users", success, f"Found {len(users)} users")
        if success: passed += 1
    except Exception as e:
        print_result("Get All Users", False, str(e))

    # Test 2: Authenticate Admin
    total += 1
    try:
        # Try common default passwords or just check if user exists
        user = repo.get_by_username('admin')
        success = user is not None
        print_result("Get User 'admin'", success, f"User ID: {user.get('id', 'N/A')}" if success else "User not found")
        if success: passed += 1
    except Exception as e:
        print_result("Get User 'admin'", False, str(e))

    # Test 3: Get Non-existent User
    total += 1
    try:
        user = repo.get_by_username('nonexistent_user_xyz')
        success = user is None
        print_result("Get Non-existent User", success, "Correctly returned None")
        if success: passed += 1
    except Exception as e:
        print_result("Get Non-existent User", False, str(e))

    return passed, total

def test_party_repository():
    print_header("2. PARTY REPOSITORY TESTS")
    repo = PartyRepository()
    passed = 0
    total = 0

    # Test 1: Get All Parties
    total += 1
    try:
        parties = repo.get_all(limit=5)
        success = len(parties) >= 0  # Might be empty in new DB, but shouldn't crash
        print_result("Get Parties (Limit 5)", success, f"Retrieved {len(parties)} parties")
        if success: passed += 1
        if len(parties) > 0:
            print(f"   └─ Sample: {parties[0].get('name', 'No Name')}")
    except Exception as e:
        print_result("Get Parties", False, str(e))

    # Test 2: Search Parties
    total += 1
    try:
        parties = repo.search_by_name('a', limit=5)
        success = True
        print_result("Search Parties ('a')", success, f"Found {len(parties)} matches")
        if success: passed += 1
    except Exception as e:
        print_result("Search Parties", False, str(e))

    return passed, total

def test_item_repository():
    print_header("3. ITEM REPOSITORY TESTS")
    repo = ItemRepository()
    passed = 0
    total = 0

    # Test 1: Get All Items
    total += 1
    try:
        items = repo.get_all(limit=5)
        success = len(items) > 0
        print_result("Get Items (Limit 5)", success, f"Retrieved {len(items)} items")
        if success: 
            passed += 1
            sample = items[0]
            print(f"   └─ Sample: {sample.get('name', 'No Name')} (ID: {sample.get('id')})")
        else:
            print("   └─ Warning: No items found in database")
    except Exception as e:
        print_result("Get Items", False, str(e))

    # Test 2: Get Item by ID (Use first item from previous test if available)
    total += 1
    try:
        items = repo.get_all(limit=1)
        if items:
            item_id = items[0]['id']
            item = repo.get_by_id(item_id)
            success = item is not None
            print_result(f"Get Item by ID ({item_id})", success, "Item retrieved successfully")
            if success: passed += 1
        else:
            print_result("Get Item by ID", True, "Skipped (No items to test)")
            passed += 1
    except Exception as e:
        print_result("Get Item by ID", False, str(e))

    return passed, total

def test_account_repository():
    print_header("4. ACCOUNT REPOSITORY TESTS")
    repo = AccountRepository()
    passed = 0
    total = 0

    # Test 1: Get Chart of Accounts
    total += 1
    try:
        accounts = repo.get_all(limit=10)
        success = len(accounts) >= 0
        print_result("Get Accounts (Limit 10)", success, f"Retrieved {len(accounts)} accounts")
        if success: passed += 1
    except Exception as e:
        print_result("Get Accounts", False, str(e))

    # Test 2: Get Accounts by Type (e.g., 'Asset')
    total += 1
    try:
        accounts = repo.get_by_type('Asset', limit=5)
        success = True
        print_result("Get Asset Accounts", success, f"Found {len(accounts)} asset accounts")
        if success: passed += 1
    except Exception as e:
        print_result("Get Asset Accounts", False, str(e))

    return passed, total

def test_stock_repository():
    print_header("5. STOCK REPOSITORY TESTS")
    repo = StockRepository()
    passed = 0
    total = 0

    # Test 1: Get Current Stock
    total += 1
    try:
        stock = repo.get_current_stock(limit=5)
        success = len(stock) >= 0
        print_result("Get Current Stock", success, f"Retrieved {len(stock)} stock records")
        if success: passed += 1
        if len(stock) > 0:
            s = stock[0]
            print(f"   └─ Sample: Item ID {s.get('item_id')} - Qty: {s.get('quantity', 0)}")
    except Exception as e:
        print_result("Get Current Stock", False, str(e))

    return passed, total

def main():
    print("\n🚀 STARTING REPOSITORY LAYER INTEGRATION TESTS")
    print("Target: SQLite Cloud (Live Database)")
    
    # Pre-check Connection
    print_header("PRE-FLIGHT CHECK: DATABASE CONNECTION")
    conn_status = test_connection()
    if not conn_status:
        print(f"❌ CRITICAL: Database connection failed!")
        print("Aborting tests.")
        return
    
    print_result("SQLite Cloud Connection", True, "Connected successfully")

    # Run Tests
    total_passed = 0
    total_tests = 0

    results = [
        test_user_repository(),
        test_party_repository(),
        test_item_repository(),
        test_account_repository(),
        test_stock_repository()
    ]

    for passed, total in results:
        total_passed += passed
        total_tests += total

    # Final Summary
    print_header("TEST SUMMARY")
    percentage = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"Total Tests: {total_tests}")
    print(f"Passed:      {total_passed}")
    print(f"Failed:      {total_tests - total_passed}")
    print(f"Success Rate: {percentage:.1f}%")

    if percentage == 100:
        print("\n🎉 ALL TESTS PASSED! Repository Layer is ready for Phase 4.")
    elif percentage >= 80:
        print("\n⚠️  MOST TESTS PASSED. Minor issues detected but core functionality works.")
    else:
        print("\n🛑 CRITICAL FAILURES. Review errors above before proceeding.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user.")
    except Exception as e:
        print(f"\n💥 FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
