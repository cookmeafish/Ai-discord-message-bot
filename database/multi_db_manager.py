# database/multi_db_manager.py

import os
import re
from .db_manager import DBManager

class MultiDBManager:
    """
    Manages multiple per-server database instances.
    Each Discord server gets its own isolated database file.
    """

    def __init__(self):
        """Initialize the multi-database manager."""
        self.db_instances = {}  # Maps guild_id -> DBManager instance
        self.db_folder = "database"
        os.makedirs(self.db_folder, exist_ok=True)

        # Load existing server databases
        self._discover_existing_databases()

    def _sanitize_server_name(self, server_name):
        """
        Sanitizes server name to be filesystem-safe.
        Removes/replaces special characters and limits length.
        """
        # Remove or replace invalid filename characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', server_name)
        # Limit length to 50 characters
        sanitized = sanitized[:50]
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip('. ')
        # If empty after sanitization, use a default
        if not sanitized:
            sanitized = "server"
        return sanitized

    def _get_db_filename(self, server_name, guild_id):
        """
        Generates database filename: {guild_id}_{servername}_data.db
        Guild ID ensures uniqueness even if servers share names or get renamed.
        """
        sanitized_name = self._sanitize_server_name(server_name)
        return f"{guild_id}_{sanitized_name}_data.db"

    def _discover_existing_databases(self):
        """
        Scans the database folder for existing *_data.db files
        and loads them into memory.
        """
        if not os.path.exists(self.db_folder):
            return

        for filename in os.listdir(self.db_folder):
            if filename.endswith('_data.db') and filename != '_data.db':
                # Extract guild_id from filename if possible
                # For now, we'll load them on-demand when needed
                pass

    def get_or_create_db(self, guild_id, server_name):
        """
        Gets or creates a database instance for a specific server.

        Args:
            guild_id: Discord guild ID (int or str)
            server_name: Discord server name (str)

        Returns:
            DBManager instance for this server
        """
        guild_id = str(guild_id)

        # Check if already loaded
        if guild_id in self.db_instances:
            return self.db_instances[guild_id]

        # Create new database instance
        db_filename = self._get_db_filename(server_name, guild_id)
        db_path = os.path.join(self.db_folder, db_filename)

        print(f"Creating/loading database for server '{server_name}' (ID: {guild_id})")
        print(f"Database file: {db_path}")

        # Create DBManager with custom path
        db_manager = DBManager(db_path=db_path)
        self.db_instances[guild_id] = db_manager

        return db_manager

    def get_db(self, guild_id):
        """
        Gets an existing database instance for a server.
        Returns None if not found.

        Args:
            guild_id: Discord guild ID

        Returns:
            DBManager instance or None
        """
        return self.db_instances.get(str(guild_id))

    def has_db(self, guild_id):
        """
        Checks if a database exists for a server.

        Args:
            guild_id: Discord guild ID

        Returns:
            Boolean
        """
        return str(guild_id) in self.db_instances

    def close_all(self):
        """Closes all database connections."""
        for guild_id, db_manager in self.db_instances.items():
            try:
                db_manager.close()
                print(f"Closed database for guild {guild_id}")
            except Exception as e:
                print(f"Error closing database for guild {guild_id}: {e}")
        self.db_instances.clear()
