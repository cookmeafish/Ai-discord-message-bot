"""
Simple database viewer script
Shows all tables and their contents in the bot database
"""

import sqlite3
import os

DB_PATH = os.path.join("database", "bot_data.db")

def view_database():
    """Display all database tables and their contents"""
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()

    print("=" * 80)
    print(f"DATABASE CONTENTS: {DB_PATH}")
    print("=" * 80)

    for (table_name,) in tables:
        print(f"\n### TABLE: {table_name}")
        print("-" * 80)

        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row_count = cursor.fetchone()[0]

        print(f"Columns: {', '.join(column_names)}")
        print(f"Row count: {row_count}")

        if row_count > 0:
            # Show first 10 rows
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 10")
            rows = cursor.fetchall()

            print("\nData (first 10 rows):")
            for row in rows:
                # Format row data, truncate long strings
                formatted_row = []
                for val in row:
                    if isinstance(val, str) and len(val) > 50:
                        formatted_row.append(val[:47] + "...")
                    else:
                        formatted_row.append(str(val))
                print(f"  {' | '.join(formatted_row)}")

        print()

    cursor.close()
    conn.close()

    print("=" * 80)
    print("To edit data, use DB Browser for SQLite:")
    print("https://sqlitebrowser.org/dl/")
    print("=" * 80)

if __name__ == "__main__":
    view_database()
