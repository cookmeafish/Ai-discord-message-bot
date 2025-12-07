# modules/conversation_detector.py

import openai
import json
from datetime import datetime, timedelta

class ConversationDetector:
    """
    Detects whether the bot should respond to a message based on conversation context.
    Uses AI to determine if a message is directed at the bot without explicit mentions.
    """

    def __init__(self, config_manager):
        """
        Initialize the conversation detector.

        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        self.config = config_manager.get_config().get('conversation_detection', {})
        self.client = None  # Will be set by AI handler

    def set_openai_client(self, client):
        """Set the OpenAI client (called by AI handler during initialization)"""
        self.client = client

    async def should_respond(self, recent_messages, current_message, bot_id, bot_name, threshold=0.7):
        """
        Analyzes conversation context to determine if bot should respond.

        Args:
            recent_messages: List of recent messages from short-term memory (dicts with 'content', 'author_id', 'nickname')
            current_message: The current message object to analyze
            bot_id: Discord bot user ID
            bot_name: Bot's display name
            threshold: Confidence threshold (0.0-1.0) for responding

        Returns:
            bool: True if bot should respond, False otherwise
        """
        print(f"\n{'='*80}")
        print(f"CONVERSATION CONTINUATION DETECTION - START")
        print(f"{'='*80}")
        print(f"Bot name: {bot_name}")
        print(f"Bot ID: {bot_id}")
        print(f"Current message: '{current_message.content}'")
        print(f"Author: {current_message.author.display_name} ({current_message.author.id})")
        print(f"Threshold: {threshold}")
        print(f"Recent messages count: {len(recent_messages)}")

        if not self.client:
            print("❌ ConversationDetector: OpenAI client not set, cannot detect conversation continuation")
            print(f"{'='*80}\n")
            return False

        # Check if bot's last message was a question - if so, user is likely answering
        bot_asked_question = self._did_bot_ask_question(recent_messages, bot_id, current_message.author.id)
        if bot_asked_question:
            print(f"🔔 Bot's last message to this user was a question - auto-responding")
            print(f"{'='*80}\n")
            return True

        # Format conversation history for AI analysis
        context = self._format_conversation_history(recent_messages, bot_id, bot_name)
        print(f"\nFormatted conversation context:")
        print(f"{context}")

        # Get current message details
        current_user = current_message.author.display_name if hasattr(current_message.author, 'display_name') else current_message.author.name
        current_content = current_message.content

        # Call GPT-4o-mini for classification
        score = await self._classify_message_target(context, current_user, current_content, bot_name)

        # Log decision for debugging
        should_respond = score >= threshold
        print(f"\n✅ CONVERSATION DETECTION RESULT:")
        print(f"   Score: {score:.2f}")
        print(f"   Threshold: {threshold}")
        print(f"   Should respond: {should_respond}")
        print(f"{'='*80}\n")

        return should_respond

    def _format_conversation_history(self, messages, bot_id, bot_name):
        """
        Formats recent messages into a readable conversation history.

        Args:
            messages: List of message dicts from short-term memory
            bot_id: Bot's Discord ID
            bot_name: Bot's display name

        Returns:
            str: Formatted conversation history
        """
        if not messages:
            return "No recent conversation history."

        # Take last 10 messages for context
        recent = messages[-10:] if len(messages) > 10 else messages

        formatted_lines = []
        for msg in recent:
            author_id = msg.get('author_id', '')
            nickname = msg.get('nickname', 'Unknown')
            content = msg.get('content', '')

            # Identify if message is from bot
            if str(author_id) == str(bot_id):
                formatted_lines.append(f"{bot_name} (bot): {content}")
            else:
                formatted_lines.append(f"{nickname}: {content}")

        return "\n".join(formatted_lines)

    async def _classify_message_target(self, conversation_history, current_user, current_message, bot_name):
        """
        Uses GPT-4o-mini to classify if the message is directed at the bot.

        Args:
            conversation_history: Formatted string of recent messages
            current_user: Name of user who sent current message
            current_message: Content of current message
            bot_name: Bot's display name

        Returns:
            float: Confidence score (0.0-1.0) that message is directed at bot
        """
        system_prompt = f"""You are analyzing a Discord conversation to determine if the latest message warrants a response from a bot named "{bot_name}".

