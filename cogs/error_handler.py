# cogs/error_handler.py

import discord
from discord.ext import commands

class ErrorHandlerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # You can add a @commands.Cog.listener("on_command_error") here later

async def setup(bot):
    await bot.add_cog(ErrorHandlerCog(bot))