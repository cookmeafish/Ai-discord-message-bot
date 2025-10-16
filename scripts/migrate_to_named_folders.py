#!/usr/bin/env python3
"""
Migration script to convert database folders to include server names.

Old structure: database/{guild_id}/data.db
New structure: database/{guild_id}_{server_name}/data.db

This makes it easier for users to identify which folder belongs to which server.
"""

import os
import re
import shutil
import json

def get_server_name_for_guild(guild_id):
    """
    Tries to get the server name from config.json channel_settings.
    Falls back to "Server" if not found.
    """
    config_path = "config.json"
    if not os.path.exists(config_path):
        return "Server"

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Look for any channel that belongs to this guild
        channel_settings = config.get('channel_settings', {})
        for channel_id, settings in channel_settings.items():
            if settings.get('guild_id') == guild_id:
                # Found a channel for this guild, use the server name if available
                return settings.get('server_name', "Server")

        return "Server"
    except Exception as e:
        print(f"Error reading config: {e}")
        return "Server"

def sanitize_server_name(server_name):
    """Sanitizes server name for folder naming."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', server_name)
    sanitized = sanitized[:50].strip('. ')
    if not sanitized:
        sanitized = "server"
    return sanitized

def migrate_database_folders():
    """Migrates database folders to include server names."""
    db_folder = "database"

    if not os.path.exists(db_folder):
        print("ERROR: database folder not found!")
        return

    migrated_count = 0
    skipped_count = 0

    print("=" * 60)
    print("DATABASE MIGRATION: Adding Server Names to Folders")
    print("=" * 60)
    print()

    # Scan for folders
    for item in os.listdir(db_folder):
        item_path = os.path.join(db_folder, item)

        # Skip non-directories
        if not os.path.isdir(item_path):
            continue

        # Check if folder contains data.db
        data_db_path = os.path.join(item_path, "data.db")
        if not os.path.exists(data_db_path):
            continue

        # Check if already in new format ({guild_id}_{server_name})
        match = re.match(r'^(\d+)_(.+)$', item)
        if match:
            print(f"SKIP: {item} (already in new format)")
            skipped_count += 1
            continue

        # Check if it's in old format ({guild_id} only)
        if item.isdigit():
            guild_id = item
            server_name = get_server_name_for_guild(guild_id)
            sanitized_name = sanitize_server_name(server_name)

            new_folder_name = f"{guild_id}_{sanitized_name}"
            new_folder_path = os.path.join(db_folder, new_folder_name)

            # Check if target already exists
            if os.path.exists(new_folder_path):
                print(f"SKIP: {item} (target {new_folder_name} already exists)")
                skipped_count += 1
                continue

            # Rename folder
            print(f"Migrating: {item} -> {new_folder_name}")
            shutil.move(item_path, new_folder_path)
            migrated_count += 1
            print()

    print("=" * 60)
    print(f"Migration Complete!")
    print(f"   Migrated: {migrated_count} folders")
    print(f"   Skipped: {skipped_count} folders")
    print("=" * 60)
    print()

    if migrated_count > 0:
        print("IMPORTANT: Please restart the bot for changes to take effect.")

if __name__ == "__main__":
    print()
    response = input("This will rename database folders to include server names.\nContinue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        migrate_database_folders()
    else:
        print("Migration cancelled.")
