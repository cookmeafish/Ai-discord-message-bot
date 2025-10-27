#!/usr/bin/env python3
"""
Quick test script to verify new relationship metrics implementation.
Tests database operations and data retrieval.
"""

import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db_manager import DBManager

def test_new_metrics():
    """Test that new metrics are working correctly."""

    print("=" * 60)
    print("TESTING NEW RELATIONSHIP METRICS")
    print("=" * 60)

    # Test with Mistel Fiech server database
    db_path = "database/Mistel Fiech's Server/1260857723193528360_data.db"

    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return False

    print(f"\n[INFO] Testing with: {db_path}\n")

    try:
        db_manager = DBManager(db_path)

        # Test 1: Get metrics for TestUser (should have special values)
        print("[TEST 1] Retrieving metrics for TestUser (ID: 968980122440970252)")
        test_user_metrics = db_manager.get_relationship_metrics(968980122440970252)

        print(f"  Rapport: {test_user_metrics['rapport']}/10")
        print(f"  Trust: {test_user_metrics['trust']}/10")
        print(f"  Anger: {test_user_metrics['anger']}/10")
        print(f"  Formality: {test_user_metrics['formality']}")

        # Check new metrics
        if 'fear' in test_user_metrics:
            print(f"  Fear: {test_user_metrics['fear']}/10")
            print(f"  Respect: {test_user_metrics['respect']}/10")
            print(f"  Affection: {test_user_metrics['affection']}/10")
            print(f"  Familiarity: {test_user_metrics['familiarity']}/10")
            print(f"  Intimidation: {test_user_metrics['intimidation']}/10")

            # Verify TestUser's special values
            if (test_user_metrics['fear'] == 9 and
                test_user_metrics['respect'] == 10 and
                test_user_metrics['intimidation'] == 10):
                print("  [PASS] TestUser's special metrics are correct!")
            else:
                print("  [FAIL] TestUser's metrics don't match expected values")
                return False
        else:
            print("  [FAIL] New metrics not found!")
            return False

        print()

        # Test 2: Get all users and verify they have new metrics
        print("[TEST 2] Checking all users have new metrics")
        all_users = db_manager.get_all_users_with_metrics()

        if not all_users:
            print("  [FAIL] No users found")
            return False

        print(f"  Found {len(all_users)} users")

        for user in all_users[:3]:  # Check first 3 users
            if 'fear' not in user:
                print(f"  [FAIL] User {user['user_id']} missing new metrics")
                return False

        print("  [PASS] All users have new metrics!")
        print()

        # Test 3: Test metric update functionality
        print("[TEST 3] Testing metric update")
        test_user_id = 1395983671747678333  # User with high rapport

        original_metrics = db_manager.get_relationship_metrics(test_user_id)
        print(f"  Original fear: {original_metrics['fear']}")

        # Update fear to 5
        db_manager.update_relationship_metrics(test_user_id, respect_locks=False, fear=5)

        updated_metrics = db_manager.get_relationship_metrics(test_user_id)
        print(f"  Updated fear: {updated_metrics['fear']}")

        if updated_metrics['fear'] == 5:
            print("  [PASS] Metric update successful!")

            # Restore original value
            db_manager.update_relationship_metrics(test_user_id, respect_locks=False, fear=original_metrics['fear'])
            print(f"  Restored fear to: {original_metrics['fear']}")
        else:
            print("  [FAIL] Metric update failed")
            return False

        print()

        # Test 4: Test lock functionality
        print("[TEST 4] Testing metric locks")

        # Set fear_locked to True
        db_manager.update_relationship_metrics(test_user_id, respect_locks=False, fear_locked=1)

        # Try to update fear with respect_locks=True (should be blocked)
        db_manager.update_relationship_metrics(test_user_id, respect_locks=True, fear=8)

        locked_metrics = db_manager.get_relationship_metrics(test_user_id)

        if locked_metrics['fear'] == original_metrics['fear']:  # Should still be original value
            print("  [PASS] Lock successfully prevented update!")
        else:
            print("  [FAIL] Lock did not prevent update")
            return False

        # Unlock and restore
        db_manager.update_relationship_metrics(test_user_id, respect_locks=False, fear_locked=0)
        print("  Restored lock status")

        print()

        db_manager.close()

        print("=" * 60)
        print("[SUCCESS] All tests passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_new_metrics()
    sys.exit(0 if success else 1)
