# cogs/events.py

import discord
from discord.ext import commands
import random
import asyncio
import logging 

class EventsCog(commands.Cog):
    _processing_messages = set()

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_ready")
    async def on_cog_ready(self):
        print("EventsCog is ready and listening for messages.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        is_mentioned = self.bot.user.mentioned_in(message)
        is_reply_to_bot = False
        if message.reference and message.reference.resolved:
            if message.reference.resolved.author.id == self.bot.user.id:
                is_reply_to_bot = True
        
        was_directed_at_bot = is_mentioned or is_reply_to_bot
        
        self.bot.db_manager.log_message(message, directed_at_bot=was_directed_at_bot)

        ctx = await self.bot.get_context(message)
        
        if ctx.valid:
            await self.bot.process_commands(message)
            return

        if message.id in EventsCog._processing_messages:
            return

        EventsCog._processing_messages.add(message.id)
        try:
            config = self.bot.config_manager.get_config()
            active_channels_str = config.get('channel_settings', {}).keys()
            active_channels_int = [int(ch_id) for ch_id in active_channels_str]
            is_active_channel = message.channel.id in active_channels_int
            rand_chance = config.get('random_reply_chance', 0.05)
            is_random_reply = random.random() < rand_chance

            if was_directed_at_bot or (is_active_channel and is_random_reply):
                async with message.channel.typing():
                    short_term_memory = self.bot.db_manager.get_short_term_memory()

                    ai_response_text = await self.bot.ai_handler.generate_response(
                        message=message,
                        short_term_memory=short_term_memory
                    )

                    if ai_response_text:
                        final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text)
                        await message.channel.send(final_response)
                    else:
                        # Failsafe to prevent silence
                        await message.channel.send("I'm not sure how to respond to that.")
        
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