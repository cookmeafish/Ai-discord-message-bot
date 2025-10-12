import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import openai

class MemoryTasksCog(commands.Cog):
    """
    Handles background memory management tasks including daily consolidation
    of short-term message logs into long-term memories.
    """
    def __init__(self, bot):
        self.bot = bot
        # Background task is commented out - uncomment when ready for automatic daily runs
        # self.memory_consolidation_loop.start()

    async def consolidate_memories(self):
        """
        Consolidates short-term message logs into long-term memories.

        Process:
        1. Retrieves last 24h of messages from short_term_message_log
        2. Groups messages by user
        3. Uses AI to extract important facts/memories from each user's messages
        4. Saves extracted facts to long_term_memory (with duplicate checking)

        Returns:
            Dictionary with consolidation results (users_processed, memories_added, errors)
        """
        print("=== Starting Memory Consolidation ===")

        # Get short-term memory (last 24h)
        messages = self.bot.db_manager.get_short_term_memory()

        if not messages:
            print("No messages found in short-term memory to consolidate.")
            return {"users_processed": 0, "memories_added": 0, "errors": 0}

        print(f"Found {len(messages)} messages to analyze")

        # Group messages by user (excluding bot's own messages)
        user_messages = {}
        for msg in messages:
            user_id = msg["author_id"]
            if user_id == self.bot.user.id:
                continue  # Skip bot's own messages

            if user_id not in user_messages:
                user_messages[user_id] = []
            user_messages[user_id].append(msg["content"])

        print(f"Grouped messages from {len(user_messages)} unique users")

        # Get AI model configuration for memory consolidation
        config = self.bot.config_manager.get_config()
        model_config = config.get('ai_models', {}).get('memory_consolidation', {})
        model = model_config.get('model', 'gpt-4o')
        max_tokens = model_config.get('max_tokens', 500)
        temperature = model_config.get('temperature', 0.3)

        print(f"Using AI model: {model} for memory extraction")

        users_processed = 0
        memories_added = 0
        errors = 0

        # Process each user's messages
        for user_id, messages_list in user_messages.items():
            try:
                # Get user display name for source attribution
                try:
                    member = self.bot.get_user(user_id)
                    user_name = member.display_name if member else f"User {user_id}"
                except:
                    user_name = f"User {user_id}"

                # Combine all messages from this user
                conversation_text = "\n".join([f"- {msg}" for msg in messages_list])

                # Create AI prompt for extracting facts
                extraction_prompt = f"""Analyze the following messages from a Discord user and extract ANY important facts, preferences, or information worth remembering about them.

Extract facts such as:
- Personal preferences (favorite things, likes/dislikes)
- Life details (job, hobbies, location, family)
- Opinions and beliefs
- Future plans or goals
- Anything the bot should remember for future conversations

User's messages from the last 24 hours:
{conversation_text}

Instructions:
- Extract ONLY facts that are clearly stated or strongly implied
- Format each fact as a short, clear sentence
- If there are NO meaningful facts to extract, respond with "NO_FACTS"
- Maximum 5 most important facts
- Each fact should be on a new line, prefixed with "FACT:"

Example output:
FACT: Likes pizza
FACT: Works as a software engineer
FACT: Has a cat named Whiskers
"""

                # Call OpenAI API
                client = openai.AsyncOpenAI(api_key=self.bot.config_manager.get_secret("OPENAI_API_KEY"))
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{'role': 'system', 'content': extraction_prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                result = response.choices[0].message.content.strip()

                # Parse extracted facts
                if result == "NO_FACTS":
                    print(f"No facts extracted for user {user_id}")
                    users_processed += 1
                    continue

                # Extract facts from response
                facts = []
                for line in result.split('\n'):
                    line = line.strip()
                    if line.startswith("FACT:"):
                        fact = line.replace("FACT:", "").strip()
                        if fact:
                            facts.append(fact)

                # Save each fact to database
                for fact in facts:
                    # Use "Memory Consolidation" as the source
                    self.bot.db_manager.add_long_term_memory(
                        user_id=user_id,
                        fact=fact,
                        source_user_id=user_id,
                        source_nickname=user_name
                    )
                    memories_added += 1
                    print(f"Saved memory for user {user_id}: {fact[:50]}...")

                users_processed += 1
                print(f"Processed user {user_id}: {len(facts)} facts extracted")

            except Exception as e:
                print(f"ERROR processing user {user_id}: {e}")
                errors += 1

        print(f"=== Memory Consolidation Complete ===")
        print(f"Users Processed: {users_processed}")
        print(f"Memories Added: {memories_added}")
        print(f"Errors: {errors}")

        # Archive and clear short-term memory now that it's been consolidated
        print("\n=== Archiving and Clearing Short-Term Memory ===")
        archived_count, deleted_count, archive_filename = self.bot.db_manager.archive_and_clear_short_term_memory()

        if archive_filename:
            print(f"Successfully archived {archived_count} messages to {archive_filename}")
            print(f"Deleted {deleted_count} messages from short-term memory")
        else:
            print("No messages to archive or archival failed")

        return {
            "users_processed": users_processed,
            "memories_added": memories_added,
            "errors": errors,
            "archived_count": archived_count,
            "deleted_count": deleted_count,
            "archive_filename": archive_filename
        }

    @app_commands.command(name="consolidate_memory", description="Manually trigger memory consolidation (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def consolidate_memory_command(self, interaction: discord.Interaction):
        """
        Admin slash command to manually trigger memory consolidation.
        Useful for testing or manual runs.
        """
        await interaction.response.defer(ephemeral=True)

        try:
            results = await self.consolidate_memories()

            response = f"**Memory Consolidation Complete**\n"
            response += f"- Users Processed: {results['users_processed']}\n"
            response += f"- Memories Added: {results['memories_added']}\n"
            response += f"- Errors: {results['errors']}\n\n"
            response += f"**Short-Term Memory Archive**\n"
            response += f"- Messages Archived: {results['archived_count']}\n"
            response += f"- Messages Deleted: {results['deleted_count']}\n"

            if results['archive_filename']:
                response += f"- Archive File: `{results['archive_filename']}`"
            else:
                response += f"- No messages to archive"

            await interaction.followup.send(response, ephemeral=True)

        except Exception as e:
            await interaction.followup.send(
                f"Error during memory consolidation: {e}",
                ephemeral=True
            )

    # Commented out automatic daily task - uncomment when ready
    # @tasks.loop(hours=24)
    # async def memory_consolidation_loop(self):
    #     """
    #     Background task that runs once per day to consolidate memories.
    #     """
    #     print("Running scheduled memory consolidation...")
    #     await self.consolidate_memories()


# This is the mandatory setup function that main.py looks for
async def setup(bot):
    await bot.add_cog(MemoryTasksCog(bot))
