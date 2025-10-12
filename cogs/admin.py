import discord
from discord.ext import commands
from discord import app_commands

class AdminCog(commands.Cog):
    """
    Real-Time Administration Interface for managing the bot's database.
    All commands require administrator permissions.
    """
    
    def __init__(self, bot):
        self.bot = bot

    # ==================== BOT IDENTITY COMMANDS ====================
    
    @app_commands.command(name="bot_add_trait", description="Add a personality trait to the bot")
    @app_commands.describe(trait="The trait to add (e.g., 'sarcastic', 'loves medical terms')")
    @app_commands.default_permissions(administrator=True)
    async def bot_add_trait(self, interaction: discord.Interaction, trait: str):
        """Add a personality trait to the bot's identity."""
        self.bot.db_manager.add_bot_identity("trait", trait)
        await interaction.response.send_message(
            f"✅ Added trait: **{trait}**\nThis will take effect immediately in the next interaction.",
            ephemeral=True
        )
    
    @app_commands.command(name="bot_add_lore", description="Add a lore entry to the bot's background")
    @app_commands.describe(lore="A lore entry about the bot's backstory")
    @app_commands.default_permissions(administrator=True)
    async def bot_add_lore(self, interaction: discord.Interaction, lore: str):
        """Add a lore entry to the bot's identity."""
        self.bot.db_manager.add_bot_identity("lore", lore)
        await interaction.response.send_message(
            f"✅ Added lore: **{lore}**\nThis will take effect immediately.",
            ephemeral=True
        )
    
    @app_commands.command(name="bot_add_fact", description="Add a fact/quirk about the bot")
    @app_commands.describe(fact="A fact or quirk about the bot")
    @app_commands.default_permissions(administrator=True)
    async def bot_add_fact(self, interaction: discord.Interaction, fact: str):
        """Add a fact/quirk to the bot's identity."""
        self.bot.db_manager.add_bot_identity("fact", fact)
        await interaction.response.send_message(
            f"✅ Added fact: **{fact}**\nThis will take effect immediately.",
            ephemeral=True
        )
    
    @app_commands.command(name="bot_view_identity", description="View the bot's current personality from the database")
    @app_commands.default_permissions(administrator=True)
    async def bot_view_identity(self, interaction: discord.Interaction):
        """Display the bot's complete identity from the database."""
        
        traits = self.bot.db_manager.get_bot_identity("trait")
        lore = self.bot.db_manager.get_bot_identity("lore")
        facts = self.bot.db_manager.get_bot_identity("fact")
        
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
            embed.description = "No identity data found. Use `/bot_add_trait`, `/bot_add_lore`, or `/bot_add_fact` to populate."
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ==================== USER RELATIONSHIP COMMANDS ====================
    
    @app_commands.command(name="user_view_metrics", description="View relationship metrics for a user")
    @app_commands.describe(user="The user to check metrics for")
    @app_commands.default_permissions(administrator=True)
    async def user_view_metrics(self, interaction: discord.Interaction, user: discord.Member):
        """View relationship metrics for a specific user."""
        
        metrics = self.bot.db_manager.get_relationship_metrics(user.id)
        
        embed = discord.Embed(
            title=f"📊 Relationship Metrics: {user.display_name}",
            color=discord.Color.green()
        )
        
        embed.add_field(name="Rapport", value=f"{metrics['rapport']}/10", inline=True)
        embed.add_field(name="Trust", value=f"{metrics['trust']}/10", inline=True)
        embed.add_field(name="Anger", value=f"{metrics['anger']}/10", inline=True)
        embed.add_field(name="Formality", value=f"{metrics['formality']} (range: -5 to +5)", inline=False)
        
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
        user="The user to modify",
        rapport="Rapport level (0-10)",
        trust="Trust level (0-10)",
        anger="Anger level (0-10)",
        formality="Formality level (-5 to +5)"
    )
    @app_commands.default_permissions(administrator=True)
    async def user_set_metrics(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member,
        rapport: app_commands.Range[int, 0, 10] = None,
        trust: app_commands.Range[int, 0, 10] = None,
        anger: app_commands.Range[int, 0, 10] = None,
        formality: app_commands.Range[int, -5, 5] = None
    ):
        """Manually set relationship metrics for a user."""
        
        updates = {}
        if rapport is not None:
            updates['rapport'] = rapport
        if trust is not None:
            updates['trust'] = trust
        if anger is not None:
            updates['anger'] = anger
        if formality is not None:
            updates['formality'] = formality
        
        if not updates:
            await interaction.response.send_message(
                "❌ You must specify at least one metric to update.",
                ephemeral=True
            )
            return
        
        self.bot.db_manager.update_relationship_metrics(user.id, **updates)
        
        changes_text = "\n".join([f"• **{k.capitalize()}**: {v}" for k, v in updates.items()])
        
        await interaction.response.send_message(
            f"✅ Updated metrics for **{user.display_name}**:\n{changes_text}\n\nChanges take effect immediately.",
            ephemeral=True
        )
    
    # ==================== USER MEMORY COMMANDS ====================
    
    @app_commands.command(name="user_view_memory", description="View stored facts about a user")
    @app_commands.describe(user="The user to view memories for")
    @app_commands.default_permissions(administrator=True)
    async def user_view_memory(self, interaction: discord.Interaction, user: discord.Member):
        """View all stored long-term memory facts about a user."""
        
        memories = self.bot.db_manager.get_long_term_memory(user.id)
        
        if not memories:
            await interaction.response.send_message(
                f"ℹ️ No stored memories found for **{user.display_name}**.",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title=f"🧠 Stored Memories: {user.display_name}",
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
        user="The user this fact is about",
        fact="The fact to remember"
    )
    @app_commands.default_permissions(administrator=True)
    async def user_add_memory(self, interaction: discord.Interaction, user: discord.Member, fact: str):
        """Manually add a long-term memory fact about a user."""
        
        self.bot.db_manager.add_long_term_memory(
            user.id, 
            fact, 
            interaction.user.id, 
            interaction.user.display_name
        )
        
        await interaction.response.send_message(
            f"✅ Added memory for **{user.display_name}**: \"{fact}\"",
            ephemeral=True
        )
    
    # ==================== GLOBAL STATE COMMANDS ====================
    
    @app_commands.command(name="bot_set_mood", description="Set the bot's global mood state")
    @app_commands.describe(
        mood_type="Type of mood (anger, happiness, energy, etc.)",
        value="Mood value (typically 0-10)"
    )
    @app_commands.default_permissions(administrator=True)
    async def bot_set_mood(self, interaction: discord.Interaction, mood_type: str, value: int):
        """Set a global mood state for the bot."""
        
        state_key = f"daily_mood_{mood_type.lower()}"
        self.bot.db_manager.set_global_state(state_key, value)
        
        await interaction.response.send_message(
            f"✅ Set global mood **{mood_type}** to **{value}**",
            ephemeral=True
        )
    
    @app_commands.command(name="bot_get_mood", description="Get the bot's current global mood state")
    @app_commands.describe(mood_type="Type of mood to check")
    @app_commands.default_permissions(administrator=True)
    async def bot_get_mood(self, interaction: discord.Interaction, mood_type: str):
        """Get a global mood state value."""
        
        state_key = f"daily_mood_{mood_type.lower()}"
        value = self.bot.db_manager.get_global_state(state_key)
        
        if value is None:
            await interaction.response.send_message(
                f"ℹ️ No mood state found for **{mood_type}**. Use `/bot_set_mood` to set it.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"📊 Current **{mood_type}** mood: **{value}**",
                ephemeral=True
            )


async def setup(bot):
    """Required setup function to load the cog."""
    await bot.add_cog(AdminCog(bot))
