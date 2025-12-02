# cogs/random_events.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from datetime import datetime, timedelta
from modules.logging_manager import get_logger

class RandomEvents(commands.Cog):
    """
    Handles random event triggers for bot engagement.

    Every X hours (configurable), each enabled channel has a Y% chance (configurable)
    to trigger a random event. If triggered, the bot will either:
    - Read recent messages and respond to the conversation
    - Rant about its current Discord status

    Self-reply prevention ensures the bot doesn't respond to itself.
    """

    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger()
        # Track last event time per channel to enforce interval
        self.last_event_times = {}  # {channel_id: datetime}
        self.random_event_loop.start()
        self.logger.info("Random events system initialized")

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.random_event_loop.cancel()

    @tasks.loop(minutes=30)  # Check every 30 minutes for potential events
    async def random_event_loop(self):
        """
        Background task that checks channels for random event triggers.
        Each channel has its own interval and chance settings.
        """
        try:
            config = self.bot.config_manager.get_config()
            random_events_config = config.get('random_events', {})

            # Check if random events are globally enabled
            if not random_events_config.get('enabled', True):
                return

            self.logger.debug("Running random event check cycle")

            for guild in self.bot.guilds:
                try:
                    db_manager = self.bot.get_server_db(str(guild.id), guild.name)

                    # Get all channel settings from database
                    cursor = db_manager.conn.cursor()
                    cursor.execute("""
                        SELECT channel_id, random_event_enabled, random_event_chance,
                               random_event_interval_hours
                        FROM channel_settings
                        WHERE guild_id = ? AND random_event_enabled = 1
                    """, (str(guild.id),))
                    channels = cursor.fetchall()
                    cursor.close()

                    for channel_data in channels:
                        channel_id_str, enabled, chance, interval_hours = channel_data

                        if not enabled:
                            continue

                        channel_id = int(channel_id_str)
                        channel = guild.get_channel(channel_id)

                        if not channel or not isinstance(channel, discord.TextChannel):
                            continue

                        # Check if enough time has passed since last event
                        last_event = self.last_event_times.get(channel_id)
                        now = datetime.utcnow()

                        if last_event:
                            time_since_last = (now - last_event).total_seconds() / 3600  # hours
                            if time_since_last < interval_hours:
                                continue

                        # Roll the dice - does event trigger?
                        roll = random.random() * 100  # 0-100
                        if roll > chance:
                            self.logger.debug(f"Random event roll failed for #{channel.name}: {roll:.1f} > {chance}")
                            continue

                        self.logger.info(f"Random event triggered for #{channel.name} (roll: {roll:.1f} <= {chance})")

                        # Get recent messages to check last author
                        try:
                            recent_messages = []
                            async for message in channel.history(limit=10):
                                recent_messages.append(message)

                            if not recent_messages:
                                continue

                            # CRITICAL: Don't trigger if last message was from bot
                            last_message = recent_messages[0]
                            if last_message.author.id == self.bot.user.id:
                                self.logger.debug(f"Skipping random event in #{channel.name} - last message was from bot")
                                continue

                            # Reverse for chronological order
                            recent_messages.reverse()

                            # 50/50 choice: respond to conversation OR rant about status
                            event_type = random.choice(['conversation', 'status_rant'])

                            response = await self._generate_random_event_response(
                                channel, recent_messages, db_manager, event_type
                            )

                            if response:
                                await channel.send(response)
                                self.last_event_times[channel_id] = now
                                self.logger.info(f"Sent random event ({event_type}) in #{channel.name}")

                        except discord.Forbidden:
                            self.logger.warning(f"No permission to read/send in #{channel.name}")
                        except Exception as e:
                            self.logger.error(f"Error processing random event in channel {channel_id}: {e}")

                except Exception as e:
                    self.logger.error(f"Error processing guild {guild.id} for random events: {e}")

        except Exception as e:
            self.logger.error(f"Error in random_event_loop: {e}", exc_info=True)

    @random_event_loop.before_loop
    async def before_random_event_loop(self):
        """Wait until bot is ready before starting the task."""
        await self.bot.wait_until_ready()
        self.logger.info("Random events background task started")

    async def _generate_random_event_response(self, channel, recent_messages, db_manager, event_type):
        """
        Generate a response for a random event.

        Args:
            channel: Discord channel
            recent_messages: List of recent Message objects
            db_manager: Server database manager
            event_type: 'conversation' or 'status_rant'

        Returns:
            str: Generated response or None
        """
        try:
            # Get bot's current status
            current_status = None
            if self.bot.activity and hasattr(self.bot.activity, 'name'):
                current_status = self.bot.activity.name

            # Get channel config for personality settings
            channel_config = db_manager.get_channel_setting(str(channel.id)) or {}

            # Build identity prompt
            identity_prompt = self.bot.ai_handler._build_bot_identity_prompt(db_manager, channel_config)

            # Get emotes
            available_emotes = self.bot.ai_handler.emote_handler.get_emotes_with_context(guild_id=channel.guild.id)

            if event_type == 'status_rant':
                # Rant about current Discord status
                if not current_status:
                    current_status = "just vibing"

                system_prompt = f"""{identity_prompt}

You are randomly deciding to rant or comment about your current Discord status.
Your current status is: "{current_status}"

**TASK**: Make a short, casual comment or mini-rant about your status. Be in-character.
- Could be explaining WHY you set that status
- Could be complaining about something related to it
- Could be just randomly bringing it up
- Keep it brief (1-3 sentences max)
- Sound natural, like you just randomly felt like saying something
- You can use emotes: {available_emotes}

Do NOT make it sound like an announcement. Just casually bring it up."""

            else:  # conversation
                # React to recent conversation
                conversation_context = "\n".join([
                    f"{msg.author.display_name}: {msg.content[:200]}"
                    for msg in recent_messages[-5:]
                    if msg.content
                ])

                system_prompt = f"""{identity_prompt}

You've been lurking and reading the conversation. Now you randomly feel like jumping in.

**Recent conversation:**
{conversation_context}

**TASK**: Make a brief, natural comment about what people were talking about.
- React to something said, share your opinion, or add a joke
- Keep it short (1-2 sentences)
- Sound like you naturally wanted to chime in
- You can use emotes: {available_emotes}

Do NOT explain why you're talking. Just jump in naturally."""

            # Generate response
            response = await self.bot.ai_handler.client.chat.completions.create(
                model=self.bot.ai_handler._get_model_config('main_response')['model'],
                messages=[{'role': 'system', 'content': system_prompt}],
                max_tokens=100,
                temperature=0.9
            )

            result = response.choices[0].message.content.strip()

            # Replace emote tags
            result = self.bot.ai_handler.emote_handler.replace_emote_tags(result, channel.guild.id)

            return result

        except Exception as e:
            self.logger.error(f"Error generating random event response: {e}")
            return None

    # --- Slash Commands for Configuration ---

    @app_commands.command(name="random_event_config", description="Configure random events for this channel")
    @app_commands.describe(
        enabled="Enable or disable random events in this channel",
        chance="Percentage chance to trigger (0-100, default 50)",
        interval_hours="Hours between potential triggers (default 5)"
    )
    @app_commands.default_permissions(manage_channels=True)
    async def random_event_config(
        self,
        interaction: discord.Interaction,
        enabled: bool = None,
        chance: float = None,
        interval_hours: float = None
    ):
        """Configure random event settings for this channel."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        try:
            await interaction.response.defer(ephemeral=True)

            db_manager = self.bot.get_server_db(str(interaction.guild.id), interaction.guild.name)
            channel_id = str(interaction.channel.id)

            # Check if channel is activated
            current_settings = db_manager.get_channel_setting(channel_id)
            if not current_settings:
                await interaction.followup.send(
                    "This channel is not activated. Use `/activate` first.",
                    ephemeral=True
                )
                return

            # Build update query
            updates = []
            params = []

            if enabled is not None:
                updates.append("random_event_enabled = ?")
                params.append(1 if enabled else 0)

            if chance is not None:
                if chance < 0 or chance > 100:
                    await interaction.followup.send("Chance must be between 0 and 100.", ephemeral=True)
                    return
                updates.append("random_event_chance = ?")
                params.append(chance)

            if interval_hours is not None:
                if interval_hours < 0.5:
                    await interaction.followup.send("Interval must be at least 0.5 hours.", ephemeral=True)
                    return
                updates.append("random_event_interval_hours = ?")
                params.append(interval_hours)

            if updates:
                params.append(channel_id)
                query = f"UPDATE channel_settings SET {', '.join(updates)} WHERE channel_id = ?"
                cursor = db_manager.conn.cursor()
                cursor.execute(query, params)
                db_manager.conn.commit()
                cursor.close()

            # Fetch current settings
            cursor = db_manager.conn.cursor()
            cursor.execute("""
                SELECT random_event_enabled, random_event_chance, random_event_interval_hours
                FROM channel_settings WHERE channel_id = ?
            """, (channel_id,))
            result = cursor.fetchone()
            cursor.close()

            if result:
                is_enabled, current_chance, current_interval = result
                status = "Enabled" if is_enabled else "Disabled"

                embed = discord.Embed(
                    title="Random Event Configuration",
                    description=f"Settings for #{interaction.channel.name}",
                    color=discord.Color.green() if is_enabled else discord.Color.red()
                )
                embed.add_field(name="Status", value=status, inline=True)
                embed.add_field(name="Trigger Chance", value=f"{current_chance}%", inline=True)
                embed.add_field(name="Check Interval", value=f"{current_interval} hours", inline=True)
                embed.add_field(
                    name="How It Works",
                    value=f"Every {current_interval} hours, there's a {current_chance}% chance the bot will:\n"
                          f"- React to recent conversation (50%)\n"
                          f"- Rant about its status (50%)\n"
                          f"Bot won't trigger if it sent the last message.",
                    inline=False
                )

                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("Failed to retrieve settings.", ephemeral=True)

        except Exception as e:
            self.logger.error(f"Error in random_event_config: {e}")
            await interaction.followup.send(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="random_event_view", description="View random event settings for this channel")
    async def random_event_view(self, interaction: discord.Interaction):
        """View current random event settings."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        try:
            db_manager = self.bot.get_server_db(str(interaction.guild.id), interaction.guild.name)
            channel_id = str(interaction.channel.id)

            cursor = db_manager.conn.cursor()
            cursor.execute("""
                SELECT random_event_enabled, random_event_chance, random_event_interval_hours
                FROM channel_settings WHERE channel_id = ?
            """, (channel_id,))
            result = cursor.fetchone()
            cursor.close()

            if result:
                is_enabled, chance, interval = result
                # Handle None values (column doesn't exist yet)
                is_enabled = is_enabled if is_enabled is not None else 0
                chance = chance if chance is not None else 50.0
                interval = interval if interval is not None else 5.0

                status = "Enabled" if is_enabled else "Disabled"

                embed = discord.Embed(
                    title="Random Event Settings",
                    description=f"Current settings for #{interaction.channel.name}",
                    color=discord.Color.green() if is_enabled else discord.Color.gray()
                )
                embed.add_field(name="Status", value=status, inline=True)
                embed.add_field(name="Trigger Chance", value=f"{chance}%", inline=True)
                embed.add_field(name="Check Interval", value=f"{interval} hours", inline=True)

                # Check last event time
                last_event = self.last_event_times.get(int(channel_id))
                if last_event:
                    time_ago = datetime.utcnow() - last_event
                    hours_ago = time_ago.total_seconds() / 3600
                    embed.add_field(name="Last Event", value=f"{hours_ago:.1f} hours ago", inline=True)
                else:
                    embed.add_field(name="Last Event", value="Never (this session)", inline=True)

                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(
                    "This channel is not activated. Use `/activate` first.",
                    ephemeral=True
                )

        except Exception as e:
            self.logger.error(f"Error in random_event_view: {e}")
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="random_event_trigger", description="Manually trigger a random event (for testing)")
    @app_commands.describe(event_type="Type of event to trigger")
    @app_commands.choices(event_type=[
        app_commands.Choice(name="Conversation Response", value="conversation"),
        app_commands.Choice(name="Status Rant", value="status_rant"),
        app_commands.Choice(name="Random (50/50)", value="random")
    ])
    @app_commands.default_permissions(manage_channels=True)
    async def random_event_trigger(
        self,
        interaction: discord.Interaction,
        event_type: str = "random"
    ):
        """Manually trigger a random event for testing."""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return

        try:
            await interaction.response.defer()

            db_manager = self.bot.get_server_db(str(interaction.guild.id), interaction.guild.name)

            # Get recent messages
            recent_messages = []
            async for message in interaction.channel.history(limit=10):
                recent_messages.append(message)
            recent_messages.reverse()

            # Determine event type
            if event_type == "random":
                event_type = random.choice(['conversation', 'status_rant'])

            response = await self._generate_random_event_response(
                interaction.channel, recent_messages, db_manager, event_type
            )

            if response:
                await interaction.followup.send(f"**[Test Event - {event_type}]**\n{response}")
            else:
                await interaction.followup.send("Failed to generate event response.", ephemeral=True)

        except Exception as e:
            self.logger.error(f"Error in random_event_trigger: {e}")
            await interaction.followup.send(f"Error: {e}", ephemeral=True)


async def setup(bot):
    """Required setup function for cog loading."""
    await bot.add_cog(RandomEvents(bot))
