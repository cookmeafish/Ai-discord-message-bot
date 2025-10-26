#!/usr/bin/env python3
"""Script to add Mistel Fiech's appearance description to Destiny 2 database."""

import sys
sys.path.insert(0, '/root/Ai-discord-message-bot')

from database.db_manager import DBManager

# Mistel Fiech's User ID
mistel_user_id = 968980122440970252

# Mistel Fiech's appearance descriptions (split into multiple facts under 500 chars each)
appearance_facts = [
    "Has a hybrid creature appearance combining distinct features of a fish head with powerful, muscular humanoid physique. Stands in commanding pose with body angled, head turned to look over right shoulder.",
    "Fish head has sleek, elongated shape tapering to pointed mouth. Single large round eye, light in coloration with dark central pupil, conveying vacant or unblinking gaze characteristic of fish. Smooth skin lacking visible scales or gill structures.",
    "Body features exceptionally muscular, robust humanoid torso. Profoundly defined musculature with prominently developed pectoral muscles, distinct six-pack abs, substantial broad shoulders. Thick muscular neck connects fish head to powerful torso.",
    "Body postured to emphasize impressive musculature, creating imposing and dynamic stance. Strong light/shadow contrasts highlight muscles, with bright areas on head top, right shoulder, upper chest. Deep shadows define muscle contours for dramatic 3D effect.",
    "Overall impression: bizarre, powerful, somewhat solemn being. Unique fusion creates surreal and striking visual of fish-human hybrid."
]

# Database path
db_path = "database/Destiny 2/1427827466432548957_data.db"

print("Adding Mistel Fiech's appearance to Destiny 2 database...")
print(f"User ID: {mistel_user_id}\n")

db = DBManager(db_path)

# Check if appearance facts already exist
cursor = db.conn.cursor()
cursor.execute("""
    SELECT fact FROM long_term_memory
    WHERE user_id = ? AND (LOWER(fact) LIKE '%fish head%' OR LOWER(fact) LIKE '%muscular%' OR LOWER(fact) LIKE '%hybrid%')
""", (mistel_user_id,))

existing = cursor.fetchall()

if existing:
    print(f"⚠️  Found {len(existing)} existing appearance-related fact(s):")
    for fact in existing:
        print(f"    - {fact[0][:80]}...")
    print("\nAdding new facts anyway...\n")

# Add the appearance facts
added = 0
for fact in appearance_facts:
    try:
        db.add_long_term_memory(
            user_id=mistel_user_id,
            fact=fact,
            source_user_id=None,
            source_nickname="System"
        )
        added += 1
        print(f"✓ Added fact {added}/{len(appearance_facts)}: {fact[:60]}...")
    except Exception as e:
        print(f"✗ Failed to add fact: {e}")

print(f"\n✓ Successfully added {added}/{len(appearance_facts)} appearance facts")

db.close()

print("\n✓ Done!")
