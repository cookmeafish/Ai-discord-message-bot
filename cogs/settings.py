# cogs/settings.py

import discord
from discord.ext import commands
from discord import app_commands

class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="activate", description="Activates the bot in a channel.")
    @app_commands.describe(
        channel="Optional: Specify a channel to activate (defaults to current channel).",
        purpose="Optional: A specific purpose for the bot in this channel.",
        random_reply_chance="Optional: Set a random reply chance from 0.0 (0%) to 1.0 (100%)."
    )
    @app_commands.default_permissions(manage_guild=True)
    async def activate_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel = None,
        purpose: str = None,
        random_reply_chance: app_commands.Range[float, 0.0, 1.0] = None
    ):
        """Slash command to activate the bot and create server database if needed."""
        # Use specified channel or default to current channel
        target_channel = channel if channel else interaction.channel
        channel_id = str(target_channel.id)
        guild = interaction.guild

        # Create or get server-specific database
        if not guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager = self.bot.get_server_db(guild.id, guild.name)

        # Auto-populate bot identity if this is a new database
        from main import _populate_bot_identity_if_empty
        from modules.logging_manager import get_logger
        logger = get_logger()
        _populate_bot_identity_if_empty(db_manager, logger)

        # Add channel to database
        final_settings = db_manager.add_channel_setting(
            channel_id=channel_id,
            guild_id=str(guild.id),
            channel_name=target_channel.name,
            purpose=purpose,
            random_reply_chance=random_reply_chance
        )

        if not final_settings:
            await interaction.response.send_message("❌ Failed to activate channel.", ephemeral=True)
            return

        reply_chance_percent = final_settings.get('random_reply_chance', 0.0) * 100

        await interaction.response.send_message(
            f"✅ Bot has been **activated** in {target_channel.mention}.\n"
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

    @app_commands.command(name="deactivate", description="Deactivates the bot in a channel.")
    @app_commands.describe(
        channel="Optional: Specify a channel to deactivate (defaults to current channel)."
    )
    @app_commands.default_permissions(manage_guild=True)
    async def deactivate_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Slash command to deactivate the bot."""
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Use specified channel or default to current channel
        target_channel = channel if channel else interaction.channel
        channel_id = str(target_channel.id)

        # Get server-specific database
        db_manager = self.bot.get_server_db(guild.id, guild.name)

        if db_manager.remove_channel_setting(channel_id):
            await interaction.response.send_message(
                f"🔴 Bot has been **deactivated** in {target_channel.mention}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"ℹ️ The bot is not currently active in {target_channel.mention}.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(SettingsCog(bot))