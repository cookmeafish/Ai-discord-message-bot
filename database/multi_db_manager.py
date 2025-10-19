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

    def _get_server_folder(self, guild_id, server_name):
        """
        Returns the folder path for a specific server.
        Structure: database/{server_name}/
        Folder uses human-readable server name for easy identification.

        Case-insensitive matching: If folder exists with different case,
        returns existing folder path instead of creating new one.
        """
        sanitized_name = self._sanitize_server_name(server_name)
        target_path = os.path.join(self.db_folder, sanitized_name)

        # Check if folder already exists (case-insensitive on Linux/Mac)
        if os.path.exists(self.db_folder):
            for existing_folder in os.listdir(self.db_folder):
                existing_path = os.path.join(self.db_folder, existing_folder)
                # Only check directories
                if os.path.isdir(existing_path):
                    # Case-insensitive comparison
                    if existing_folder.lower() == sanitized_name.lower():
                        # Found existing folder with different case
                        if existing_folder != sanitized_name:
                            print(f"DATABASE: Found existing folder '{existing_folder}' (case-insensitive match for '{sanitized_name}')")
                        return existing_path

        return target_path

    def _get_db_path(self, guild_id, server_name):
        """
        Returns the database file path for a specific server.
        Structure: database/{server_name}/{guild_id}_data.db
        Folder: Human-readable server name
        File: Guild ID ensures uniqueness (handles server renames)
        """
        server_folder = self._get_server_folder(guild_id, server_name)
        db_filename = f"{guild_id}_data.db"
        return os.path.join(server_folder, db_filename)

    def _discover_existing_databases(self):
        """
        Scans the database folder for existing server subdirectories.
        Supports:
        - New format: {server_name}/{guild_id}_data.db
        - Legacy formats for backward compatibility
        """
        if not os.path.exists(self.db_folder):
            return

        for item in os.listdir(self.db_folder):
            item_path = os.path.join(self.db_folder, item)
            # Check if it's a directory
            if os.path.isdir(item_path):
                # Look for database files in this folder
                for filename in os.listdir(item_path):
                    # New format: {guild_id}_data.db
                    match = re.match(r'^(\d+)_data\.db$', filename)
                    if match:
                        guild_id = match.group(1)
                        print(f"Discovered existing database for guild {guild_id} in folder '{item}'")
                        break
                    # Legacy format: data.db
                    elif filename == "data.db":
                        print(f"Discovered legacy database in folder '{item}'")
                        break
                # Databases will be loaded on-demand when accessed

    def get_or_create_db(self, guild_id, server_name):
        """
        Gets or creates a database instance for a specific server.

        Args:
            guild_id: Discord guild ID (int or str)
            server_name: Discord server name (str, used for folder naming and logging)

        Returns:
            DBManager instance for this server
        """
        guild_id = str(guild_id)

        # Check if already loaded
        if guild_id in self.db_instances:
            return self.db_instances[guild_id]

        # Create server folder if it doesn't exist
        server_folder = self._get_server_folder(guild_id, server_name)
        os.makedirs(server_folder, exist_ok=True)

        # Get database path
        db_path = self._get_db_path(guild_id, server_name)

        print(f"Creating/loading database for server '{server_name}' (ID: {guild_id})")
        print(f"Database path: {db_path}")

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
