# cogs/status_tasks.py

import discord
from discord.ext import commands, tasks
from datetime import datetime, time
from modules.status_updater import StatusUpdater
from modules.logging_manager import get_logger

class StatusTasks(commands.Cog):
    """
    Handles scheduled status update tasks.
    Generates and updates bot status once per day at configured time.
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

        except Exception as e:
            self.logger.error(f"Error in daily_status_update task: {e}", exc_info=True)

    @daily_status_update.before_loop
    async def before_daily_status_update(self):
        """Wait until bot is ready before starting the task."""
        await self.bot.wait_until_ready()
        self.logger.info("Status update background task started")

async def setup(bot):
    """Required setup function for cog loading."""
    await bot.add_cog(StatusTasks(bot))
