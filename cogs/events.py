# cogs/events.py

import discord
from discord.ext import commands
import random
import asyncio

class EventsCog(commands.Cog):
    # This is now a class variable, not an instance variable.
    # This creates a SINGLE, shared set across all potential instances of this cog,
    # which is a more robust way to prevent race conditions from duplicate events.
    _processing_messages = set()

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener("on_ready")
    async def on_cog_ready(self):
        # This event fires when the cog is loaded and ready.
        print(f"✅ EventsCog is ready and listening for messages.")

    @commands.Cog.listener()
    async def on_message(self, message):
        # --- Start of Pre-checks ---

        # Ignore messages from the bot itself to prevent loops
        if message.author.bot:
            return
            
        # Check the class-level set to see if this message ID is already being processed.
        if message.id in EventsCog._processing_messages:
            return

        # Add the message ID to the class-level set to "lock" it.
        EventsCog._processing_messages.add(message.id)
        try:
            # Check for command prefix. If it's a command, let the bot's
            # command handler deal with it and do not proceed with chat logic.
            if message.content.startswith(self.bot.command_prefix):
                await self.bot.process_commands(message)
                return

            # --- Determine if the bot should respond to the chat message ---
            config = self.bot.config_manager.get_config()
            
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
        
        finally:
            # IMPORTANT: Always remove the message ID from the shared set to "unlock" it
            # after processing is complete.
            EventsCog._processing_messages.remove(message.id)


async def setup(bot):
    await bot.add_cog(EventsCog(bot))
