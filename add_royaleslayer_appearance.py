#!/usr/bin/env python3
"""
Script to add Royale Slayer's appearance description to Destiny 2 database.
Royale Slayer is described as a figure wearing a Guy Fawkes mask.
"""

import sqlite3
import sys

# Database path
DB_PATH = "database/Destiny 2/1427827466432548957_data.db"

# Royale Slayer's appearance facts
ROYALE_SLAYER_APPEARANCE = [
    "Royale Slayer wears a stylized Guy Fawkes mask that completely obscures their face.",
    "Royale Slayer's mask is pale off-white with highly defined painted features: thin black sharply arched eyebrows, thin black upturned mustache, and small pointed black goatee on chin.",
    "Royale Slayer's mask has subtle pinkish circles on the cheeks and a slight enigmatic smile. The eye openings are dark empty voids.",
    "Royale Slayer wears a black hooded garment with the hood pulled up and forward, shrouding the head and casting the upper portion of the mask in shadow.",
    "Royale Slayer has an intense and focused appearance, often leaning forward with dramatic lighting.",
    "Royale Slayer uses a laptop with a distinctive emblem: a silhouette of a person in business suit with head replaced by large question mark, wireframe globe background, flanked by olive branches creating circular crest.",
]

def add_royale_slayer_appearance(user_id: str):
    """Add Royale Slayer's appearance facts to the database."""

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
        for fact in ROYALE_SLAYER_APPEARANCE:
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
            """, (user_id, fact, user_id, "Royale Slayer"))

            added_count += 1
            print(f"✅ Added: {fact[:60]}...")

        conn.commit()
        print(f"\n✅ Successfully added {added_count} appearance facts for Royale Slayer (User ID: {user_id})")

        # Show all facts for Royale Slayer
        cursor.execute("""
            SELECT fact FROM long_term_memory
            WHERE user_id = ?
            ORDER BY id
        """, (user_id,))

        print(f"\n📋 All facts for Royale Slayer:")
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
    print("Add Royale Slayer's Appearance (Guy Fawkes Mask) to Destiny 2 Database")
    print("=" * 70)

    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        # Default to the user ID with high intimidation/respect metrics
        user_id = "541114289176444940"
        print(f"\nNo user ID provided. Using default: {user_id}")
        print("(This user has high intimidation/respect metrics in the database)")

    print(f"\nTarget User ID: {user_id}")
    print(f"Database: {DB_PATH}")
    print(f"Facts to add: {len(ROYALE_SLAYER_APPEARANCE)}")
    print()

    add_royale_slayer_appearance(user_id)
