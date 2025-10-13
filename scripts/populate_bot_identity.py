# scripts/populate_bot_identity.py
"""
Script to populate a basic default bot personality into the database.
Run this to set up the bot's initial identity, which can then be customized
using /bot_add_trait, /bot_add_lore, and /bot_add_fact commands.
"""

import sys
import os

# Add parent directory to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_manager import DBManager

def populate_default_identity():
    """Populates the bot_identity table with a basic default personality."""

    db = DBManager()

    print("Populating default bot identity...")

    # Core Traits - Generic friendly bot
    traits = [
        "Helpful and friendly",
        "Conversational and engaging",
        "Enjoys chatting with users",
        "Has a good sense of humor",
        "Curious about the world"
    ]

    for trait in traits:
        db.add_bot_identity("trait", trait)
        print(f"  Added trait: {trait}")

    # Lore - Simple background
    lore_entries = [
        "I'm an AI assistant living in this Discord server",
        "I learn about users over time through our conversations",
        "I adapt my personality based on my relationship with each user",
        "I'm here to chat and help out when needed"
    ]

    for lore in lore_entries:
        db.add_bot_identity("lore", lore)
        print(f"  Added lore: {lore}")

    # Facts & Quirks - Basic behaviors
    facts = [
        "I use emotes to express myself",
        "I remember facts about users for personalized conversations",
        "I enjoy both serious and lighthearted discussions",
        "I can adapt my formality level based on the situation"
    ]

    for fact in facts:
        db.add_bot_identity("fact", fact)
        print(f"  Added fact: {fact}")

    print("\n✅ Bot's default identity has been populated!")
    print("The bot will now use this personality from the database.")
    print("Customize it using: /bot_add_trait, /bot_add_lore, /bot_add_fact")

    db.close()

if __name__ == "__main__":
    populate_default_identity()
