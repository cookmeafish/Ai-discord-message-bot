# modules/proactive_engagement.py

import discord
import openai
import os
from datetime import datetime, timedelta
from modules.config_manager import ConfigManager
from modules.logging_manager import get_logger

class ProactiveEngagement:
    """
    Handles proactive bot engagement - randomly joining conversations
    when the context is interesting, without being explicitly mentioned.

    CRITICAL: Prevents self-reply loops by checking if last message was from bot.
    """

    def __init__(self, bot):
        self.bot = bot
        self.config_manager = ConfigManager()
        self.logger = get_logger()

        # Set up OpenAI API key
        openai.api_key = os.getenv('OPENAI_API_KEY')

        # Track last engagement per channel to avoid spam
        self.last_engagement_time = {}

    async def should_engage(self, channel_id, recent_messages):
        """
        Determines if the bot should proactively engage in a channel.

        Args:
            channel_id: Discord channel ID
            recent_messages: List of recent Message objects (most recent last)

        Returns:
            bool: True if bot should engage, False otherwise
        """
        try:
            config = self.config_manager.get_config()
            proactive_config = config.get('proactive_engagement', {})

            # Check if proactive engagement is enabled
            if not proactive_config.get('enabled', False):
                return False

            # CRITICAL: Check if last message was from the bot
            if recent_messages and recent_messages[-1].author.id == self.bot.user.id:
                self.logger.debug(f"Skipping proactive engagement in channel {channel_id}: Last message was from bot")
                return False

            # Check if enough time has passed since last engagement in this channel
            cooldown_minutes = proactive_config.get('cooldown_minutes', 30)
            last_engagement = self.last_engagement_time.get(channel_id)

            if last_engagement:
                time_since_last = datetime.now() - last_engagement
                if time_since_last < timedelta(minutes=cooldown_minutes):
                    return False

            # Check if there are enough messages to analyze
            min_messages = proactive_config.get('min_messages_to_analyze', 5)
            if len(recent_messages) < min_messages:
                return False

            # Use AI to determine if conversation is interesting
            is_interesting = await self._is_conversation_interesting(recent_messages, proactive_config)

            if is_interesting:
                # Update last engagement time
                self.last_engagement_time[channel_id] = datetime.now()
                self.logger.info(f"✅ Proactive engagement triggered in channel {channel_id}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error in should_engage: {e}", exc_info=True)
            return False

    async def _is_conversation_interesting(self, recent_messages, proactive_config):
        """
        Uses AI to determine if the conversation is interesting enough to join.

        Args:
            recent_messages: List of recent Message objects
            proactive_config: Proactive engagement configuration dict

        Returns:
            bool: True if conversation is interesting, False otherwise
        """
        try:
            # Get engagement threshold (0.0 to 1.0, higher = more selective)
            threshold = proactive_config.get('engagement_threshold', 0.7)

            # Build conversation context
            conversation_text = "\n".join([
                f"{msg.author.display_name}: {msg.content}"
                for msg in recent_messages[-10:]  # Analyze last 10 messages
                if msg.content  # Skip empty messages
            ])

            if not conversation_text:
                return False

            # AI prompt to judge conversation interest
            system_prompt = f"""You are analyzing a Discord conversation to determine if an AI bot should join.

The bot should join conversations that are:
- Asking questions the bot could answer
- Discussing topics related to the bot's personality/interests
- Engaging in creative or fun discussions
- Having a debate or discussion where bot input would be valuable

The bot should NOT join conversations that are:
- Just casual greetings or small talk
- Very short or low-effort exchanges
- Private or intimate discussions
- Already ending/concluded

Conversation:
{conversation_text}

On a scale of 0.0 to 1.0, how interesting/relevant is this conversation for the bot to join?
Respond with ONLY a number (e.g., 0.8)."""

            # Get AI judgment
            config = self.config_manager.get_config()
            model_config = config.get('ai_models', {}).get('intent_classification', {})
            model = model_config.get('model', 'gpt-4.1-mini')

            response = openai.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_prompt}],
                max_tokens=10,
                temperature=0.3
            )

            score_text = response.choices[0].message.content.strip()

            # Parse score
            try:
                score = float(score_text)
            except ValueError:
                self.logger.warning(f"Invalid score from AI: {score_text}")
                return False

            self.logger.debug(f"Conversation interest score: {score} (threshold: {threshold})")

            # Return True if score exceeds threshold
            return score >= threshold

        except Exception as e:
            self.logger.error(f"Error in _is_conversation_interesting: {e}", exc_info=True)
            return False

    async def generate_proactive_response(self, channel, recent_messages, db_manager):
        """
        Generates a proactive response for the given channel/conversation.

        Args:
            channel: Discord TextChannel object
            recent_messages: List of recent Message objects
            db_manager: Database manager for this server

        Returns:
            str: Generated response text, or None if generation fails
        """
        try:
            if not recent_messages:
                return None

            # Generate response using AI handler's dedicated proactive method
            # CRITICAL: This uses NEUTRAL context (no specific user's relationship/memory)
            # to avoid confusing users with each other
            response = await self.bot.ai_handler.generate_proactive_response(
                channel,
                recent_messages,
                db_manager
            )

            return response

        except Exception as e:
            self.logger.error(f"Error generating proactive response: {e}", exc_info=True)
            return None

    def get_channel_cooldown_status(self, channel_id):
        """
        Gets cooldown status for a channel.

        Returns:
            dict: {
                'on_cooldown': bool,
                'time_remaining_minutes': int or None
            }
        """
        config = self.config_manager.get_config()
        cooldown_minutes = config.get('proactive_engagement', {}).get('cooldown_minutes', 30)

        last_engagement = self.last_engagement_time.get(channel_id)

        if not last_engagement:
            return {'on_cooldown': False, 'time_remaining_minutes': None}

        time_since_last = datetime.now() - last_engagement
        cooldown_delta = timedelta(minutes=cooldown_minutes)

        if time_since_last < cooldown_delta:
            time_remaining = cooldown_delta - time_since_last
            return {
                'on_cooldown': True,
                'time_remaining_minutes': int(time_remaining.total_seconds() / 60)
            }
        else:
            return {'on_cooldown': False, 'time_remaining_minutes': None}
