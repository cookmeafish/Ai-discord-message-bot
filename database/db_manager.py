# database/db_manager.py
import sqlite3
import os
import re
from . import schemas
from .input_validator import InputValidator
import datetime

# Define the location for the database file
DB_FOLDER = "database"
DB_FILE = "bot_data.db"
DB_PATH = os.path.join(DB_FOLDER, DB_FILE)

class DBManager:
    """Handles all database operations for the bot."""
    def __init__(self, db_path=None):
        """
        Initialize database manager.

        Args:
            db_path: Optional custom database path. If None, uses default path.
        """
        # Use custom path or default
        if db_path:
            self.db_path = db_path
            # Ensure parent directory exists
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)
        else:
            # Ensure the 'database' directory exists
            os.makedirs(DB_FOLDER, exist_ok=True)
            self.db_path = DB_PATH

        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Enable foreign key constraints
            self.conn.execute("PRAGMA foreign_keys = ON")
            # Enable auto-vacuum for automatic database compaction
            self.conn.execute("PRAGMA auto_vacuum = FULL")
            self._initialize_database()
            self._ensure_archive_directory()
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
            # Run migrations for existing databases
            self._run_migrations()
        except Exception as e:
            print(f"DATABASE ERROR: Failed to initialize tables: {e}")
            raise
        finally:
            cursor.close()

    def _run_migrations(self):
        """
        Runs database migrations to add new columns to existing tables.
        This is safe to run multiple times - it only adds columns that don't exist.
        """
        cursor = self.conn.cursor()
        try:
            # Migration: Add conversation detection columns to channel_settings (2025-01-23)
            self._add_column_if_not_exists(
                cursor,
                'channel_settings',
                'enable_conversation_detection',
                'INTEGER DEFAULT 0'
            )
            self._add_column_if_not_exists(
                cursor,
                'channel_settings',
                'conversation_detection_threshold',
                'REAL DEFAULT 0.7'
            )
            self._add_column_if_not_exists(
                cursor,
                'channel_settings',
                'conversation_context_window',
                'INTEGER DEFAULT 10'
            )

            # Migration: Add random event columns to channel_settings (2025-12-01)
            self._add_column_if_not_exists(
                cursor,
                'channel_settings',
                'random_event_enabled',
                'INTEGER DEFAULT 0'
            )
            self._add_column_if_not_exists(
                cursor,
                'channel_settings',
                'random_event_chance',
                'REAL DEFAULT 50.0'
            )
            self._add_column_if_not_exists(
                cursor,
                'channel_settings',
                'random_event_interval_hours',
                'REAL DEFAULT 5.0'
            )

            self.conn.commit()
            print("Database migrations completed successfully.")
        except Exception as e:
            print(f"DATABASE WARNING: Migration error (may be safe to ignore): {e}")
            # Don't raise - migrations are best-effort for backwards compatibility
        finally:
            cursor.close()

    def _add_column_if_not_exists(self, cursor, table_name, column_name, column_definition):
        """
        Adds a column to a table if it doesn't already exist.

        Args:
            cursor: Database cursor
            table_name: Name of the table
            column_name: Name of the column to add
            column_definition: SQL definition for the column (e.g., 'INTEGER DEFAULT 0')
        """
        # Check if column exists
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]

        if column_name not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")
            print(f"Added column '{column_name}' to table '{table_name}'")

    def _ensure_archive_directory(self):
        """
        Ensures the archive directory exists for this database.
        Creates the directory structure based on the database path format.
        Called during initialization to prepare for future memory consolidation.
        """
        import re

        db_dir = os.path.dirname(self.db_path)
        db_filename = os.path.basename(self.db_path)

        # Determine archive directory based on database structure
        match = re.match(r'^(\d+)_data\.db$', db_filename)
        if match:
            # New format: {guild_id}_data.db in a server folder
            archive_dir = os.path.join(db_dir, "archive")
        elif db_filename == "data.db":
            # Legacy folder structure: data.db
            archive_dir = os.path.join(db_dir, "archive")
        else:
            # Very old flat structure: database/{guild_id}_{name}_data.db
            archive_dir = os.path.join(DB_FOLDER, "archive")

        # Create archive directory if it doesn't exist
        try:
            os.makedirs(archive_dir, exist_ok=True)
            print(f"Archive directory ensured: {archive_dir}")
        except Exception as e:
            print(f"WARNING: Failed to create archive directory {archive_dir}: {e}")

    # --- Message Logging Methods ---

    def log_message(self, message, directed_at_bot=False):
        """
        Logs a message to the short_term_message_log table.
        Also logs the user's nickname for GUI display purposes.

        Args:
            message: Discord message object
            directed_at_bot: Boolean indicating if the message was directed at the bot

        Returns:
            bool: True if logged successfully, False if validation failed
        """
        # Validate message content
        is_valid, error = InputValidator.validate_message_content(message.content)
        if not is_valid:
            print(f"DATABASE: Rejected message {message.id}: {error}")
            return False

        # Ensure user exists before logging nickname (prevents foreign key constraint failure)
        self._ensure_user_exists(message.author.id)

        query = """
        INSERT OR REPLACE INTO short_term_message_log (message_id, user_id, nickname, channel_id, content, timestamp, directed_at_bot)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        timestamp = message.created_at.isoformat()
        directed_flag = 1 if directed_at_bot else 0

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (
                message.id,
                message.author.id,
                message.author.display_name,
                message.channel.id,
                message.content,
                timestamp,
                directed_flag
            ))

            # Also log the nickname for GUI display
            self._log_nickname(message.author.id, message.author.display_name, timestamp)

            self.conn.commit()
            cursor.close()
            return True
        except sqlite3.IntegrityError:
            # Message already exists, skip silently
            return True
        except Exception as e:
            print(f"DATABASE ERROR: Failed to log message {message.id}: {e}")
            return False

    def _log_nickname(self, user_id, nickname, timestamp):
        """
        Internal helper to log user nicknames for GUI display.

        Args:
            user_id: Discord user ID
            nickname: User's display name
            timestamp: ISO format timestamp
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO nicknames (user_id, nickname, timestamp) VALUES (?, ?, ?)",
                (user_id, nickname, timestamp)
            )
            # Don't commit here - let the caller commit
        except Exception as e:
            # Silently fail - nickname logging is not critical
            pass

    def get_short_term_memory(self, channel_id=None):
        """
        Retrieves all messages from the short_term_message_log table.

        Args:
            channel_id: Optional channel ID to filter messages by channel

        Returns:
            List of message dictionaries
        """
        if channel_id:
            query = """
            SELECT message_id, user_id, nickname, channel_id, content, timestamp, directed_at_bot
            FROM short_term_message_log
            WHERE channel_id = ?
            ORDER BY timestamp ASC
            """
        else:
            query = """
            SELECT message_id, user_id, nickname, channel_id, content, timestamp, directed_at_bot
            FROM short_term_message_log
            ORDER BY timestamp ASC
            """

        try:
            cursor = self.conn.cursor()
            if channel_id:
                cursor.execute(query, (channel_id,))
            else:
                cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()

            return [{
                "message_id": row[0],
                "author_id": row[1],
                "nickname": row[2],
                "channel_id": row[3],
                "content": row[4],
                "timestamp": row[5],
                "directed_at_bot": bool(row[6])
            } for row in rows]
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get short term memory: {e}")
            return []

    def get_short_term_message_count(self):
        """
        Returns the total number of messages in the short_term_message_log table.

        Returns:
            Integer count of messages
        """
        query = "SELECT COUNT(*) FROM short_term_message_log"

        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            count = cursor.fetchone()[0]
            cursor.close()
            return count
        except Exception as e:
            print(f"DATABASE ERROR: Failed to count short term messages: {e}")
            return 0

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

    def get_all_long_term_memory(self):
        """
        Retrieves ALL long-term memory facts across all users.
        Used for searching when we don't know which user the fact is about.

        Returns:
            List of tuples (fact, source_user_id, source_nickname)
        """
        query = "SELECT fact, source_user_id, source_nickname FROM long_term_memory ORDER BY reference_count DESC, last_mentioned_timestamp DESC"

        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            return rows
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get all long term memory: {e}")
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

        Returns:
            bool: True if fact added successfully, False if validation failed
        """
        # Validate inputs
        is_valid, error = InputValidator.validate_fact(fact)
        if not is_valid:
            print(f"DATABASE: Rejected invalid fact: {error}")
            return False

        is_valid, error = InputValidator.validate_nickname(source_nickname)
        if not is_valid:
            print(f"DATABASE: Rejected invalid nickname: {error}")
            return False

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
                cursor.close()
                return True
            else:
                print(f"DATABASE: Fact already exists for user {user_id}, not saving duplicate.")
                cursor.close()
                return False
        except Exception as e:
            print(f"DATABASE ERROR: Failed to add long-term memory for user {user_id}: {e}")
            return False

    def find_contradictory_memory(self, user_id, new_fact):
        """
        Finds facts that may contradict the new fact.
        Returns active facts only (status != 'superseded').

        Args:
            user_id: Discord user ID
            new_fact: The new fact to check against

        Returns:
            List of tuples (fact_id, fact_text) for potential contradictions
        """
        # NOTE: After migration, use status filter. Before migration, this will work without it.
        try:
            query = "SELECT id, fact FROM long_term_memory WHERE user_id = ?"
            # Try to filter by status if column exists
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(long_term_memory)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'status' in columns:
                query += " AND (status IS NULL OR status = 'active')"

            cursor.execute(query, (user_id,))
            rows = cursor.fetchall()
            cursor.close()

            return [(row[0], row[1]) for row in rows]

        except Exception as e:
            print(f"DATABASE ERROR: Failed to find contradictory memories: {e}")
            return []

    def update_long_term_memory_fact(self, fact_id, new_fact_text):
        """
        Updates an existing long-term memory fact.
        Increments reference_count and updates last_mentioned_timestamp.

        Args:
            fact_id: ID of the fact to update
            new_fact_text: New fact text

        Returns:
            bool: True if update successful, False otherwise
        """
        # Validate input
        is_valid, error = InputValidator.validate_fact(new_fact_text)
        if not is_valid:
            print(f"DATABASE: Cannot update fact - {error}")
            return False

        query = """
        UPDATE long_term_memory
        SET fact = ?,
            last_mentioned_timestamp = ?,
            reference_count = reference_count + 1
        WHERE id = ?
        """
        now = datetime.datetime.utcnow().isoformat()

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (new_fact_text, now, fact_id))
            self.conn.commit()
            cursor.close()
            print(f"DATABASE: Updated fact ID {fact_id} to: '{new_fact_text}'")
            return True
        except Exception as e:
            print(f"DATABASE ERROR: Failed to update fact {fact_id}: {e}")
            return False

    def supersede_long_term_memory_fact(self, old_fact_id, new_fact_id=None):
        """
        Marks an old fact as superseded by a new fact (soft delete).
        NOTE: Requires migration to add status column first.

        Args:
            old_fact_id: ID of the fact to supersede
            new_fact_id: Optional ID of the fact that replaces it

        Returns:
            bool: True if supersede successful, False otherwise
        """
        # Check if status column exists
        try:
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(long_term_memory)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'status' not in columns:
                print(f"DATABASE: Cannot supersede fact - status column does not exist. Run migration first.")
                cursor.close()
                return False

            query = """
            UPDATE long_term_memory
            SET status = 'superseded',
                superseded_by_id = ?,
                last_mentioned_timestamp = ?
            WHERE id = ?
            """
            now = datetime.datetime.utcnow().isoformat()

            cursor.execute(query, (new_fact_id, now, old_fact_id))
            self.conn.commit()
            cursor.close()
            print(f"DATABASE: Superseded fact ID {old_fact_id} (replaced by: {new_fact_id})")
            return True

        except Exception as e:
            print(f"DATABASE ERROR: Failed to supersede fact {old_fact_id}: {e}")
            return False

    def delete_long_term_memory_fact(self, fact_id):
        """
        Permanently deletes a long-term memory fact.
        WARNING: This is irreversible. Prefer supersede_long_term_memory_fact() for soft deletes.

        Args:
            fact_id: ID of the fact to delete

        Returns:
            bool: True if deletion successful, False otherwise
        """
        query = "DELETE FROM long_term_memory WHERE id = ?"

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (fact_id,))
            self.conn.commit()
            cursor.close()
            print(f"DATABASE: Permanently deleted fact ID {fact_id}")
            return True
        except Exception as e:
            print(f"DATABASE ERROR: Failed to delete fact {fact_id}: {e}")
            return False

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

        Returns:
            bool: True if added successfully, False if validation failed
        """
        # Validate category (whitelist approach)
        if not InputValidator.validate_bot_identity_category(category):
            print(f"DATABASE: Rejected invalid bot identity category: {category}")
            return False

        # Validate content
        is_valid, error = InputValidator.validate_bot_identity_content(content)
        if not is_valid:
            print(f"DATABASE: Rejected invalid bot identity content: {error}")
            return False

        query = "INSERT INTO bot_identity (category, content) VALUES (?, ?)"

        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (category, content))
            self.conn.commit()
            cursor.close()
            print(f"DATABASE: Added bot identity - {category}: '{content}'")
            return True
        except Exception as e:
            print(f"DATABASE ERROR: Failed to add bot identity: {e}")
            return False

    # --- User Management Methods ---

    def _ensure_user_exists(self, user_id):
        """
        Ensures a user record exists in the users table.
        Creates one if it doesn't exist.

        Args:
            user_id: Discord user ID
        """
        check_query = "SELECT user_id FROM users WHERE user_id = ?"
        insert_query = "INSERT INTO users (user_id, first_seen, last_seen) VALUES (?, ?, ?)"

        try:
            cursor = self.conn.cursor()
            cursor.execute(check_query, (user_id,))
            if cursor.fetchone() is None:
                now = datetime.datetime.utcnow().isoformat()
                cursor.execute(insert_query, (user_id, now, now))
                self.conn.commit()
                print(f"DATABASE: Created user record for {user_id}")
            cursor.close()
        except Exception as e:
            print(f"DATABASE ERROR: Failed to ensure user exists for {user_id}: {e}")

    # --- Relationship Metrics Methods (NEW) ---

    def get_relationship_metrics(self, user_id):
        """
        Retrieves relationship metrics for a user, including lock status.
        Auto-creates a record with default values if none exists.

        Args:
            user_id: Discord user ID

        Returns:
            Dictionary with all relationship metric values and their lock status
        """
        # Check which columns exist
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info(relationship_metrics)")
        columns = [row[1] for row in cursor.fetchall()]
        has_locks = 'rapport_locked' in columns
        has_new_metrics = 'fear' in columns

        # Build query based on available columns
        base_metrics = ["anger", "rapport", "trust", "formality"]
        new_metrics = ["fear", "respect", "affection", "familiarity", "intimidation"]

        select_cols = base_metrics.copy()
        if has_new_metrics:
            select_cols.extend(new_metrics)

        if has_locks:
            lock_cols = [f"{m}_locked" for m in select_cols]
            select_cols.extend(lock_cols)

        query = f"SELECT {', '.join(select_cols)} FROM relationship_metrics WHERE user_id = ?"
        insert_query = "INSERT INTO relationship_metrics (user_id, anger, rapport, trust, formality, fear, respect, affection, familiarity, intimidation) VALUES (?, 0, 5, 5, 0, 0, 5, 3, 5, 0)"

        try:
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()

            if row:
                cursor.close()
                result = {
                    "anger": row[0],
                    "rapport": row[1],
                    "trust": row[2],
                    "formality": row[3]
                }

                # Add new metrics if they exist
                if has_new_metrics:
                    result.update({
                        "fear": row[4],
                        "respect": row[5],
                        "affection": row[6],
                        "familiarity": row[7],
                        "intimidation": row[8]
                    })

                # Add lock status if locks exist
                if has_locks:
                    lock_offset = 9 if has_new_metrics else 4
                    result.update({
                        "rapport_locked": bool(row[lock_offset]),
                        "anger_locked": bool(row[lock_offset + 1]),
                        "trust_locked": bool(row[lock_offset + 2]),
                        "formality_locked": bool(row[lock_offset + 3])
                    })
                    if has_new_metrics:
                        result.update({
                            "fear_locked": bool(row[lock_offset + 4]),
                            "respect_locked": bool(row[lock_offset + 5]),
                            "affection_locked": bool(row[lock_offset + 6]),
                            "familiarity_locked": bool(row[lock_offset + 7]),
                            "intimidation_locked": bool(row[lock_offset + 8])
                        })

                return result
            else:
                # Ensure user exists in users table first (for foreign key constraint)
                cursor.close()
                self._ensure_user_exists(user_id)

                # Now create relationship metrics record
                cursor = self.conn.cursor()
                cursor.execute(insert_query, (user_id,))
                self.conn.commit()
                cursor.close()
                print(f"DATABASE: Auto-created relationship metrics for user {user_id} with defaults")
                result = {
                    "anger": 0,
                    "rapport": 5,
                    "trust": 5,
                    "formality": 0
                }
                if has_new_metrics:
                    result.update({
                        "fear": 0,
                        "respect": 5,
                        "affection": 3,
                        "familiarity": 5,
                        "intimidation": 0
                    })
                if has_locks:
                    result.update({
                        "rapport_locked": False,
                        "anger_locked": False,
                        "trust_locked": False,
                        "formality_locked": False
                    })
                    if has_new_metrics:
                        result.update({
                            "fear_locked": False,
                            "respect_locked": False,
                            "affection_locked": False,
                            "familiarity_locked": False,
                            "intimidation_locked": False
                        })
                return result
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get relationship metrics for user {user_id}: {e}")
            result = {"anger": 0, "rapport": 0, "trust": 0, "formality": 0}
            if has_new_metrics:
                result.update({
                    "fear": 0,
                    "respect": 0,
                    "affection": 0,
                    "familiarity": 0,
                    "intimidation": 0
                })
            if has_locks:
                result.update({
                    "rapport_locked": False,
                    "anger_locked": False,
                    "trust_locked": False,
                    "formality_locked": False
                })
                if has_new_metrics:
                    result.update({
                        "fear_locked": False,
                        "respect_locked": False,
                        "affection_locked": False,
                        "familiarity_locked": False,
                        "intimidation_locked": False
                    })
            return result

    def update_relationship_metrics(self, user_id, respect_locks=True, **kwargs):
        """
        Updates relationship metrics for a user.

        Args:
            user_id: Discord user ID
            respect_locks: If True, won't update locked metrics (default: True)
            **kwargs: Any combination of metrics (anger, rapport, trust, formality, fear, respect, affection, familiarity, intimidation)
                     and their lock flags (*_locked)
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

            # If respecting locks, check which metrics are locked
            locked_metrics = set()
            if respect_locks:
                cursor.execute("PRAGMA table_info(relationship_metrics)")
                columns = [row[1] for row in cursor.fetchall()]
                has_locks = 'rapport_locked' in columns
                has_new_metrics = 'fear' in columns

                if has_locks:
                    # Build lock query dynamically based on available columns
                    lock_cols = ["rapport_locked", "anger_locked", "trust_locked", "formality_locked"]
                    if has_new_metrics:
                        lock_cols.extend(["fear_locked", "respect_locked", "affection_locked", "familiarity_locked", "intimidation_locked"])

                    cursor.execute(f"SELECT {', '.join(lock_cols)} FROM relationship_metrics WHERE user_id = ?", (user_id,))
                    row = cursor.fetchone()
                    if row:
                        metric_names = ["rapport", "anger", "trust", "formality"]
                        if has_new_metrics:
                            metric_names.extend(["fear", "respect", "affection", "familiarity", "intimidation"])

                        for i, metric_name in enumerate(metric_names):
                            if row[i]:
                                locked_metrics.add(metric_name)

            # Now update the metrics (with whitelist validation and lock checking)
            updates = []
            params = []
            for key, value in kwargs.items():
                # SECURITY: Whitelist validation for column names
                if InputValidator.validate_metric_key(key) or key.endswith('_locked'):
                    # Skip locked metrics unless we're updating the lock itself
                    if key in locked_metrics and respect_locks:
                        print(f"DATABASE: Skipped updating locked metric '{key}' for user {user_id}")
                        continue

                    updates.append(f"{key} = ?")
                    params.append(value)
                else:
                    print(f"DATABASE: Rejected invalid metric key: {key}")

            if updates:
                query = f"UPDATE relationship_metrics SET {', '.join(updates)} WHERE user_id = ?"
                params.append(user_id)
                cursor.execute(query, params)
                self.conn.commit()
                print(f"DATABASE: Updated relationship metrics for user {user_id}")

            cursor.close()
        except Exception as e:
            print(f"DATABASE ERROR: Failed to update relationship metrics for user {user_id}: {e}")

    def get_all_users_with_metrics(self):
        """
        Retrieves all users that have relationship metrics in the database.

        Returns:
            List of dictionaries with user_id and their metrics (including locks if available)
        """
        try:
            cursor = self.conn.cursor()

            # Check which columns exist
            cursor.execute("PRAGMA table_info(relationship_metrics)")
            columns = [row[1] for row in cursor.fetchall()]
            has_locks = 'rapport_locked' in columns
            has_new_metrics = 'fear' in columns

            # Build query based on available columns
            base_metrics = ["anger", "rapport", "trust", "formality"]
            new_metrics = ["fear", "respect", "affection", "familiarity", "intimidation"]

            select_cols = ["user_id"] + base_metrics.copy()
            if has_new_metrics:
                select_cols.extend(new_metrics)

            if has_locks:
                lock_cols = [f"{m}_locked" for m in (base_metrics + (new_metrics if has_new_metrics else []))]
                select_cols.extend(lock_cols)

            query = f"SELECT {', '.join(select_cols)} FROM relationship_metrics ORDER BY user_id"

            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()

            users = []
            for row in rows:
                user_data = {
                    "user_id": row[0],
                    "anger": row[1],
                    "rapport": row[2],
                    "trust": row[3],
                    "formality": row[4]
                }

                # Add new metrics if they exist
                if has_new_metrics:
                    user_data.update({
                        "fear": row[5],
                        "respect": row[6],
                        "affection": row[7],
                        "familiarity": row[8],
                        "intimidation": row[9]
                    })

                # Add lock status if locks exist
                if has_locks:
                    lock_offset = 10 if has_new_metrics else 5
                    user_data.update({
                        "rapport_locked": bool(row[lock_offset]),
                        "anger_locked": bool(row[lock_offset + 1]),
                        "trust_locked": bool(row[lock_offset + 2]),
                        "formality_locked": bool(row[lock_offset + 3])
                    })
                    if has_new_metrics:
                        user_data.update({
                            "fear_locked": bool(row[lock_offset + 4]),
                            "respect_locked": bool(row[lock_offset + 5]),
                            "affection_locked": bool(row[lock_offset + 6]),
                            "familiarity_locked": bool(row[lock_offset + 7]),
                            "intimidation_locked": bool(row[lock_offset + 8])
                        })

                users.append(user_data)

            return users

        except Exception as e:
            print(f"DATABASE ERROR: Failed to get all users with metrics: {e}")
            return []

    # --- Archival and Cleanup Methods ---

    def archive_and_clear_short_term_memory(self):
        """
        Archives all short-term messages to a JSON file in the server's archive folder,
        then deletes them from the short_term_message_log table.

        Returns:
            Tuple of (archived_count, deleted_count, archive_filename)
        """
        import json

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

            # Determine archive directory based on db_path structure
            # New format: database/{server_name}/{guild_id}_data.db -> database/{server_name}/archive/
            # Legacy formats handled for backward compatibility
            db_dir = os.path.dirname(self.db_path)
            db_filename = os.path.basename(self.db_path)

            # Try to extract guild_id from filename
            match = re.match(r'^(\d+)_data\.db$', db_filename)
            if match:
                # New format: {guild_id}_data.db in a server folder
                guild_id = match.group(1)
                archive_dir = os.path.join(db_dir, "archive")
                archive_timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                archive_filename = f"short_term_archive_{archive_timestamp}.json"
            elif db_filename == "data.db":
                # Legacy folder structure: data.db
                archive_dir = os.path.join(db_dir, "archive")
                guild_id = os.path.basename(db_dir)  # Use folder name as guild_id
                archive_timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                archive_filename = f"short_term_archive_{archive_timestamp}.json"
            else:
                # Very old flat structure: database/{guild_id}_{name}_data.db
                archive_dir = os.path.join(DB_FOLDER, "archive")
                guild_id = db_filename.split('_')[0] if '_' in db_filename else "unknown"
                archive_timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                archive_filename = f"short_term_archive_{guild_id}_{archive_timestamp}.json"

            # Create archive directory if it doesn't exist
            os.makedirs(archive_dir, exist_ok=True)
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

    # --- Image Rate Limiting Methods ---

    def increment_user_image_count(self, user_id, reset_period_hours=1):
        """
        Increments the image count for a user. Creates a new record if none exists.
        Resets count if the specified period has passed.

        Args:
            user_id: Discord user ID
            reset_period_hours: Hours before count resets (default: 1 for hourly, can be 2 for image generation)
        """
        now = datetime.datetime.utcnow()
        today = now.date().isoformat()
        period_seconds = reset_period_hours * 3600

        try:
            cursor = self.conn.cursor()

            # Check if user has a record
            cursor.execute("SELECT last_image_time, hourly_count, daily_count, date FROM user_image_stats WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                last_image_time_str, hourly_count, daily_count, date = row
                last_image_time = datetime.datetime.fromisoformat(last_image_time_str)

                # Check if we need to reset hourly count based on period
                if (now - last_image_time).total_seconds() >= period_seconds:
                    hourly_count = 0

                # Check if we need to reset daily count (different day)
                if date != today:
                    daily_count = 0

                # Increment counts
                hourly_count += 1
                daily_count += 1

                # Update record
                cursor.execute("""
                    UPDATE user_image_stats
                    SET last_image_time = ?, hourly_count = ?, daily_count = ?, date = ?
                    WHERE user_id = ?
                """, (now.isoformat(), hourly_count, daily_count, today, user_id))
            else:
                # Create new record
                cursor.execute("""
                    INSERT INTO user_image_stats (user_id, last_image_time, hourly_count, daily_count, date)
                    VALUES (?, ?, 1, 1, ?)
                """, (user_id, now.isoformat(), today))

            self.conn.commit()
            cursor.close()
            print(f"DATABASE: Incremented image count for user {user_id} (period: {reset_period_hours}h)")

        except Exception as e:
            print(f"DATABASE ERROR: Failed to increment image count for user {user_id}: {e}")

    def get_user_image_count_last_hour(self, user_id):
        """
        Gets the number of images a user has sent in the last hour.

        Args:
            user_id: Discord user ID

        Returns:
            Integer count of images sent in the last hour
        """
        now = datetime.datetime.utcnow()

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT last_image_time, hourly_count FROM user_image_stats WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return 0

            last_image_time_str, hourly_count = row
            last_image_time = datetime.datetime.fromisoformat(last_image_time_str)

            # If more than 1 hour has passed, count is 0
            if (now - last_image_time).total_seconds() >= 3600:
                return 0

            return hourly_count

        except Exception as e:
            print(f"DATABASE ERROR: Failed to get hourly image count for user {user_id}: {e}")
            return 0

    def get_user_image_count_today(self, user_id):
        """
        Gets the number of images a user has sent today.

        Args:
            user_id: Discord user ID

        Returns:
            Integer count of images sent today
        """
        today = datetime.datetime.utcnow().date().isoformat()

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT daily_count, date FROM user_image_stats WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return 0

            daily_count, date = row

            # If different day, count is 0
            if date != today:
                return 0

            return daily_count

        except Exception as e:
            print(f"DATABASE ERROR: Failed to get daily image count for user {user_id}: {e}")
            return 0

    def get_user_image_generation_count(self, user_id, period_hours):
        """
        Gets the number of generated images (AI drawings) a user has requested within a time period.
        Uses the same user_image_stats table but checks against the configurable period.

        Args:
            user_id: Discord user ID
            period_hours: Number of hours for the reset period (e.g., 2 for every 2 hours)

        Returns:
            Integer count of images generated within the period
        """
        now = datetime.datetime.utcnow()
        period_seconds = period_hours * 3600

        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT last_image_time, hourly_count FROM user_image_stats WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return 0

            last_image_time_str, count = row
            last_image_time = datetime.datetime.fromisoformat(last_image_time_str)

            # If more than period_hours has passed, count is 0
            if (now - last_image_time).total_seconds() >= period_seconds:
                return 0

            return count

        except Exception as e:
            print(f"DATABASE ERROR: Failed to get image generation count for user {user_id}: {e}")
            return 0

    # --- Channel Settings Methods (Per-Server) ---

    def add_channel_setting(self, channel_id, guild_id, channel_name=None, purpose=None,
                           random_reply_chance=None, immersive_character=None,
                           allow_technical_language=None, use_server_info=None,
                           enable_roleplay_formatting=None, allow_proactive_engagement=None,
                           enable_conversation_detection=None, conversation_detection_threshold=None,
                           conversation_context_window=None,
                           formality=None, formality_locked=None):
        """
        Adds or updates a channel setting in the database.

        Args:
            channel_id: Discord channel ID (str)
            guild_id: Discord guild ID (str)
            channel_name: Human-readable channel name
            purpose: Channel-specific instructions
            random_reply_chance: Probability of random replies (0.0-1.0)
            immersive_character: Whether bot believes it's the character (bool)
            allow_technical_language: Whether bot can use technical terms (bool)
            use_server_info: Whether to load Server_Info files (bool)
            enable_roleplay_formatting: Whether to format actions in italics (bool)
            allow_proactive_engagement: Whether bot can join conversations proactively (bool)
            formality: Formality level (-5 to +5)
            formality_locked: Whether formality is locked from auto-updates (bool)

        Returns:
            Dictionary with the final channel settings
        """
        from datetime import datetime

        try:
            cursor = self.conn.cursor()

            # Check if channel already exists
            cursor.execute("SELECT * FROM channel_settings WHERE channel_id = ?", (channel_id,))
            existing = cursor.fetchone()

            if existing:
                # Update existing channel
                update_fields = []
                update_values = []

                if channel_name is not None:
                    update_fields.append("channel_name = ?")
                    update_values.append(channel_name)
                if purpose is not None:
                    update_fields.append("purpose = ?")
                    update_values.append(purpose)
                if random_reply_chance is not None:
                    update_fields.append("random_reply_chance = ?")
                    update_values.append(random_reply_chance)
                if immersive_character is not None:
                    update_fields.append("immersive_character = ?")
                    update_values.append(1 if immersive_character else 0)
                if allow_technical_language is not None:
                    update_fields.append("allow_technical_language = ?")
                    update_values.append(1 if allow_technical_language else 0)
                if use_server_info is not None:
                    update_fields.append("use_server_info = ?")
                    update_values.append(1 if use_server_info else 0)
                if enable_roleplay_formatting is not None:
                    update_fields.append("enable_roleplay_formatting = ?")
                    update_values.append(1 if enable_roleplay_formatting else 0)
                if allow_proactive_engagement is not None:
                    update_fields.append("allow_proactive_engagement = ?")
                    update_values.append(1 if allow_proactive_engagement else 0)
                if enable_conversation_detection is not None:
                    update_fields.append("enable_conversation_detection = ?")
                    update_values.append(1 if enable_conversation_detection else 0)
                if conversation_detection_threshold is not None:
                    update_fields.append("conversation_detection_threshold = ?")
                    update_values.append(conversation_detection_threshold)
                if conversation_context_window is not None:
                    update_fields.append("conversation_context_window = ?")
                    update_values.append(conversation_context_window)
                if formality is not None:
                    update_fields.append("formality = ?")
                    update_values.append(formality)
                if formality_locked is not None:
                    update_fields.append("formality_locked = ?")
                    update_values.append(1 if formality_locked else 0)

                if update_fields:
                    update_values.append(channel_id)
                    update_query = f"UPDATE channel_settings SET {', '.join(update_fields)} WHERE channel_id = ?"
                    cursor.execute(update_query, tuple(update_values))
                    self.conn.commit()
                    print(f"DATABASE: Updated channel settings for {channel_id}")
            else:
                # Insert new channel
                now = datetime.utcnow().isoformat()
                cursor.execute("""
                    INSERT INTO channel_settings (
                        channel_id, guild_id, channel_name, purpose, random_reply_chance,
                        immersive_character, allow_technical_language, use_server_info,
                        enable_roleplay_formatting, allow_proactive_engagement,
                        enable_conversation_detection, conversation_detection_threshold,
                        conversation_context_window,
                        formality, formality_locked, activated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    channel_id, guild_id, channel_name, purpose,
                    random_reply_chance if random_reply_chance is not None else 0.0,
                    1 if immersive_character is True else (0 if immersive_character is False else 1),
                    1 if allow_technical_language is True else (0 if allow_technical_language is False else 0),
                    1 if use_server_info is True else (0 if use_server_info is False else 0),
                    1 if enable_roleplay_formatting is True else (0 if enable_roleplay_formatting is False else 1),
                    1 if allow_proactive_engagement is True else (0 if allow_proactive_engagement is False else 1),
                    1 if enable_conversation_detection is True else (0 if enable_conversation_detection is False else 0),
                    conversation_detection_threshold if conversation_detection_threshold is not None else 0.7,
                    conversation_context_window if conversation_context_window is not None else 10,
                    formality if formality is not None else 0,
                    1 if formality_locked is True else (0 if formality_locked is False else 0),
                    now
                ))
                self.conn.commit()
                print(f"DATABASE: Added channel settings for {channel_id}")

            cursor.close()

            # Return the final settings
            return self.get_channel_setting(channel_id)

        except Exception as e:
            print(f"DATABASE ERROR: Failed to add/update channel setting for {channel_id}: {e}")
            return None

    def get_channel_setting(self, channel_id):
        """
        Retrieves settings for a specific channel.

        Args:
            channel_id: Discord channel ID (str)

        Returns:
            Dictionary with channel settings, or None if not found
        """
        try:
            cursor = self.conn.cursor()

            # First verify the table exists (handles legacy databases)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_settings'")
            if not cursor.fetchone():
                print(f"DATABASE WARNING: channel_settings table does not exist, channel {channel_id} is not active")
                cursor.close()
                return None

            # Use explicit column names to avoid issues with column order after migrations
            # SQLite ALTER TABLE adds columns at the END, not in schema-defined order
            cursor.execute("""
                SELECT channel_id, channel_name, guild_id, purpose, random_reply_chance,
                       immersive_character, allow_technical_language, use_server_info,
                       enable_roleplay_formatting, allow_proactive_engagement,
                       enable_conversation_detection, conversation_detection_threshold,
                       conversation_context_window, formality, formality_locked, activated_at
                FROM channel_settings WHERE channel_id = ?
            """, (channel_id,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            return {
                'channel_id': row[0],
                'channel_name': row[1],
                'guild_id': row[2],
                'purpose': row[3],
                'random_reply_chance': row[4],
                'immersive_character': bool(row[5]),
                'allow_technical_language': bool(row[6]),
                'use_server_info': bool(row[7]),
                'enable_roleplay_formatting': bool(row[8]),
                'allow_proactive_engagement': bool(row[9]),
                'enable_conversation_detection': bool(row[10]) if row[10] is not None else False,
                'conversation_detection_threshold': row[11] if row[11] is not None else 0.7,
                'conversation_context_window': row[12] if row[12] is not None else 10,
                'formality': row[13],
                'formality_locked': bool(row[14]),
                'activated_at': row[15]
            }
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get channel setting for {channel_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_all_channel_settings(self, guild_id=None):
        """
        Retrieves all channel settings, optionally filtered by guild.

        Args:
            guild_id: Optional Discord guild ID to filter by

        Returns:
            Dictionary mapping channel_id to settings dict
        """
        try:
            cursor = self.conn.cursor()

            # First verify the table exists (handles legacy databases)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='channel_settings'")
            if not cursor.fetchone():
                print(f"DATABASE WARNING: channel_settings table does not exist")
                cursor.close()
                return {}

            # Use explicit column names to avoid issues with column order after migrations
            # SQLite ALTER TABLE adds columns at the END, not in schema-defined order
            columns = """channel_id, channel_name, guild_id, purpose, random_reply_chance,
                        immersive_character, allow_technical_language, use_server_info,
                        enable_roleplay_formatting, allow_proactive_engagement,
                        enable_conversation_detection, conversation_detection_threshold,
                        conversation_context_window, formality, formality_locked, activated_at"""

            if guild_id:
                cursor.execute(f"SELECT {columns} FROM channel_settings WHERE guild_id = ?", (guild_id,))
            else:
                cursor.execute(f"SELECT {columns} FROM channel_settings")

            rows = cursor.fetchall()
            cursor.close()

            channels = {}
            for row in rows:
                channels[row[0]] = {
                    'channel_id': row[0],
                    'channel_name': row[1],
                    'guild_id': row[2],
                    'purpose': row[3],
                    'random_reply_chance': row[4],
                    'immersive_character': bool(row[5]),
                    'allow_technical_language': bool(row[6]),
                    'use_server_info': bool(row[7]),
                    'enable_roleplay_formatting': bool(row[8]),
                    'allow_proactive_engagement': bool(row[9]),
                    'enable_conversation_detection': bool(row[10]) if row[10] is not None else False,
                    'conversation_detection_threshold': row[11] if row[11] is not None else 0.7,
                    'conversation_context_window': row[12] if row[12] is not None else 10,
                    'formality': row[13],
                    'formality_locked': bool(row[14]),
                    'activated_at': row[15]
                }

            return channels
        except Exception as e:
            print(f"DATABASE ERROR: Failed to get all channel settings: {e}")
            return {}

    def remove_channel_setting(self, channel_id):
        """
        Removes a channel setting from the database.

        Args:
            channel_id: Discord channel ID (str)

        Returns:
            Boolean indicating success
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM channel_settings WHERE channel_id = ?", (channel_id,))
            deleted = cursor.rowcount > 0
            self.conn.commit()
            cursor.close()

            if deleted:
                print(f"DATABASE: Removed channel settings for {channel_id}")
            return deleted
        except Exception as e:
            print(f"DATABASE ERROR: Failed to remove channel setting for {channel_id}: {e}")
            return False

    def close(self):
        """Closes the database connection."""
        if self.conn:
            try:
                self.conn.close()
                print("Database connection closed.")
            except Exception as e:
                print(f"DATABASE ERROR: Failed to close connection: {e}")




