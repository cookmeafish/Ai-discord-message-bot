# modules/emote_orchestrator.py

import discord
import re

class EmoteOrchestrator:
    """
    A class to manage loading and using custom emotes from all servers the bot is in.
    """
    def __init__(self, bot):
        self.bot = bot
        self.emotes = {}

    def load_emotes(self):
        """Scans all guilds and loads all available custom emotes into a dictionary."""
        print("Loading custom emotes from all servers...")
        self.emotes.clear()
        
        try:
            for guild in self.bot.guilds:
                for emote in guild.emojis:
                    if emote.name not in self.emotes:
                        self.emotes[emote.name] = emote
            print(f"Successfully loaded {len(self.emotes)} unique custom emotes.")
        except Exception as e:
            print(f"ERROR: Failed to load emotes: {e}")
            self.emotes = {}

    def get_emote(self, name):
        """
        Gets an emote object by its name.
        Returns None if the emote doesn't exist.
        """
        return self.emotes.get(name)

    def get_available_emote_names(self):
        """
        Returns a comma-separated string of all available emote names.
        """
        return ", ".join(self.emotes.keys()) if self.emotes else "No emotes loaded"

    def replace_emote_tags(self, text):
        """
        Finds all occurrences of :emote_name: in a string and replaces them
        with the actual Discord emote string if the emote exists.
        
        CRITICAL FIX: This function now correctly replaces only the :emote_name: tag
        and does not create malformed emote strings.
        """
        if not text:
            return text
            
        def replace_match(match):
            tag_name = match.group(1)
            emote = self.get_emote(tag_name)
            if emote:
                # Build the proper Discord emote format
                if emote.animated:
                    return f'<a:{emote.name}:{emote.id}>'
                else:
                    return f'<:{emote.name}:{emote.id}>'
            else:
                # If emote is not found, leave the original tag unchanged
                return match.group(0)

        try:
            # This regex finds all words enclosed in colons, e.g., :smile:
            # It will NOT match emotes that are already in Discord format <:name:id>
            result = re.sub(r'(?<!<):(\w+):(?!>)', replace_match, text)
            return result
        except Exception as e:
            print(f"ERROR: Emote replacement failed: {e}")
            return text




