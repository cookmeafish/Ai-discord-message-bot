# cogs/events.py

import discord
from discord.ext import commands
import random
import asyncio
from modules.logging_manager import get_logger

class EventsCog(commands.Cog):
    """
    Handles all Discord events, including message processing and error handling.
    Implements the Core Interaction Handler (3.1) from the architecture.
    """
    _processing_messages = set()

    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger()

    @commands.Cog.listener("on_ready")
    async def on_cog_ready(self):
        """Called when the cog is ready."""
        self.logger.info("EventsCog is ready and listening for messages.")

    @commands.Cog.listener()
    async def on_message(self, message):
        """
        Main message handler. Processes all incoming messages.
        Logs all messages to the database and triggers AI responses when appropriate.
        """
        # Log bot's own messages to database for conversation history
        if message.author.bot:
            # Only log if it's our bot
            if message.author.id == self.bot.user.id:
                try:
                    self.bot.db_manager.log_message(message, directed_at_bot=False)
                    self.logger.debug(f"Logged bot message: {message.content[:50]}...")
                except Exception as e:
                    self.logger.error(f"Failed to log bot message to database: {e}")
            return

        self.logger.debug(f"Received message from {message.author.name}: {message.content[:50]}...")

        # Get configuration
        config = self.bot.config_manager.get_config()
        active_channels_str = config.get('channel_settings', {}).keys()
        active_channels_int = [int(ch_id) for ch_id in active_channels_str]

        # Check if this is an active channel
        is_active_channel = message.channel.id in active_channels_int

        # Always process commands, even in inactive channels
        if message.content.startswith('!'):
            await self.bot.process_commands(message)
            return

        # For slash commands, process and return
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            await self.bot.process_commands(message)
            return

        # Determine if the message was directed at the bot
        is_mentioned = self.bot.user.mentioned_in(message)
        is_reply_to_bot = False
        if message.reference and message.reference.resolved:
            if message.reference.resolved.author.id == self.bot.user.id:
                is_reply_to_bot = True

        was_directed_at_bot = is_mentioned or is_reply_to_bot

        # Log ALL user messages to the database (not just those in active channels)
        # This ensures the 24-hour rolling memory is complete
        try:
            self.bot.db_manager.log_message(message, directed_at_bot=was_directed_at_bot)
            self.logger.debug(f"Logged user message to database (directed_at_bot={was_directed_at_bot})")
        except Exception as e:
            self.logger.error(f"Failed to log message to database: {e}")

        # Only generate AI responses in active channels
        if not is_active_channel:
            self.logger.debug(f"Channel {message.channel.id} is not active, skipping response")
            return

        # Prevent duplicate processing
        if message.id in EventsCog._processing_messages:
            self.logger.warning(f"Message {message.id} is already being processed, skipping")
            return
        EventsCog._processing_messages.add(message.id)

        try:
            # Check if we should respond based on random chance or direct mention
            channel_config = config.get('channel_settings', {}).get(str(message.channel.id), {})
            rand_chance = channel_config.get('random_reply_chance', config.get('random_reply_chance', 0.0))
            is_random_reply = random.random() < rand_chance

            # Respond if directed at bot or if random chance triggers
            if was_directed_at_bot or is_random_reply:
                self.logger.info(f"Generating response for message from {message.author.name} (directed={was_directed_at_bot}, random={is_random_reply})")

                async with message.channel.typing():
                    try:
                        # Get channel-specific short-term memory
                        short_term_memory = self.bot.db_manager.get_short_term_memory(
                            channel_id=message.channel.id
                        )
                        self.logger.debug(f"Retrieved {len(short_term_memory)} messages from short-term memory")

                        # Log the last few messages for debugging
                        if short_term_memory:
                            self.logger.debug("Last 3 messages in context:")
                            for msg in short_term_memory[-3:]:
                                author_indicator = "BOT" if msg["author_id"] == self.bot.user.id else "USER"
                                self.logger.debug(f"  [{author_indicator}] {msg['content'][:50]}...")

                        # Generate AI response
                        ai_response_text = await self.bot.ai_handler.generate_response(
                            message=message,
                            short_term_memory=short_term_memory
                        )

                        self.logger.debug(f"AI generated response: {ai_response_text[:50] if ai_response_text else 'None'}...")

                        # Replace emote tags and send response
                        if ai_response_text:
                            final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text)
                            sent_message = await message.channel.send(final_response)
                            self.logger.info(f"Sent response: {final_response[:50]}...")

                            # Note: The bot's message will be logged when it triggers on_message
                        else:
                            self.logger.warning(f"AI handler returned empty response for message {message.id}")

                    except Exception as e:
                        self.logger.error(f"Failed to generate AI response: {e}", exc_info=True)
                        # Optionally send an error message to the channel
                        await message.channel.send("Sorry, I encountered an error while processing that.")

        finally:
            # Always remove from processing set
            EventsCog._processing_messages.discard(message.id)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """
        Global error handler for commands.
        Provides user-friendly error messages and logs errors.
        """
        # Ignore command not found errors
        if isinstance(error, commands.CommandNotFound):
            return

        # Handle missing permissions
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(
                "You don't have the required permissions to run this command.",
                ephemeral=True
            )

        # Handle missing required arguments
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                f"Missing required argument: {error.param.name}",
                ephemeral=True
            )

        # Handle bad arguments
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                f"Invalid argument provided. Please check the command usage.",
                ephemeral=True
            )

        # Handle all other errors
        else:
            self.logger.error(f"Unhandled error in command '{ctx.command}': {error}", exc_info=True)
            await ctx.send(
                "Sorry, something went wrong while running that command.",
                ephemeral=True
            )

async def setup(bot):
    """Required setup function to load the cog."""
    await bot.add_cog(EventsCog(bot))
