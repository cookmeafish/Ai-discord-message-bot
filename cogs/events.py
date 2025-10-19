# cogs/events.py

import discord
from discord.ext import commands
import random
import asyncio
import re
from modules.logging_manager import get_logger
from database.input_validator import InputValidator

class EventsCog(commands.Cog):
    """
    Handles all Discord events, including message processing and error handling.
    Implements the Core Interaction Handler (3.1) from the architecture.
    """
    _processing_messages = set()
    _active_responses = 0  # Track number of concurrent AI responses
    _max_concurrent_responses = 3  # Maximum concurrent responses to prevent overwhelming the bot

    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger()

    def _normalize_text(self, text):
        """
        Normalizes text by removing spaces, periods, and special characters.
        Converts to lowercase for case-insensitive matching.

        Examples:
            "Bot Name" -> "botname"
            "Gordon Ramsay" -> "gordonramsay"
            "shark-bot" -> "sharkbot"
        """
        # Remove all non-alphanumeric characters and convert to lowercase
        return re.sub(r'[^a-z0-9]', '', text.lower())

    def _check_bot_name_mentioned(self, message):
        """
        Checks if the bot's name or any alternative nicknames are mentioned in the message.
        Uses flexible matching that ignores spaces, periods, and special characters.

        Returns:
            bool: True if bot name/nickname is mentioned, False otherwise
        """
        # Normalize the message content
        normalized_message = self._normalize_text(message.content)

        # Get bot's Discord username
        bot_username = self.bot.user.name
        if self._normalize_text(bot_username) in normalized_message:
            return True

        # Get bot's server nickname (if it has one)
        if message.guild:
            bot_member = message.guild.get_member(self.bot.user.id)
            if bot_member and bot_member.nick:
                if self._normalize_text(bot_member.nick) in normalized_message:
                    return True

        # Get alternative nicknames from config (server-specific first, then global)
        config = self.bot.config_manager.get_config()

        # Check server-specific alternative nicknames first
        if message.guild:
            server_nicknames = config.get('server_alternative_nicknames', {})
            guild_nicknames = server_nicknames.get(str(message.guild.id), [])

            for nickname in guild_nicknames:
                if self._normalize_text(nickname) in normalized_message:
                    return True

        # Fall back to global alternative nicknames for backward compatibility
        alternative_nicknames = config.get('alternative_nicknames', [])

        for nickname in alternative_nicknames:
            if self._normalize_text(nickname) in normalized_message:
                return True

        return False

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
        # Skip DMs - only process server messages
        if not message.guild:
            return

        # Get server-specific database
        db_manager = self.bot.get_server_db(message.guild.id, message.guild.name)
        if not db_manager:
            self.logger.warning(f"No database found for guild {message.guild.id}")
            return

        # Log bot's own messages to database for conversation history
        if message.author.bot:
            # Only log if it's our bot
            if message.author.id == self.bot.user.id:
                try:
                    db_manager.log_message(message, directed_at_bot=False)
                    self.logger.debug(f"Logged bot message: {message.content[:50]}...")
                except Exception as e:
                    self.logger.error(f"Failed to log bot message to database: {e}")
            return

        self.logger.debug(f"Received message from {message.author.name}: {message.content[:50]}...")

        # Check if channel is active in this server's database
        channel_setting = db_manager.get_channel_setting(str(message.channel.id))
        is_active_channel = channel_setting is not None

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

        # Check if bot's name/nickname is mentioned in message (flexible matching)
        bot_name_mentioned = self._check_bot_name_mentioned(message)

        was_directed_at_bot = is_mentioned or is_reply_to_bot or bot_name_mentioned

        # Only log and respond to messages from active channels
        # (but bot still has access to ALL historical data when responding)
        if not is_active_channel:
            self.logger.debug(f"Channel {message.channel.id} is not active, skipping message logging and response")
            return

        try:
            db_manager.log_message(message, directed_at_bot=was_directed_at_bot)
            self.logger.debug(f"Logged user message to database (directed_at_bot={was_directed_at_bot})")
        except Exception as e:
            self.logger.error(f"Failed to log message to database: {e}")

        # CRITICAL SECURITY: Validate message for SQL injection attempts BEFORE AI processing
        # This prevents users from manipulating the bot into executing SQL commands
        # Messages are logged above for admin visibility, but blocked from reaching AI
        is_valid, error_message = InputValidator.validate_message_for_sql_injection(message.content)
        if not is_valid:
            self.logger.warning(f"SECURITY: Blocked SQL injection attempt from {message.author.name} (ID: {message.author.id}): {message.content[:100]}")
            # Silently reject without revealing security details to potential attacker
            # Admins can see the attempt in logs
            return

        # Check if we need to trigger memory consolidation
        import os
        trigger_file = os.path.join("database", f".consolidate_trigger_{message.guild.id}")
        message_count = db_manager.get_short_term_message_count()
        message_limit = config.get('response_limits', {}).get('short_term_message_limit', 500)

        # Check for GUI trigger file or message count limit
        gui_triggered = os.path.exists(trigger_file)
        count_triggered = message_count >= message_limit

        if gui_triggered or count_triggered:
            trigger_reason = "GUI button" if gui_triggered else f"message count ({message_count}/{message_limit})"
            self.logger.info(f"Memory consolidation triggered by: {trigger_reason}")

            try:
                # Remove trigger file if it exists
                if gui_triggered:
                    os.remove(trigger_file)
                    self.logger.info("Removed GUI trigger file")

                # Get the memory tasks cog and trigger consolidation
                memory_cog = self.bot.get_cog('MemoryTasksCog')
                if memory_cog:
                    # Run consolidation in background without awaiting (pass guild info)
                    asyncio.create_task(memory_cog.consolidate_memories(message.guild.id, db_manager))
                    self.logger.info("Memory consolidation task started in background")
                else:
                    self.logger.warning("MemoryTasksCog not found, cannot trigger consolidation")
            except Exception as e:
                self.logger.error(f"Failed to trigger memory consolidation: {e}")

        # Prevent duplicate processing
        if message.id in EventsCog._processing_messages:
            self.logger.warning(f"Message {message.id} is already being processed, skipping")
            return
        EventsCog._processing_messages.add(message.id)

        try:
            # Check if message has images/attachments
            has_images = len(message.attachments) > 0

            # Respond ONLY if directed at bot (mentioned, replied to, or name mentioned)
            if was_directed_at_bot:
                # Check if bot is currently overwhelmed (too many concurrent responses)
                if EventsCog._active_responses >= EventsCog._max_concurrent_responses:
                    self.logger.warning(f"Bot is currently processing {EventsCog._active_responses} responses (max: {EventsCog._max_concurrent_responses}). Skipping message from {message.author.name}")
                    await message.reply("I'm currently responding to multiple people at once. Please wait a moment and try again!")
                    return

                self.logger.info(f"Generating response for message from {message.author.name} (mentioned={is_mentioned}, reply={is_reply_to_bot}, name_mentioned={bot_name_mentioned}, has_images={has_images})")

                # Increment active response counter
                EventsCog._active_responses += 1
                self.logger.debug(f"Active responses: {EventsCog._active_responses}/{EventsCog._max_concurrent_responses}")

                try:
                    async with message.channel.typing():
                        # Check if message has images - if so, process through image pipeline
                        if has_images:
                            self.logger.info(f"Message has {len(message.attachments)} attachment(s), checking for images")

                            # Process the first image attachment
                            for attachment in message.attachments:
                                # Check if it's an image or video/gif
                                if attachment.content_type and (
                                    attachment.content_type.startswith('image/') or
                                    attachment.content_type.startswith('video/') or
                                    attachment.filename.lower().endswith(('.gif', '.mp4', '.mov', '.webm'))
                                ):
                                    self.logger.info(f"Processing image/video: {attachment.filename}")

                                    # Process image through safety pipeline
                                    ai_response_text = await self.bot.ai_handler.process_image(
                                        message=message,
                                        image_url=attachment.url,
                                        image_filename=attachment.filename,
                                        db_manager=db_manager
                                    )

                                    if ai_response_text:
                                        final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text, message.guild.id)
                                        sent_message = await message.reply(final_response)
                                        self.logger.info(f"Sent image response: {final_response[:50]}...")
                                    else:
                                        self.logger.warning(f"Image processing returned no response")

                                    # Only process the first image
                                    break

                            # Skip normal text processing since we handled the image
                            return

                        # Normal text message processing
                        # Get server-wide short-term memory (not filtered by channel)
                        short_term_memory = db_manager.get_short_term_memory()
                        self.logger.debug(f"Retrieved {len(short_term_memory)} messages from server-wide short-term memory")

                        # Log the last few messages for debugging
                        if short_term_memory:
                            self.logger.debug("Last 3 messages in context:")
                            for msg in short_term_memory[-3:]:
                                author_indicator = "BOT" if msg["author_id"] == self.bot.user.id else "USER"
                                self.logger.debug(f"  [{author_indicator}] {msg['content'][:50]}...")

                        # Generate AI response with server-specific database
                        ai_response_text = await self.bot.ai_handler.generate_response(
                            message=message,
                            short_term_memory=short_term_memory,
                            db_manager=db_manager
                        )

                        self.logger.debug(f"AI generated response: {ai_response_text[:50] if ai_response_text else 'None'}...")

                        # Replace emote tags and send response
                        if ai_response_text:
                            # Check if response is a tuple (text + image bytes from image_generation intent)
                            if isinstance(ai_response_text, tuple) and len(ai_response_text) == 2:
                                text_response, image_bytes = ai_response_text
                                final_response = self.bot.emote_handler.replace_emote_tags(text_response, message.guild.id)

                                # Send image with caption
                                import io
                                image_file = discord.File(io.BytesIO(image_bytes), filename="drawing.png")
                                sent_message = await message.reply(content=final_response, file=image_file)
                                self.logger.info(f"Sent image response with caption: {final_response[:50]}...")
                            else:
                                # Normal text response
                                final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text, message.guild.id)
                                sent_message = await message.reply(final_response)
                                self.logger.info(f"Sent response: {final_response[:50]}...")

                            # Note: The bot's message will be logged when it triggers on_message
                        else:
                            self.logger.warning(f"AI handler returned empty response for message {message.id}")

                except Exception as e:
                    self.logger.error(f"Failed to generate AI response: {e}", exc_info=True)
                    # Optionally send an error message to the channel
                    await message.reply("Sorry, I encountered an error while processing that.")
                finally:
                    # Always decrement active response counter
                    EventsCog._active_responses -= 1
                    self.logger.debug(f"Response complete. Active responses: {EventsCog._active_responses}/{EventsCog._max_concurrent_responses}")

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