Recent conversation history:
{conversation_history}

Latest message (from {current_user}): "{current_message}"

**ANALYZE THE CONTEXT CAREFULLY.**

**=== SCORE 0.0 - DO NOT RESPOND ===**
- Message starts with ANOTHER USER'S NAME (e.g., "yo mike", "hey sarah", "alex you wanna...")
- User is clearly talking to someone else (not the bot)
- Simple reactions with no question: ":)", "lol", "nice", "cool", "ok", "I like it"

**=== SCORE 0.8-1.0 - SHOULD RESPOND ===**
- Message contains "{bot_name}" or "fish" or "dr"
- User JUST had an exchange with the bot (bot's last message was to this user) AND user is now asking a question or continuing
- User says "you" and the bot was the last one they talked to
- Direct question with no other person mentioned as the target

**=== SCORE 0.3-0.6 - MAYBE RESPOND ===**
- Ambiguous who the message is for
- Could be for bot or others

**KEY CONTEXT RULE:**
Look at who the user was JUST talking to. If their previous message was to the bot and bot responded, then their next message is LIKELY still directed at the bot (score 0.8+), UNLESS they explicitly address someone else by name.

Example: User says "yo dr fish" → Bot says "Hey" → User says "you wanna play?" = Score 0.9 (continuing conversation with bot)
Example: User says "yo dr fish" → Bot says "Hey" → User says "yo mike wanna play?" = Score 0.0 (now talking to mike)

Return ONLY a single number between 0.0 and 1.0. No explanations."""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.get('model', 'gpt-4o-mini'),
                messages=[{'role': 'system', 'content': system_prompt}],
                max_tokens=self.config.get('max_tokens', 10),
                temperature=self.config.get('temperature', 0.0)
            )

            score_text = response.choices[0].message.content.strip()

            # Parse the score
            try:
                score = float(score_text)
                # Clamp to valid range
                score = max(0.0, min(1.0, score))
                return score
            except ValueError:
                print(f"ConversationDetector: Failed to parse score '{score_text}', defaulting to 0.0")
                return 0.0

        except Exception as e:
            print(f"ConversationDetector: Error classifying message: {e}")
            return 0.0

    def is_bot_recently_active(self, messages, bot_id, max_messages=10):
        """
        Checks if the bot has participated in the recent conversation.
        Optimization: Only run detection if bot was recently active.

        Args:
            messages: List of recent messages
            bot_id: Bot's Discord ID
            max_messages: How many recent messages to check

        Returns:
            bool: True if bot sent at least one message in last N messages
        """
        recent = messages[-max_messages:] if len(messages) > max_messages else messages

        for msg in recent:
            author_id = msg.get('author_id', '')
            if str(author_id) == str(bot_id):
                return True

        return False

    def _did_bot_ask_question(self, messages, bot_id, current_user_id):
        """
        Checks if the bot's last message in the conversation was a question.
        This helps detect when a user is answering the bot's question.

        Args:
            messages: List of recent messages from short-term memory
            bot_id: Bot's Discord ID
            current_user_id: ID of the user who sent the current message

        Returns:
            bool: True if bot's last message ended with a question mark
        """
        if not messages:
            return False

        # Look through messages in reverse to find the most recent bot message
        # that occurred BEFORE any messages from the current user
        found_user_message = False
        for msg in reversed(messages):
            author_id = msg.get('author_id', '')
            content = msg.get('content', '').strip()

            # If we hit a message from the current user, mark that we've passed their messages
            if str(author_id) == str(current_user_id):
                found_user_message = True
                continue

            # If this is a bot message AND we've already passed a user message
            # (meaning this bot message came before the user's recent messages)
            if str(author_id) == str(bot_id) and found_user_message:
                # Check if this message ends with a question mark
                # Strip emotes and whitespace from the end
                import re
                # Remove Discord emotes <:name:id> and <a:name:id> from the end
                cleaned = re.sub(r'<a?:\w+:\d+>\s*$', '', content).strip()
                if cleaned.endswith('?'):
                    print(f"   Bot's last message was a question: '{content[:50]}...'")
                    return True
                return False

        return False
