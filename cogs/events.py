# cogs/events.py

import discord
from discord.ext import commands
import random
import asyncio

class EventsCog(commands.Cog):
    # This is a class variable to prevent race conditions from duplicate events.
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
        
        # First, determine if the message is a command.
        ctx = await self.bot.get_context(message)
        
        # If the message is a valid command, process it and stop here.
        if ctx.valid:
            await self.bot.process_commands(message)
            return

        # If we reach here, the message is not a command, so we can proceed with chat logic.

        # This lock prevents race conditions from duplicate Discord gateway events.
        if message.id in EventsCog._processing_messages:
            return

        EventsCog._processing_messages.add(message.id)
        try:
            # --- Determine if the bot should respond to the chat message ---
            config = self.bot.config_manager.get_config()
            
            is_mentioned = self.bot.user.mentioned_in(message)
            
            active_channels_str = config.get('channel_settings', {}).keys()
            active_channels_int = [int(ch_id) for ch_id in active_channels_str]
            is_active_channel = message.channel.id in active_channels_int

            rand_chance = config.get('random_reply_chance', 0.05)
            is_random_reply = random.random() < rand_chance

            # Respond if mentioned anywhere, OR randomly in an active channel.
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
                        final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text)
                        await message.channel.send(final_response)
        
        finally:
            # Always remove the message ID from the set to "unlock" it.
            EventsCog._processing_messages.discard(message.id)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """A global error handler for all commands."""
        
        # isinstance checks if the error is a specific type
        if isinstance(error, commands.CommandNotFound):
            # Silently ignore commands that don't exist.
            return
        elif isinstance(error, commands.MissingPermissions):
            # Tell the user they are missing permissions.
            await ctx.send("You don't have the required permissions to run this command.", ephemeral=True)
        else:
            # For any other errors, log it to the console and inform the user.
            print(f"An unhandled error occurred in command '{ctx.command}': {error}")
            await ctx.send("Sorry, something went wrong while running that command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(EventsCog(bot))

