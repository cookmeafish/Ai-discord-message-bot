import discord
from discord.ext import commands
from discord import app_commands
import testing

class AdminCog(commands.Cog):
    """
    Real-Time Administration Interface for managing the bot's database.
    All commands require administrator permissions.
    Commands are server-specific - each server has its own isolated database.
    """

    def __init__(self, bot):
        self.bot = bot

    def _get_db(self, interaction):
        """Helper to get server-specific database and validate guild context."""
        if not interaction.guild:
            return None
        return self.bot.get_server_db(interaction.guild.id, interaction.guild.name)

    async def _resolve_user(self, interaction: discord.Interaction, user_input: str):
        """
        Helper to resolve a user from either a user ID or mention.

        Args:
            interaction: Discord interaction object
            user_input: String containing either a user ID or mention

        Returns:
            tuple: (discord.Member or None, error_message or None)
        """
        if not interaction.guild:
            return None, "This command can only be used in a server."

        # Remove mention formatting if present (<@123456789> or <@!123456789>)
        user_id_str = user_input.strip().replace('<@', '').replace('!', '').replace('>', '')

        # Try to convert to integer
        try:
            user_id = int(user_id_str)
        except ValueError:
            return None, f"❌ Invalid user ID or mention: `{user_input}`\nPlease provide a valid user ID (e.g., `123456789`) or mention (e.g., `@username`)."

        # Try to fetch the member from the guild
        try:
            member = await interaction.guild.fetch_member(user_id)
            return member, None
        except discord.NotFound:
            return None, f"❌ User with ID `{user_id}` not found in this server.\nMake sure the user is a member of this server."
        except discord.HTTPException as e:
            return None, f"❌ Error fetching user: {str(e)}"

    # ==================== UTILITY COMMANDS ====================

    @app_commands.command(name="sync", description="Manually sync slash commands with Discord")
    @app_commands.default_permissions(administrator=True)
    async def sync_commands(self, interaction: discord.Interaction):
        """Manually sync slash commands with Discord. Use this after bot updates or when commands don't appear."""
        await interaction.response.defer(ephemeral=True)

        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(
                f"✅ Successfully synced **{len(synced)}** slash command(s) with Discord!\n"
                f"All commands should now be visible. If you still don't see them, try:\n"
                f"• Restarting your Discord client\n"
                f"• Checking bot permissions (requires 'applications.commands' scope)\n"
                f"• Waiting a few minutes for Discord to update",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Failed to sync commands: {str(e)}\n"
                f"This may happen if the bot doesn't have proper permissions.",
                ephemeral=True
            )

    # ==================== BOT IDENTITY COMMANDS ====================

    @app_commands.command(name="identity_add_trait", description="Add a personality trait to the bot")
    @app_commands.describe(trait="The trait to add (e.g., 'sarcastic', 'loves medical terms')")
    @app_commands.default_permissions(administrator=True)
    async def identity_add_trait(self, interaction: discord.Interaction, trait: str):
        """Add a personality trait to the bot's identity."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager.add_bot_identity("trait", trait)
        await interaction.response.send_message(
            f"✅ Added trait: **{trait}**\nThis will take effect immediately in the next interaction.",
            ephemeral=True
        )

    @app_commands.command(name="identity_add_lore", description="Add a lore entry to the bot's background")
    @app_commands.describe(lore="A lore entry about the bot's backstory")
    @app_commands.default_permissions(administrator=True)
    async def identity_add_lore(self, interaction: discord.Interaction, lore: str):
        """Add a lore entry to the bot's identity."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager.add_bot_identity("lore", lore)
        await interaction.response.send_message(
            f"✅ Added lore: **{lore}**\nThis will take effect immediately.",
            ephemeral=True
        )

    @app_commands.command(name="identity_add_fact", description="Add a fact/quirk about the bot")
    @app_commands.describe(fact="A fact or quirk about the bot")
    @app_commands.default_permissions(administrator=True)
    async def identity_add_fact(self, interaction: discord.Interaction, fact: str):
        """Add a fact/quirk to the bot's identity."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager.add_bot_identity("fact", fact)
        await interaction.response.send_message(
            f"✅ Added fact: **{fact}**\nThis will take effect immediately.",
            ephemeral=True
        )

    @app_commands.command(name="identity_view", description="View the bot's current personality from the database")
    @app_commands.default_permissions(administrator=True)
    async def identity_view(self, interaction: discord.Interaction):
        """Display the bot's complete identity from the database."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        traits = db_manager.get_bot_identity("trait")
        lore = db_manager.get_bot_identity("lore")
        facts = db_manager.get_bot_identity("fact")

        embed = discord.Embed(
            title="🐟 Bot Identity",
            description="Current personality stored in the database",
            color=discord.Color.blue()
        )

        if traits:
            traits_text = "\n".join([f"• {t}" for t in traits])
            embed.add_field(name="Core Traits", value=traits_text, inline=False)

        if lore:
            lore_text = "\n".join([f"• {l}" for l in lore])
            embed.add_field(name="Background & Lore", value=lore_text, inline=False)

        if facts:
            facts_text = "\n".join([f"• {f}" for f in facts[:10]])  # Limit to first 10
            if len(facts) > 10:
                facts_text += f"\n... and {len(facts) - 10} more facts"
            embed.add_field(name="Facts & Quirks", value=facts_text, inline=False)

        if not traits and not lore and not facts:
            embed.description = "No identity data found. Use `/identity_add_trait`, `/identity_add_lore`, or `/identity_add_fact` to populate."

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== USER RELATIONSHIP COMMANDS ====================

    @app_commands.command(name="user_view_metrics", description="View relationship metrics for a user")
    @app_commands.describe(user="The user to check metrics for (mention or user ID)")
    @app_commands.default_permissions(administrator=True)
    async def user_view_metrics(self, interaction: discord.Interaction, user: str):
        """View relationship metrics for a specific user."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Resolve user from ID or mention
        member, error = await self._resolve_user(interaction, user)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        metrics = db_manager.get_relationship_metrics(member.id)

        embed = discord.Embed(
            title=f"📊 Relationship Metrics: {member.display_name}",
            color=discord.Color.green()
        )

        # Helper function to format metric with lock indicator
        def format_metric(name, value, max_val=10, show_range=None):
            lock_key = f"{name.lower()}_locked"
            is_locked = metrics.get(lock_key, False)
            lock_icon = " 🔒" if is_locked else ""
            if show_range:
                return f"{value} ({show_range}){lock_icon}"
            return f"{value}/{max_val}{lock_icon}"

        # Core metrics
        embed.add_field(name="Rapport", value=format_metric("rapport", metrics['rapport']), inline=True)
        embed.add_field(name="Trust", value=format_metric("trust", metrics['trust']), inline=True)
        embed.add_field(name="Anger", value=format_metric("anger", metrics['anger']), inline=True)
        embed.add_field(name="Formality", value=format_metric("formality", metrics['formality'], show_range="-5 to +5"), inline=False)

        # New expanded metrics (2025-10-16)
        if 'fear' in metrics:
            embed.add_field(name="Fear", value=format_metric("fear", metrics['fear']), inline=True)
            embed.add_field(name="Respect", value=format_metric("respect", metrics['respect']), inline=True)
            embed.add_field(name="Affection", value=format_metric("affection", metrics['affection']), inline=True)
            embed.add_field(name="Familiarity", value=format_metric("familiarity", metrics['familiarity']), inline=True)
            embed.add_field(name="Intimidation", value=format_metric("intimidation", metrics['intimidation']), inline=True)

        # Add interpretation
        interpretations = []
        if metrics['rapport'] >= 8:
            interpretations.append("🟢 **High Rapport**: Bot is friendly and casual with this user")
        elif metrics['rapport'] <= 3:
            interpretations.append("🔴 **Low Rapport**: Bot is distant and brief")

        if metrics['trust'] >= 7:
            interpretations.append("🟢 **High Trust**: Bot is vulnerable and open")
        elif metrics['trust'] <= 3:
            interpretations.append("🔴 **Low Trust**: Bot is guarded")

        if metrics['anger'] >= 7:
            interpretations.append("🔴 **High Anger**: Bot is defensive and rude")

        if metrics['formality'] >= 3:
            interpretations.append("📝 **Formal**: Bot uses professional language")
        elif metrics['formality'] <= -3:
            interpretations.append("💬 **Casual**: Bot uses slang and informal speech")

        if interpretations:
            embed.add_field(name="Current State", value="\n".join(interpretations), inline=False)

        # Check if any metrics are locked and add footer explanation
        locked_metrics = [k.replace('_locked', '') for k, v in metrics.items() if k.endswith('_locked') and v]
        if locked_metrics:
            embed.set_footer(text="🔒 = Locked (won't change from automatic sentiment analysis)")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="user_set_metrics", description="Manually set relationship metrics for a user")
    @app_commands.describe(
        user="The user to modify (mention or user ID)",
        rapport="Rapport level (0-10)",
        trust="Trust level (0-10)",
        anger="Anger level (0-10)",
        formality="Formality level (-5 to +5)",
        fear="Fear level (0-10)",
        respect="Respect level (0-10)",
        affection="Affection level (0-10)",
        familiarity="Familiarity level (0-10)",
        intimidation="Intimidation level (0-10)"
    )
    @app_commands.default_permissions(administrator=True)
    async def user_set_metrics(
        self,
        interaction: discord.Interaction,
        user: str,
        rapport: app_commands.Range[int, 0, 10] = None,
        trust: app_commands.Range[int, 0, 10] = None,
        anger: app_commands.Range[int, 0, 10] = None,
        formality: app_commands.Range[int, -5, 5] = None,
        fear: app_commands.Range[int, 0, 10] = None,
        respect: app_commands.Range[int, 0, 10] = None,
        affection: app_commands.Range[int, 0, 10] = None,
        familiarity: app_commands.Range[int, 0, 10] = None,
        intimidation: app_commands.Range[int, 0, 10] = None
    ):
        """Manually set relationship metrics for a user."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Resolve user from ID or mention
        member, error = await self._resolve_user(interaction, user)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        updates = {}
        if rapport is not None:
            updates['rapport'] = rapport
        if trust is not None:
            updates['trust'] = trust
        if anger is not None:
            updates['anger'] = anger
        if formality is not None:
            updates['formality'] = formality
        if fear is not None:
            updates['fear'] = fear
        if respect is not None:
            updates['respect'] = respect
        if affection is not None:
            updates['affection'] = affection
        if familiarity is not None:
            updates['familiarity'] = familiarity
        if intimidation is not None:
            updates['intimidation'] = intimidation

        if not updates:
            await interaction.response.send_message(
                "❌ You must specify at least one metric to update.",
                ephemeral=True
            )
            return

        db_manager.update_relationship_metrics(member.id, respect_locks=False, **updates)

        changes_text = "\n".join([f"• **{k.capitalize()}**: {v}" for k, v in updates.items()])

        await interaction.response.send_message(
            f"✅ Updated metrics for **{member.display_name}**:\n{changes_text}\n\nChanges take effect immediately.",
            ephemeral=True
        )

    # ==================== USER MEMORY COMMANDS ====================

    @app_commands.command(name="user_view_memory", description="View stored facts about a user")
    @app_commands.describe(user="The user to view memories for (mention or user ID)")
    @app_commands.default_permissions(administrator=True)
    async def user_view_memory(self, interaction: discord.Interaction, user: str):
        """View all stored long-term memory facts about a user."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Resolve user from ID or mention
        member, error = await self._resolve_user(interaction, user)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        memories = db_manager.get_long_term_memory(member.id)

        if not memories:
            await interaction.response.send_message(
                f"ℹ️ No stored memories found for **{member.display_name}**.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🧠 Stored Memories: {member.display_name}",
            description=f"Total facts: {len(memories)}",
            color=discord.Color.purple()
        )

        # Show first 10 memories
        for i, (fact, source_id, source_name) in enumerate(memories[:10], 1):
            source_info = f" (told by {source_name})" if source_name else ""
            embed.add_field(
                name=f"Memory #{i}",
                value=f"{fact}{source_info}",
                inline=False
            )

        if len(memories) > 10:
            embed.set_footer(text=f"Showing 10 of {len(memories)} memories. Use database tools to view all.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="user_add_memory", description="Manually add a memory fact about a user")
    @app_commands.describe(
        user="The user this fact is about (mention or user ID)",
        fact="The fact to remember"
    )
    @app_commands.default_permissions(administrator=True)
    async def user_add_memory(self, interaction: discord.Interaction, user: str, fact: str):
        """Manually add a long-term memory fact about a user."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Resolve user from ID or mention
        member, error = await self._resolve_user(interaction, user)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        db_manager.add_long_term_memory(
            member.id,
            fact,
            interaction.user.id,
            interaction.user.display_name
        )

        await interaction.response.send_message(
            f"✅ Added memory for **{member.display_name}**: \"{fact}\"",
            ephemeral=True
        )

    # ==================== GLOBAL STATE COMMANDS ====================

    @app_commands.command(name="refresh_nicknames", description="Refresh cached nicknames for all server members")
    @app_commands.default_permissions(administrator=True)
    async def refresh_nicknames(self, interaction: discord.Interaction):
        """Refresh the nicknames table by fetching current member display names."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ Database error.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            from datetime import datetime
            timestamp = datetime.now().isoformat()
            updated_count = 0

            # Get all members in the guild
            for member in interaction.guild.members:
                try:
                    # Log the nickname
                    cursor = db_manager.conn.cursor()
                    cursor.execute(
                        "INSERT INTO nicknames (user_id, nickname, timestamp) VALUES (?, ?, ?)",
                        (member.id, member.display_name, timestamp)
                    )
                    updated_count += 1
                except Exception as e:
                    # Skip if error (probably already exists or other issue)
                    pass

            db_manager.conn.commit()

            await interaction.followup.send(
                f"✅ Refreshed nicknames for **{updated_count}** members in this server.\n"
                f"The GUI User Manager will now display their current usernames.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error refreshing nicknames: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="mood_set", description="Set the bot's global mood state")
    @app_commands.describe(
        mood_type="Type of mood (anger, happiness, energy, etc.)",
        value="Mood value (typically 0-10)"
    )
    @app_commands.default_permissions(administrator=True)
    async def mood_set(self, interaction: discord.Interaction, mood_type: str, value: int):
        """Set a global mood state for the bot."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        state_key = f"daily_mood_{mood_type.lower()}"
        db_manager.set_global_state(state_key, value)

        await interaction.response.send_message(
            f"✅ Set global mood **{mood_type}** to **{value}**",
            ephemeral=True
        )

    @app_commands.command(name="mood_get", description="Get the bot's current global mood state")
    @app_commands.describe(mood_type="Type of mood to check")
    @app_commands.default_permissions(administrator=True)
    async def mood_get(self, interaction: discord.Interaction, mood_type: str):
        """Get a global mood state value."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        state_key = f"daily_mood_{mood_type.lower()}"
        value = db_manager.get_global_state(state_key)

        if value is None:
            await interaction.response.send_message(
                f"ℹ️ No mood state found for **{mood_type}**. Use `/mood_set` to set it.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"📊 Current **{mood_type}** mood: **{value}**",
                ephemeral=True
            )

    # ==================== TESTING COMMANDS ====================

    @app_commands.command(name="run_tests", description="Run comprehensive bot tests and send results via DM")
    @app_commands.default_permissions(administrator=True)
    async def run_tests(self, interaction: discord.Interaction):
        """
        Run comprehensive test suite and send results to admin's DM.
        Tests database operations, AI integration, config, and more.
        """
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Defer response since tests might take a while
        await interaction.response.defer(ephemeral=True)

        try:
            # Run tests
            summary = await testing.run_tests_for_guild(
                self.bot,
                interaction.guild.id,
                interaction.guild.name
            )

            # Format results for Discord
            messages = testing.format_results_for_discord(summary)

            # Send results via DM
            try:
                for message in messages:
                    await interaction.user.send(message)

                # Add log file location info
                log_info = f"\n\nDetailed results saved to: `logs/test_results_*.json`"

                await interaction.followup.send(
                    f"✅ Test suite complete! Results sent to your DM.\n"
                    f"**Summary**: {summary['passed']}/{summary['total']} tests passed ({summary['pass_rate']:.1f}%){log_info}",
                    ephemeral=True
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    "❌ Could not send DM. Please enable DMs from server members.\n"
                    f"**Test Summary**: {summary['passed']}/{summary['total']} tests passed ({summary['pass_rate']:.1f}%)\n"
                    f"Detailed results saved to: `logs/test_results_*.json`",
                    ephemeral=True
                )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error running tests: {e}\n"
                f"Check console logs for details.",
                ephemeral=True
            )

    # ==================== CHANNEL PERSONALITY MODE COMMANDS ====================

    @app_commands.command(name="channel_set_personality", description="Configure personality mode for this channel")
    @app_commands.describe(
        immersive_character="Should bot believe it's the character? (true/false)",
        allow_technical_language="Allow technical terms like 'cached', 'database'? (true/false)"
    )
    @app_commands.default_permissions(administrator=True)
    async def channel_set_personality(
        self,
        interaction: discord.Interaction,
        immersive_character: bool = None,
        allow_technical_language: bool = None
    ):
        """Configure personality mode settings for the current channel."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        channel_id = str(interaction.channel.id)

        # Get current config
        config = self.bot.config_manager.get_config()
        if 'channel_settings' not in config:
            config['channel_settings'] = {}

        if channel_id not in config['channel_settings']:
            config['channel_settings'][channel_id] = {}

        # Update personality mode settings
        updates = []
        if immersive_character is not None:
            config['channel_settings'][channel_id]['immersive_character'] = immersive_character
            updates.append(f"• **Immersive Character**: {immersive_character}")

        if allow_technical_language is not None:
            config['channel_settings'][channel_id]['allow_technical_language'] = allow_technical_language
            updates.append(f"• **Allow Technical Language**: {allow_technical_language}")

        if not updates:
            # Show current settings
            current_immersive = config['channel_settings'][channel_id].get(
                'immersive_character',
                config.get('personality_mode', {}).get('immersive_character', True)
            )
            current_technical = config['channel_settings'][channel_id].get(
                'allow_technical_language',
                config.get('personality_mode', {}).get('allow_technical_language', False)
            )

            await interaction.response.send_message(
                f"📋 **Current Personality Mode Settings for <#{channel_id}>:**\n"
                f"• **Immersive Character**: {current_immersive}\n"
                f"• **Allow Technical Language**: {current_technical}\n\n"
                f"To change settings, provide at least one parameter.",
                ephemeral=True
            )
            return

        # Save config
        self.bot.config_manager.update_config(config)

        changes_text = "\n".join(updates)
        await interaction.response.send_message(
            f"✅ **Updated personality mode for <#{channel_id}>:**\n{changes_text}\n\n"
            f"Changes take effect immediately in the next interaction.",
            ephemeral=True
        )

    # ==================== SERVER SETTINGS COMMANDS ====================

    @app_commands.command(name="server_add_nickname", description="Add an alternative nickname for the bot in this server")
    @app_commands.describe(nickname="Nickname the bot should respond to (e.g., 'BotName', 'Assistant')")
    @app_commands.default_permissions(administrator=True)
    async def server_add_nickname(self, interaction: discord.Interaction, nickname: str):
        """Add an alternative nickname the bot will respond to in this server."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()

        if 'server_alternative_nicknames' not in config:
            config['server_alternative_nicknames'] = {}

        if guild_id not in config['server_alternative_nicknames']:
            config['server_alternative_nicknames'][guild_id] = []

        # Check if nickname already exists
        if nickname.lower() in [n.lower() for n in config['server_alternative_nicknames'][guild_id]]:
            await interaction.response.send_message(
                f"⚠️ Nickname **{nickname}** already exists for this server.",
                ephemeral=True
            )
            return

        config['server_alternative_nicknames'][guild_id].append(nickname)
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Added nickname: **{nickname}**\n"
            f"Bot will now respond when mentioned by this name in this server.",
            ephemeral=True
        )

    @app_commands.command(name="server_remove_nickname", description="Remove an alternative nickname from this server")
    @app_commands.describe(nickname="Nickname to remove")
    @app_commands.default_permissions(administrator=True)
    async def server_remove_nickname(self, interaction: discord.Interaction, nickname: str):
        """Remove an alternative nickname from this server."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()

        if 'server_alternative_nicknames' not in config or guild_id not in config['server_alternative_nicknames']:
            await interaction.response.send_message(
                f"ℹ️ No nicknames configured for this server.",
                ephemeral=True
            )
            return

        # Find matching nickname (case-insensitive)
        nicknames = config['server_alternative_nicknames'][guild_id]
        matching = [n for n in nicknames if n.lower() == nickname.lower()]

        if not matching:
            await interaction.response.send_message(
                f"❌ Nickname **{nickname}** not found.",
                ephemeral=True
            )
            return

        config['server_alternative_nicknames'][guild_id].remove(matching[0])
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Removed nickname: **{matching[0]}**",
            ephemeral=True
        )

    @app_commands.command(name="server_list_nicknames", description="List all alternative nicknames for this server")
    @app_commands.default_permissions(administrator=True)
    async def server_list_nicknames(self, interaction: discord.Interaction):
        """List all alternative nicknames configured for this server."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()

        nicknames = config.get('server_alternative_nicknames', {}).get(guild_id, [])

        if not nicknames:
            await interaction.response.send_message(
                f"ℹ️ No alternative nicknames configured for this server.\n"
                f"Use `/server_add_nickname` to add one.",
                ephemeral=True
            )
            return

        nicknames_text = "\n".join([f"• {n}" for n in nicknames])
        await interaction.response.send_message(
            f"📋 **Alternative Nicknames for {interaction.guild.name}:**\n{nicknames_text}",
            ephemeral=True
        )

    @app_commands.command(name="server_set_status_memory", description="Toggle whether status updates are added to this server's memory")
    @app_commands.describe(enabled="Should status updates be added to short-term memory? (true/false)")
    @app_commands.default_permissions(administrator=True)
    async def server_set_status_memory(self, interaction: discord.Interaction, enabled: bool):
        """Configure whether daily status updates are added to this server's short-term memory."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()

        if 'server_status_settings' not in config:
            config['server_status_settings'] = {}

        if guild_id not in config['server_status_settings']:
            config['server_status_settings'][guild_id] = {}

        config['server_status_settings'][guild_id]['add_to_memory'] = enabled
        self.bot.config_manager.update_config(config)

        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"✅ Status update memory logging **{status}** for this server.\n"
            f"Daily status updates will {'now' if enabled else 'no longer'} be added to short-term memory.",
            ephemeral=True
        )

    # ==================== CHANNEL PROACTIVE ENGAGEMENT COMMANDS ====================

    @app_commands.command(name="channel_set_proactive", description="Configure proactive engagement settings for this channel")
    @app_commands.describe(
        enabled="Allow bot to proactively join conversations? (true/false)",
        check_interval="Minutes between proactive engagement checks (default: 30)",
        threshold="Engagement threshold 0.0-1.0, higher = more selective (default: 0.7)"
    )
    @app_commands.default_permissions(administrator=True)
    async def channel_set_proactive(
        self,
        interaction: discord.Interaction,
        enabled: bool = None,
        check_interval: app_commands.Range[int, 5, 180] = None,
        threshold: app_commands.Range[float, 0.0, 1.0] = None
    ):
        """Configure proactive engagement settings for the current channel."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        channel_id = str(interaction.channel.id)

        # Get current config
        config = self.bot.config_manager.get_config()
        if 'channel_settings' not in config:
            config['channel_settings'] = {}

        if channel_id not in config['channel_settings']:
            config['channel_settings'][channel_id] = {}

        # Update proactive engagement settings
        updates = []
        if enabled is not None:
            config['channel_settings'][channel_id]['allow_proactive_engagement'] = enabled
            updates.append(f"• **Enabled**: {enabled}")

        if check_interval is not None:
            config['channel_settings'][channel_id]['proactive_check_interval'] = check_interval
            updates.append(f"• **Check Interval**: {check_interval} minutes")

        if threshold is not None:
            config['channel_settings'][channel_id]['proactive_threshold'] = threshold
            updates.append(f"• **Engagement Threshold**: {threshold}")

        if not updates:
            # Show current settings
            current_enabled = config['channel_settings'][channel_id].get('allow_proactive_engagement', True)
            current_interval = config['channel_settings'][channel_id].get('proactive_check_interval', 30)
            current_threshold = config['channel_settings'][channel_id].get('proactive_threshold', 0.7)

            await interaction.response.send_message(
                f"📋 **Current Proactive Engagement Settings for <#{channel_id}>:**\n"
                f"• **Enabled**: {current_enabled}\n"
                f"• **Check Interval**: {current_interval} minutes\n"
                f"• **Engagement Threshold**: {current_threshold}\n\n"
                f"To change settings, provide at least one parameter.",
                ephemeral=True
            )
            return

        # Save config
        self.bot.config_manager.update_config(config)

        changes_text = "\n".join(updates)
        await interaction.response.send_message(
            f"✅ **Updated proactive engagement for <#{channel_id}>:**\n{changes_text}\n\n"
            f"Changes take effect immediately.",
            ephemeral=True
        )

    # ==================== CONVERSATION CONTINUATION DETECTION COMMANDS ====================

    @app_commands.command(name="channel_conversation_enable", description="Let bot respond without @mentions in this channel by detecting conversations")
    @app_commands.describe(
        enabled="Allow bot to respond without @mentions when continuing conversation?",
        threshold="Confidence threshold (0.0-1.0, higher = more selective, default: 0.7)",
        context_window="Number of recent messages to analyze (5-20, default: 10)"
    )
    @app_commands.default_permissions(administrator=True)
    async def channel_conversation_enable(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        threshold: app_commands.Range[float, 0.0, 1.0] = 0.7,
        context_window: app_commands.Range[int, 5, 20] = 10
    ):
        """Configure conversation continuation settings for this channel."""
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.followup.send("❌ Failed to access server database.", ephemeral=True)
            return

        channel_id = str(interaction.channel_id)
        channel_setting = db_manager.get_channel_setting(channel_id)

        if not channel_setting:
            await interaction.followup.send(
                "❌ This channel is not activated yet. Please use `/activate` first.",
                ephemeral=True
            )
            return

        # Update settings with provided or default values
        db_manager.add_channel_setting(
            channel_id=channel_id,
            guild_id=str(interaction.guild.id),
            enable_conversation_detection=enabled,
            conversation_detection_threshold=threshold,
            conversation_context_window=context_window
        )

        status = "✅ **Enabled**" if enabled else "❌ **Disabled**"
        await interaction.followup.send(
            f"**Conversation Continuation Updated**\n\n"
            f"**Status:** {status}\n"
            f"**Threshold:** {threshold:.2f} (0.0 = very responsive, 1.0 = very selective)\n"
            f"**Context Window:** {context_window} messages\n\n"
            f"{'✅ Bot will now respond without @mentions when it detects conversations directed at it.' if enabled else '❌ Bot requires @mentions or replies to respond.'}\n\n"
            f"Changes take effect immediately.",
            ephemeral=True
        )

    @app_commands.command(name="channel_conversation_view", description="View conversation continuation settings for this channel")
    @app_commands.default_permissions(administrator=True)
    async def channel_conversation_view(self, interaction: discord.Interaction):
        """View current conversation continuation settings for this channel."""
        # Defer immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.followup.send("❌ Failed to access server database.", ephemeral=True)
            return

        channel_id = str(interaction.channel_id)
        channel_setting = db_manager.get_channel_setting(channel_id)

        if not channel_setting:
            await interaction.followup.send(
                "❌ This channel is not activated yet. Please use `/activate` first.",
                ephemeral=True
            )
            return

        enabled = channel_setting.get('enable_conversation_detection', 0)
        threshold = channel_setting.get('conversation_detection_threshold', 0.7)
        context_window = channel_setting.get('conversation_context_window', 10)

        status = "✅ Enabled" if enabled else "❌ Disabled"
        responsiveness = "Very Responsive (may have false positives)" if threshold < 0.5 else \
                        "Balanced" if threshold < 0.8 else \
                        "Conservative (only responds when very confident)"

        embed = discord.Embed(
            title="⚙️ Conversation Continuation Settings",
            description=f"Settings for {interaction.channel.mention}",
            color=discord.Color.blue()
        )

        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Threshold", value=f"{threshold:.2f} ({responsiveness})", inline=True)
        embed.add_field(name="Context Window", value=f"{context_window} messages", inline=True)

        embed.add_field(
            name="How It Works",
            value=(
                "When enabled, the bot uses AI to detect if messages are directed at it without requiring @mentions.\n\n"
                "**Threshold**: Lower = more responsive (may respond when not intended), Higher = more selective.\n"
                "**Context Window**: How many recent messages to analyze for conversation flow.\n\n"
                "**Note**: Explicit @mentions and replies always trigger responses regardless of this setting."
            ),
            inline=False
        )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ==================== GLOBAL BOT CONFIGURATION COMMANDS ====================

    @app_commands.command(name="config_set_reply_chance", description="Set global random reply chance")
    @app_commands.describe(chance="Random reply chance (0.0-1.0, e.g., 0.05 for 5%)")
    @app_commands.default_permissions(administrator=True)
    async def config_set_reply_chance(self, interaction: discord.Interaction, chance: app_commands.Range[float, 0.0, 1.0]):
        """Set the global random reply chance for the bot."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        config['random_reply_chance'] = chance
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Set global random reply chance to **{chance * 100:.1f}%**\n"
            f"Bot will randomly respond to {int(chance * 100)} out of every 100 non-mentioned messages.",
            ephemeral=True
        )

    @app_commands.command(name="config_set_personality", description="Update default personality traits and lore for new servers")
    @app_commands.describe(
        traits="Personality traits (comma-separated, optional)",
        lore="Background lore (optional)"
    )
    @app_commands.default_permissions(administrator=True)
    async def config_set_personality(self, interaction: discord.Interaction, traits: str = None, lore: str = None):
        """Update the default personality configuration for new servers."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        if not traits and not lore:
            await interaction.response.send_message(
                "❌ You must specify at least one parameter: `traits` or `lore`.",
                ephemeral=True
            )
            return

        config = self.bot.config_manager.get_config()
        if 'default_personality' not in config:
            config['default_personality'] = {}

        updates = []
        if traits is not None:
            config['default_personality']['personality_traits'] = traits
            updates.append(f"• **Traits**: {traits}")

        if lore is not None:
            config['default_personality']['lore'] = lore
            updates.append(f"• **Lore**: {lore}")

        self.bot.config_manager.update_config(config)

        changes_text = "\n".join(updates)
        await interaction.response.send_message(
            f"✅ **Updated default personality for new servers:**\n{changes_text}\n\n"
            f"This affects newly activated servers only. Existing servers keep their personality.",
            ephemeral=True
        )

    @app_commands.command(name="config_add_global_nickname", description="Add a global alternative nickname")
    @app_commands.describe(nickname="Nickname the bot should respond to globally (e.g., 'botname', 'assistant')")
    @app_commands.default_permissions(administrator=True)
    async def config_add_global_nickname(self, interaction: discord.Interaction, nickname: str):
        """Add a global alternative nickname that works on all servers."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()

        if 'alternative_nicknames' not in config:
            config['alternative_nicknames'] = []

        # Check if nickname already exists
        if nickname.lower() in [n.lower() for n in config['alternative_nicknames']]:
            await interaction.response.send_message(
                f"⚠️ Global nickname **{nickname}** already exists.",
                ephemeral=True
            )
            return

        config['alternative_nicknames'].append(nickname)
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Added global nickname: **{nickname}**\n"
            f"Bot will respond to this nickname on ALL servers.",
            ephemeral=True
        )

    @app_commands.command(name="config_remove_global_nickname", description="Remove a global alternative nickname")
    @app_commands.describe(nickname="Nickname to remove")
    @app_commands.default_permissions(administrator=True)
    async def config_remove_global_nickname(self, interaction: discord.Interaction, nickname: str):
        """Remove a global alternative nickname."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()

        if 'alternative_nicknames' not in config or not config['alternative_nicknames']:
            await interaction.response.send_message(
                f"ℹ️ No global nicknames configured.",
                ephemeral=True
            )
            return

        # Find matching nickname (case-insensitive)
        nicknames = config['alternative_nicknames']
        matching = [n for n in nicknames if n.lower() == nickname.lower()]

        if not matching:
            await interaction.response.send_message(
                f"❌ Global nickname **{nickname}** not found.",
                ephemeral=True
            )
            return

        config['alternative_nicknames'].remove(matching[0])
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Removed global nickname: **{matching[0]}**",
            ephemeral=True
        )

    @app_commands.command(name="config_list_global_nicknames", description="List all global alternative nicknames")
    @app_commands.default_permissions(administrator=True)
    async def config_list_global_nicknames(self, interaction: discord.Interaction):
        """List all global alternative nicknames configured."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        nicknames = config.get('alternative_nicknames', [])

        if not nicknames:
            await interaction.response.send_message(
                f"ℹ️ No global alternative nicknames configured.\n"
                f"Use `/config_add_global_nickname` to add one.",
                ephemeral=True
            )
            return

        nicknames_text = "\n".join([f"• {n}" for n in nicknames])
        await interaction.response.send_message(
            f"📋 **Global Alternative Nicknames (work on all servers):**\n{nicknames_text}",
            ephemeral=True
        )

    # ==================== IMAGE GENERATION CONFIGURATION COMMANDS ====================

    @app_commands.command(name="image_config_enable", description="Enable or disable image generation globally")
    @app_commands.describe(enabled="Should image generation be enabled? (true/false)")
    @app_commands.default_permissions(administrator=True)
    async def image_config_enable(self, interaction: discord.Interaction, enabled: bool):
        """Enable or disable AI image generation globally."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        if 'image_generation' not in config:
            config['image_generation'] = {}

        config['image_generation']['enabled'] = enabled
        self.bot.config_manager.update_config(config)

        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"✅ Image generation **{status}** globally.\n"
            f"Users {'can now' if enabled else 'can no longer'} request bot to draw images.",
            ephemeral=True
        )

    @app_commands.command(name="image_config_set_limits", description="Configure rate limiting for image generation")
    @app_commands.describe(
        max_per_period="Maximum images per user per period (e.g., 5)",
        reset_period_hours="Hours before limit resets (e.g., 2)"
    )
    @app_commands.default_permissions(administrator=True)
    async def image_config_set_limits(
        self,
        interaction: discord.Interaction,
        max_per_period: app_commands.Range[int, 1, 100],
        reset_period_hours: app_commands.Range[int, 1, 168]
    ):
        """Configure rate limits for image generation."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        if 'image_generation' not in config:
            config['image_generation'] = {}

        config['image_generation']['max_per_user_per_period'] = max_per_period
        config['image_generation']['reset_period_hours'] = reset_period_hours
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Updated image generation limits:\n"
            f"• **Max per period**: {max_per_period} images\n"
            f"• **Reset period**: {reset_period_hours} hours\n\n"
            f"Each user can generate up to {max_per_period} images every {reset_period_hours} hours.",
            ephemeral=True
        )

    @app_commands.command(name="image_config_view", description="View current image generation settings")
    @app_commands.default_permissions(administrator=True)
    async def image_config_view(self, interaction: discord.Interaction):
        """View current image generation configuration."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        img_config = config.get('image_generation', {})

        enabled = img_config.get('enabled', True)
        max_per_period = img_config.get('max_per_user_per_period', 5)
        reset_period = img_config.get('reset_period_hours', 2)
        model = img_config.get('model', 'black-forest-labs/FLUX.1-schnell')
        style = img_config.get('style_prefix', 'Childlike crayon drawing')

        embed = discord.Embed(
            title="🎨 Image Generation Configuration",
            color=discord.Color.blue()
        )

        status_emoji = "✅" if enabled else "❌"
        embed.add_field(name="Status", value=f"{status_emoji} {'Enabled' if enabled else 'Disabled'}", inline=False)
        embed.add_field(name="Max Per Period", value=f"{max_per_period} images", inline=True)
        embed.add_field(name="Reset Period", value=f"{reset_period} hours", inline=True)
        embed.add_field(name="Model", value=model, inline=False)
        embed.add_field(name="Style", value=style, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="image_reset_limit", description="Reset image generation limit for a user")
    @app_commands.describe(user="The user to reset limits for (mention or user ID)")
    @app_commands.default_permissions(administrator=True)
    async def image_reset_limit(self, interaction: discord.Interaction, user: str):
        """Reset a user's image generation rate limits."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ Database error.", ephemeral=True)
            return

        # Resolve user from ID or mention
        member, error = await self._resolve_user(interaction, user)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        try:
            # Delete the user's image stats to reset their limits
            cursor = db_manager.conn.cursor()
            cursor.execute("DELETE FROM user_image_stats WHERE user_id = ?", (member.id,))
            db_manager.conn.commit()
            cursor.close()

            config = self.bot.config_manager.get_config()
            img_config = config.get('image_generation', {})
            max_per_period = img_config.get('max_per_user_per_period', 5)
            reset_period = img_config.get('reset_period_hours', 2)

            await interaction.response.send_message(
                f"✅ Reset image generation limits for **{member.display_name}**.\n"
                f"They can now generate up to **{max_per_period}** images in the next **{reset_period}** hours.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error resetting image limits: {str(e)}",
                ephemeral=True
            )

    @app_commands.command(name="image_reset_all_limits", description="Reset image generation limits for ALL users in this server")
    @app_commands.default_permissions(administrator=True)
    async def image_reset_all_limits(self, interaction: discord.Interaction):
        """Reset image generation rate limits for all users in the server."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ Database error.", ephemeral=True)
            return

        try:
            # Count how many users will be affected
            cursor = db_manager.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM user_image_stats")
            count_result = cursor.fetchone()
            users_affected = count_result[0] if count_result else 0

            # Delete all user image stats to reset everyone's limits
            cursor.execute("DELETE FROM user_image_stats")
            db_manager.conn.commit()
            cursor.close()

            config = self.bot.config_manager.get_config()
            img_config = config.get('image_generation', {})
            max_per_period = img_config.get('max_per_user_per_period', 5)
            reset_period = img_config.get('reset_period_hours', 2)

            await interaction.response.send_message(
                f"✅ Reset image generation limits for **ALL users** in this server.\n"
                f"**{users_affected}** user(s) affected.\n"
                f"Everyone can now generate up to **{max_per_period}** images in the next **{reset_period}** hours.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error resetting all image limits: {str(e)}",
                ephemeral=True
            )

    # ==================== STATUS UPDATE CONFIGURATION COMMANDS ====================

    @app_commands.command(name="status_config_enable", description="Enable or disable daily status updates")
    @app_commands.describe(enabled="Should daily status updates be enabled? (true/false)")
    @app_commands.default_permissions(administrator=True)
    async def status_config_enable(self, interaction: discord.Interaction, enabled: bool):
        """Enable or disable daily AI-generated status updates."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        if 'status_updates' not in config:
            config['status_updates'] = {}

        config['status_updates']['enabled'] = enabled
        self.bot.config_manager.update_config(config)

        status = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"✅ Daily status updates **{status}** globally.\n"
            f"Bot will {'now' if enabled else 'no longer'} update its Discord status once per day.",
            ephemeral=True
        )

    @app_commands.command(name="status_config_set_time", description="Set the time for daily status updates")
    @app_commands.describe(time="Update time in 24h format (e.g., '14:30' for 2:30 PM)")
    @app_commands.default_permissions(administrator=True)
    async def status_config_set_time(self, interaction: discord.Interaction, time: str):
        """Set the time when daily status updates occur."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Validate time format
        import re
        if not re.match(r'^\d{1,2}:\d{2}$', time):
            await interaction.response.send_message(
                f"❌ Invalid time format. Use 24h format like '14:30' or '09:00'.",
                ephemeral=True
            )
            return

        # Validate time values
        try:
            hours, minutes = map(int, time.split(':'))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                f"❌ Invalid time values. Hours must be 0-23, minutes 0-59.",
                ephemeral=True
            )
            return

        config = self.bot.config_manager.get_config()
        if 'status_updates' not in config:
            config['status_updates'] = {}

        config['status_updates']['update_time'] = time
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Set daily status update time to **{time}** (24h format).\n"
            f"Bot will update its status at this time every day.",
            ephemeral=True
        )

    async def server_name_autocomplete(self, interaction: discord.Interaction, current: str):
        """Autocomplete function for server names."""
        # Get list of all servers the bot is in
        server_names = ["Most Active Server"] + [guild.name for guild in self.bot.guilds]

        # Filter based on what user has typed so far
        if current:
            filtered = [name for name in server_names if current.lower() in name.lower()]
            return [app_commands.Choice(name=name, value=name) for name in filtered[:25]]
        else:
            # Return first 25 servers if no input yet
            return [app_commands.Choice(name=name, value=name) for name in server_names[:25]]

    @app_commands.command(name="status_config_set_source_server", description="Choose which server's personality generates status")
    @app_commands.describe(server_name="Server name (or 'Most Active Server' for automatic selection)")
    @app_commands.autocomplete(server_name=server_name_autocomplete)
    @app_commands.default_permissions(administrator=True)
    async def status_config_set_source_server(self, interaction: discord.Interaction, server_name: str):
        """Set which server's personality should be used for status generation."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        if 'status_updates' not in config:
            config['status_updates'] = {}

        config['status_updates']['source_server_name'] = server_name
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Set status generation source server to: **{server_name}**\n"
            f"Daily status updates will use this server's bot personality and lore.",
            ephemeral=True
        )

    @app_commands.command(name="status_config_view", description="View current status update configuration")
    @app_commands.default_permissions(administrator=True)
    async def status_config_view(self, interaction: discord.Interaction):
        """View current status update configuration."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()
        status_config = config.get('status_updates', {})

        enabled = status_config.get('enabled', False)
        update_time = status_config.get('update_time', '12:00')
        source_server = status_config.get('source_server_name', 'Most Active Server')

        embed = discord.Embed(
            title="📊 Status Update Configuration",
            color=discord.Color.green()
        )

        status_emoji = "✅" if enabled else "❌"
        embed.add_field(name="Status", value=f"{status_emoji} {'Enabled' if enabled else 'Disabled'}", inline=False)
        embed.add_field(name="Update Time", value=update_time, inline=True)
        embed.add_field(name="Source Server", value=source_server, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="status_refresh", description="Immediately refresh the bot's status with a new AI-generated message")
    @app_commands.default_permissions(administrator=True)
    async def status_refresh(self, interaction: discord.Interaction):
        """Manually trigger an immediate status update."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Check if status updates are enabled
        config = self.bot.config_manager.get_config()
        status_config = config.get('status_updates', {})

        if not status_config.get('enabled', False):
            await interaction.response.send_message(
                "⚠️ Status updates are currently disabled.\n"
                "Use `/status_config_enable enabled:true` to enable them first.",
                ephemeral=True
            )
            return

        # Defer response since status generation might take a moment
        await interaction.response.defer(ephemeral=True)

        try:
            # Get the status updater from the bot
            from modules.status_updater import StatusUpdater
            from modules.logging_manager import get_logger
            logger = get_logger()

            logger.info(f"Manual status refresh triggered by {interaction.user.name}")
            status_updater = StatusUpdater(self.bot)

            # Generate and update status
            await status_updater.generate_and_update_status()

            # Get the current status to show in response
            current_status = "Unknown"
            if self.bot.activity:
                # CustomActivity stores text in 'state' attribute, not 'name'
                if hasattr(self.bot.activity, 'state') and self.bot.activity.state:
                    current_status = self.bot.activity.state
                elif hasattr(self.bot.activity, 'name') and self.bot.activity.name:
                    current_status = self.bot.activity.name

            logger.info(f"Status refresh completed. New status: {current_status}")

            await interaction.followup.send(
                f"✅ Status refreshed successfully!\n\n"
                f"**New Status:** {current_status}",
                ephemeral=True
            )

        except Exception as e:
            from modules.logging_manager import get_logger
            logger = get_logger()
            logger.error(f"Error in status_refresh command: {e}", exc_info=True)

            await interaction.followup.send(
                f"❌ Error refreshing status: {str(e)}\n\n"
                f"Please check the bot logs for more details.",
                ephemeral=True
            )

    # ==================== CHANNEL CONFIGURATION COMMANDS ====================

    @app_commands.command(name="channel_set_purpose", description="Set channel purpose/instructions")
    @app_commands.describe(purpose="Instructions for how the bot should behave in this channel")
    @app_commands.default_permissions(administrator=True)
    async def channel_set_purpose(self, interaction: discord.Interaction, purpose: str):
        """Set the purpose/instructions for the current channel."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        channel_id = str(interaction.channel.id)
        config = self.bot.config_manager.get_config()

        if 'channel_settings' not in config:
            config['channel_settings'] = {}

        if channel_id not in config['channel_settings']:
            config['channel_settings'][channel_id] = {}

        config['channel_settings'][channel_id]['purpose'] = purpose
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Set channel purpose for <#{channel_id}>:\n\n**{purpose}**\n\n"
            f"Bot will follow these instructions when responding in this channel.",
            ephemeral=True
        )

    @app_commands.command(name="channel_set_reply_chance", description="Set per-channel random reply chance")
    @app_commands.describe(chance="Random reply chance for this channel (0.0-1.0, e.g., 0.08 for 8%)")
    @app_commands.default_permissions(administrator=True)
    async def channel_set_reply_chance(self, interaction: discord.Interaction, chance: app_commands.Range[float, 0.0, 1.0]):
        """Set the random reply chance for the current channel."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        channel_id = str(interaction.channel.id)
        config = self.bot.config_manager.get_config()

        if 'channel_settings' not in config:
            config['channel_settings'] = {}

        if channel_id not in config['channel_settings']:
            config['channel_settings'][channel_id] = {}

        config['channel_settings'][channel_id]['random_reply_chance'] = chance
        self.bot.config_manager.update_config(config)

        await interaction.response.send_message(
            f"✅ Set random reply chance for <#{channel_id}> to **{chance * 100:.1f}%**\n"
            f"Bot will randomly respond to {int(chance * 100)} out of every 100 non-mentioned messages in this channel.",
            ephemeral=True
        )

    @app_commands.command(name="channel_view_settings", description="View all current channel settings")
    @app_commands.default_permissions(administrator=True)
    async def channel_view_settings(self, interaction: discord.Interaction):
        """View all settings for the current channel."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        channel_id = str(interaction.channel.id)
        config = self.bot.config_manager.get_config()

        channel_config = config.get('channel_settings', {}).get(channel_id, {})
        global_personality = config.get('personality_mode', {})

        if not channel_config:
            await interaction.response.send_message(
                f"ℹ️ No settings configured for <#{channel_id}>. Using global defaults.\n"
                f"Use `/activate` to activate this channel first.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"⚙️ Channel Settings: #{interaction.channel.name}",
            color=discord.Color.blue()
        )

        # Basic settings
        purpose = channel_config.get('purpose', 'Default purpose')
        embed.add_field(name="Purpose", value=purpose[:1024], inline=False)

        reply_chance = channel_config.get('random_reply_chance', config.get('random_reply_chance', 0.05))
        embed.add_field(name="Random Reply Chance", value=f"{reply_chance * 100:.1f}%", inline=True)

        # Personality mode
        immersive = channel_config.get('immersive_character', global_personality.get('immersive_character', True))
        tech_lang = channel_config.get('allow_technical_language', global_personality.get('allow_technical_language', False))
        use_server_info = channel_config.get('use_server_info', False)
        roleplay_fmt = channel_config.get('enable_roleplay_formatting', global_personality.get('enable_roleplay_formatting', True))

        embed.add_field(name="Immersive Character", value="✅ Yes" if immersive else "❌ No", inline=True)
        embed.add_field(name="Technical Language", value="✅ Allowed" if tech_lang else "❌ Forbidden", inline=True)
        embed.add_field(name="Use Server Info", value="✅ Yes" if use_server_info else "❌ No", inline=True)
        embed.add_field(name="Roleplay Formatting", value="✅ Yes" if roleplay_fmt else "❌ No", inline=True)

        # Proactive engagement
        proactive_enabled = channel_config.get('allow_proactive_engagement', True)
        proactive_interval = channel_config.get('proactive_check_interval', 30)
        proactive_threshold = channel_config.get('proactive_threshold', 0.7)

        embed.add_field(name="Proactive Engagement", value="✅ Enabled" if proactive_enabled else "❌ Disabled", inline=True)
        embed.add_field(name="Check Interval", value=f"{proactive_interval} min", inline=True)
        embed.add_field(name="Threshold", value=f"{proactive_threshold:.2f}", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== SERVER EMOTE MANAGEMENT COMMANDS ====================

    @app_commands.command(
        name="server_set_emote_sources",
        description="Control which servers' emotes the bot can use in responses"
    )
    @app_commands.describe(
        action="What to do: list current sources, add/remove a server, or clear all restrictions",
        guild_id="Server ID to add or remove (use /server_view_emote_sources to see available IDs)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="📋 List - View current emote sources", value="list"),
        app_commands.Choice(name="➕ Add - Allow emotes from a server", value="add"),
        app_commands.Choice(name="➖ Remove - Block emotes from a server", value="remove"),
        app_commands.Choice(name="🗑️ Clear - Remove all restrictions (use all emotes)", value="clear"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def server_set_emote_sources(
        self,
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        guild_id: str = None
    ):
        """Manage which servers' emotes can be used in this server."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        current_guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()

        if 'server_emote_sources' not in config:
            config['server_emote_sources'] = {}

        action_value = action.value  # Extract value from Choice

        if action_value == "list":
            # List available servers and current sources
            current_sources = config['server_emote_sources'].get(current_guild_id, [])
            all_servers = []

            # Get all available servers from bot
            for guild in self.bot.guilds:
                all_servers.append((str(guild.id), guild.name))

            embed = discord.Embed(
                title="🎭 Emote Source Configuration",
                description=f"Server: {interaction.guild.name}",
                color=discord.Color.blue()
            )

            if not current_sources:
                embed.add_field(name="Current Status", value="✅ All emotes from all servers are available (no restrictions)", inline=False)
            else:
                sources_text = "\n".join([f"• {gid}" for gid in current_sources])
                embed.add_field(name="Allowed Servers", value=sources_text, inline=False)

            available_text = "\n".join([f"• `{gid}` - {name}" for gid, name in all_servers[:10]])
            if len(all_servers) > 10:
                available_text += f"\n... and {len(all_servers) - 10} more"
            embed.add_field(name="Available Servers", value=available_text, inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif action_value == "add":
            if not guild_id:
                await interaction.response.send_message(
                    "❌ You must specify a `guild_id` to add.",
                    ephemeral=True
                )
                return

            if current_guild_id not in config['server_emote_sources']:
                config['server_emote_sources'][current_guild_id] = []

            if guild_id in config['server_emote_sources'][current_guild_id]:
                await interaction.response.send_message(
                    f"⚠️ Guild ID `{guild_id}` is already in the allowed list.",
                    ephemeral=True
                )
                return

            config['server_emote_sources'][current_guild_id].append(guild_id)
            self.bot.config_manager.update_config(config)

            await interaction.response.send_message(
                f"✅ Added emote source: `{guild_id}`\n"
                f"Emotes from this server are now available in {interaction.guild.name}.",
                ephemeral=True
            )

        elif action_value == "remove":
            if not guild_id:
                await interaction.response.send_message(
                    "❌ You must specify a `guild_id` to remove.",
                    ephemeral=True
                )
                return

            if current_guild_id not in config['server_emote_sources'] or guild_id not in config['server_emote_sources'][current_guild_id]:
                await interaction.response.send_message(
                    f"❌ Guild ID `{guild_id}` is not in the allowed list.",
                    ephemeral=True
                )
                return

            config['server_emote_sources'][current_guild_id].remove(guild_id)
            self.bot.config_manager.update_config(config)

            await interaction.response.send_message(
                f"✅ Removed emote source: `{guild_id}`\n"
                f"Emotes from this server are no longer available in {interaction.guild.name}.",
                ephemeral=True
            )

        elif action_value == "clear":
            if current_guild_id in config['server_emote_sources']:
                del config['server_emote_sources'][current_guild_id]
                self.bot.config_manager.update_config(config)

            await interaction.response.send_message(
                f"✅ Cleared all emote restrictions for {interaction.guild.name}.\n"
                f"All emotes from all servers are now available.",
                ephemeral=True
            )

    @app_commands.command(
        name="server_view_emote_sources",
        description="View which servers' emotes the bot can use and available server IDs"
    )
    @app_commands.default_permissions(administrator=True)
    async def server_view_emote_sources(self, interaction: discord.Interaction):
        """View current emote source configuration and available servers."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        current_guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()
        current_sources = config.get('server_emote_sources', {}).get(current_guild_id, [])

        embed = discord.Embed(
            title="🎭 Emote Source Configuration",
            description=f"**Server:** {interaction.guild.name}",
            color=discord.Color.blue()
        )

        # Current status
        if not current_sources:
            embed.add_field(
                name="📊 Current Status",
                value="✅ **No restrictions** - Using emotes from ALL servers the bot is in",
                inline=False
            )
        else:
            # Resolve server names and check validity
            sources_list = []
            invalid_sources = []
            for source_id in current_sources:
                try:
                    guild = self.bot.get_guild(int(source_id))
                except (ValueError, TypeError):
                    guild = None

                if guild:
                    emote_count = len([e for e in guild.emojis if e.available])
                    sources_list.append(f"✅ `{source_id}` - {guild.name} ({emote_count} emotes)")
                else:
                    sources_list.append(f"⚠️ `{source_id}` - Bot not in this server")
                    invalid_sources.append(source_id)

            sources_text = "\n".join(sources_list)
            if invalid_sources:
                sources_text += f"\n\n💡 *{len(invalid_sources)} server(s) are inaccessible - use Clear action to reset*"

            embed.add_field(
                name="📊 Allowed Emote Sources",
                value=sources_text,
                inline=False
            )

        # Available servers
        available_servers = []
        for guild in self.bot.guilds:
            emote_count = len([e for e in guild.emojis if e.available])
            available_servers.append(f"• `{guild.id}` - {guild.name} ({emote_count} emotes)")

        if available_servers:
            # Split into chunks if too many servers
            servers_text = "\n".join(available_servers[:15])
            if len(available_servers) > 15:
                servers_text += f"\n... and {len(available_servers) - 15} more servers"
            embed.add_field(
                name="🌐 Available Servers (copy ID to add)",
                value=servers_text,
                inline=False
            )

        # Current emote count
        emote_count = self.bot.emote_handler.get_emote_count(guild_id=interaction.guild.id)
        embed.add_field(
            name="🎨 Emotes Available",
            value=f"**{emote_count}** emotes currently usable by the bot",
            inline=False
        )

        embed.set_footer(text="Use /server_set_emote_sources to modify settings")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== VIEW/DISCOVERY COMMANDS ====================

    @app_commands.command(name="config_view_all", description="View all global configuration settings")
    @app_commands.default_permissions(administrator=True)
    async def config_view_all(self, interaction: discord.Interaction):
        """View all global bot configuration settings."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        config = self.bot.config_manager.get_config()

        embed = discord.Embed(
            title="⚙️ Global Bot Configuration",
            color=discord.Color.blue()
        )

        # Basic settings
        reply_chance = config.get('random_reply_chance', 0.05)
        embed.add_field(name="Random Reply Chance", value=f"{reply_chance * 100:.1f}%", inline=True)

        # Default personality
        default_personality = config.get('default_personality', {})
        traits = default_personality.get('personality_traits', 'N/A')
        lore = default_personality.get('lore', 'N/A')
        embed.add_field(name="Default Traits", value=traits[:100], inline=False)
        embed.add_field(name="Default Lore", value=lore[:100], inline=False)

        # Global nicknames
        global_nicknames = config.get('alternative_nicknames', [])
        nicknames_text = ", ".join(global_nicknames) if global_nicknames else "None"
        embed.add_field(name="Global Nicknames", value=nicknames_text[:100], inline=False)

        # Image generation
        img_config = config.get('image_generation', {})
        img_enabled = "✅ Enabled" if img_config.get('enabled', True) else "❌ Disabled"
        img_limits = f"{img_config.get('max_per_user_per_period', 5)}/{img_config.get('reset_period_hours', 2)}h"
        embed.add_field(name="Image Generation", value=img_enabled, inline=True)
        embed.add_field(name="Image Limits", value=img_limits, inline=True)

        # Status updates
        status_config = config.get('status_updates', {})
        status_enabled = "✅ Enabled" if status_config.get('enabled', False) else "❌ Disabled"
        status_time = status_config.get('update_time', '12:00')
        embed.add_field(name="Status Updates", value=status_enabled, inline=True)
        embed.add_field(name="Status Time", value=status_time, inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="server_view_settings", description="View all server-specific settings")
    @app_commands.default_permissions(administrator=True)
    async def server_view_settings(self, interaction: discord.Interaction):
        """View all settings specific to this server."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()

        embed = discord.Embed(
            title=f"🏠 Server Settings: {interaction.guild.name}",
            color=discord.Color.green()
        )

        # Alternative nicknames
        server_nicknames = config.get('server_alternative_nicknames', {}).get(guild_id, [])
        nicknames_text = ", ".join(server_nicknames) if server_nicknames else "None"
        embed.add_field(name="Alternative Nicknames", value=nicknames_text[:1024], inline=False)

        # Emote sources
        emote_sources = config.get('server_emote_sources', {}).get(guild_id, [])
        if not emote_sources:
            emotes_text = "All servers (no restrictions)"
        else:
            emotes_text = f"{len(emote_sources)} server(s) allowed"
        embed.add_field(name="Emote Sources", value=emotes_text, inline=True)

        # Status memory
        status_settings = config.get('server_status_settings', {}).get(guild_id, {})
        status_memory = status_settings.get('add_to_memory', True)
        embed.add_field(name="Status Memory", value="✅ Enabled" if status_memory else "❌ Disabled", inline=True)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== MEMORY CONSOLIDATION COMMANDS ====================

    @app_commands.command(name="consolidate_memory", description="Manually trigger memory consolidation for this server")
    @app_commands.default_permissions(administrator=True)
    async def consolidate_memory(self, interaction: discord.Interaction):
        """Manually trigger memory consolidation (extract facts from short-term messages)."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            memory_cog = self.bot.get_cog('MemoryTasksCog')
            if not memory_cog:
                await interaction.followup.send(
                    "❌ Memory consolidation system not available. MemoryTasksCog not loaded.",
                    ephemeral=True
                )
                return

            cursor = db_manager.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM short_term_message_log")
            message_count = cursor.fetchone()[0]

            if message_count == 0:
                await interaction.followup.send(
                    "ℹ️ No messages to consolidate. Short-term memory is empty.",
                    ephemeral=True
                )
                return

            result = await memory_cog.consolidate_memories(interaction.guild.id, db_manager)

            facts_extracted = result.get('memories_added', 0) if result else 0
            users_processed = result.get('users_processed', 0) if result else 0

            await interaction.followup.send(
                f"✅ **Memory consolidation complete!**\n\n"
                f"• **Messages processed**: {message_count}\n"
                f"• **Users analyzed**: {users_processed}\n"
                f"• **Facts extracted**: {facts_extracted}\n"
                f"• **Archive created**: `database/{interaction.guild.name}/archive/short_term_archive_*.json`\n\n"
                f"Short-term memory has been cleared and facts saved to long-term memory.",
                ephemeral=True
            )

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(
                f"❌ Error during memory consolidation: {e}\n"
                f"Check console logs for details.",
                ephemeral=True
            )


    # ==================== LOGGING COMMANDS ====================

    @app_commands.command(name="get_logs", description="Retrieve bot log files (sent via DM)")
    @app_commands.describe(
        lines="Number of recent lines to retrieve (default: 100)",
        date="Log file date in YYYYMMDD format (default: today)"
    )
    @app_commands.default_permissions(administrator=True)
    async def get_logs(self, interaction: discord.Interaction, lines: int = 100, date: str = None):
        """
        Retrieve bot log files and send them via DM.

        Args:
            interaction: Discord interaction object
            lines: Number of recent lines to retrieve (default: 100, max: 2000)
            date: Log file date in YYYYMMDD format (default: today)
        """
        await interaction.response.defer(ephemeral=True)

        try:
            # Validate lines parameter
            if lines < 1:
                await interaction.followup.send("❌ Number of lines must be at least 1.", ephemeral=True)
                return
            if lines > 2000:
                await interaction.followup.send("❌ Maximum 2000 lines allowed. Use date parameter to access older logs.", ephemeral=True)
                return

            # Determine log file date
            if date is None:
                # Use today's date
                from datetime import datetime
                date_str = datetime.now().strftime("%Y%m%d")
            else:
                # Validate date format
                try:
                    from datetime import datetime
                    datetime.strptime(date, "%Y%m%d")
                    date_str = date
                except ValueError:
                    await interaction.followup.send(
                        f"❌ Invalid date format: `{date}`\nPlease use YYYYMMDD format (e.g., 20251027).",
                        ephemeral=True
                    )
                    return

            # Construct log file path
            log_file_path = f"/root/Ai-discord-message-bot/logs/bot_{date_str}.log"

            # Check if log file exists
            import os
            if not os.path.exists(log_file_path):
                await interaction.followup.send(
                    f"❌ Log file not found: `bot_{date_str}.log`\n"
                    f"Available log files:\n" +
                    "\n".join([f"• {f}" for f in os.listdir("/root/Ai-discord-message-bot/logs") if f.endswith(".log")][:10]),
                    ephemeral=True
                )
                return

            # Read the log file (last N lines)
            with open(log_file_path, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                selected_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines

            log_content = ''.join(selected_lines)

            # Send log content
            # If content is small enough, send as message. Otherwise, send as file
            if len(log_content) <= 1900:  # Leave room for formatting
                await interaction.user.send(
                    f"**Log file: `bot_{date_str}.log`** (last {len(selected_lines)} lines)\n```\n{log_content}\n```"
                )
                await interaction.followup.send(
                    f"✅ Sent **{len(selected_lines)} lines** from `bot_{date_str}.log` via DM.",
                    ephemeral=True
                )
            else:
                # Send as file attachment
                import io
                log_file = discord.File(
                    io.BytesIO(log_content.encode('utf-8')),
                    filename=f"bot_{date_str}_last_{len(selected_lines)}_lines.log"
                )
                await interaction.user.send(
                    f"**Log file: `bot_{date_str}.log`** (last {len(selected_lines)} lines)",
                    file=log_file
                )
                await interaction.followup.send(
                    f"✅ Sent **{len(selected_lines)} lines** from `bot_{date_str}.log` via DM as file attachment.",
                    ephemeral=True
                )

        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Cannot send DM. Please enable DMs from server members in your privacy settings.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Error retrieving logs: {str(e)}\nCheck console for details.",
                ephemeral=True
            )
            print(f"Error in get_logs command: {e}")

    # ==================== USER METRIC LOCKING COMMANDS ====================

    @app_commands.command(name="user_lock_metrics", description="Lock specific relationship metrics to prevent auto-updates")
    @app_commands.describe(
        user="The user whose metrics to lock (mention or user ID)",
        rapport="Lock rapport metric",
        trust="Lock trust metric",
        anger="Lock anger metric",
        formality="Lock formality metric",
        fear="Lock fear metric",
        respect="Lock respect metric",
        affection="Lock affection metric",
        familiarity="Lock familiarity metric",
        intimidation="Lock intimidation metric"
    )
    @app_commands.default_permissions(administrator=True)
    async def user_lock_metrics(
        self,
        interaction: discord.Interaction,
        user: str,
        rapport: bool = False,
        trust: bool = False,
        anger: bool = False,
        formality: bool = False,
        fear: bool = False,
        respect: bool = False,
        affection: bool = False,
        familiarity: bool = False,
        intimidation: bool = False
    ):
        """Lock specific metrics to prevent automatic sentiment-based updates."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Resolve user
        member, error = await self._resolve_user(interaction, user)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        # Build lock updates
        lock_updates = {}
        if rapport:
            lock_updates['rapport_locked'] = 1
        if trust:
            lock_updates['trust_locked'] = 1
        if anger:
            lock_updates['anger_locked'] = 1
        if formality:
            lock_updates['formality_locked'] = 1
        if fear:
            lock_updates['fear_locked'] = 1
        if respect:
            lock_updates['respect_locked'] = 1
        if affection:
            lock_updates['affection_locked'] = 1
        if familiarity:
            lock_updates['familiarity_locked'] = 1
        if intimidation:
            lock_updates['intimidation_locked'] = 1

        if not lock_updates:
            await interaction.response.send_message(
                "❌ No metrics specified to lock. Use the command parameters to select metrics.",
                ephemeral=True
            )
            return

        # Update locks in database
        for lock_field, value in lock_updates.items():
            db_manager.cursor.execute(f'''
                UPDATE relationship_metrics
                SET {lock_field} = ?
                WHERE user_id = ?
            ''', (value, member.id))
        db_manager.conn.commit()

        locked_names = [name.replace('_locked', '') for name in lock_updates.keys()]
        await interaction.response.send_message(
            f"✅ Locked metrics for **{member.display_name}**: {', '.join(locked_names)}\n"
            f"These metrics will no longer update automatically from sentiment analysis.",
            ephemeral=True
        )

    @app_commands.command(name="user_unlock_metrics", description="Unlock specific relationship metrics to allow auto-updates")
    @app_commands.describe(
        user="The user whose metrics to unlock (mention or user ID)",
        rapport="Unlock rapport metric",
        trust="Unlock trust metric",
        anger="Unlock anger metric",
        formality="Unlock formality metric",
        fear="Unlock fear metric",
        respect="Unlock respect metric",
        affection="Unlock affection metric",
        familiarity="Unlock familiarity metric",
        intimidation="Unlock intimidation metric"
    )
    @app_commands.default_permissions(administrator=True)
    async def user_unlock_metrics(
        self,
        interaction: discord.Interaction,
        user: str,
        rapport: bool = False,
        trust: bool = False,
        anger: bool = False,
        formality: bool = False,
        fear: bool = False,
        respect: bool = False,
        affection: bool = False,
        familiarity: bool = False,
        intimidation: bool = False
    ):
        """Unlock specific metrics to allow automatic sentiment-based updates."""
        db_manager = self._get_db(interaction)
        if not db_manager:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        # Resolve user
        member, error = await self._resolve_user(interaction, user)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return

        # Build unlock updates
        unlock_updates = {}
        if rapport:
            unlock_updates['rapport_locked'] = 0
        if trust:
            unlock_updates['trust_locked'] = 0
        if anger:
            unlock_updates['anger_locked'] = 0
        if formality:
            unlock_updates['formality_locked'] = 0
        if fear:
            unlock_updates['fear_locked'] = 0
        if respect:
            unlock_updates['respect_locked'] = 0
        if affection:
            unlock_updates['affection_locked'] = 0
        if familiarity:
            unlock_updates['familiarity_locked'] = 0
        if intimidation:
            unlock_updates['intimidation_locked'] = 0

        if not unlock_updates:
            await interaction.response.send_message(
                "❌ No metrics specified to unlock. Use the command parameters to select metrics.",
                ephemeral=True
            )
            return

        # Update locks in database
        for lock_field, value in unlock_updates.items():
            db_manager.cursor.execute(f'''
                UPDATE relationship_metrics
                SET {lock_field} = ?
                WHERE user_id = ?
            ''', (value, member.id))
        db_manager.conn.commit()

        unlocked_names = [name.replace('_locked', '') for name in unlock_updates.keys()]
        await interaction.response.send_message(
            f"✅ Unlocked metrics for **{member.display_name}**: {', '.join(unlocked_names)}\n"
            f"These metrics will now update automatically from sentiment analysis.",
            ephemeral=True
        )


async def setup(bot):
    """Required setup function to load the cog."""
    await bot.add_cog(AdminCog(bot))
