#!/usr/bin/env python3
"""
Migration script to move channel settings from config.json to per-server databases.
Safe to run multiple times - skips channels that already exist in database.
"""

import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.db_manager import DBManager

def migrate_channel_settings():
    """
    Migrates channel settings from config.json to per-server databases.
    """
    print("=" * 60)
    print("Migrating Channel Settings from config.json to Databases")
    print("=" * 60)
    print()

    # Load config.json
    config_path = "config.json"
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found")
        sys.exit(1)

    with open(config_path, 'r') as f:
        config = json.load(f)

    channel_settings = config.get('channel_settings', {})

    if not channel_settings:
        print("No channel settings found in config.json")
        return

    print(f"Found {len(channel_settings)} channels in config.json")
    print()

    # Group channels by guild_id
    channels_by_guild = {}
    channels_no_guild = []

    for channel_id, settings in channel_settings.items():
        guild_id = settings.get('guild_id')
        if guild_id:
            if guild_id not in channels_by_guild:
                channels_by_guild[guild_id] = []
            channels_by_guild[guild_id].append((channel_id, settings))
        else:
            channels_no_guild.append((channel_id, settings))

    print(f"Channels grouped by server:")
    print(f"  - {len(channels_by_guild)} servers with guild_id")
    print(f"  - {len(channels_no_guild)} channels without guild_id (will be skipped)")
    print()

    # Find all server database files
    database_dir = "database"
    migrated_count = 0
    skipped_count = 0
    error_count = 0

    for guild_id, channels in channels_by_guild.items():
        print(f"Processing server {guild_id}...")

        # Find the database file for this guild
        db_path = None
        for server_folder in os.listdir(database_dir):
            server_path = os.path.join(database_dir, server_folder)
            if not os.path.isdir(server_path):
                continue

            # Look for database file matching guild_id
            for file in os.listdir(server_path):
                if file == f"{guild_id}_data.db":
                    db_path = os.path.join(server_path, file)
                    break
            if db_path:
                break

        if not db_path:
            print(f"  [WARNING] No database found for guild {guild_id}, skipping")
            skipped_count += len(channels)
            continue

        print(f"  Found database: {db_path}")

        # Open database and migrate channels
        try:
            db_manager = DBManager(db_path=db_path)

            for channel_id, settings in channels:
                # Check if channel already exists in database
                existing = db_manager.get_channel_setting(channel_id)
                if existing:
                    print(f"    [SKIP] Channel {channel_id} already in database")
                    skipped_count += 1
                    continue

                # Migrate channel settings
                result = db_manager.add_channel_setting(
                    channel_id=channel_id,
                    guild_id=guild_id,
                    channel_name=settings.get('channel_name'),
                    purpose=settings.get('purpose'),
                    random_reply_chance=settings.get('random_reply_chance'),
                    immersive_character=settings.get('immersive_character'),
                    allow_technical_language=settings.get('allow_technical_language'),
                    use_server_info=settings.get('use_server_info'),
                    enable_roleplay_formatting=settings.get('enable_roleplay_formatting'),
                    allow_proactive_engagement=settings.get('allow_proactive_engagement'),
                    formality=settings.get('formality'),
                    formality_locked=settings.get('formality_locked')
                )

                if result:
                    print(f"    [OK] Migrated channel {channel_id} ({settings.get('channel_name', 'unknown')})")
                    migrated_count += 1
                else:
                    print(f"    [ERROR] Failed to migrate channel {channel_id}")
                    error_count += 1

            db_manager.close()

        except Exception as e:
            print(f"  [ERROR] Error processing database {db_path}: {e}")
            error_count += len(channels)

        print()

    # Summary
    print("=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"  Migrated: {migrated_count} channels")
    print(f"  Skipped (already in DB): {skipped_count} channels")
    print(f"  Skipped (no guild_id): {len(channels_no_guild)} channels")
    if error_count > 0:
        print(f"  Errors: {error_count} channels")
    print()
    print("Migration complete!")
    print()
    print("IMPORTANT: Channel settings are now per-server in databases.")
    print("You can safely remove 'channel_settings' from config.json after verifying.")

if __name__ == "__main__":
    migrate_channel_settings()
