# emote_orchestrator.py

import discord
import re

class EmoteOrchestrator:
    """
    A class to manage loading and using custom emotes from all servers the bot is in.
    """
    def __init__(self, bot):
        """
        Initializes the orchestrator.
        
        Args:
            bot (commands.Bot): The instance of the discord bot.
        """
        self.bot = bot
        self.emotes = {}

    def load_emotes(self):
        """Scans all guilds and loads all available custom emotes into a dictionary."""
        print("Loading custom emotes from all servers...")
        self.emotes.clear()
        for guild in self.bot.guilds:
            for emote in guild.emojis:
                # Add the emote if its name isn't already in the dictionary
                if emote.name not in self.emotes:
                    self.emotes[emote.name] = emote
        print(f"Successfully loaded {len(self.emotes)} unique custom emotes.")

    def get_emote(self, name):
        """
        Gets an emote object by its name.
        
        Args:
            name (str): The name of the emote to find.
        
        Returns:
            discord.Emoji or None: The emote object if found, otherwise None.
        """
        return self.emotes.get(name)

    def get_available_emote_names(self):
        """
        Returns a comma-separated string of all available emote names.
        This is useful for passing to the AI model.
        
        Returns:
            str: A string of emote names, e.g., "smile, laugh, cry".
        """
        return ", ".join(self.emotes.keys())

    def replace_emote_tags(self, text):
        """
        Finds all occurrences of :emote_name: in a string and replaces them
        with the actual emote string if the emote exists.
        
        Args:
            text (str): The input string from the AI.
        
        Returns:
            str: The processed string with emote tags replaced.
        """
        # This regex finds all words enclosed in colons, e.g., :smile:
        emote_tags = re.findall(r':(\w+):', text)
        for tag in emote_tags:
            emote = self.get_emote(tag)
            if emote:
                # Replace the tag (e.g., :smile:) with the emote's string representation
                text = text.replace(f':{tag}:', str(emote))
        return text