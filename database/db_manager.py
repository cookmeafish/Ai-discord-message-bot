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
        self.conn = sqlite3.connect(DB_PATH)
        self._initialize_database()

    def _initialize_database(self):
        """Creates all necessary tables if they don't already exist."""
        cursor = self.conn.cursor()
        try:
            for table_sql in schemas.ALL_TABLES:
                cursor.execute(table_sql)
            self.conn.commit()
            print("Database initialized and tables verified successfully.")
        except Exception as e:
            print(f"DATABASE ERROR: Failed to initialize tables: {e}")
        finally:
            cursor.close()

    def log_message(self, message, directed_at_bot=False):
        """Logs a message to the short_term_message_log table."""
        query = """
        INSERT INTO short_term_message_log (message_id, user_id, channel_id, content, timestamp, directed_at_bot)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        timestamp = message.created_at.isoformat()
        directed_flag = 1 if directed_at_bot else 0
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (message.id, message.author.id, message.channel.id, message.content, timestamp, directed_flag))
            self.conn.commit()
            cursor.close()
        except sqlite3.IntegrityError:
            pass 
        except Exception as e:
            print(f"DATABASE ERROR: Failed to log message {message.id}: {e}")

    def get_short_term_memory(self):
        """Retrieves all messages from the last 24 hours."""
        query = "SELECT message_id, user_id, channel_id, content, timestamp, directed_at_bot FROM short_term_message_log WHERE timestamp >= ?"
        twenty_four_hours_ago = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).isoformat()
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (twenty_four_hours_ago,))
            rows = cursor.fetchall()
            cursor.close()
            return [{
                "message_id": row[0], "author_id": row[1], "channel_id": row[2],
                "content": row[3], "timestamp": row[4], "directed_at_bot": bool(row[5])
            } for row in rows]
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get short term memory: {e}")
            return []

    def get_long_term_memory(self, user_id):
        """Retrieves long-term memory facts for a given user, including the source."""
        query = "SELECT fact, source_user_id, source_nickname FROM long_term_memory WHERE user_id = ?"
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
            cursor.close()
            return rows # Returns a list of tuples (fact, source_id, source_name)
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get long term memory for user {user_id}: {e}")
            return []

    def add_long_term_memory(self, user_id, fact, source_user_id, source_nickname):
        """Adds a new long-term memory fact for a user, including the source."""
        check_query = "SELECT id FROM long_term_memory WHERE user_id = ? AND fact = ?"
        insert_query = """
        INSERT INTO long_term_memory (user_id, fact, source_user_id, source_nickname, first_mentioned_timestamp, last_mentioned_timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        now = datetime.datetime.utcnow().isoformat()
        try:
            cursor = self.conn.cursor()
            cursor.execute(check_query, (user_id, fact))
            if cursor.fetchone() is None:
                cursor.execute(insert_query, (user_id, fact, source_user_id, source_nickname, now, now))
                self.conn.commit()
                print(f"DATABASE: Saved new fact for user {user_id}: '{fact}' from source {source_nickname}")
            else:
                print(f"DATABASE: Fact already exists for user {user_id}, not saving duplicate.")
            cursor.close()
        except Exception as e:
            print(f"DATABASE ERROR: Failed to add long-term memory for user {user_id}: {e}")

    def close(self):
        if self.conn:
            self.conn.close()