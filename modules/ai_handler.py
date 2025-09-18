# modules/ai_handler.py

import openai
import re
import json
from .emote_orchestrator import EmoteOrchestrator

class AIHandler:
    def __init__(self, api_key: str, emote_handler: EmoteOrchestrator):
        if not api_key:
            print("AI Handler Error: OpenAI API key is missing!")
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.emote_handler = emote_handler
        print("AI Handler: Initialized successfully.")

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
            f"- **CRITICAL EMOTE RULE**: You MUST enclose emote names in colons. To use the 'fishstrong' emote, you MUST write ':fishstrong:'. Never write the name of an emote as plain text. Your available emotes are: {available_emotes}"
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
            
            final_content = sanitized_content
            if role == "user":
                user_name = user_id_to_name.get(msg_data["author_id"], "Unknown User")
                channel_prefix = ""
                if msg_data["channel_id"] != channel.id:
                    channel_name = channel_id_to_name.get(msg_data["channel_id"], "unknown-channel")
                    channel_prefix = f"[In #{channel_name}] "
                final_content = f"{channel_prefix}{user_name}: {sanitized_content}"

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