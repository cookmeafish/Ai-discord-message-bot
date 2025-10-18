# modules/status_updater.py

import discord
import openai
import os
import json
from datetime import datetime
from database.multi_db_manager import MultiDBManager
from modules.config_manager import ConfigManager

class StatusUpdater:
    """
    Handles daily AI-generated status updates for the bot.
    Generates funny/quirky status messages based on bot's personality/lore.
    Prevents duplicate statuses by tracking history.
    """

    STATUS_HISTORY_FILE = "status_history.json"
    MAX_HISTORY_SIZE = 100  # Keep last 100 statuses to prevent duplicates

    def __init__(self, bot):
        self.bot = bot
        self.config_manager = ConfigManager()
        self.multi_db_manager = MultiDBManager()

        # Set up OpenAI API key
        openai.api_key = os.getenv('OPENAI_API_KEY')

    def _load_status_history(self):
        """Load the history of previously generated statuses."""
        try:
            if os.path.exists(self.STATUS_HISTORY_FILE):
                with open(self.STATUS_HISTORY_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"Error loading status history: {e}")
            return []

    def _save_status_history(self, history):
        """Save the status history, keeping only the most recent entries."""
        try:
            # Limit history size
            if len(history) > self.MAX_HISTORY_SIZE:
                history = history[-self.MAX_HISTORY_SIZE:]

            with open(self.STATUS_HISTORY_FILE, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving status history: {e}")

    def _is_duplicate_status(self, status, history):
        """Check if a status already exists in history (case-insensitive)."""
        status_lower = status.lower().strip()
        return any(s.lower().strip() == status_lower for s in history)

    async def generate_and_update_status(self):
        """
        Generates a new AI status and updates the bot's Discord status.
        Optionally logs the status to selected servers' short-term memory.
        """
        from modules.logging_manager import get_logger
        logger = get_logger()

        try:
            config = self.config_manager.get_config()
            status_config = config.get('status_updates', {})

            # Check if status updates are enabled
            if not status_config.get('enabled', False):
                logger.warning("Status updates are disabled in config")
                return

            # Get source server for personality data
            source_server_name = status_config.get('source_server_name', 'Most Active Server')
            logger.info(f"Generating status using personality from: {source_server_name}")

            # Get guild_id for the source server
            source_guild_id = await self._get_source_guild_id(source_server_name)

            if not source_guild_id:
                logger.error(f"Could not find source server: {source_server_name}")
                logger.info(f"Available servers: {[guild.name for guild in self.bot.guilds]}")
                return

            # Get server database
            guild = self.bot.get_guild(int(source_guild_id))
            if not guild:
                logger.error(f"Bot is not in guild {source_guild_id}")
                return

            db_manager = self.bot.get_server_db(source_guild_id, guild.name)

            # Get bot's personality/lore for status generation
            personality_traits = db_manager.get_bot_identity('trait')
            lore = db_manager.get_bot_identity('lore')
            facts = db_manager.get_bot_identity('fact')

            logger.info(f"Loaded personality: {len(personality_traits)} traits, {len(lore)} lore, {len(facts)} facts")

            # Combine personality data
            personality_context = f"Personality traits: {', '.join(personality_traits)}\n"
            personality_context += f"Lore/backstory: {', '.join(lore)}\n"
            personality_context += f"Facts/quirks: {', '.join(facts)}"

            # Load status history to prevent duplicates
            status_history = self._load_status_history()
            logger.info(f"Loaded {len(status_history)} previous statuses from history")

            # Generate unique status with retry logic
            max_retries = 5
            new_status = None

            for attempt in range(max_retries):
                candidate_status = await self._generate_status_with_ai(personality_context)

                if not candidate_status:
                    logger.error("Failed to generate status - AI returned None")
                    break

                # Check if this status is a duplicate
                if self._is_duplicate_status(candidate_status, status_history):
                    logger.warning(f"Attempt {attempt + 1}: Generated duplicate status '{candidate_status}', retrying...")
                    continue
                else:
                    # Found a unique status!
                    new_status = candidate_status
                    logger.info(f"Generated unique status on attempt {attempt + 1}: {new_status}")
                    break

            if new_status:
                # Update bot's Discord status
                # CustomActivity doesn't use 'name' parameter, just pass the status directly
                await self.bot.change_presence(activity=discord.CustomActivity(new_status))
                logger.info(f"✅ Updated bot status to: {new_status}")

                # Add to history to prevent future duplicates
                status_history.append(new_status)
                self._save_status_history(status_history)

                # Add to short-term memory for servers that have it enabled
                await self._add_status_to_memory(new_status, source_guild_id)
            else:
                logger.error("Failed to generate unique status after all retries")

        except Exception as e:
            logger.error(f"Error updating status: {e}", exc_info=True)

    async def _get_source_guild_id(self, source_server_name):
        """
        Determines the guild_id to use for status generation.
        Returns guild_id as string.
        """
        if source_server_name == 'Most Active Server':
            # Find the most active server (most messages in short-term memory)
            return await self._find_most_active_server()
        else:
            # Find guild_id by server name (case-insensitive matching)
            for guild in self.bot.guilds:
                if guild.name.lower() == source_server_name.lower():
                    return str(guild.id)
            return None

    async def _find_most_active_server(self):
        """
        Finds the server with the most messages in short-term memory.
        Returns guild_id as string.
        """
        max_messages = 0
        most_active_guild_id = None

        for guild in self.bot.guilds:
            try:
                db_manager = self.bot.get_server_db(str(guild.id), guild.name)
                message_count = db_manager.get_short_term_message_count()

                if message_count > max_messages:
                    max_messages = message_count
                    most_active_guild_id = str(guild.id)
            except Exception as e:
                print(f"Error checking message count for guild {guild.id}: {e}")
                continue

        return most_active_guild_id

    async def _generate_status_with_ai(self, personality_context):
        """
        Uses OpenAI to generate a funny/quirky status based on bot's personality.
        Returns the generated status string (max 50 characters for comfortable viewing).
        """
        try:
            config = self.config_manager.get_config()
            model_config = config.get('ai_models', {}).get('main_response', {})
            model = model_config.get('model', 'gpt-4.1-mini')

            system_prompt = f"""You are generating a Discord bot status message. The status should be:
- A funny, quirky thought or activity the bot is "doing" or "thinking about"
- Based on the bot's personality and lore below
- Natural and in-character
- MAX 50 characters (must be short and punchy!)
- NO emotes, NO emoji, NO custom Discord emotes (like :emotename:)
- No quotes, just the raw status text
- Examples: "Plotting surgery", "Avoiding patients", "Napping in the ER"

{personality_context}

Generate a single SHORT status message (under 50 characters) that reflects something the bot might be doing or thinking based on its personality. Do NOT use any emotes or emoji."""

            response = openai.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}],
                max_tokens=20,  # Reduced for shorter output
                temperature=0.9  # Higher temperature for more creative/varied statuses
            )

            status = response.choices[0].message.content.strip()

            # Remove quotes if AI added them
            status = status.strip('"').strip("'")

            # Strip any emotes that slipped through (format: :emotename:)
            import re
            status = re.sub(r':[a-zA-Z0-9_]+:', '', status).strip()

            # Ensure it fits the 50 character limit
            if len(status) > 50:
                status = status[:47] + "..."

            return status

        except Exception as e:
            print(f"Error generating status with AI: {e}")
            return None

    async def _add_status_to_memory(self, status_text, source_guild_id):
        """
        Adds the generated status to short-term memory for servers that have it enabled.
        """
        try:
            config = self.config_manager.get_config()
            server_status_settings = config.get('server_status_settings', {})

            timestamp = datetime.now().isoformat()

            # Check each server to see if they want status added to memory
            for guild in self.bot.guilds:
                guild_id_str = str(guild.id)

                # Check if this server wants status added to memory (default: True)
                add_to_memory = server_status_settings.get(guild_id_str, {}).get('add_to_memory', True)

                if add_to_memory:
                    try:
                        db_manager = self.bot.get_server_db(guild_id_str, guild.name)

                        # Add as a system message to short-term memory
                        db_manager.log_message(
                            user_id=str(self.bot.user.id),
                            nickname=self.bot.user.display_name,
                            content=f"[BOT STATUS UPDATE] {status_text}",
                            channel_id="status_update",  # Special channel identifier
                            timestamp=timestamp
                        )

                        print(f"  Added status to memory for server: {guild.name}")

                    except Exception as e:
                        print(f"  Error adding status to memory for guild {guild_id_str}: {e}")

        except Exception as e:
            print(f"Error in _add_status_to_memory: {e}")
