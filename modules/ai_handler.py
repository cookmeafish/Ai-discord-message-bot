# modules/ai_handler.py

import openai
import re
import json
import datetime
from dateutil import parser
from .emote_orchestrator import EmoteOrchestrator

class AIHandler:
    def __init__(self, api_key: str, emote_handler: EmoteOrchestrator):
        if not api_key:
            print("AI Handler Error: OpenAI API key is missing!")
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.emote_handler = emote_handler
        print("AI Handler: Initialized successfully.")

    def _get_relative_time(self, timestamp_str: str) -> str:
        """Calculates a human-readable relative time string from an ISO timestamp."""
        if not timestamp_str:
            return ""
        try:
            past_time = parser.isoparse(timestamp_str)
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = now - past_time
            
            seconds = int(delta.total_seconds())

            if seconds < 10:
                return "just now"
            elif seconds < 60:
                return f"{seconds} seconds ago"
            elif seconds < 3600:
                minutes = int(seconds / 60)
                return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            elif seconds < 86400:
                hours = int(seconds / 3600)
                return f"{hours} hour{'s' if hours > 1 else ''} ago"
            elif seconds < 172800:
                return "yesterday"
            else:
                days = int(seconds / 86400)
                return f"{days} days ago"
        except (ValueError, TypeError):
            return ""

    def _sanitize_content_for_ai(self, content: str) -> str:
        """
        Sanitizes message content before sending it to the AI.
        - Replaces custom Discord emote strings back to their simple :name: format.
        """
        return re.sub(r'<a?:(\w+):\d+>', r':\1:', content)

    async def generate_response(self, message, short_term_memory):
        channel = message.channel
        author = message.author
        
        config = self.emote_handler.bot.config_manager.get_config()
        channel_id_str = str(channel.id)
        personality_config = config.get('channel_settings', {}).get(channel_id_str, config.get('default_personality', {}))

        bot_name = channel.guild.me.display_name
        bot_id = self.emote_handler.bot.user.id
        bot_mention_string = f'<@{bot_id}>'
        
        available_emotes = self.emote_handler.get_available_emote_names()
        
        long_term_memory_facts = self.emote_handler.bot.db_manager.get_long_term_memory(author.id)
        long_term_memory_prompt = ""
        if long_term_memory_facts:
            facts_str = "; ".join(long_term_memory_facts)
            long_term_memory_prompt = f"--- CONTEXT ---\nUse these facts for subtle background context ONLY if directly relevant: {facts_str}"

        system_prompt = (
            f"You are {bot_name}, a casual Discord bot.\n"
            "--- CORE RULES ---\n"
            "1. **MATCH THE USER'S STYLE & LENGTH**: Your main goal is to be a natural conversationalist. **Mirror the user's message length.** If they send one word, you should reply with one or two words or a single emote. If they send a sentence, you can reply with a sentence. NEVER be significantly more verbose than the user.\n"
            "2. **FOCUS ON THE CURRENT MESSAGE**: Respond only to the user's most recent message.\n"
            "3. **BE CASUAL, NOT A THERAPIST**: Your tone is casual and friendly. Do not give unsolicited advice, express deep concern, or act like a therapist.\n"
            "4. **AVOID USING NAMES**: Do not use the user's name.\n\n"
            f"--- PERSONA ---\n- Traits: {personality_config.get('personality_traits', 'helpful')}\n\n"
            f"{long_term_memory_prompt}\n\n"
            "--- TECHNICAL INSTRUCTIONS ---\n"
            "The conversation history is prefixed with relative timestamps (e.g., '[5 minutes ago]'). **Do not mention these timestamps in your replies unless the user specifically asks 'when' something happened.** Use them only as internal context to answer direct questions about time.\n"
            f"Use these emotes to add personality: {available_emotes}"
        )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        
        user_id_to_name = {member.id: member.display_name for member in channel.guild.members}
        user_id_to_name[self.emote_handler.bot.user.id] = bot_name
        channel_id_to_name = {ch.id: ch.name for ch in channel.guild.channels if hasattr(ch, 'name')}

        sorted_memory = sorted(short_term_memory, key=lambda x: x["timestamp"])

        for msg_data in sorted_memory:
            sanitized_content = self._sanitize_content_for_ai(
                msg_data["content"].replace(bot_mention_string, f'@{bot_name}')
            )
            role = "assistant" if msg_data["author_id"] == bot_id else "user"
            
            relative_time = self._get_relative_time(msg_data.get("timestamp"))
            time_prefix = f"[{relative_time}] " if relative_time else ""

            final_content = sanitized_content
            if role == "user":
                user_name = user_id_to_name.get(msg_data["author_id"], "Unknown User")
                channel_prefix = ""
                if msg_data["channel_id"] != channel.id:
                    channel_name = channel_id_to_name.get(msg_data["channel_id"], "unknown-channel")
                    channel_prefix = f"[In #{channel_name}] "
                final_content = f"{time_prefix}{channel_prefix}{user_name}: {sanitized_content}"
            else: # For assistant's own messages
                final_content = f"{time_prefix}{sanitized_content}"

            messages_for_api.append({'role': role, 'content': final_content.strip()})

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                max_tokens=80,
                temperature=0.7
            )
            ai_response_text = response.choices[0].message.content.strip()
            return ai_response_text if ai_response_text else None

        except openai.APIError as e:
            print(f"AI HANDLER ERROR: An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"AI HANDLER ERROR: An unexpected error occurred: {e}")
            return None