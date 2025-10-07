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
        
        This function correctly replaces only :emote_name: tags (not already-formatted Discord emotes).
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
            # CRITICAL FIX: This regex ONLY matches :word: patterns that are NOT already 
            # part of a Discord emote format <:name:id> or <a:name:id>
            # The negative lookbehind (?<!<) ensures we don't match emotes after '<'
            # The negative lookbehind (?<!<a) ensures we don't match animated emotes after '<a'
            # The negative lookahead (?!>\d+>) ensures we don't match if followed by '>digits>'
            result = re.sub(r'(?<!<)(?<!<a):(\w+):(?!>\d+>)', replace_match, text)
            return result
        except Exception as e:
            print(f"ERROR: Emote replacement failed: {e}")
            return text


