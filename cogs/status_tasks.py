# cogs/status_tasks.py

import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta
from modules.status_updater import StatusUpdater
from modules.logging_manager import get_logger
import asyncio

class StatusTasks(commands.Cog):
    """
    Handles scheduled status update tasks.
    Generates and updates bot status once per day at configured time.
    Triggers memory consolidation 5 minutes after status updates.
    """

    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger()
        self.status_updater = StatusUpdater(bot)
        self.daily_status_update.start()  # Start the background task
        self.logger.info("Status update tasks initialized")

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.daily_status_update.cancel()

    @tasks.loop(minutes=1)  # Check every minute
    async def daily_status_update(self):
        """
        Background task that checks if it's time to update the status.
        Runs every minute but only updates at the configured time.
        """
        try:
            config = self.bot.config_manager.get_config()
            status_config = config.get('status_updates', {})

            # Check if status updates are enabled
            if not status_config.get('enabled', False):
                return

            # Get configured update time (default: 12:00)
            update_time_str = status_config.get('update_time', '12:00')

            try:
                # Parse the time string (format: "HH:MM")
                hour, minute = map(int, update_time_str.split(':'))
                target_time = time(hour=hour, minute=minute)
            except (ValueError, AttributeError):
                self.logger.error(f"Invalid update_time format in config: {update_time_str}. Expected 'HH:MM'.")
                return

            # Get current time
            now = datetime.now().time()

            # Check if we're within the target minute
            if now.hour == target_time.hour and now.minute == target_time.minute:
                # Check if we've already updated today (prevent multiple updates in the same minute)
                if not hasattr(self, 'last_update_date') or self.last_update_date != datetime.now().date():
                    self.logger.info(f"🕐 Triggering daily status update at {now.strftime('%H:%M')}")
                    await self.status_updater.generate_and_update_status()
                    self.last_update_date = datetime.now().date()

                    # Schedule memory consolidation for 5 minutes later
                    self.logger.info("📅 Scheduling memory consolidation for 5 minutes from now...")
                    asyncio.create_task(self._delayed_memory_consolidation())

        except Exception as e:
            self.logger.error(f"Error in daily_status_update task: {e}", exc_info=True)

    async def _delayed_memory_consolidation(self):
        """
        Waits 5 minutes after status update, then triggers memory consolidation
        for all active servers.
        """
        try:
            # Wait 5 minutes
            await asyncio.sleep(300)  # 300 seconds = 5 minutes

            self.logger.info("🧠 Starting scheduled memory consolidation for all servers...")

            # Get memory tasks cog
            memory_cog = self.bot.get_cog('MemoryTasksCog')
            if not memory_cog:
                self.logger.error("MemoryTasksCog not found - cannot run consolidation")
                return

            # Consolidate memories for all servers
            consolidated_count = 0
            for guild in self.bot.guilds:
                try:
                    db_manager = self.bot.get_server_db(guild.id, guild.name)
                    if db_manager:
                        self.logger.info(f"Consolidating memories for: {guild.name}")
                        result = await memory_cog.consolidate_memories(guild.id, db_manager)
                        if result:
                            consolidated_count += 1
                            self.logger.info(
                                f"✅ {guild.name}: {result['users_processed']} users, "
                                f"{result['memories_added']} memories added"
                            )
                except Exception as e:
                    self.logger.error(f"Error consolidating memories for {guild.name}: {e}")

            self.logger.info(f"🧠 Memory consolidation complete. Processed {consolidated_count} servers.")

        except Exception as e:
            self.logger.error(f"Error in delayed memory consolidation: {e}", exc_info=True)

    @daily_status_update.before_loop
    async def before_daily_status_update(self):
        """Wait until bot is ready before starting the task."""
        await self.bot.wait_until_ready()
        self.logger.info("Status update background task started")

async def setup(bot):
    """Required setup function for cog loading."""
    await bot.add_cog(StatusTasks(bot))
