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

        # Check if bot's last message was a question (used as context hint for AI)
        bot_asked_question = self._did_bot_ask_question(recent_messages, bot_id, current_message.author.id)
        if bot_asked_question:
            print(f"📝 Note: Bot's last message was a question - will factor into AI analysis")

        # Format conversation history for AI analysis
        context = self._format_conversation_history(recent_messages, bot_id, bot_name)
        print(f"\nFormatted conversation context:")
        print(f"{context}")

        # Get current message details
        current_user = current_message.author.display_name if hasattr(current_message.author, 'display_name') else current_message.author.name
        current_content = current_message.content

        # Call GPT-4o-mini for classification (pass whether bot asked a question as context)
        score = await self._classify_message_target(context, current_user, current_content, bot_name, bot_asked_question)

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

    async def _classify_message_target(self, conversation_history, current_user, current_message, bot_name, bot_asked_question=False):
        """
        Uses GPT-4o-mini to classify if the message is directed at the bot.

        Args:
            conversation_history: Formatted string of recent messages
            current_user: Name of user who sent current message
            current_message: Content of current message
            bot_name: Bot's display name
            bot_asked_question: Whether bot's last message was a question

        Returns:
            float: Confidence score (0.0-1.0) that message is directed at bot
        """
        # Add context about bot asking a question
        question_context = ""
        if bot_asked_question:
            question_context = f"""
**CONTEXT: The bot's last message ended with a question mark.**
This MIGHT mean the user is answering the bot's question - BUT ONLY if the message is actually a response to that question.
If the message is clearly addressing someone ELSE (contains another user's name, greeting to someone else), then it's NOT answering the bot's question.
"""

        system_prompt = f"""You are analyzing a Discord conversation to determine if the latest message warrants a response from a bot named "{bot_name}".

Recent conversation history:
{conversation_history}

Latest message (from {current_user}): "{current_message}"
{question_context}
**ANALYZE THE CONTEXT CAREFULLY.**

**CRITICAL FIRST CHECK - SCAN FOR OTHER USERNAMES:**
Look at EVERY name that appears before ":" in the conversation history. Those are REAL USERS in this chat.
If the latest message contains ANY word that matches or partially matches one of those usernames → Score 0.0 immediately.

**CRITICAL SECOND CHECK - CONVERSATION FLOW:**
Look at the SAME USER's recent messages in sequence. If they:
1. Started by addressing another user (e.g., "yo [name]", "hey [name]")
2. Then sent follow-up messages without explicitly addressing the bot
→ Those follow-ups are STILL for the other user, NOT the bot. Score 0.0.

Example: User says "yo mike" then "wassup" then "hope ur okay" → ALL THREE are for mike, not the bot.
The bot should NOT respond to "wassup" or "hope ur okay" just because they don't contain a name.

**IMPORTANT RULES:**
1. If message starts with ANOTHER USER'S NAME → Score 0.0 (talking to someone else)
2. If message is a simple reaction with no engagement → Score 0.0
3. Indirect mentions or comments on the bot's conversation only score 0.7 if they INVITE a response
4. If user JUST @mentioned another person, their follow-up is likely STILL to that person → Score 0.0
5. LOOK AT THE USERNAMES IN THE CONVERSATION HISTORY - if the message contains any part of another user's name, it's probably for them

**=== SCORE 0.0 - DO NOT RESPOND ===**
- Message contains a word that matches or partially matches another USERNAME visible in the conversation history
  - Look at every "Name:" at the start of lines in the history - those are real users
  - If the message says "yo [word]" and [word] matches any part of a username in history → Score 0.0
- Message starts with ANOTHER USER'S NAME (e.g., "yo mike", "hey sarah", "alex you wanna...")
- User JUST @mentioned someone else in a previous message - their next message is probably still to that person
- User is clearly talking to someone else (not the bot)
- Simple reactions with no question: ":)", "lol", "nice", "cool", "ok", "I like it", "fair enough"
- Someone comment ABOUT the bot that is just an observation (not inviting response):
  - "lol she's weird" (just commenting)
  - "the bot is broken" (complaint, not engagement)
  - "he's funny" (observation to others)

**=== SCORE 0.7 - INDIRECT MENTION (MAYBE RESPOND) ===**
- User talks ABOUT the bot in third person AND seems to invite a response:
  - "What do you think, {bot_name}?" (directly asking)
  - "I wonder what she thinks about this" (inviting input)
  - "Looks like you're talking to someone" or similar (acknowledging bot's presence)
  - Rhetorical questions about the bot that expect engagement
- Only score 0.7 if the indirect mention IMPLIES they want the bot to respond

**=== SCORE 0.8-1.0 - SHOULD RESPOND ===**
- Message contains "{bot_name}" directly addressed
- User JUST had an exchange with the bot AND is continuing the conversation AND message doesn't address someone else
- User says "you" and the bot was the last one they talked to AND no other user's name in message
- Direct question with no other person mentioned as the target

**=== SCORE 0.3-0.5 - AMBIGUOUS ===**
- Could be for bot or others, unclear intent

**KEY CONTEXT RULE:**
Look at who the user was JUST talking to. If their previous message was to the bot and bot responded, their next message is LIKELY still directed at the bot (score 0.8+), UNLESS they explicitly address someone else by name.

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
