# cogs/proactive_tasks.py

import discord
from discord.ext import commands, tasks
from modules.proactive_engagement import ProactiveEngagement
from modules.logging_manager import get_logger

class ProactiveTasks(commands.Cog):
    """
    Handles proactive engagement background tasks.
    Periodically checks active channels and decides whether to jump into conversations.
    """

    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger()
        self.proactive_handler = ProactiveEngagement(bot)
        self.proactive_check_loop.start()  # Start the background task
        self.logger.info("Proactive engagement tasks initialized")

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.proactive_check_loop.cancel()

    @tasks.loop(minutes=30)  # Check every 30 minutes (configurable)
    async def proactive_check_loop(self):
        """
        Background task that periodically checks channels for proactive engagement opportunities.
        """
        try:
            config = self.bot.config_manager.get_config()
            proactive_config = config.get('proactive_engagement', {})

            # Check if proactive engagement is enabled
            if not proactive_config.get('enabled', False):
                return

            # Get check interval (update loop if different from current)
            check_interval_minutes = proactive_config.get('check_interval_minutes', 30)
            if self.proactive_check_loop.minutes != check_interval_minutes:
                self.proactive_check_loop.change_interval(minutes=check_interval_minutes)

            self.logger.debug(f"🔍 Running proactive engagement check across all servers")

            # Track how many channels we engaged in this cycle
            engagement_count = 0

            # Iterate through all guilds the bot is in
            for guild in self.bot.guilds:
                try:
                    # Get server-specific database
                    db_manager = self.bot.get_server_db(str(guild.id), guild.name)

                    # Get per-server proactive engagement settings
                    server_proactive_settings = config.get('server_proactive_settings', {})
                    server_enabled = server_proactive_settings.get(str(guild.id), {}).get('enabled', True)

                    if not server_enabled:
                        continue

                    # Get active channels for this server from config
                    channel_settings = config.get('channel_settings', {})

                    # Check each active channel
                    for channel_id_str, channel_config in channel_settings.items():
                        # Skip if not in this guild
                        if channel_config.get('guild_id') != str(guild.id):
                            continue

                        # Skip if proactive engagement is disabled for this channel
                        if not channel_config.get('allow_proactive_engagement', True):
                            continue

                        try:
                            channel = guild.get_channel(int(channel_id_str))

                            if not channel or not isinstance(channel, discord.TextChannel):
                                continue

                            # Get recent messages (last 20)
                            try:
                                recent_messages = []
                                async for message in channel.history(limit=20):
                                    recent_messages.append(message)

                                # Reverse to get chronological order (oldest first)
                                recent_messages.reverse()

                                if not recent_messages:
                                    continue

                                # Check if bot should engage
                                should_engage = await self.proactive_handler.should_engage(
                                    channel.id,
                                    recent_messages
                                )

                                if should_engage:
                                    # Generate and send proactive response
                                    response = await self.proactive_handler.generate_proactive_response(
                                        channel,
                                        recent_messages,
                                        db_manager
                                    )

                                    if response:
                                        # Send the response
                                        await channel.send(response)
                                        engagement_count += 1
                                        self.logger.info(f"📨 Sent proactive message in #{channel.name} ({guild.name})")

                            except discord.Forbidden:
                                self.logger.warning(f"No permission to read messages in #{channel.name}")
                                continue

                        except Exception as e:
                            self.logger.error(f"Error processing channel {channel_id_str}: {e}")
                            continue

                except Exception as e:
                    self.logger.error(f"Error processing guild {guild.id}: {e}")
                    continue

            if engagement_count > 0:
                self.logger.info(f"✅ Proactive engagement cycle complete: Engaged in {engagement_count} channel(s)")
            else:
                self.logger.debug("Proactive engagement cycle complete: No engagements this cycle")

        except Exception as e:
            self.logger.error(f"Error in proactive_check_loop: {e}", exc_info=True)

    @proactive_check_loop.before_loop
    async def before_proactive_check_loop(self):
        """Wait until bot is ready before starting the task."""
        await self.bot.wait_until_ready()
        self.logger.info("Proactive engagement background task started")

async def setup(bot):
    """Required setup function for cog loading."""
    await bot.add_cog(ProactiveTasks(bot))
