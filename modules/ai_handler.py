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
        user_profile_prompt = ""
        if long_term_memory_facts:
            facts_str = "; ".join(long_term_memory_facts)
            user_profile_prompt = f"Background info on '{author.display_name}': {facts_str}."

        system_prompt = (
            f"You are {bot_name}, a chill, low-energy Discord bot. Your main goal is to be a natural, concise conversationalist. "
            f"Your personality traits are: {personality_config.get('personality_traits', 'helpful')}. "
            f"{user_profile_prompt}\n\n"
            "--- CRITICAL RULES ---\n"
            "1. **DO NOT CONFUSE IDENTITIES**: The background info provided is about the user, NOT you. Pay close attention to the names in the chat history to keep track of who said what. Do not claim another user's facts as your own.\n"
            "2. **BE CONCISE & AVOID QUESTIONS**: Keep replies short and match the user's energy. Do not ask follow-up questions like 'what about you?'.\n"
            "3. **TIME CONTEXT IS INTERNAL**: The chat history has timestamps like '[5 minutes ago]'. Do NOT mention these timestamps. Use them ONLY as internal context if the user asks WHEN something happened.\n"
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
                final_content = f"{time_prefix}{user_name}: {sanitized_content}"
            else:
                final_content = f"{time_prefix}{sanitized_content}"


            messages_for_api.append({'role': role, 'content': final_content.strip()})
            
        user_message_length = len(message.content.split())
        if user_message_length <= 2:
            max_tokens = 20
        elif user_message_length <= 5:
            max_tokens = 40
        else:
            max_tokens = 80

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                max_tokens=max_tokens,
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