#!/usr/bin/env python3
"""
Script to add Dr. Fish's physical appearance to bot_identity in Destiny 2 database.
Dr. Fish is described as a humanoid with a fish head wearing professional medical attire.
"""

import sqlite3

# Database path
DB_PATH = "database/Destiny 2/1427827466432548957_data.db"

# Dr. Fish's appearance facts (for bot_identity table)
DR_FISH_APPEARANCE = [
    "Dr. Fish has the head of a large fish resembling a carp or goldfish.",
    "Dr. Fish's head has a complex color pattern: dark metallic silver-grey on top transitioning to vibrant reddish-orange on the sides, with off-white around the mouth and lower jaw.",
    "Dr. Fish has large round bulging eyes with dark wide pupils and dark iris, giving a very distinct fish-like appearance.",
    "Dr. Fish's mouth is fleshy and downturned, characteristic of carp species.",
    "Dr. Fish's head is covered in visible overlapping scales with a slight sheen.",
    "Dr. Fish has a broad-shouldered, solid, stout humanoid body build.",
    "Dr. Fish wears a crisp white lab coat worn open, revealing a dark garment underneath.",
    "Dr. Fish has a stethoscope draped around the neck and over shoulders, with black tubing and silver-colored metal parts.",
    "Dr. Fish typically stands in a neutral professional stance, facing forward.",
]

def add_drfish_appearance():
    """Add Dr. Fish's appearance facts to bot_identity table."""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check current bot_identity structure
        cursor.execute("PRAGMA table_info(bot_identity);")
        columns = cursor.fetchall()
        print("📋 Bot Identity Table Structure:")
        for col in columns:
            print(f"   {col[1]} ({col[2]})")
        print()

        # Add appearance facts under "appearance" category
        added_count = 0
        for fact in DR_FISH_APPEARANCE:
            # Check if fact already exists
            cursor.execute("""
                SELECT id FROM bot_identity
                WHERE category = 'appearance' AND content = ?
            """, (fact,))

            if cursor.fetchone():
                print(f"⏭️  Fact already exists: {fact[:50]}...")
                continue

            # Add the fact
            cursor.execute("""
                INSERT INTO bot_identity (category, content)
                VALUES ('appearance', ?)
            """, (fact,))

            added_count += 1
            print(f"✅ Added: {fact[:60]}...")

        conn.commit()
        print(f"\n✅ Successfully added {added_count} appearance facts for Dr. Fish")

        # Show all appearance facts
        cursor.execute("""
            SELECT content FROM bot_identity
            WHERE category = 'appearance'
            ORDER BY id
        """)

        print(f"\n📋 All appearance facts for Dr. Fish:")
        for row in cursor.fetchall():
            print(f"   - {row[0]}")

        # Show summary of all bot_identity categories
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM bot_identity
            GROUP BY category
            ORDER BY category
        """)

        print(f"\n📊 Bot Identity Summary:")
        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]} entries")

    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

    return True

if __name__ == "__main__":
    print("=" * 70)
    print("Add Dr. Fish's Physical Appearance to Destiny 2 Bot Identity")
    print("=" * 70)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Category: appearance")
    print(f"Facts to add: {len(DR_FISH_APPEARANCE)}")
    print()

    add_drfish_appearance()
