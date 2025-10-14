# cogs/utility.py

import discord
from discord.ext import commands
from discord import app_commands

class UtilityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # You can add commands here later
    @commands.command(name='ping')
    async def ping(self, ctx):
        await ctx.send(f'Pong! {round(self.bot.latency * 1000)}ms')

    @app_commands.command(name="reload_emotes", description="Reloads all custom emotes from all servers")
    @app_commands.default_permissions(manage_guild=True)
    async def reload_emotes(self, interaction: discord.Interaction):
        """Manually reload all emotes from all servers the bot is in."""
        await interaction.response.defer(ephemeral=True)

        # Reload emotes
        self.bot.emote_handler.load_emotes()

        # Get list of available emotes
        emote_list = self.bot.emote_handler.get_available_emote_names()
        emote_count = len(self.bot.emote_handler.emotes)

        await interaction.followup.send(
            f"✅ Reloaded {emote_count} custom emotes!\n\n"
            f"**Available emotes:** {emote_list}",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))