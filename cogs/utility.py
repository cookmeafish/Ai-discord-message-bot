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
        try:
            await interaction.response.defer(ephemeral=True)

            # Reload emotes
            self.bot.emote_handler.load_emotes()

            # Get emote count and list
            emote_count = len(self.bot.emote_handler.emotes)
            emote_names = list(self.bot.emote_handler.emotes.keys())

            # Truncate list if too long for Discord message
            if len(emote_names) > 50:
                emote_display = ", ".join(f":{name}:" for name in emote_names[:50])
                emote_display += f"\n... and {len(emote_names) - 50} more"
            else:
                emote_display = ", ".join(f":{name}:" for name in emote_names) if emote_names else "None"

            await interaction.followup.send(
                f"✅ Reloaded **{emote_count}** custom emotes!\n\n"
                f"**Available emotes:** {emote_display}",
                ephemeral=True
            )
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ Error reloading emotes: {e}", ephemeral=True)
            except:
                print(f"Error in reload_emotes command: {e}")

async def setup(bot):
    await bot.add_cog(UtilityCog(bot))