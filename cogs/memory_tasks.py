import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import openai
import json

class MemoryTasksCog(commands.Cog):
    """
    Handles background memory management tasks including daily consolidation
    of short-term message logs into long-term memories.
    """
    def __init__(self, bot):
        self.bot = bot
        # Background task is commented out - uncomment when ready for automatic daily runs
        # self.memory_consolidation_loop.start()

    async def _analyze_user_sentiment_batch(self, user_id, messages_list, db_manager, client, model):
        """
        Analyzes all messages from a user during consolidation and updates relationship metrics.
        This is a batch analysis of the entire conversation history, not per-message.

        Args:
            user_id: Discord user ID
            messages_list: List of message contents from this user
            db_manager: Server-specific database manager
            client: OpenAI client
            model: AI model to use
        """
        if not messages_list:
            return

        # Combine messages for analysis
        conversation_text = "\n".join([f"- {msg}" for msg in messages_list[-50:]])  # Last 50 messages max

        sentiment_prompt = f"""Analyze these messages from a Discord user and determine their OVERALL sentiment toward the bot.
Based on the conversation tone, determine if relationship metrics should change.

User's messages:
{conversation_text}

Respond with ONLY a JSON object:
{{
    "should_update": true/false,
    "rapport_change": 0,
    "trust_change": 0,
    "anger_change": 0,
    "respect_change": 0,
    "affection_change": 0,
    "familiarity_change": 0,
    "fear_change": 0,
    "intimidation_change": 0,
    "reason": "brief explanation"
}}

Guidelines (changes should be -2 to +2 based on OVERALL tone across all messages):
- **Rapport**: Friendly/warm messages → +1/+2, Cold/dismissive → -1/-2
- **Trust**: User shares personal info → +1, User is secretive/suspicious → -1
- **Anger**: User is hostile/rude → +1/+2, User is patient/kind → -1/-2
- **Respect**: User acknowledges bot's abilities → +1, User dismisses/mocks bot → -1
- **Affection**: User expresses care/appreciation → +1, User is indifferent → -1
- **Familiarity**: Regular positive interaction → +1 (slowly increases over time)
- **Fear**: User makes threats → +1, User is reassuring/protective → -1
- **Intimidation**: User displays power/authority → +1, User shows vulnerability/asks for help → -1

IMPORTANT: Only set should_update to true if there's a clear pattern across messages.
Normal casual conversation should result in no changes (should_update: false).
"""

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{'role': 'system', 'content': sentiment_prompt}],
                max_tokens=150,
                temperature=0.0
            )

            result_text = response.choices[0].message.content.strip()
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(result_text)

            if result.get('should_update', False):
                current_metrics = db_manager.get_relationship_metrics(user_id)

                updates = {}
                metric_changes = [
                    ('rapport', 'rapport_change'),
                    ('trust', 'trust_change'),
                    ('anger', 'anger_change'),
                    ('respect', 'respect_change'),
                    ('affection', 'affection_change'),
                    ('familiarity', 'familiarity_change'),
                    ('fear', 'fear_change'),
                    ('intimidation', 'intimidation_change')
                ]

                for metric_name, change_key in metric_changes:
                    change = result.get(change_key, 0)
                    if change != 0 and metric_name in current_metrics:
                        new_value = max(0, min(10, current_metrics[metric_name] + change))
                        updates[metric_name] = new_value

                if updates:
                    # Update with respect_locks=True to honor locked metrics
                    db_manager.update_relationship_metrics(user_id, respect_locks=True, **updates)
                    print(f"  📊 Updated metrics for user {user_id}: {result.get('reason', 'sentiment analysis')}")
                    for metric_name, new_value in updates.items():
                        old_value = current_metrics[metric_name]
                        if old_value != new_value:
                            print(f"     {metric_name}: {old_value} → {new_value}")

        except Exception as e:
            print(f"  ⚠️ Sentiment analysis failed for user {user_id}: {e}")

    async def consolidate_memories(self, guild_id, db_manager):
        """
        Consolidates short-term message logs into long-term memories for a specific server.

        Args:
            guild_id: Discord guild ID
            db_manager: Server-specific database manager

        Process:
        1. Retrieves all messages from short_term_message_log for this server
        2. Groups messages by user
        3. Uses AI to extract important facts/memories from each user's messages
        4. Saves extracted facts to long_term_memory (with duplicate checking)

        Returns:
            Dictionary with consolidation results (users_processed, memories_added, errors)
        """
        print(f"=== Starting Memory Consolidation for Guild {guild_id} ===")

        # Get short-term memory from server-specific database
        messages = db_manager.get_short_term_memory()

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
                extraction_prompt = f"""Analyze the following messages from a Discord user (User ID: {user_id}) and extract ANY important facts, preferences, or information worth remembering about THIS SPECIFIC USER.

Extract facts such as:
- Personal preferences (favorite things, likes/dislikes)
- Life details (job, hobbies, location, family)
- Opinions and beliefs
- Future plans or goals
- Anything the bot should remember for future conversations with THIS user

User's messages:
{conversation_text}

**CRITICAL INSTRUCTIONS**:
- Extract facts about THIS USER ONLY (the one who wrote these messages)
- Ignore questions the user asks about other people
- Write facts in a way that clearly refers to THIS user, not "someone" or vague references
- If the user says "I love X", extract as "Loves X" (about them specifically)
- If the user asks "who likes X?" without stating they like it themselves, DO NOT extract a fact about liking X
- Extract ONLY facts that are clearly stated or strongly implied about THIS user's own life, preferences, and experiences
- Format each fact as a short, clear sentence starting with a verb or adjective (e.g., "Loves building houses", "Works as an engineer")
- If there are NO meaningful facts to extract, respond with "NO_FACTS"
- Maximum 5 most important facts
- Each fact should be on a new line, prefixed with "FACT:"

Example output (facts about THIS user):
FACT: Loves building houses in Arizona
FACT: Finds building houses to be hard work
FACT: Favorite food is pizza
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
                facts = []
                if result == "NO_FACTS":
                    print(f"No facts extracted for user {user_id}")
                else:
                    # Extract facts from response
                    for line in result.split('\n'):
                        line = line.strip()
                        if line.startswith("FACT:"):
                            fact = line.replace("FACT:", "").strip()
                            if fact:
                                facts.append(fact)

                # Only run sentiment analysis if user has enough messages (minimum 3)
                # This prevents metrics from changing for inactive users or based on just 1-2 messages
                MIN_MESSAGES_FOR_SENTIMENT = 3
                if len(messages_list) >= MIN_MESSAGES_FOR_SENTIMENT:
                    await self._analyze_user_sentiment_batch(user_id, messages_list, db_manager, client, model)
                else:
                    print(f"  ⏭️ Skipping sentiment analysis for user {user_id} (only {len(messages_list)} messages, need {MIN_MESSAGES_FOR_SENTIMENT})")

                # If no facts, skip fact processing but still count as processed
                if not facts:
                    users_processed += 1
                    print(f"Processed user {user_id}: 0 facts extracted (sentiment analyzed)")
                    continue

                # Save each fact to database with contradiction detection
                for fact in facts:
                    # Check for contradictory memories
                    existing_facts = db_manager.find_contradictory_memory(user_id, fact)

                    if existing_facts:
                        # Use AI to determine if there's a contradiction
                        contradiction_prompt = f"""You are a memory contradiction detector. Compare a new fact with existing facts about a user.

