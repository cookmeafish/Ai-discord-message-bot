# cogs/events.py

import discord
from discord.ext import commands
import random
import asyncio
import logging # --- ADDED ---

class EventsCog(commands.Cog):
    _processing_messages = set()

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_ready")
    async def on_cog_ready(self):
        print(f"✅ EventsCog is ready and listening for messages.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        
        ctx = await self.bot.get_context(message)
        
        if ctx.valid:
            await self.bot.process_commands(message)
            return

        if message.id in EventsCog._processing_messages:
            return

        EventsCog._processing_messages.add(message.id)
        try:
            config = self.bot.config_manager.get_config()
            is_mentioned = self.bot.user.mentioned_in(message)
            active_channels_str = config.get('channel_settings', {}).keys()
            active_channels_int = [int(ch_id) for ch_id in active_channels_str]
            is_active_channel = message.channel.id in active_channels_int
            rand_chance = config.get('random_reply_chance', 0.05)
            is_random_reply = random.random() < rand_chance

            if is_mentioned or (is_active_channel and is_random_reply):
                async with message.channel.typing():
                    history = [msg async for msg in message.channel.history(limit=10)]
                    history.reverse()

                    ai_response_text = await self.bot.ai_handler.generate_response(
                        message.channel, 
                        message.author, 
                        history
                    )

                    if ai_response_text:
                        # --- MODIFIED FOR LOGGING ---
                        logging.info("="*60)
                        logging.info(f"Raw response from AI:\n{ai_response_text}")
                        # --- END MODIFIED ---

                        final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text)

                        # --- MODIFIED FOR LOGGING ---
                        logging.info(f"Final message being sent to Discord:\n{final_response}")
                        logging.info("="*60)
                        # --- END MODIFIED ---

                        await message.channel.send(final_response)
        
        finally:
            EventsCog._processing_messages.discard(message.id)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("You don't have the required permissions to run this command.", ephemeral=True)
        else:
            print(f"An unhandled error occurred in command '{ctx.command}': {error}")
            await ctx.send("Sorry, something went wrong while running that command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(EventsCog(bot))