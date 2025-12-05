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
        Analyzes all messages from a user during memory consolidation and updates relationship metrics.
        This is a batch analysis of SHORT-TERM memory only, not influenced by long-term memory.

        IMPORTANT: This ONLY runs during memory consolidation, never at startup or per-message.

        Args:
            user_id: Discord user ID
            messages_list: List of message contents from this user (from short-term memory ONLY)
            db_manager: Server-specific database manager
            client: OpenAI client
            model: AI model to use
        """
        if not messages_list:
            return

        # Get current metrics to inform decay decisions
        current_metrics = db_manager.get_relationship_metrics(user_id)

        # Combine messages for analysis (SHORT-TERM MEMORY ONLY)
        conversation_text = "\n".join([f"- {msg}" for msg in messages_list[-50:]])  # Last 50 messages max

        sentiment_prompt = f"""Analyze these recent messages from a Discord user and determine how relationship metrics should change.
This analysis is based ONLY on these recent messages (short-term memory), not any stored facts about the user.

⚠️ **CRITICAL: HOLISTIC NON-ADDITIVE ANALYSIS** ⚠️
You are analyzing the OVERALL TONE of this conversation as a SINGLE UNIT.
- Changes are CAPPED at -2 to +2 MAXIMUM, regardless of message count
- 50 rude messages = +1 or +2 anger (NOT +50)
- 100 kind messages = +1 or +2 rapport (NOT +100)
- DO NOT add up changes per message - assess the OVERALL vibe

User's recent messages:
{conversation_text}

Current metric levels (for context on decay):
- Anger: {current_metrics.get('anger', 5)}/10
- Fear: {current_metrics.get('fear', 5)}/10
- Intimidation: {current_metrics.get('intimidation', 5)}/10

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

**ABSOLUTE LIMITS** (NEVER exceed these):
- Maximum change per metric: -2 to +2
- Any value outside this range is INVALID

**NEGATIVE EMOTIONS SHOULD DECAY:**
- **Anger**:
  - User is hostile/rude/insulting → +1 (mild) or +2 (severe/repeated hostility)
  - User is neutral (normal conversation) AND current anger > 3 → -1 (natural decay)
  - User is patient/kind/friendly → -1/-2
- **Fear**:
  - User makes threats → +1 (or +2 for severe threats)
  - User is neutral AND current fear > 3 → -1 (natural decay)
  - User is reassuring/protective → -1/-2
- **Intimidation**:
  - User displays power/authority aggressively → +1 (or +2 for severe)
  - User is neutral AND current intimidation > 3 → -1 (natural decay)
  - User shows vulnerability/asks for help → -1/-2

**POSITIVE EMOTIONS:**
- **Rapport**: Friendly/warm → +1/+2, Cold/dismissive → -1/-2
- **Trust**: User shares personal info → +1, User is secretive/suspicious → -1
- **Respect**: User acknowledges bot's abilities → +1, User dismisses/mocks bot → -1
- **Affection**: User expresses care/appreciation → +1/+2, User is cold/indifferent → -1
- **Familiarity**: Regular interaction → +1 (slowly increases over time)

IMPORTANT RULES:
1. Normal casual conversation with NO hostility should DECREASE anger if anger is currently high (>3)
2. Only INCREASE anger if there are CLEARLY hostile/rude messages (insults, aggression, rudeness)
3. Playful teasing or jokes are NOT hostile - do not increase anger for humor
4. If the conversation is neutral/positive, set should_update to true and apply natural decay to negative emotions
5. Be conservative with increases (+1 max for mild cases), generous with decreases (-1/-2 for positive interactions)
6. NEVER output a change value outside the range [-2, +2] - this is a hard limit
"""

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[{'role': 'system', 'content': sentiment_prompt}],
                max_tokens=150,
                temperature=0.0
            )

            result_text = response.choices[0].message.content.strip()
            # DEBUG: Log raw sentiment analysis response
            print(f"  🔍 Sentiment Analysis Response for user {user_id}:")
            print(f"     Raw: {result_text[:300]}{'...' if len(result_text) > 300 else ''}")

            result_text = result_text.replace('```json', '').replace('```', '').strip()
            # Fix invalid JSON: AI sometimes returns +1 instead of 1 (valid JSON doesn't allow + prefix)
            import re
            result_text = re.sub(r':\s*\+(\d)', r': \1', result_text)
            result = json.loads(result_text)

            # DEBUG: Log parsed result
            print(f"     Parsed: should_update={result.get('should_update')}, reason={result.get('reason', 'N/A')}")

            if result.get('should_update', False):
                # current_metrics already fetched above for the prompt

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

                # DEBUG: Log all proposed changes
                print(f"     AI Proposed Changes:")
                for metric_name, change_key in metric_changes:
                    change = result.get(change_key, 0)
                    if change != 0:
                        print(f"       {metric_name}: {change:+d}")

                for metric_name, change_key in metric_changes:
                    change = result.get(change_key, 0)
                    # CRITICAL: Clamp change to -2 to +2 to enforce non-additive behavior
                    # Even if AI misbehaves and returns +10, we cap it at +2
                    change = max(-2, min(2, change))
                    if change != 0 and metric_name in current_metrics:
                        new_value = max(0, min(10, current_metrics[metric_name] + change))
                        updates[metric_name] = new_value

                if updates:
                    # Update with respect_locks=True to honor locked metrics
                    print(f"  📊 Attempting to update metrics for user {user_id}...")
                    db_manager.update_relationship_metrics(user_id, respect_locks=True, **updates)
                    print(f"     Reason: {result.get('reason', 'sentiment analysis')}")
                    for metric_name, new_value in updates.items():
                        old_value = current_metrics[metric_name]
                        print(f"     {metric_name}: {old_value} → {new_value}")
                else:
                    print(f"     No metric updates needed (all changes were 0 or already at limit)")
            else:
                print(f"     AI said should_update=False, skipping metric updates")

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

                # DEBUG: Log messages being sent to AI
                print(f"\n  📝 User {user_id} ({user_name}) - {len(messages_list)} messages:")
                for msg in messages_list[:5]:  # Show first 5 messages
                    print(f"     - {msg[:80]}{'...' if len(msg) > 80 else ''}")
                if len(messages_list) > 5:
                    print(f"     ... and {len(messages_list) - 5} more messages")

                # Call OpenAI API
                client = openai.AsyncOpenAI(api_key=self.bot.config_manager.get_secret("OPENAI_API_KEY"))
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{'role': 'system', 'content': extraction_prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                result = response.choices[0].message.content.strip()

                # DEBUG: Log raw AI response for fact extraction
                print(f"  🤖 AI Fact Extraction Response for user {user_id}:")
                print(f"     Raw: {result[:200]}{'...' if len(result) > 200 else ''}")

                # Parse extracted facts
                facts = []
                if result == "NO_FACTS" or "NO_FACTS" in result:
                    print(f"  ❌ No facts extracted for user {user_id} (AI returned NO_FACTS)")
                else:
                    # Extract facts from response
                    for line in result.split('\n'):
                        line = line.strip()
                        if line.startswith("FACT:"):
                            fact = line.replace("FACT:", "").strip()
                            if fact:
                                facts.append(fact)
                                print(f"  ✅ Extracted fact: {fact}")

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
                        # Use AI to determine if there's a contradiction OR duplicate
                        # Note: existing_facts is a list of tuples (fact_id, fact_text)
                        contradiction_prompt = f"""You are a memory fact analyzer. Compare a new fact with existing facts about a user.