NEW FACT: {fact}

EXISTING FACTS:
{chr(10).join([f"{i+1}. {ef['fact']}" for i, ef in enumerate(existing_facts)])}

Determine if the new fact contradicts any existing fact. If it does:
- Respond with ONLY the number (1, 2, 3, etc.) of the contradicted fact that should be replaced
- The new fact should replace the old one if it's more recent or more specific

If there is NO contradiction:
- Respond with ONLY the word "NO_CONTRADICTION"

Response (number or NO_CONTRADICTION):"""

                        try:
                            response = await client.chat.completions.create(
                                model=model,
                                messages=[{'role': 'system', 'content': contradiction_prompt}],
                                max_tokens=10,
                                temperature=0.0
                            )

                            contradiction_result = response.choices[0].message.content.strip()

                            # Check if AI detected a contradiction
                            if contradiction_result.isdigit():
                                # AI identified a contradictory fact - update it
                                fact_index = int(contradiction_result) - 1
                                if 0 <= fact_index < len(existing_facts):
                                    old_fact_id = existing_facts[fact_index]['id']
                                    db_manager.update_long_term_memory_fact(old_fact_id, fact)
                                    print(f"Updated contradictory memory for user {user_id}: {fact[:50]}...")
                                else:
                                    # Invalid index, add as new fact
                                    db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
                                    print(f"Saved memory for user {user_id}: {fact[:50]}...")
                            else:
                                # No contradiction detected, add as new fact
                                db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
                                print(f"Saved memory for user {user_id}: {fact[:50]}...")

                            memories_added += 1

                        except Exception as e:
                            # If contradiction detection fails, fall back to adding as new
                            print(f"Warning: Contradiction detection failed for user {user_id}: {e}")
                            db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
                            memories_added += 1
                            print(f"Saved memory for user {user_id}: {fact[:50]}...")
                    else:
                        # No existing similar facts, add as new
                        db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
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
        archived_count, deleted_count, archive_filename = db_manager.archive_and_clear_short_term_memory()

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

    # Note: The /consolidate_memory slash command is defined in cogs/admin.py
    # This avoids duplicate command registration while keeping the consolidation logic here

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
