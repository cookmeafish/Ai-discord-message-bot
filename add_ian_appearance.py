#!/usr/bin/env python3
"""
Script to add Ian's appearance description to Destiny 2 database.
Ian is described as a ferret with specific markings.
"""

import sqlite3
import sys

# Database path
DB_PATH = "database/Destiny 2/1427827466432548957_data.db"

# Ian's appearance facts (ferret description)
IAN_APPEARANCE = [
    "Ian is a ferret with a multi-toned coat.",
    "Ian has predominantly dark brown or black fur on head and body.",
    "Ian has distinct white or cream-colored markings on face, specifically around muzzle and eyebrows, creating a mask-like pattern.",
    "Ian has small front paws covered in dark fur.",
    "Ian has long, light-colored, non-retractable claws that are clearly visible.",
    "Ian's facial features include the characteristic ferret mask pattern with white/cream around the muzzle and eyebrows.",
]

def add_ian_appearance(user_id: str):
    """Add Ian's appearance facts to the database."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if user exists in relationship_metrics
        cursor.execute("SELECT user_id FROM relationship_metrics WHERE user_id = ?", (user_id,))
        if not cursor.fetchone():
            print(f"⚠️  User {user_id} not found in relationship_metrics.")
            print("   Creating relationship metrics entry first...")

            # Create default relationship metrics
            cursor.execute("""
                INSERT INTO relationship_metrics
                (user_id, rapport, anger, trust, formality, fear, respect, affection, familiarity, intimidation)
                VALUES (?, 5, 0, 5, 0, 0, 5, 3, 5, 0)
            """, (user_id,))
            print(f"✅ Created relationship metrics for user {user_id}")

        # Add appearance facts
        added_count = 0
        for fact in IAN_APPEARANCE:
            # Check if fact already exists
            cursor.execute("""
                SELECT id FROM long_term_memory
                WHERE user_id = ? AND fact = ?
            """, (user_id, fact))

            if cursor.fetchone():
                print(f"⏭️  Fact already exists: {fact[:50]}...")
                continue

            # Add the fact
            cursor.execute("""
                INSERT INTO long_term_memory
                (user_id, fact, source_user_id, source_nickname, first_mentioned_timestamp, last_mentioned_timestamp, reference_count)
                VALUES (?, ?, ?, ?, datetime('now'), datetime('now'), 0)
            """, (user_id, fact, user_id, "Ian"))

            added_count += 1
            print(f"✅ Added: {fact[:60]}...")

        conn.commit()
        print(f"\n✅ Successfully added {added_count} appearance facts for Ian (User ID: {user_id})")

        # Show all facts for Ian
        cursor.execute("""
            SELECT fact FROM long_term_memory
            WHERE user_id = ?
            ORDER BY id
        """, (user_id,))

        print(f"\n📋 All facts for Ian:")
        for row in cursor.fetchall():
            print(f"   - {row[0]}")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

    return True

if __name__ == "__main__":
    print("=" * 70)
    print("Add Ian's Appearance (Ferret) to Destiny 2 Database")
    print("=" * 70)

    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        print("\nPlease provide Ian's Discord user ID:")
        print("Usage: python3 add_ian_appearance.py <user_id>")
        print("\nExample: python3 add_ian_appearance.py 123456789012345678")
        sys.exit(1)

    print(f"\nTarget User ID: {user_id}")
    print(f"Database: {DB_PATH}")
    print(f"Facts to add: {len(IAN_APPEARANCE)}")
    print()

    add_ian_appearance(user_id)
