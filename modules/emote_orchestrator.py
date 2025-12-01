# modules/emote_orchestrator.py

import discord
import re
import random

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
                print(f"  Scanning guild: {guild.name} (ID: {guild.id})")
                guild_emote_count = 0
                for emote in guild.emojis:
                    # Only load emotes that are available (not boost-locked)
                    if emote.available and emote.name not in self.emotes:
                        self.emotes[emote.name] = emote
                        guild_emote_count += 1
                        print(f"    Loaded emote: :{emote.name}: (ID: {emote.id})")
                    elif not emote.available:
                        print(f"    Skipped boost-locked emote: :{emote.name}:")
                print(f"  Found {guild_emote_count} unique available emotes in {guild.name}")
            print(f"Successfully loaded {len(self.emotes)} total unique custom emotes.")
            print(f"Available emote names: {', '.join(sorted(self.emotes.keys()))}")
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
        Returns a comma-separated string of all available emote names with colons.
        This format matches the expected syntax for using emotes in bot responses.
        """
        return ", ".join(f":{name}:" for name in self.emotes.keys()) if self.emotes else "No emotes loaded"

    def get_emote_count(self, guild_id=None):
        """Returns the number of emotes available for a guild."""
        emotes_to_use = self.get_emotes_for_guild(guild_id) if guild_id else self.emotes
        return len(emotes_to_use)

    def get_random_emote_sample(self, guild_id=None, sample_size=50):
        """
        Returns a randomized sample of emotes for better variety in AI responses.

        Args:
            guild_id: Optional guild ID to filter emotes (uses server_emote_sources config)
            sample_size: Number of emotes to include in the sample (default: 50)

        Returns:
            str: Comma-separated string of random emote names with colons
        """
        # Get appropriate emote set (filtered or all)
        emotes_to_use = self.get_emotes_for_guild(guild_id) if guild_id else self.emotes

        if not emotes_to_use:
            return "No emotes loaded"

        # Get list of emote names
        emote_names = list(emotes_to_use.keys())

        # Sample randomly (or use all if fewer than sample_size)
        if len(emote_names) <= sample_size:
            sampled_names = emote_names
        else:
            sampled_names = random.sample(emote_names, sample_size)

        # Shuffle the sample for additional randomness
        random.shuffle(sampled_names)

        # Return as comma-separated string with colons
        return ", ".join(f":{name}:" for name in sampled_names)

    def get_emotes_with_context(self, guild_id=None):
        """
        Returns emotes with contextual hints about when to use them based on their names.
        This helps the AI choose appropriate emotes for different situations.

        Returns:
            str: Formatted string with emotes and usage hints
        """
        emotes_to_use = self.get_emotes_for_guild(guild_id) if guild_id else self.emotes

        if not emotes_to_use:
            return "No emotes loaded"

        # Keywords that suggest emotional context
        emotion_keywords = {
            # Positive emotions
            'happy': 'happy/cheerful moments',
            'smile': 'friendly/pleasant reactions',
            'laugh': 'funny moments, jokes',
            'lol': 'funny moments, jokes',
            'lmao': 'very funny moments',
            'love': 'affection, appreciation',
            'heart': 'affection, love, appreciation',
            'hug': 'comfort, affection',
            'yay': 'excitement, celebration',
            'excited': 'excitement, anticipation',
            'party': 'celebration, excitement',
            'cool': 'approval, impressed',
            'nice': 'approval, agreement',
            'strong': 'confidence, power, determination',
            'flex': 'confidence, showing off',
            'proud': 'pride, accomplishment',
            'blush': 'embarrassment, flattery, shy',
            'shy': 'embarrassment, bashful',
            'cute': 'endearing moments',

            # Neutral/reactions
            'think': 'pondering, considering',
            'hmm': 'thinking, skeptical',
            'read': 'focused, studying, paying attention',
            'wait': 'patience, anticipation',
            'shrug': 'uncertainty, indifference',
            'meh': 'indifference, unimpressed',
            'what': 'confusion, surprise, disbelief',
            'huh': 'confusion, curiosity',
            'sus': 'suspicion, doubt',
            'eye': 'watching, skeptical, side-eye',
            'stare': 'intense focus, disbelief',
            'look': 'attention, interest',

            # Negative emotions
            'sad': 'sadness, disappointment',
            'cry': 'sadness, overwhelming emotion',
            'angry': 'anger, frustration',
            'mad': 'anger, frustration',
            'rage': 'intense anger',
            'annoyed': 'mild frustration',
            'tired': 'exhaustion, boredom',
            'sleep': 'tiredness, bored',
            'dead': 'exhaustion, giving up',
            'rip': 'sympathy, failure',
            'pain': 'suffering, cringe',
            'cringe': 'secondhand embarrassment',
            'scared': 'fear, anxiety',
            'fear': 'fear, worry',
            'nervous': 'anxiety, worry',
            'sweat': 'nervous, anxious',
            'worry': 'concern, anxiety',

            # Actions/misc
            'wave': 'greeting, goodbye',
            'hi': 'greeting',
            'bye': 'farewell',
            'nod': 'agreement, acknowledgment',
            'no': 'disagreement, refusal',
            'yes': 'agreement, approval',
            'thumbs': 'approval or disapproval',
            'clap': 'applause, appreciation',
            'pat': 'comfort, reassurance',
            'poke': 'playful, attention-getting',
            'bonk': 'playful punishment',
            'eat': 'hungry, enjoying',
            'drink': 'thirsty, cheers',
            'coffee': 'tired, need energy',
            'sip': 'watching drama, judging',
        }

        emote_hints = []
        for name in emotes_to_use.keys():
            name_lower = name.lower()
            hints = []

            # Check for keyword matches in the emote name
            for keyword, context in emotion_keywords.items():
                if keyword in name_lower:
                    hints.append(context)

            if hints:
                # Deduplicate hints
                unique_hints = list(dict.fromkeys(hints))
                emote_hints.append(f":{name}: → {', '.join(unique_hints[:2])}")  # Max 2 hints per emote
            else:
                # No keyword match - just list the emote
                emote_hints.append(f":{name}: → general use")

        return "\n".join(emote_hints)

    def get_emotes_for_guild(self, guild_id):
        """
        Gets emotes available for a specific guild based on server_emote_sources config.

        Args:
            guild_id: Discord guild ID (int or str)

        Returns:
            dict: Filtered emotes dict {name: emote_object}
        """
        guild_id = str(guild_id)

        # Get config to check emote sources
        config = self.bot.config_manager.get_config()
        server_emote_sources = config.get('server_emote_sources', {})

        # If guild not configured, return all emotes (backward compatible)
        if guild_id not in server_emote_sources:
            return self.emotes

        # Get list of allowed guild IDs for this server
        allowed_guild_ids = server_emote_sources[guild_id]
        if not allowed_guild_ids:
            return self.emotes  # Empty list = all emotes

        # Filter emotes to only those from allowed guilds (and only available ones)
        filtered_emotes = {}
        for guild in self.bot.guilds:
            if str(guild.id) in [str(gid) for gid in allowed_guild_ids]:
                for emote in guild.emojis:
                    # Only include emotes that are available (not boost-locked)
                    if emote.available and emote.name not in filtered_emotes:
                        filtered_emotes[emote.name] = emote

        return filtered_emotes

    def replace_emote_tags(self, text, guild_id=None):
        """
        Finds all occurrences of :emote_name: in a string and replaces them
        with the actual Discord emote string if the emote exists.

        Optionally filters emotes based on guild_id if provided.

        Args:
            text: The text to process
            guild_id: Optional guild ID to filter emotes (uses server_emote_sources config)
        """
        if not text:
            return text

        # Get appropriate emote set (filtered or all)
        emotes_to_use = self.get_emotes_for_guild(guild_id) if guild_id else self.emotes

        def replace_match(match):
            tag_name = match.group(1)
            emote = emotes_to_use.get(tag_name)
            if emote:
                # Build the proper Discord emote format
                if emote.animated:
                    return f'<a:{emote.name}:{emote.id}>'
                else:
                    return f'<:{emote.name}:{emote.id}>'
            else:
                # If emote is not found, leave the original tag unchanged and log warning
                print(f"WARNING: Emote ':{tag_name}:' not found. Available emotes: {', '.join(emotes_to_use.keys())}")
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


