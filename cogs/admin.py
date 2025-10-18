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

        # Core metrics
        embed.add_field(name="Rapport", value=f"{metrics['rapport']}/10", inline=True)
        embed.add_field(name="Trust", value=f"{metrics['trust']}/10", inline=True)
        embed.add_field(name="Anger", value=f"{metrics['anger']}/10", inline=True)
        embed.add_field(name="Formality", value=f"{metrics['formality']} (range: -5 to +5)", inline=False)

        # New expanded metrics (2025-10-16)
        if 'fear' in metrics:
            embed.add_field(name="Fear", value=f"{metrics['fear']}/10", inline=True)
            embed.add_field(name="Respect", value=f"{metrics['respect']}/10", inline=True)
            embed.add_field(name="Affection", value=f"{metrics['affection']}/10", inline=True)
            embed.add_field(name="Familiarity", value=f"{metrics['familiarity']}/10", inline=True)
            embed.add_field(name="Intimidation", value=f"{metrics['intimidation']}/10", inline=True)

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
                if hasattr(self.bot.activity, 'name') and self.bot.activity.name:
                    current_status = self.bot.activity.name
                elif hasattr(self.bot.activity, 'state') and self.bot.activity.state:
                    current_status = self.bot.activity.state

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

    @app_commands.command(name="channel_list_active", description="List all active channels in this server")
    @app_commands.default_permissions(administrator=True)
    async def channel_list_active(self, interaction: discord.Interaction):
        """List all channels activated in this server."""
        if not interaction.guild:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        config = self.bot.config_manager.get_config()
        channel_settings = config.get('channel_settings', {})

        # Filter channels by guild_id
        server_channels = []
        for channel_id, channel_config in channel_settings.items():
            channel_guild_id = channel_config.get('guild_id', None)
            if channel_guild_id == guild_id or channel_guild_id is None:
                server_channels.append((channel_id, channel_config))

        if not server_channels:
            await interaction.response.send_message(
                f"ℹ️ No channels activated in this server yet.\n"
                f"Use `/activate` in a channel to activate it.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"📋 Active Channels in {interaction.guild.name}",
            description=f"Total: {len(server_channels)} channels",
            color=discord.Color.green()
        )

        for channel_id, channel_config in server_channels[:15]:  # Limit to 15 to avoid embed limits
            channel_name = channel_config.get('channel_name', f'Channel {channel_id}')
            purpose = channel_config.get('purpose', 'Default purpose')[:50]

            embed.add_field(
                name=f"#{channel_name}",
                value=f"ID: {channel_id}\n{purpose}...",
                inline=False
            )

        if len(server_channels) > 15:
            embed.set_footer(text=f"Showing 15 of {len(server_channels)} channels")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== SERVER EMOTE MANAGEMENT COMMANDS ====================

    @app_commands.command(name="server_set_emote_sources", description="Configure which servers' emotes are available")
    @app_commands.describe(
        action="Action to perform: list, add, remove, or clear",
        guild_id="Guild ID to add or remove (optional, required for add/remove)"
    )
    @app_commands.default_permissions(administrator=True)
    async def server_set_emote_sources(
        self,
        interaction: discord.Interaction,
        action: str,
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

        action = action.lower()

        if action == "list":
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

        elif action == "add":
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

        elif action == "remove":
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

        elif action == "clear":
            if current_guild_id in config['server_emote_sources']:
                del config['server_emote_sources'][current_guild_id]
                self.bot.config_manager.update_config(config)

            await interaction.response.send_message(
                f"✅ Cleared all emote restrictions for {interaction.guild.name}.\n"
                f"All emotes from all servers are now available.",
                ephemeral=True
            )

        else:
            await interaction.response.send_message(
                f"❌ Invalid action. Must be one of: `list`, `add`, `remove`, `clear`",
                ephemeral=True
            )

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

        # Defer response as this might take a while
        await interaction.response.defer(ephemeral=True)

        try:
            # Import consolidation handler
            from modules.memory_consolidation_handler import consolidate_memory

            # Count messages before consolidation
            cursor = db_manager.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM short_term_message_log")
            message_count = cursor.fetchone()[0]

            if message_count == 0:
                await interaction.followup.send(
                    "ℹ️ No messages to consolidate. Short-term memory is empty.",
                    ephemeral=True
                )
                return

            # Perform consolidation
            facts_extracted = await consolidate_memory(db_manager, interaction.guild.name)

            await interaction.followup.send(
                f"✅ **Memory consolidation complete!**\n\n"
                f"• **Messages processed**: {message_count}\n"
                f"• **Facts extracted**: {facts_extracted}\n"
                f"• **Archive created**: `database/{interaction.guild.name}/archive/short_term_archive_*.json`\n\n"
                f"Short-term memory has been cleared and facts saved to long-term memory.",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ Error during memory consolidation: {e}\n"
                f"Check console logs for details.",
                ephemeral=True
            )


async def setup(bot):
    """Required setup function to load the cog."""
    await bot.add_cog(AdminCog(bot))