NEW FACT: {fact}

EXISTING FACTS:
{chr(10).join([f"{i+1}. {ef[1]}" for i, ef in enumerate(existing_facts)])}

Determine if the new fact is:
1. **CONTRADICTORY** - The new fact conflicts with an existing fact (e.g., "Favorite color is red" vs "Favorite color is blue")
2. **REDUNDANT/DUPLICATE** - The new fact says the same thing as an existing fact in different words (e.g., "Loves pizza" vs "Favorite food is pizza")

Response format:
- If CONTRADICTORY: "CONTRADICTION:X" where X is the fact number (new fact replaces old)
- If REDUNDANT/DUPLICATE: "DUPLICATE:X" where X is the fact number (keep old, skip new)
- If TRULY NEW: "NEW" (add as new fact)

Examples:
- "Loves chilaquiles" vs "Favorite food is chilaquiles" → DUPLICATE:1
- "Favorite color is red" vs "Favorite color is blue" → CONTRADICTION:1
- "Works as a nurse" vs "Loves hiking" → NEW

Response (CONTRADICTION:X, DUPLICATE:X, or NEW):"""

                        try:
                            response = await client.chat.completions.create(
                                model=model,
                                messages=[{'role': 'system', 'content': contradiction_prompt}],
                                max_tokens=20,
                                temperature=0.0
                            )

                            result = response.choices[0].message.content.strip().upper()

                            if result.startswith("CONTRADICTION:"):
                                # AI identified a contradictory fact - replace it with new fact
                                try:
                                    fact_index = int(result.split(":")[1]) - 1
                                    if 0 <= fact_index < len(existing_facts):
                                        old_fact_id = existing_facts[fact_index][0]
                                        old_fact_text = existing_facts[fact_index][1]
                                        db_manager.update_long_term_memory_fact(old_fact_id, fact)
                                        print(f"  🔄 Updated contradictory fact for user {user_id}:")
                                        print(f"     OLD: {old_fact_text[:50]}...")
                                        print(f"     NEW: {fact[:50]}...")
                                        memories_added += 1
                                    else:
                                        db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
                                        print(f"Saved memory for user {user_id}: {fact[:50]}...")
                                        memories_added += 1
                                except (ValueError, IndexError):
                                    db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
                                    print(f"Saved memory for user {user_id}: {fact[:50]}...")
                                    memories_added += 1

                            elif result.startswith("DUPLICATE:"):
                                # AI identified a duplicate fact - skip adding the new one
                                try:
                                    fact_index = int(result.split(":")[1]) - 1
                                    if 0 <= fact_index < len(existing_facts):
                                        existing_fact_text = existing_facts[fact_index][1]
                                        print(f"  ⏭️ Skipped duplicate fact for user {user_id}:")
                                        print(f"     NEW: {fact[:50]}...")
                                        print(f"     EXISTING: {existing_fact_text[:50]}...")
                                        # Don't increment memories_added - we're not adding anything
                                    else:
                                        # Invalid index, add as new fact
                                        db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
                                        print(f"Saved memory for user {user_id}: {fact[:50]}...")
                                        memories_added += 1
                                except (ValueError, IndexError):
                                    db_manager.add_long_term_memory(user_id, fact, user_id, user_name)
                                    print(f"Saved memory for user {user_id}: {fact[:50]}...")
                                    memories_added += 1

                            else:
                                # NEW or unrecognized response - add as new fact
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
