#!/usr/bin/env python3
"""
Migration script to add 'nickname' column to short_term_message_log table.
Safe to run multiple times - checks if column exists before adding.
"""

import sqlite3
import os
import sys

def add_nickname_column(db_path):
    """
    Adds nickname column to short_term_message_log if it doesn't exist.

    Args:
        db_path: Path to the database file
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if nickname column already exists
        cursor.execute("PRAGMA table_info(short_term_message_log)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'nickname' in columns:
            print(f"  [OK] Column 'nickname' already exists in {db_path}")
            conn.close()
            return True

        # Add the column
        print(f"  [+] Adding 'nickname' column to {db_path}")
        cursor.execute("ALTER TABLE short_term_message_log ADD COLUMN nickname TEXT")
        conn.commit()

        print(f"  [OK] Successfully added 'nickname' column")
        conn.close()
        return True

    except Exception as e:
        print(f"  [ERROR] Error migrating {db_path}: {e}")
        return False

def main():
    """
    Migrate all server databases to include nickname column.
    """
    print("=" * 60)
    print("Adding 'nickname' column to short_term_message_log tables")
    print("=" * 60)
    print()

    database_dir = "database"

    if not os.path.exists(database_dir):
        print(f"Error: Database directory '{database_dir}' not found")
        sys.exit(1)

    # Find all server database files
    migrated_count = 0
    error_count = 0

    for server_folder in os.listdir(database_dir):
        server_path = os.path.join(database_dir, server_folder)

        # Skip if not a directory
        if not os.path.isdir(server_path):
            continue

        # Find .db files in this server folder
        for file in os.listdir(server_path):
            if file.endswith('_data.db'):
                db_path = os.path.join(server_path, file)
                print(f"Migrating: {server_folder}/{file}")

                if add_nickname_column(db_path):
                    migrated_count += 1
                else:
                    error_count += 1
                print()

    print("=" * 60)
    print(f"Migration complete!")
    print(f"  Successfully migrated: {migrated_count} database(s)")
    if error_count > 0:
        print(f"  Errors: {error_count} database(s)")
    print("=" * 60)

if __name__ == "__main__":
    main()
