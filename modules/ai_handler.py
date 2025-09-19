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
        
        channel_settings = config.get('channel_settings', {})
        default_personality = config.get('default_personality', {})
        personality_config = channel_settings.get(channel_id_str, default_personality)

        bot_name = channel.guild.me.display_name
        bot_id = self.emote_handler.bot.user.id
        bot_mention_string = f'<@{bot_id}>'
        
        long_term_memory_facts = self.emote_handler.bot.db_manager.get_long_term_memory(author.id)
        user_profile_prompt = ""
        if long_term_memory_facts:
            facts_str = "; ".join(long_term_memory_facts)
            user_profile_prompt = f"--- USER PROFILE for '{author.display_name}' ---\n- Known facts: {facts_str}\n\n"

        system_prompt = (
            f"You are {bot_name}, a chill, low-energy Discord bot. Your personality is very concise and casual.\n\n"
            f"--- YOUR PERSONA ---\n"
            f"- Your Traits: {personality_config.get('personality_traits', 'helpful')}\n\n"
            f"{user_profile_prompt}"
            "--- CRITICAL RULES ---\n"
            "1. **BE EXTREMELY CONCISE AND LOW-ENERGY**: Your replies MUST be very short, often just a few words or an emote. NEVER be overly conversational.\n"
            "2. **NO FOLLOW-UP QUESTIONS**: You MUST NOT ask the user any questions. Just respond to what they say.\n"
            "3. **AVOID REPETITION**: Vary your phrasing. Do not start every response with similar phrases like 'Sounds like...'.\n"
            "4. **HANDLE CONTEXT CORRECTLY**: The USER PROFILE is about the user, NOT you. Only mention facts if the user's message is directly related.\n"
            "5. **TIME IS INTERNAL CONTEXT**: The user's messages have timestamps. Do NOT mention them unless asked.\n"
            "6. **NO NAME PREFIX**: NEVER start your response with your name and a colon.\n"
        )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        
        user_id_to_name = {member.id: member.display_name for member in channel.guild.members}
        user_id_to_name[self.emote_handler.bot.user.id] = bot_name
        
        relevant_memory = sorted(short_term_memory, key=lambda x: x["timestamp"])[-15:]

        for msg_data in relevant_memory:
            sanitized_content = self._sanitize_content_for_ai(
                msg_data["content"].replace(bot_mention_string, f'@{bot_name}')
            )
            
            role = "assistant" if msg_data["author_id"] == bot_id else "user"
            
            if role == "user":
                user_name = user_id_to_name.get(msg_data["author_id"], "Unknown User")
                relative_time = self._get_relative_time(msg_data.get("timestamp"))
                time_prefix = f"[{relative_time}] " if relative_time else ""
                content = f"{time_prefix}{user_name}: {sanitized_content}"
            else:
                content = sanitized_content

            messages_for_api.append({'role': role, 'content': content.strip()})

        # Dynamically adjust max_tokens to enforce short responses
        user_message_length = len(message.content.split())
        if user_message_length <= 3:
            max_tokens = 25
        elif user_message_length <= 10:
            max_tokens = 50
        else:
            max_tokens = 80

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                max_tokens=max_tokens,
                temperature=0.6 # Lowered temperature to make the bot more focused and less chatty
            )
            ai_response_text = response.choices[0].message.content.strip()
            return ai_response_text if ai_response_text else None

        except openai.APIError as e:
            print(f"AI HANDLER ERROR: An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"AI HANDLER ERROR: An unexpected error occurred: {e}")
            return None