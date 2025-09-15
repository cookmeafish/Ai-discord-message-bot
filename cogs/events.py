# cogs/events.py

import discord
from discord.ext import commands
import random

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Modules are now attached to the bot object in main.py,
        # so we access them via self.bot instead of creating new ones.

    @commands.Cog.listener("on_ready")
    async def on_cog_ready(self):
        # This event fires when the cog is loaded and ready.
        print(f"✅ EventsCog is ready and listening for messages.")

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore messages from the bot itself or other bots to prevent loops
        if message.author.bot:
            return

        # Let commands be processed by the bot framework, ignore for chat logic
        if message.content.startswith(self.bot.command_prefix):
            return

        # Reload config to get the latest channel settings
        config = self.bot.config_manager.get_config()
        
        # --- Determine if the bot should respond ---
        is_mentioned = self.bot.user.mentioned_in(message)
        
        active_channels_str = config.get('channel_settings', {}).keys()
        active_channels_int = [int(ch_id) for ch_id in active_channels_str]
        is_active_channel = message.channel.id in active_channels_int

        rand_chance = config.get('random_reply_chance', 0.05)
        is_random_reply = random.random() < rand_chance

        # New Logic: Respond if mentioned anywhere, OR randomly in an active channel.
        if is_mentioned or (is_active_channel and is_random_reply):
            async with message.channel.typing():
                history = [msg async for msg in message.channel.history(limit=10)]
                history.reverse()

                # Access the shared AI handler from the bot object
                ai_response_text = await self.bot.ai_handler.generate_response(
                    message.channel, 
                    message.author, 
                    history
                )

                if ai_response_text:
                    # Access the shared emote handler for processing emotes
                    final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text)
                    await message.channel.send(final_response)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))
