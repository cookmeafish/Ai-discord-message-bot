#!/usr/bin/env python3
"""
Migration script to convert database from flat structure to folder-based structure.

Old structure: database/{guild_id}_{servername}_data.db
New structure: database/{guild_id}/data.db

Also migrates archive files to per-server folders.
"""

import os
import re
import shutil
import json

def migrate_databases():
    """Migrates existing databases to the new folder-based structure."""
    db_folder = "database"
    archive_folder = os.path.join(db_folder, "archive")

    if not os.path.exists(db_folder):
        print("ERROR: database folder not found!")
        return

    migrated_count = 0
    skipped_count = 0

    print("=" * 60)
    print("DATABASE MIGRATION: Flat to Folder Structure")
    print("=" * 60)
    print()

    # Scan for old-format database files
    for filename in os.listdir(db_folder):
        if not filename.endswith('_data.db') or filename == '_data.db':
            continue

        old_db_path = os.path.join(db_folder, filename)

        # Skip if it's a directory
        if os.path.isdir(old_db_path):
            continue

        # Try to extract guild_id from filename
        # Format: {guild_id}_{servername}_data.db or {servername}_data.db
        match = re.match(r'^(\d+)_(.+)_data\.db$', filename)

        if not match:
            # Very old format without guild_id prefix - skip with warning
            print(f"SKIPPED: {filename} (no guild_id found - please manually migrate)")
            skipped_count += 1
            continue

        guild_id = match.group(1)
        server_name = match.group(2)

        # Create new folder structure
        new_folder = os.path.join(db_folder, guild_id)
        new_db_path = os.path.join(new_folder, "data.db")

        # Check if new structure already exists
        if os.path.exists(new_db_path):
            print(f"SKIPPED: {filename} (target already exists: {new_db_path})")
            skipped_count += 1
            continue

        # Create guild_id folder
        os.makedirs(new_folder, exist_ok=True)

        # Move database file
        print(f"Migrating: {filename}")
        print(f"   -> {new_db_path}")
        shutil.move(old_db_path, new_db_path)

        # Migrate archive files for this guild (if any)
        if os.path.exists(archive_folder):
            new_archive_folder = os.path.join(new_folder, "archive")
            archive_pattern = f"short_term_archive_{guild_id}_"

            for archive_file in os.listdir(archive_folder):
                if archive_file.startswith(archive_pattern):
                    old_archive_path = os.path.join(archive_folder, archive_file)

                    # Create new archive folder if needed
                    os.makedirs(new_archive_folder, exist_ok=True)

                    # New filename without guild_id prefix
                    new_archive_filename = archive_file.replace(f"{guild_id}_", "")
                    new_archive_path = os.path.join(new_archive_folder, new_archive_filename)

                    print(f"   Archive: {archive_file} -> {guild_id}/archive/{new_archive_filename}")
                    shutil.move(old_archive_path, new_archive_path)

        migrated_count += 1
        print()

    print("=" * 60)
    print(f"Migration Complete!")
    print(f"   Migrated: {migrated_count} databases")
    print(f"   Skipped: {skipped_count} databases")
    print("=" * 60)
    print()

    # Clean up empty archive folder if it exists
    if os.path.exists(archive_folder) and not os.listdir(archive_folder):
        print("Removing empty archive folder...")
        os.rmdir(archive_folder)

    if migrated_count > 0:
        print("\nIMPORTANT: Please restart the bot for changes to take effect.")

    if skipped_count > 0:
        print("\nWARNING: Some databases were skipped. Please review the output above.")

if __name__ == "__main__":
    print()
    response = input("This will migrate your database files to a new folder structure.\nContinue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        migrate_databases()
    else:
        print("Migration cancelled.")
