#!/usr/bin/env python3
"""
Assigns lore-based relationship metric values to users in the Mistel Fiech server database.
Based on bot's lore and existing user relationships.
"""

import sqlite3
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mistel Fiech server database path
DB_PATH = "database/Mistel Fiech's Server/1260857723193528360_data.db"

def get_bot_lore(conn):
    """Get all bot lore entries."""
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM bot_identity WHERE category = 'lore'")
    lore_entries = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return lore_entries

def get_all_users(conn):
    """Get all users with relationship metrics."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, anger, rapport, trust, formality,
               fear, respect, affection, familiarity, intimidation
        FROM relationship_metrics
    """)
    users = cursor.fetchall()
    cursor.close()
    return users

def update_user_metrics(conn, user_id, **metrics):
    """Update user metrics."""
    cursor = conn.cursor()

    # Build update query
    updates = []
    params = []
    for key, value in metrics.items():
        updates.append(f"{key} = ?")
        params.append(value)

    query = f"UPDATE relationship_metrics SET {', '.join(updates)} WHERE user_id = ?"
    params.append(user_id)

    cursor.execute(query, params)
    conn.commit()
    cursor.close()
    print(f"  [UPDATE] User {user_id}: {metrics}")

def assign_metrics_based_on_lore():
    """
    Assigns relationship metrics based on bot's lore and existing relationships.

    Lore context from PLANNED_FEATURES.md:
    - Fear metric is for power dynamics (e.g., User A - authority figure)
    - Respect is professional/personal admiration
    - Affection is emotional warmth (familial/romantic attachment)
    - Familiarity is how well bot knows the user
    - Intimidation is passive fear from user's reputation/status
    """

    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found: {DB_PATH}")
        return False

    print(f"[INFO] Connecting to: {DB_PATH}\n")

    conn = sqlite3.connect(DB_PATH)

    # Get bot lore
    lore = get_bot_lore(conn)
    print("[INFO] Bot Lore:")
    for entry in lore:
        print(f"  - {entry}")
    print()

    # Get all users
    users = get_all_users(conn)

    if not users:
        print("[WARNING] No users found with relationship metrics")
        conn.close()
        return True

    print(f"[INFO] Found {len(users)} user(s) with metrics\n")
    print("=" * 60)

    # User ID mapping (you'll need to provide the actual user IDs)
    # Based on bot lore, we know:
    # - User A is a feared authority figure
    # - The bot has various emotional connections

    # IMPORTANT: Replace these with actual Discord user IDs
    USER_MAPPINGS = {
        # Example format:
        # "UserA": 123456789012345678,  # Replace with actual ID
        # "UserB": 987654321098765432,  # Replace with actual ID
    }

    print("\n[INFO] Current users in database:")
    for user in users:
        user_id, anger, rapport, trust, formality, fear, respect, affection, familiarity, intimidation = user
        print(f"\n  User ID: {user_id}")
        print(f"    Anger: {anger}, Rapport: {rapport}, Trust: {trust}, Formality: {formality}")
        print(f"    Fear: {fear}, Respect: {respect}, Affection: {affection}, Familiarity: {familiarity}, Intimidation: {intimidation}")

    print("\n" + "=" * 60)
    print("\n[INFO] Assigning lore-based metrics based on current relationships and bot lore...")
    print()

    # Assign metrics based on existing relationship patterns and bot lore
    # Using rapport, trust, anger as indicators of relationship type

    for user in users:
        user_id, anger, rapport, trust, formality, fear, respect, affection, familiarity, intimidation = user

        # Calculate new metrics based on existing ones
        # Familiarity based on rapport and trust (how well bot knows them)
        new_familiarity = min(10, (rapport + trust) // 2)

        # Affection based on high rapport and low anger
        if rapport >= 8 and anger <= 2:
            new_affection = min(10, rapport - 1)  # Very close friend
        elif rapport >= 5 and anger <= 4:
            new_affection = min(10, rapport // 2)  # Friendly
        else:
            new_affection = max(0, rapport - 3)  # Low affection for hostile relationships

        # Respect based on rapport and trust
        if trust >= 7:
            new_respect = min(10, (trust + rapport) // 2)
        else:
            new_respect = max(0, min(10, rapport // 2))

        # Fear - default low, but check for specific patterns
        # High anger + low rapport might indicate fear-inducing authority
        if anger >= 8 and rapport <= 4:
            new_fear = min(10, anger - 3)  # Hostile authority
        else:
            new_fear = 0  # No fear for friendly relationships

        # Intimidation - based on formality and existing metrics
        # High trust but low rapport might indicate intimidating professional respect
        if trust >= 7 and rapport <= 5 and formality >= 2:
            new_intimidation = min(10, trust - 2)
        else:
            new_intimidation = 0

        update_user_metrics(conn, user_id,
            fear=new_fear,
            respect=new_respect,
            affection=new_affection,
            familiarity=new_familiarity,
            intimidation=new_intimidation
        )

    # Special case: Check if authority figure is in the database based on lore
    # Based on the lore: "Authority figure pulled bot from eternal slumber" and "supreme ruler with absolute power"
    # We should look for the user with the most balanced/unique metrics

    # Look for a user that might be authority figure (owner/admin with special status)
    # User 968980122440970252 has anger=10, rapport=1, trust=10 - unusual high trust with high anger
    # This pattern fits: feared authority but trusted (authority figure saved bot's life)

    potential_authority_id = 968980122440970252  # High anger + high trust pattern

    print("\n[SPECIAL] Applying authority figure-specific metrics to user 968980122440970252")
    print("  (Based on lore: Authority figure pulled bot from eternal slumber, supreme ruler)")

    update_user_metrics(conn, potential_authority_id,
        fear=9,           # VERY high fear - "supreme ruler" who controls bot's fate
        respect=10,       # Maximum respect - saved bot's life, absolute authority
        affection=4,      # Moderate affection - grateful for resurrection but intimidated
        familiarity=8,    # High familiarity - knows authority figure well (resurrected bot)
        intimidation=10   # Maximum intimidation - "absolute power over everyone"
    )

    conn.close()
    print("\n[INFO] All lore-based metrics assigned successfully.")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("LORE-BASED RELATIONSHIP METRICS ASSIGNMENT")
    print("=" * 60)
    print()

    success = assign_metrics_based_on_lore()

    if success:
        print("\n[SUCCESS] Script completed successfully")
        sys.exit(0)
    else:
        print("\n[FAILED] Script failed")
        sys.exit(1)
