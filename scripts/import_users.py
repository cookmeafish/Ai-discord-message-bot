#!/usr/bin/env python3
"""
Imports users and nicknames into the database.
Run this BEFORE importing bot facts to satisfy foreign key constraints.
"""

import sqlite3
import os
import sys

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def import_users(db_path, sql_file):
    """
    Imports users and nicknames from SQL file.

    Args:
        db_path: Path to the database file
        sql_file: Path to the SQL import file
    """
    if not os.path.exists(db_path):
        print(f"[ERROR] Database not found: {db_path}")
        return False

    if not os.path.exists(sql_file):
        print(f"[ERROR] SQL file not found: {sql_file}")
        return False

    print(f"[INFO] Importing users from: {sql_file}")
    print(f"[INFO] Target database: {db_path}")

    # Read SQL file
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql_script = f.read()

    # Execute SQL
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.executescript(sql_script)
        conn.commit()

        # Verify imports
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM nicknames")
        nickname_count = cursor.fetchone()[0]

        conn.close()

        print(f"[SUCCESS] Import complete!")
        print(f"  - Users imported: {user_count}")
        print(f"  - Nicknames imported: {nickname_count}")

        return True

    except sqlite3.Error as e:
        print(f"[ERROR] Database error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

if __name__ == "__main__":
    # Database path for "Mistel Fiech's server"
    db_path = r"database\Mistel Fiech's server_data.db"
    sql_file = r"database\add_users.sql"

    success = import_users(db_path, sql_file)
    sys.exit(0 if success else 1)
