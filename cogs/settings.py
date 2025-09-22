# cogs/settings.py

import discord
from discord.ext import commands
from discord import app_commands

class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="activate", description="Activates the bot in this channel.")
    @app_commands.describe(
        purpose="Optional: A specific purpose for the bot in this channel.",
        random_reply_chance="Optional: Set a random reply chance from 0.0 (0%) to 1.0 (100%)."
    )
    @app_commands.default_permissions(manage_guild=True)
    async def activate_channel(
        self,
        interaction: discord.Interaction,
        purpose: str = None,
        random_reply_chance: app_commands.Range[float, 0.0, 1.0] = None
    ):
        """Slash command to activate the bot."""
        channel_id = str(interaction.channel_id)
        
        final_settings = self.bot.config_manager.add_or_update_channel_setting(
            channel_id, purpose, random_reply_chance
        )
        
        reply_chance_percent = final_settings.get('random_reply_chance', 0.0) * 100
        
        await interaction.response.send_message(
            f"✅ Bot has been **activated** in this channel.\n"
            f"**Purpose:** {final_settings.get('purpose', 'Default')}\n"
            f"**Random Reply Chance:** {reply_chance_percent:.0f}%",
            ephemeral=True
        )

    @app_commands.command(name="setpersonality", description="Sets the personality traits for the bot in this channel.")
    @app_commands.describe(traits="A comma-separated list of traits (e.g., sarcastic, helpful, sleepy).")
    @app_commands.default_permissions(manage_guild=True)
    async def set_personality(self, interaction: discord.Interaction, traits: str):
        """Slash command to set channel-specific personality."""
        channel_id = str(interaction.channel_id)
        
        if self.bot.config_manager.update_channel_personality(channel_id, traits):
            await interaction.response.send_message(
                f"✅ Personality for this channel has been updated.\n**New Traits:** {traits}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "ℹ️ The bot is not active in this channel. Please use `/activate` first.",
                ephemeral=True
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