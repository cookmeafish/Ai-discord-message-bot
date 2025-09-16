import discord
from discord.ext import commands, tasks

# This is the basic structure for a cog file that will run background tasks.
class MemoryTasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Start the background tasks when the cog is initialized.
        # self.proactive_engagement_loop.start()
        # self.memory_consolidation_loop.start()

    # This is where your proactive engagement task will go.
    # The decorator @tasks.loop(minutes=30) will make it run every 30 minutes.
    # @tasks.loop(minutes=30)
    # async def proactive_engagement_loop(self):
    #     # Your logic for proactive messages will go here.
    #     print("Proactive engagement loop is running...")

    # This is where your memory consolidation task will go.
    # The decorator @tasks.loop(hours=24) will make it run once a day.
    # @tasks.loop(hours=24)
    # async def memory_consolidation_loop(self):
    #     # Your logic for summarizing memories will go here.
    #     print("Memory consolidation loop is running...")


# This is the mandatory setup function that main.py looks for
async def setup(bot):
    await bot.add_cog(MemoryTasksCog(bot))
