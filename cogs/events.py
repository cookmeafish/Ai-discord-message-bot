# cogs/events.py

import discord
from discord.ext import commands
import random

# Import your modules
from modules.emote_orchestrator import EmoteOrchestrator
from modules.ai_handler import AIHandler # We will create this next
from modules.personality_manager import PersonalityManager # And this one too

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Dependency Injection: Give the cog access to your modules
        self.emote_handler = EmoteOrchestrator(bot)
        self.personality_manager = PersonalityManager(bot.config)
        # Pass the config to the AI Handler
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

        # Let the bot process commands first
        await self.bot.process_commands(message)

        # If it was a command, don't also try to generate a chat response
        if message.content.startswith(self.bot.command_prefix):
            return

        # Check if the bot should be active in this channel
        active_channels_str = self.bot.config.get('channel_settings', {}).keys()
        active_channels_int = [int(ch_id) for ch_id in active_channels_str]
        if message.channel.id not in active_channels_int:
            return

        # Respond if mentioned or by random chance
        should_respond = (self.bot.user.mentioned_in(message) or
                          random.random() < self.bot.config.get('random_reply_chance', 0.05))

        if should_respond:
            async with message.channel.typing():
                history = [msg async for msg in message.channel.history(limit=10)]
                history.reverse()

                ai_response_text = await self.ai_handler.generate_response(message.channel, message.author, history)

                if ai_response_text:
                    final_response = self.emote_handler.replace_emote_tags(ai_response_text)
                    await message.channel.send(final_response)

async def setup(bot):
    # Pass the config manager when initializing the cog
    await bot.add_cog(EventsCog(bot))