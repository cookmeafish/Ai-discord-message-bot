#!/usr/bin/env python3
"""
Migrates relationship_metrics table to add new relationship dimensions.
Adds: fear, respect, affection, familiarity, intimidation (and their lock columns)

Safe to run multiple times - will skip if columns already exist.
"""

import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def migrate_database(db_path):
    """
    Adds new relationship metric columns to relationship_metrics table.

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

        # Check if relationship_metrics table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='relationship_metrics'")
        if not cursor.fetchone():
            print(f"  [SKIP] relationship_metrics table does not exist")
            cursor.close()
            conn.close()
            return True

        # Check which columns already exist
        cursor.execute("PRAGMA table_info(relationship_metrics)")
        columns = [row[1] for row in cursor.fetchall()]

        # Define new metric columns and their lock columns
        new_metrics = [
            ("fear", "INTEGER NOT NULL DEFAULT 0"),
            ("respect", "INTEGER NOT NULL DEFAULT 0"),
            ("affection", "INTEGER NOT NULL DEFAULT 0"),
            ("familiarity", "INTEGER NOT NULL DEFAULT 0"),
            ("intimidation", "INTEGER NOT NULL DEFAULT 0")
        ]

        lock_columns = [
            ("fear_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("respect_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("affection_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("familiarity_locked", "INTEGER NOT NULL DEFAULT 0"),
            ("intimidation_locked", "INTEGER NOT NULL DEFAULT 0")
        ]

        columns_to_add = []

        # Check which metric columns need to be added
        for column_name, column_def in new_metrics:
            if column_name not in columns:
                columns_to_add.append((column_name, column_def))

        # Check which lock columns need to be added
        for column_name, column_def in lock_columns:
            if column_name not in columns:
                columns_to_add.append((column_name, column_def))

        if not columns_to_add:
            print(f"  [SKIP] All columns already exist")
            cursor.close()
            conn.close()
            return True

        # Add columns
        for column_name, column_def in columns_to_add:
            alter_query = f"ALTER TABLE relationship_metrics ADD COLUMN {column_name} {column_def}"
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

def find_all_databases():
    """
    Finds all server databases in the database/ directory.
    Supports both new structure (database/{ServerName}/{guild_id}_data.db)
    and legacy flat structure (database/{guild_id}_data.db).

    Returns:
        List of database file paths
    """
    database_dir = "database"
    db_files = []

    if not os.path.exists(database_dir):
        print("[ERROR] Database directory not found")
        return []

    # Walk through all subdirectories to find .db files
    for root, dirs, files in os.walk(database_dir):
        for file in files:
            if file.endswith('_data.db') or file == 'data.db':
                db_path = os.path.join(root, file)
                db_files.append(db_path)

    return db_files

def migrate_all_databases():
    """
    Migrates all server databases found in the database/ directory.
    """
    db_files = find_all_databases()

    if not db_files:
        print("[WARNING] No server databases found")
        return False

    print(f"[INFO] Found {len(db_files)} database(s) to migrate\n")
    print("=" * 60)

    success_count = 0
    error_count = 0

    for db_path in db_files:
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
    print("RELATIONSHIP METRICS EXPANSION MIGRATION")
    print("=" * 60)
    print("\nAdding new relationship metric columns:")
    print("  - fear (INTEGER, 0-10 scale, default 0)")
    print("  - respect (INTEGER, 0-10 scale, default 0)")
    print("  - affection (INTEGER, 0-10 scale, default 0)")
    print("  - familiarity (INTEGER, 0-10 scale, default 0)")
    print("  - intimidation (INTEGER, 0-10 scale, default 0)")
    print("\nAdding lock columns:")
    print("  - fear_locked, respect_locked, affection_locked, familiarity_locked, intimidation_locked")
    print()

    success = migrate_all_databases()

    if success:
        print("\n[SUCCESS] All migrations completed successfully")
        sys.exit(0)
    else:
        print("\n[FAILED] Some migrations failed")
        sys.exit(1)
