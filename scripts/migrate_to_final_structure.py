#!/usr/bin/env python3
"""
FINAL Migration script to convert to user-friendly structure.

Old structure: database/{guild_id}_{generic_name}/data.db
New structure: database/{server_name}/{guild_id}_data.db

This makes folders human-readable while keeping guild_id in filename for uniqueness.
"""

import os
import re
import shutil
import json

def get_server_name_for_guild(guild_id):
    """
    Tries to get the actual server name from config.json channel_settings.
    Falls back to asking the user if not found.
    """
    config_path = "config.json"
    if not os.path.exists(config_path):
        return None

    try:
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Look for any channel that belongs to this guild
        channel_settings = config.get('channel_settings', {})
        for channel_id, settings in channel_settings.items():
            channel_guild_id = settings.get('guild_id')
            if channel_guild_id and str(channel_guild_id) == str(guild_id):
                # Found a channel for this guild
                # Check if channel has a name stored
                channel_name = settings.get('channel_name', '')
                if channel_name:
                    # Extract potential server name from channel metadata if available
                    pass

        return None  # Will prompt user
    except Exception as e:
        print(f"Error reading config: {e}")
        return None

def sanitize_server_name(server_name):
    """Sanitizes server name for folder naming."""
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', server_name)
    sanitized = sanitized[:50].strip('. ')
    if not sanitized:
        sanitized = "server"
    return sanitized

def migrate_database_structure():
    """Migrates database from intermediate to final structure."""
    db_folder = "database"

    if not os.path.exists(db_folder):
        print("ERROR: database folder not found!")
        return

    migrated_count = 0
    skipped_count = 0

    print("=" * 60)
    print("FINAL DATABASE MIGRATION")
    print("Converting to: database/{server_name}/{guild_id}_data.db")
    print("=" * 60)
    print()

    # Scan for folders that need migration
    for item in os.listdir(db_folder):
        item_path = os.path.join(db_folder, item)

        # Skip non-directories
        if not os.path.isdir(item_path):
            continue

        # Check what's in this folder
        db_file = None
        for filename in os.listdir(item_path):
            if filename.endswith('_data.db') or filename == 'data.db':
                db_file = filename
                break

        if not db_file:
            continue

        # Extract guild_id
        guild_id = None
        current_server_name = item

        # Check current folder naming patterns
        if db_file == "data.db":
            # Old format folder with data.db
            folder_match = re.match(r'^(\d+)_(.+)$', item)
            if folder_match:
                guild_id = folder_match.group(1)
                current_server_name = folder_match.group(2)
            elif item.isdigit():
                guild_id = item
                current_server_name = "Server"
        else:
            # File is {guild_id}_data.db - already new format, check folder
            file_match = re.match(r'^(\d+)_data\.db$', db_file)
            if file_match:
                guild_id = file_match.group(1)
                # Folder is already the server name
                print(f"SKIP: {item} (already in final format)")
                skipped_count += 1
                continue

        if not guild_id:
            print(f"SKIP: {item} (could not determine guild_id)")
            skipped_count += 1
            continue

        # Ask user for the actual server name
        print(f"\nFound: {item}/")
        print(f"  Guild ID: {guild_id}")
        print(f"  Current name: {current_server_name}")
        server_name = input(f"  Enter actual server name (or press Enter to use '{current_server_name}'): ").strip()

        if not server_name:
            server_name = current_server_name

        sanitized_name = sanitize_server_name(server_name)
        new_folder_path = os.path.join(db_folder, sanitized_name)
        new_db_filename = f"{guild_id}_data.db"
        new_db_path = os.path.join(new_folder_path, new_db_filename)

        # Check if target already exists
        if os.path.exists(new_db_path):
            print(f"  SKIP: Target already exists at {new_db_path}")
            skipped_count += 1
            continue

        # Create new folder if needed
        os.makedirs(new_folder_path, exist_ok=True)

        # Move/rename database file
        old_db_path = os.path.join(item_path, db_file)
        print(f"  Moving: {old_db_path}")
        print(f"       -> {new_db_path}")
        shutil.copy2(old_db_path, new_db_path)

        # Move archive folder if it exists
        old_archive = os.path.join(item_path, "archive")
        if os.path.exists(old_archive):
            new_archive = os.path.join(new_folder_path, "archive")
            if not os.path.exists(new_archive):
                print(f"  Moving archive folder...")
                shutil.copytree(old_archive, new_archive)

        # Remove old folder only if migration successful
        if os.path.exists(new_db_path):
            print(f"  Removing old folder: {item_path}")
            shutil.rmtree(item_path)

        migrated_count += 1
        print()

    print("=" * 60)
    print(f"Migration Complete!")
    print(f"   Migrated: {migrated_count} databases")
    print(f"   Skipped: {skipped_count} databases")
    print("=" * 60)
    print()

    if migrated_count > 0:
        print("IMPORTANT: Please restart the bot for changes to take effect.")
        print("\nNew structure:")
        print("  database/")
        print("    Mistel Fiech's Server/")
        print("      1260857723193528360_data.db")
        print("      archive/")
        print("    Destiny 2/")
        print("      1427827466432548957_data.db")
        print("      archive/")

if __name__ == "__main__":
    print()
    print("This will migrate your database to the final user-friendly structure.")
    print("Folder = Server Name (human-readable)")
    print("File = {guild_id}_data.db (ensures uniqueness)")
    print()
    response = input("Continue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        migrate_database_structure()
    else:
        print("Migration cancelled.")
