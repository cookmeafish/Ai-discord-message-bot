# cogs/events.py

import discord
from discord.ext import commands
import random

from modules.emote_orchestrator import EmoteOrchestrator
from modules.ai_handler import AIHandler
from modules.personality_manager import PersonalityManager

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Get the main config dictionary from the manager
        self.config = bot.config_manager.get_config()

        # Dependency Injection is now cleaner
        self.emote_handler = EmoteOrchestrator(bot)
        self.personality_manager = PersonalityManager(self.config)
        
        openai_api_key = bot.config_manager.get_secret("OPENAI_API_KEY")
        self.ai_handler = AIHandler(openai_api_key, self.emote_handler, self.personality_manager)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'Bot is ready! Logged in as {self.bot.user}')
        self.emote_handler.load_emotes()
        print('------')

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        await self.bot.process_commands(message)

        if message.content.startswith(self.bot.command_prefix):
            return

        # Use the locally stored config
        active_channels_str = self.config.get('channel_settings', {}).keys()
        active_channels_int = [int(ch_id) for ch_id in active_channels_str]
        if message.channel.id not in active_channels_int:
            return

        should_respond = (self.bot.user.mentioned_in(message) or
                          random.random() < self.config.get('random_reply_chance', 0.05))

        if should_respond:
            async with message.channel.typing():
                history = [msg async for msg in message.channel.history(limit=10)]
                history.reverse()

                ai_response_text = await self.ai_handler.generate_response(message.channel, message.author, history)

                if ai_response_text:
                    final_response = self.emote_handler.replace_emote_tags(ai_response_text)
                    await message.channel.send(final_response)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))