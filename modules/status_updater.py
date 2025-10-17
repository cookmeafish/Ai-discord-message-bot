# modules/status_updater.py

import discord
import openai
import os
from datetime import datetime
from database.multi_db_manager import MultiDBManager
from modules.config_manager import ConfigManager

class StatusUpdater:
    """
    Handles daily AI-generated status updates for the bot.
    Generates funny/quirky status messages based on bot's personality/lore.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config_manager = ConfigManager()
        self.multi_db_manager = MultiDBManager()

        # Set up OpenAI API key
        openai.api_key = os.getenv('OPENAI_API_KEY')

    async def generate_and_update_status(self):
        """
        Generates a new AI status and updates the bot's Discord status.
        Optionally logs the status to selected servers' short-term memory.
        """
        try:
            config = self.config_manager.get_config()
            status_config = config.get('status_updates', {})

            # Check if status updates are enabled
            if not status_config.get('enabled', False):
                print("Status updates are disabled in config")
                return

            # Get source server for personality data
            source_server_name = status_config.get('source_server_name', 'Most Active Server')

            # Get guild_id for the source server
            source_guild_id = await self._get_source_guild_id(source_server_name)

            if not source_guild_id:
                print(f"Could not find source server: {source_server_name}")
                return

            # Get server database
            guild = self.bot.get_guild(int(source_guild_id))
            if not guild:
                print(f"Bot is not in guild {source_guild_id}")
                return

            db_manager = self.bot.get_server_db(source_guild_id, guild.name)

            # Get bot's personality/lore for status generation
            personality_traits = db_manager.get_bot_identity('trait')
            lore = db_manager.get_bot_identity('lore')
            facts = db_manager.get_bot_identity('fact')

            # Combine personality data
            personality_context = f"Personality traits: {', '.join(personality_traits)}\n"
            personality_context += f"Lore/backstory: {', '.join(lore)}\n"
            personality_context += f"Facts/quirks: {', '.join(facts)}"

            # Generate status using AI
            new_status = await self._generate_status_with_ai(personality_context)

            if new_status:
                # Update bot's Discord status
                await self.bot.change_presence(activity=discord.CustomActivity(name=new_status))
                print(f"✅ Updated bot status to: {new_status}")

                # Add to short-term memory for servers that have it enabled
                await self._add_status_to_memory(new_status, source_guild_id)

        except Exception as e:
            print(f"Error updating status: {e}")

    async def _get_source_guild_id(self, source_server_name):
        """
        Determines the guild_id to use for status generation.
        Returns guild_id as string.
        """
        if source_server_name == 'Most Active Server':
            # Find the most active server (most messages in short-term memory)
            return await self._find_most_active_server()
        else:
            # Find guild_id by server name
            for guild in self.bot.guilds:
                if guild.name == source_server_name:
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
        Returns the generated status string (max 128 characters for Discord).
        """
        try:
            config = self.config_manager.get_config()
            model_config = config.get('ai_models', {}).get('main_response', {})
            model = model_config.get('model', 'gpt-4.1-mini')

            system_prompt = f"""You are generating a Discord bot status message. The status should be:
- A funny, quirky thought or activity the bot is "doing" or "thinking about"
- Based on the bot's personality and lore below
- Natural and in-character
- MAX 128 characters (Discord limit)
- No quotes, just the raw status text
- Examples: "Thinking about fish...", "Contemplating existence", "Avoiding responsibilities"

{personality_context}

Generate a single status message that reflects something the bot might be doing or thinking based on its personality."""

            response = openai.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}],
                max_tokens=40,
                temperature=0.9  # Higher temperature for more creative/varied statuses
            )

            status = response.choices[0].message.content.strip()

            # Ensure it fits Discord's 128 character limit
            if len(status) > 128:
                status = status[:125] + "..."

            # Remove quotes if AI added them
            status = status.strip('"').strip("'")

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
