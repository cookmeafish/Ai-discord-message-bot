# database/db_manager.py
import sqlite3
import os
from . import schemas
import datetime

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

    # --- MODIFIED: Method to log messages with directed status ---
    def log_message(self, message, directed_at_bot=False):
        """Logs a message to the short_term_message_log table."""
        query = """
        INSERT INTO short_term_message_log (message_id, user_id, channel_id, content, timestamp, directed_at_bot)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        timestamp = message.created_at.isoformat()
        # Convert boolean to integer (1 for True, 0 for False) for the database
        directed_flag = 1 if directed_at_bot else 0

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (message.id, message.author.id, message.channel.id, message.content, timestamp, directed_flag))
            self.conn.commit()
            cursor.close()
        except sqlite3.IntegrityError:
            pass
        except Exception as e:
            print(f"🔴 DATABASE ERROR: Failed to log message {message.id}: {e}")

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()