#!/usr/bin/env python3
"""
Migrates long_term_memory table to add new columns for memory correction system.
Adds: status, superseded_by_id, last_validated_timestamp

Safe to run multiple times - will skip if columns already exist.
"""

import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def migrate_database(db_path):
    """
    Adds new columns to long_term_memory table.

    Args:
        db_path: Path to the database file

    Returns:
        bool: True if migration successful, False otherwise
    """
    if not os.path.exists(db_path):
        print(f"[SKIP] Database not found: {db_path}")
        return False

    print(f"\n[INFO] Migrating: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if columns already exist
        cursor.execute("PRAGMA table_info(long_term_memory)")
        columns = [row[1] for row in cursor.fetchall()]

        columns_to_add = []

        if 'status' not in columns:
            columns_to_add.append(("status", "TEXT DEFAULT 'active'"))

        if 'superseded_by_id' not in columns:
            columns_to_add.append(("superseded_by_id", "INTEGER"))

        if 'last_validated_timestamp' not in columns:
            columns_to_add.append(("last_validated_timestamp", "TEXT"))

        if not columns_to_add:
            print(f"  [SKIP] All columns already exist")
            cursor.close()
            conn.close()
            return True

        # Add columns
        for column_name, column_def in columns_to_add:
            alter_query = f"ALTER TABLE long_term_memory ADD COLUMN {column_name} {column_def}"
            cursor.execute(alter_query)
            print(f"  [ADD] Column: {column_name}")

        conn.commit()
        cursor.close()
        conn.close()

        print(f"  [SUCCESS] Migration complete ({len(columns_to_add)} columns added)")
        return True

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"  [SKIP] Columns already exist")
            return True
        else:
            print(f"  [ERROR] SQLite error: {e}")
            return False
    except Exception as e:
        print(f"  [ERROR] Unexpected error: {e}")
        return False

def migrate_all_databases():
    """
    Migrates all server databases in the database/ directory.
    """
    database_dir = "database"

    if not os.path.exists(database_dir):
        print("[ERROR] Database directory not found")
        return False

    # Find all .db files
    db_files = [f for f in os.listdir(database_dir) if f.endswith('_data.db')]

    if not db_files:
        print("[WARNING] No server databases found")
        return False

    print(f"[INFO] Found {len(db_files)} database(s) to migrate\n")
    print("=" * 60)

    success_count = 0
    skip_count = 0
    error_count = 0

    for db_file in db_files:
        db_path = os.path.join(database_dir, db_file)
        result = migrate_database(db_path)

        if result:
            success_count += 1
        else:
            error_count += 1

    print("\n" + "=" * 60)
    print(f"\n[SUMMARY]")
    print(f"  Total databases: {len(db_files)}")
    print(f"  Successful: {success_count}")
    print(f"  Errors: {error_count}")

    return error_count == 0

if __name__ == "__main__":
    print("=" * 60)
    print("LONG-TERM MEMORY SCHEMA MIGRATION")
    print("=" * 60)
    print("\nAdding columns:")
    print("  - status (TEXT, default 'active')")
    print("  - superseded_by_id (INTEGER)")
    print("  - last_validated_timestamp (TEXT)")
    print()

    success = migrate_all_databases()

    if success:
        print("\n[SUCCESS] All migrations completed successfully")
        sys.exit(0)
    else:
        print("\n[FAILED] Some migrations failed")
        sys.exit(1)
