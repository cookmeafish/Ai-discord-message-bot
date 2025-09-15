# cogs/settings.py

import discord
from discord.ext import commands
from discord import app_commands

class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="activate", description="Activates the bot in this channel with a specific purpose.")
    @app_commands.describe(purpose="The specific purpose or instructions for the bot in this channel.")
    @app_commands.default_permissions(manage_guild=True) # Only admins can use this
    async def activate_channel(self, interaction: discord.Interaction, purpose: str):
        """Slash command to activate the bot."""
        channel_id = str(interaction.channel_id)
        
        # Use the config manager to save the setting
        self.bot.config_manager.add_or_update_channel_setting(channel_id, purpose)
        
        await interaction.response.send_message(
            f"✅ Bot has been **activated** in this channel.\n**Purpose:** {purpose}",
            ephemeral=True # This message is only visible to the user who ran the command
        )

    @app_commands.command(name="deactivate", description="Deactivates the bot in this channel.")
    @app_commands.default_permissions(manage_guild=True)
    async def deactivate_channel(self, interaction: discord.Interaction):
        """Slash command to deactivate the bot."""
        channel_id = str(interaction.channel_id)
        
        if self.bot.config_manager.remove_channel_setting(channel_id):
            await interaction.response.send_message(
                "🔴 Bot has been **deactivated** in this channel.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "ℹ️ The bot is not currently active in this channel.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(SettingsCog(bot))