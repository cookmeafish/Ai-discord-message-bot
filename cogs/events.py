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

    # Message batching system - combines rapid messages from same user into one response
    _channel_locks = {}       # {channel_id: asyncio.Lock} - One response at a time per channel
    _pending_messages = {}    # {(user_id, channel_id): [messages]} - Messages waiting to be processed
    _queued_users = {}        # {channel_id: set(user_ids)} - Users currently queued per channel
    _batch_lock = None        # Global asyncio.Lock for thread-safe dictionary access
    _MAX_REGENERATIONS = 3    # Max times to regenerate if new messages arrive

    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger()
        # Initialize the batch lock if not already done
        if EventsCog._batch_lock is None:
            EventsCog._batch_lock = asyncio.Lock()

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
        self.logger.debug(f"Checking bot name in message. Normalized: '{normalized_message}'")

        # Get bot's Discord username
        bot_username = self.bot.user.name
        normalized_bot_username = self._normalize_text(bot_username)
        self.logger.debug(f"Bot username: '{bot_username}' -> normalized: '{normalized_bot_username}'")
        if normalized_bot_username in normalized_message:
            self.logger.debug(f"Match found: bot username in message")
            return True

        # Get bot's server nickname (if it has one)
        if message.guild:
            bot_member = message.guild.get_member(self.bot.user.id)
            if bot_member and bot_member.nick:
                normalized_nick = self._normalize_text(bot_member.nick)
                self.logger.debug(f"Bot server nickname: '{bot_member.nick}' -> normalized: '{normalized_nick}'")
                if normalized_nick in normalized_message:
                    self.logger.debug(f"Match found: server nickname in message")
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

    def _get_channel_lock(self, channel_id):
        """Get or create a lock for the specified channel (one response at a time per channel)."""
        if channel_id not in EventsCog._channel_locks:
            # This should NOT happen - lock should be created in _queue_message_for_batching
            # If we get here, log a warning but create the lock anyway for safety
            self.logger.warning(f"BATCHING: Channel lock missing for {channel_id} - creating fallback (this shouldn't happen!)")
            EventsCog._channel_locks[channel_id] = asyncio.Lock()
        return EventsCog._channel_locks[channel_id]

    async def _queue_message_for_batching(self, message) -> bool:
        """
        Queue a message for batching. Returns True if this is a NEW queue entry
        (caller should process), False if added to existing batch (caller should return early).

        CRITICAL: Channel lock is created here while holding batch_lock to prevent
        race condition where two messages arriving simultaneously create separate locks.
        """
        async with EventsCog._batch_lock:
            key = (message.author.id, message.channel.id)
            channel_id = message.channel.id

            # ATOMIC: Create channel lock while holding batch_lock to prevent race condition
            # This ensures all messages for a channel use the SAME lock object
            if channel_id not in EventsCog._channel_locks:
                EventsCog._channel_locks[channel_id] = asyncio.Lock()
                self.logger.debug(f"BATCHING: Created channel lock for channel {channel_id}")

            # Initialize channel tracking if needed
            if channel_id not in EventsCog._queued_users:
                EventsCog._queued_users[channel_id] = set()

            if message.author.id in EventsCog._queued_users[channel_id]:
                # User already queued - just add message to pending batch
                if key not in EventsCog._pending_messages:
                    EventsCog._pending_messages[key] = []
                EventsCog._pending_messages[key].append(message)
                self.logger.info(f"BATCHING: Added message to existing batch for {message.author.name} (now {len(EventsCog._pending_messages[key])} messages)")
                return False  # Don't start new processing

            # New user for this channel - queue them
            EventsCog._queued_users[channel_id].add(message.author.id)
            # DON'T add message to pending here - it will be used as initial_message in processing
            # Pending is only for ADDITIONAL messages that arrive during processing
            EventsCog._pending_messages[key] = []
            self.logger.info(f"BATCHING: New batch started for {message.author.name} in channel {channel_id}")
            return True  # Caller should process

    async def _process_batched_response(self, initial_message, db_manager, has_images=False, emote_handler=None):
        """
        Process response with message batching and per-channel queuing.
        Checks for new messages before sending and regenerates if needed.
        SENDS the response internally to eliminate race condition between check and send.

        Regeneration counting: Each new message counts toward the max limit.
        If 2 messages arrive at once, it counts as 2 regenerations, not 1.

        Returns:
            tuple: (sent_message_or_none, cleanup_info) - sent_message is Discord message if sent
        """
        channel_id = initial_message.channel.id
        user_id = initial_message.author.id
        key = (user_id, channel_id)
        channel_lock = self._get_channel_lock(channel_id)

        try:
            # Wait for channel lock (one user at a time per channel)
            self.logger.info(f"BATCHING: Waiting for channel lock for {initial_message.author.name} (channel {channel_id})")
            async with channel_lock:
                self.logger.info(f"BATCHING: Acquired channel lock for {initial_message.author.name}")

                async with initial_message.channel.typing():
                    regeneration_count = 0  # Counts NEW messages that triggered regeneration
                    ai_response = None
                    primary_message = initial_message
                    force_send_after_next = False  # Flag to force send after next generation
                    first_iteration = True  # Track first iteration to avoid duplicate initial_message

                    while True:
                        # Step 1: Collect all pending messages for this user+channel
                        async with EventsCog._batch_lock:
                            messages = EventsCog._pending_messages.get(key, [])
                            EventsCog._pending_messages[key] = []  # Clear for next batch

                        if first_iteration:
                            # First iteration: always include initial_message + any messages queued during startup
                            messages = [initial_message] + messages
                            first_iteration = False
                        # else: messages from pending already include initial_message from regeneration loop

                        # Step 2: Combine message contents
                        combined_content = "\n".join(m.content for m in messages if m.content)
                        primary_message = messages[-1]  # Reply to last message

                        self.logger.info(f"BATCHING: Processing {len(messages)} message(s) for {initial_message.author.name}, regeneration_count={regeneration_count}/{EventsCog._MAX_REGENERATIONS}")
                        self.logger.debug(f"BATCHING: Combined content: '{combined_content[:100]}...'")

                        # Step 3: Handle images separately (no batching for images)
                        if has_images:
                            for attachment in initial_message.attachments:
                                if attachment.content_type and (
                                    attachment.content_type.startswith('image/') or
                                    attachment.content_type.startswith('video/') or
                                    attachment.filename.lower().endswith(('.gif', '.mp4', '.mov', '.webm'))
                                ):
                                    ai_response = await self.bot.ai_handler.process_image(
                                        message=primary_message,
                                        image_url=attachment.url,
                                        image_filename=attachment.filename,
                                        db_manager=db_manager
                                    )
                                    break
                        else:
                            # Normal text processing
                            short_term_memory = db_manager.get_short_term_memory()
                            # Count bot messages in context to verify previous responses are included
                            # NOTE: short_term_memory uses 'author_id' key (not 'user_id')
                            bot_id = self.bot.user.id
                            bot_msgs_in_context = sum(1 for m in short_term_memory if m.get('author_id') == bot_id)
                            recent_msgs = short_term_memory[-3:] if len(short_term_memory) >= 3 else short_term_memory
                            recent_summary = " | ".join([f"{m.get('nickname', 'unknown')}: {m.get('content', '')[:30]}" for m in recent_msgs])
                            self.logger.info(f"BATCHING: Context for {initial_message.author.name}: {len(short_term_memory)} msgs ({bot_msgs_in_context} from bot). Recent: [{recent_summary}]")

                            ai_response = await self.bot.ai_handler.generate_response(
                                message=primary_message,
                                short_term_memory=short_term_memory,
                                db_manager=db_manager,
                                combined_content=combined_content
                            )

                        # If we were flagged to send after this generation, send and exit
                        if force_send_after_next:
                            self.logger.info(f"BATCHING: Sending after final generation (hit max regenerations)")
                            # Send response immediately after max regenerations
                            async with EventsCog._batch_lock:
                                sent_message = None
                                if ai_response:
                                    try:
                                        # Check if response is a tuple (text + image bytes)
                                        if isinstance(ai_response, tuple) and len(ai_response) == 2:
                                            text_response, image_bytes = ai_response
                                            if emote_handler:
                                                final_response = emote_handler.replace_emote_tags(text_response, initial_message.guild.id)
                                            else:
                                                final_response = text_response
                                            import io
                                            image_file = discord.File(io.BytesIO(image_bytes), filename="drawing.png")
                                            sent_message = await primary_message.reply(content=final_response, file=image_file)
                                            self.logger.info(f"Sent image response (max regen): {final_response[:50]}...")
                                        else:
                                            if emote_handler:
                                                final_response = emote_handler.replace_emote_tags(ai_response, initial_message.guild.id)
                                            else:
                                                final_response = ai_response
                                            sent_message = await primary_message.reply(final_response)
                                            self.logger.info(f"Sent response (max regen): {final_response[:50]}...")

                                        # CRITICAL: Log bot's message to short-term memory BEFORE releasing lock
                                        if sent_message:
                                            try:
                                                log_result = db_manager.log_message(sent_message, directed_at_bot=False)
                                                self.logger.info(f"BATCHING: Logged bot response to DB (success={log_result}, msg_id={sent_message.id}) [max regen]")
                                            except Exception as log_err:
                                                self.logger.error(f"BATCHING: Failed to log bot response: {log_err}")
                                    except Exception as e:
                                        self.logger.error(f"Failed to send response: {e}")

                                # CLEANUP while holding lock
                                if channel_id in EventsCog._queued_users:
                                    EventsCog._queued_users[channel_id].discard(user_id)
                                EventsCog._pending_messages.pop(key, None)
                                self.logger.debug(f"BATCHING: Cleanup complete (max regen) for {initial_message.author.name}")

                                return sent_message, (user_id, channel_id, key)

                        # Step 4: CHECK BEFORE SEND - any new messages?
                        async with EventsCog._batch_lock:
                            new_messages = EventsCog._pending_messages.get(key, [])
                            if new_messages:
                                # Count each new message toward the regeneration limit (per-user, not affected by other users)
                                new_count = len(new_messages)
                                regeneration_count += new_count

                                self.logger.info(f"BATCHING: {new_count} new message(s) from {initial_message.author.name}, regeneration_count now {regeneration_count}/{EventsCog._MAX_REGENERATIONS}")

                                # Add messages back for next iteration
                                EventsCog._pending_messages[key] = messages + new_messages

                                # Check if we've hit the limit
                                if regeneration_count >= EventsCog._MAX_REGENERATIONS:
                                    self.logger.info(f"BATCHING: Max regenerations reached, will do final generation then send")
                                    force_send_after_next = True
                                # Continue to regenerate (either under limit or doing final generation)
                                continue

                        # No new messages detected - do a final check and SEND immediately
                        # This eliminates race condition between check and send
                        await asyncio.sleep(0.1)  # 100ms window for late messages

                        # ATOMIC FINAL CHECK + SEND: Check for messages, if none then send immediately
                        async with EventsCog._batch_lock:
                            final_check_messages = EventsCog._pending_messages.get(key, [])
                            if final_check_messages and regeneration_count < EventsCog._MAX_REGENERATIONS:
                                # Last-second messages arrived! Regenerate
                                regeneration_count += len(final_check_messages)
                                EventsCog._pending_messages[key] = messages + final_check_messages
                                self.logger.info(f"BATCHING: Final check caught {len(final_check_messages)} late message(s) from {initial_message.author.name}, regenerating")
                                continue

                            # No new messages - SEND NOW while still holding batch_lock
                            # This prevents messages from being added to pending during send
                            self.logger.info(f"BATCHING: Complete for {initial_message.author.name}, total regenerations: {regeneration_count}")

                            sent_message = None
                            if ai_response:
                                try:
                                    # Check if response is a tuple (text + image bytes)
                                    if isinstance(ai_response, tuple) and len(ai_response) == 2:
                                        text_response, image_bytes = ai_response
                                        if emote_handler:
                                            final_response = emote_handler.replace_emote_tags(text_response, initial_message.guild.id)
                                        else:
                                            final_response = text_response
                                        import io
                                        image_file = discord.File(io.BytesIO(image_bytes), filename="drawing.png")
                                        sent_message = await primary_message.reply(content=final_response, file=image_file)
                                        self.logger.info(f"Sent image response: {final_response[:50]}...")
                                    else:
                                        if emote_handler:
                                            final_response = emote_handler.replace_emote_tags(ai_response, initial_message.guild.id)
                                        else:
                                            final_response = ai_response
                                        sent_message = await primary_message.reply(final_response)
                                        self.logger.info(f"Sent response: {final_response[:50]}...")

                                    # CRITICAL: Log bot's message to short-term memory BEFORE releasing lock
                                    # This ensures the next user in queue sees this response in their context
                                    # and doesn't generate a duplicate response
                                    if sent_message:
                                        try:
                                            log_result = db_manager.log_message(sent_message, directed_at_bot=False)
                                            self.logger.info(f"BATCHING: Logged bot response to DB (success={log_result}, msg_id={sent_message.id})")
                                        except Exception as log_err:
                                            self.logger.error(f"BATCHING: Failed to log bot response: {log_err}")
                                except Exception as e:
                                    self.logger.error(f"Failed to send response: {e}")

                            # CLEANUP while still holding lock - remove user from queue
                            if channel_id in EventsCog._queued_users:
                                EventsCog._queued_users[channel_id].discard(user_id)
                            EventsCog._pending_messages.pop(key, None)
                            self.logger.debug(f"BATCHING: Cleanup complete for {initial_message.author.name}")

                            return sent_message, (user_id, channel_id, key)

        except Exception as e:
            # On error, still need to cleanup
            async with EventsCog._batch_lock:
                if channel_id in EventsCog._queued_users:
                    EventsCog._queued_users[channel_id].discard(user_id)
                EventsCog._pending_messages.pop(key, None)
                self.logger.debug(f"BATCHING: Cleanup on error for {initial_message.author.name}")
            raise

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
            self.logger.info(f"CHANNEL CHECK: {message.channel.name} ({message.channel.id}) is NOT active - ignoring message from {message.author.name}")
            return
        else:
            self.logger.debug(f"CHANNEL CHECK: {message.channel.name} ({message.channel.id}) IS active")

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
        config = self.bot.config_manager.get_config()
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

            # CONVERSATION CONTINUATION DETECTION
            # If message wasn't explicitly directed at bot, check if it's a conversation continuation
            if not was_directed_at_bot:
                # Check if conversation detection is enabled for this channel
                conversation_detection_enabled = channel_setting.get('enable_conversation_detection', 0) if channel_setting else 0

                # Debug logging for conversation detection settings
                self.logger.debug(f"CONV_DETECT: channel_setting exists: {channel_setting is not None}")
                if channel_setting:
                    self.logger.debug(f"CONV_DETECT: enable_conversation_detection = {channel_setting.get('enable_conversation_detection', 'KEY_NOT_FOUND')}")
                    self.logger.debug(f"CONV_DETECT: conversation_detection_threshold = {channel_setting.get('conversation_detection_threshold', 'KEY_NOT_FOUND')}")
                    self.logger.debug(f"CONV_DETECT: conversation_context_window = {channel_setting.get('conversation_context_window', 'KEY_NOT_FOUND')}")
                self.logger.debug(f"CONV_DETECT: Final enabled value = {conversation_detection_enabled}")

                if conversation_detection_enabled:
                    # Get configuration
                    threshold = channel_setting.get('conversation_detection_threshold', 0.7)
                    context_window = channel_setting.get('conversation_context_window', 10)

                    # Get recent messages from short-term memory
                    recent_messages = db_manager.get_short_term_memory()
                    recent_messages = recent_messages[-context_window:] if len(recent_messages) > context_window else recent_messages

                    # Check if bot was recently active (optimization)
                    if self.bot.conversation_detector.is_bot_recently_active(recent_messages, self.bot.user.id, max_messages=context_window):
                        # Run AI detection
                        bot_name = message.guild.me.display_name
                        should_respond = await self.bot.conversation_detector.should_respond(
                            recent_messages=recent_messages,
                            current_message=message,
                            bot_id=self.bot.user.id,
                            bot_name=bot_name,
                            threshold=threshold
                        )

                        if should_respond:
                            self.logger.info(f"Conversation detection: Message from {message.author.name} detected as conversation continuation")
                            was_directed_at_bot = True
                        else:
                            self.logger.debug(f"Conversation detection: Message from {message.author.name} NOT detected as conversation continuation")
                    else:
                        self.logger.debug(f"Conversation detection: Bot not recently active, skipping detection")

            # Respond ONLY if directed at bot (mentioned, replied to, name mentioned, or detected as continuation)
            if was_directed_at_bot:
                # Check if bot is currently overwhelmed (too many concurrent responses)
                if EventsCog._active_responses >= EventsCog._max_concurrent_responses:
                    self.logger.warning(f"Bot is currently processing {EventsCog._active_responses} responses (max: {EventsCog._max_concurrent_responses}). Skipping message from {message.author.name}")
                    await message.reply("I'm currently responding to multiple people at once. Please wait a moment and try again!")
                    return

                self.logger.info(f"Generating response for message from {message.author.name} (mentioned={is_mentioned}, reply={is_reply_to_bot}, name_mentioned={bot_name_mentioned}, has_images={has_images})")

                # MESSAGE BATCHING: Queue message and check if we should process
                should_process = await self._queue_message_for_batching(message)

                if not should_process:
                    # Message added to existing batch - another handler will process it
                    self.logger.debug(f"Message queued for batching, returning early")
                    EventsCog._processing_messages.discard(message.id)
                    return

                # Increment active response counter
                EventsCog._active_responses += 1
                self.logger.debug(f"Active responses: {EventsCog._active_responses}/{EventsCog._max_concurrent_responses}")

                try:
                    # Use batched response processor (handles combining messages + check-before-send + SENDING)
                    # Send happens inside _process_batched_response to eliminate race condition
                    sent_message, cleanup_info = await self._process_batched_response(
                        initial_message=message,
                        db_manager=db_manager,
                        has_images=has_images,
                        emote_handler=self.bot.emote_handler
                    )

                    if not sent_message:
                        self.logger.warning(f"No response sent for message {message.id}")
                    # Note: The bot's message will be logged when it triggers on_message
                    # Cleanup already happened inside _process_batched_response

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
