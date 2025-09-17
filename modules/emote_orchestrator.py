# emote_orchestrator.py

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
        for guild in self.bot.guilds:
            for emote in guild.emojis:
                if emote.name not in self.emotes:
                    self.emotes[emote.name] = emote
        print(f"Successfully loaded {len(self.emotes)} unique custom emotes.")

    def get_emote(self, name):
        """
        Gets an emote object by its name.
        """
        return self.emotes.get(name)

    def get_available_emote_names(self):
        """
        Returns a comma-separated string of all available emote names.
        """
        return ", ".join(self.emotes.keys())

    def replace_emote_tags(self, text):
        """
        Finds all occurrences of :emote_name: in a string and replaces them
        with the actual emote string if the emote exists.
        """
        def replace_match(match):
            tag_name = match.group(1)
            emote = self.get_emote(tag_name)
            if emote:
                # Manually build the emote string for maximum reliability
                if emote.animated:
                    return f'<a:{emote.name}:{emote.id}>'
                else:
                    return f'<:{emote.name}:{emote.id}>'
            else:
                # If emote is not found, return the original tag e.g. :smile:
                return match.group(0)

        # This regex finds all words enclosed in colons, e.g., :smile:
        return re.sub(r':(\w+):', replace_match, text)