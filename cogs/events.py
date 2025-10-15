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
            # Check if we should respond based on random chance or direct mention
            channel_config = config.get('channel_settings', {}).get(str(message.channel.id), {})
            rand_chance = channel_config.get('random_reply_chance', config.get('random_reply_chance', 0.0))
            is_random_reply = random.random() < rand_chance

            # Check if message has images/attachments
            has_images = len(message.attachments) > 0

            # Respond if directed at bot or if random chance triggers or if has images
            if was_directed_at_bot or is_random_reply or has_images:
                self.logger.info(f"Generating response for message from {message.author.name} (directed={was_directed_at_bot}, random={is_random_reply}, has_images={has_images})")

                async with message.channel.typing():
                    try:
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
                                        final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text)
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
                            final_response = self.bot.emote_handler.replace_emote_tags(ai_response_text)
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
