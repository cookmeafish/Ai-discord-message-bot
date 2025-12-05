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

Determine if this message is:
- A continuation of the conversation with the bot
- A direct question/statement to the bot
- A response to something the bot said
- A comment ABOUT the bot's conversation that invites a response (e.g., "that's funny", "you're so weird")
- Mentioning the bot indirectly in a way that expects acknowledgment

Score from 0.0 to 1.0 (higher = more likely the bot should respond):
- 1.0 = Clearly talking to/about bot (references bot's previous message, asks bot a question, comments on bot's behavior)
- 0.7 = Indirect mention (talks about bot in third person, comments on bot's conversation with someone else)
- 0.5 = Ambiguous (could be for bot or someone else)
- 0.0 = Clearly NOT for bot (talking exclusively to another user, changing topic completely, general announcement)

IMPORTANT RULES:
- If someone comments on the bot's conversation (e.g., "looks like you're talking to X", "that was funny"), score 0.7+
- If someone says something nice/mean about the bot (e.g., "it's so cute", "the bot is weird"), score 0.7+
- If someone is ONLY talking to another human about unrelated topics, score 0.0
- If someone is addressing another user by name about something unrelated to the bot, score 0.0

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
