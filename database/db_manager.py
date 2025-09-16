# database/db_manager.py
import sqlite3
import os
from . import schemas

# Define the location for the database file
DB_FOLDER = "database"
DB_FILE = "bot_data.db"
DB_PATH = os.path.join(DB_FOLDER, DB_FILE)

class DBManager:
    """Handles all database operations for the bot."""
    def __init__(self):
        # Ensure the 'database' directory exists.
        os.makedirs(DB_FOLDER, exist_ok=True)
        
        # Connect to the database. If the file doesn't exist,
        # sqlite3 will create it automatically.
        self.conn = sqlite3.connect(DB_PATH)
        
        self._initialize_database()

    def _initialize_database(self):
        """Creates all necessary tables if they don't already exist."""
        cursor = self.conn.cursor()
        try:
            for table_sql in schemas.ALL_TABLES:
                # The "IF NOT EXISTS" clause prevents errors on subsequent runs
                cursor.execute(table_sql)
            self.conn.commit()
            print("✅ Database initialized and tables verified successfully.")
        except Exception as e:
            print(f"🔴 DATABASE ERROR: Failed to initialize tables: {e}")
        finally:
            cursor.close()

    def get_connection(self):
        """Returns the active database connection."""
        return self.conn

    # --- You will add more methods here for interacting with the data ---
    # Example:
    # def get_user_facts(self, user_id):
    #     cursor = self.conn.cursor()
    #     cursor.execute("SELECT fact FROM long_term_memory WHERE user_id = ?", (user_id,))
    #     facts = cursor.fetchall()
    #     cursor.close()
    #     return [fact[0] for fact in facts]

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()
