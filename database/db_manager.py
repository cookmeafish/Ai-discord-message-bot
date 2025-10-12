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
        # Ensure the 'database' directory exists
        os.makedirs(DB_FOLDER, exist_ok=True)

        try:
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            # Enable foreign key constraints
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Enable auto-vacuum for automatic database compaction
            self.conn.execute("PRAGMA auto_vacuum = FULL")
            self._initialize_database()
            print("Database optimization enabled: auto_vacuum = FULL")
        except Exception as e:
            print(f"CRITICAL DATABASE ERROR: Failed to connect to database: {e}")
            raise

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
            raise
        finally:
            cursor.close()

    # --- Message Logging Methods ---

    def log_message(self, message, directed_at_bot=False):
        """
        Logs a message to the short_term_message_log table.
        
        Args:
            message: Discord message object
            directed_at_bot: Boolean indicating if the message was directed at the bot
        """
        query = """
        INSERT OR REPLACE INTO short_term_message_log (message_id, user_id, channel_id, content, timestamp, directed_at_bot)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        timestamp = message.created_at.isoformat()
        directed_flag = 1 if directed_at_bot else 0
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (
                message.id, 
                message.author.id, 
                message.channel.id, 
                message.content, 
                timestamp, 
                directed_flag
            ))
            self.conn.commit()
            cursor.close()
        except sqlite3.IntegrityError:
            # Message already exists, skip silently
            pass
        except Exception as e:
            print(f"DATABASE ERROR: Failed to log message {message.id}: {e}")

    def get_short_term_memory(self, channel_id=None):
        """
        Retrieves all messages from the last 24 hours.
        
        Args:
            channel_id: Optional channel ID to filter messages by channel
            
        Returns:
            List of message dictionaries
        """
        if channel_id:
            query = """
            SELECT message_id, user_id, channel_id, content, timestamp, directed_at_bot 
            FROM short_term_message_log 
            WHERE timestamp >= ? AND channel_id = ?
            ORDER BY timestamp ASC
            """
        else:
            query = """
            SELECT message_id, user_id, channel_id, content, timestamp, directed_at_bot 
            FROM short_term_message_log 
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """
        
        twenty_four_hours_ago = (datetime.datetime.utcnow() - datetime.timedelta(hours=24)).isoformat()
        
        try:
            cursor = self.conn.cursor()
            if channel_id:
                cursor.execute(query, (twenty_four_hours_ago, channel_id))
            else:
                cursor.execute(query, (twenty_four_hours_ago,))
            rows = cursor.fetchall()
            cursor.close()
            
            return [{
                "message_id": row[0], 
                "author_id": row[1], 
                "channel_id": row[2],
                "content": row[3], 
                "timestamp": row[4], 
                "directed_at_bot": bool(row[5])
            } for row in rows]
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get short term memory: {e}")
            return []

    # --- Long-Term Memory Methods ---

    def get_long_term_memory(self, user_id):
        """
        Retrieves long-term memory facts for a given user, including the source.
        
        Args:
            user_id: Discord user ID
            
        Returns:
            List of tuples (fact, source_user_id, source_nickname)
        """
        query = "SELECT fact, source_user_id, source_nickname FROM long_term_memory WHERE user_id = ? ORDER BY reference_count DESC, last_mentioned_timestamp DESC"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get long term memory for user {user_id}: {e}")
            return []

    def add_long_term_memory(self, user_id, fact, source_user_id, source_nickname):
        """
        Adds a new long-term memory fact for a user, including the source.
        Checks for exact duplicates before adding.
        
        Args:
            user_id: Discord user ID this fact is about
            fact: The fact to remember
            source_user_id: Discord ID of who told the bot this fact
            source_nickname: Display name of who told the bot this fact
        """
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

    # --- Global State Methods (NEW) ---

    def get_global_state(self, key):
        """
        Retrieves a global state value by key.
        
        Args:
            key: The state key to retrieve
            
        Returns:
            The state value as a string, or None if not found
        """
        query = "SELECT state_value FROM global_state WHERE state_key = ?"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (key,))
            row = cursor.fetchone()
            cursor.close()
            return row[0] if row else None
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get global state for key '{key}': {e}")
            return None

    def set_global_state(self, key, value):
        """
        Sets or updates a global state value.
        
        Args:
            key: The state key
            value: The state value (will be converted to string)
        """
        query = """
        INSERT OR REPLACE INTO global_state (state_key, state_value, last_updated)
        VALUES (?, ?, ?)
        """
        now = datetime.datetime.utcnow().isoformat()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (key, str(value), now))
            self.conn.commit()
            cursor.close()
            print(f"DATABASE: Set global state '{key}' = '{value}'")
        except Exception as e:
            print(f"DATABASE ERROR: Failed to set global state for key '{key}': {e}")

    # --- Bot Identity Methods (NEW) ---

    def get_bot_identity(self, category=None):
        """
        Retrieves bot identity entries.
        
        Args:
            category: Optional category filter ('trait', 'lore', 'fact')
            
        Returns:
            List of content strings
        """
        if category:
            query = "SELECT content FROM bot_identity WHERE category = ?"
            params = (category,)
        else:
            query = "SELECT category, content FROM bot_identity"
            params = ()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            cursor.close()
            
            if category:
                return [row[0] for row in rows]
            else:
                return rows
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get bot identity: {e}")
            return []

    def add_bot_identity(self, category, content):
        """
        Adds a new bot identity entry.
        
        Args:
            category: 'trait', 'lore', or 'fact'
            content: The content to add
        """
        query = "INSERT INTO bot_identity (category, content) VALUES (?, ?)"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (category, content))
            self.conn.commit()
            cursor.close()
            print(f"DATABASE: Added bot identity - {category}: '{content}'")
        except Exception as e:
            print(f"DATABASE ERROR: Failed to add bot identity: {e}")

    # --- Relationship Metrics Methods (NEW) ---

    def get_relationship_metrics(self, user_id):
        """
        Retrieves relationship metrics for a user.
        Auto-creates a record with default values (0,0,0,0) if none exists.

        Args:
            user_id: Discord user ID

        Returns:
            Dictionary with anger, rapport, trust, formality values
        """
        query = "SELECT anger, rapport, trust, formality FROM relationship_metrics WHERE user_id = ?"
        insert_query = "INSERT INTO relationship_metrics (user_id, anger, rapport, trust, formality) VALUES (?, 0, 0, 0, 0)"

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()

            if row:
                cursor.close()
                return {
                    "anger": row[0],
                    "rapport": row[1],
                    "trust": row[2],
                    "formality": row[3]
                }
            else:
                # Auto-create record with default values
                cursor.execute(insert_query, (user_id,))
                self.conn.commit()
                cursor.close()
                print(f"DATABASE: Auto-created relationship metrics for user {user_id} with defaults (0,0,0,0)")
                return {
                    "anger": 0,
                    "rapport": 0,
                    "trust": 0,
                    "formality": 0
                }
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get relationship metrics for user {user_id}: {e}")
            return {"anger": 0, "rapport": 0, "trust": 0, "formality": 0}

    def update_relationship_metrics(self, user_id, **kwargs):
        """
        Updates relationship metrics for a user.
        
        Args:
            user_id: Discord user ID
            **kwargs: anger, rapport, trust, formality (any combination)
        """
        # First, ensure a record exists
        check_query = "SELECT user_id FROM relationship_metrics WHERE user_id = ?"
        insert_query = "INSERT INTO relationship_metrics (user_id) VALUES (?)"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute(check_query, (user_id,))
            if cursor.fetchone() is None:
                cursor.execute(insert_query, (user_id,))
                self.conn.commit()
            
            # Now update the metrics
            updates = []
            params = []
            for key, value in kwargs.items():
                if key in ['anger', 'rapport', 'trust', 'formality']:
                    updates.append(f"{key} = ?")
                    params.append(value)
            
            if updates:
                query = f"UPDATE relationship_metrics SET {', '.join(updates)} WHERE user_id = ?"
                params.append(user_id)
                cursor.execute(query, params)
                self.conn.commit()
                print(f"DATABASE: Updated relationship metrics for user {user_id}")
            
            cursor.close()
        except Exception as e:
            print(f"DATABASE ERROR: Failed to update relationship metrics for user {user_id}: {e}")

    # --- Archival and Cleanup Methods ---

    def archive_and_clear_short_term_memory(self):
        """
        Archives all short-term messages to a JSON file in database/archive/,
        then deletes them from the short_term_message_log table.

        Returns:
            Tuple of (archived_count, deleted_count, archive_filename)
        """
        import json

        # Create archive directory if it doesn't exist
        archive_dir = os.path.join(DB_FOLDER, "archive")
        os.makedirs(archive_dir, exist_ok=True)

        try:
            # Get ALL messages from short_term_message_log (no time filter)
            query = """
            SELECT message_id, user_id, channel_id, content, timestamp, directed_at_bot
            FROM short_term_message_log
            ORDER BY timestamp ASC
            """

            cursor = self.conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()

            if not rows:
                print("DATABASE: No messages to archive in short-term memory.")
                cursor.close()
                return (0, 0, None)

            # Convert to list of dictionaries
            messages = [{
                "message_id": row[0],
                "user_id": row[1],
                "channel_id": row[2],
                "content": row[3],
                "timestamp": row[4],
                "directed_at_bot": bool(row[5])
            } for row in rows]

            # Create archive filename with timestamp
            archive_timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            archive_filename = f"short_term_archive_{archive_timestamp}.json"
            archive_path = os.path.join(archive_dir, archive_filename)

            # Write to JSON file
            with open(archive_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "archived_at": datetime.datetime.utcnow().isoformat(),
                    "message_count": len(messages),
                    "messages": messages
                }, f, indent=2, ensure_ascii=False)

            archived_count = len(messages)
            print(f"DATABASE: Archived {archived_count} messages to {archive_filename}")

            # Now delete all messages from short_term_message_log
            delete_query = "DELETE FROM short_term_message_log"
            cursor.execute(delete_query)
            deleted_count = cursor.rowcount
            self.conn.commit()
            cursor.close()

            print(f"DATABASE: Deleted {deleted_count} messages from short_term_message_log")
            print(f"DATABASE: Archive saved to: {archive_path}")

            return (archived_count, deleted_count, archive_filename)

        except Exception as e:
            print(f"DATABASE ERROR: Failed to archive and clear short-term memory: {e}")
            return (0, 0, None)

    def close(self):
        """Closes the database connection."""
        if self.conn:
            try:
                self.conn.close()
                print("Database connection closed.")
            except Exception as e:
                print(f"DATABASE ERROR: Failed to close connection: {e}")




