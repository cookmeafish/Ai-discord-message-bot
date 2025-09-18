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
        emote_instructions = (
            f"You can use custom server emotes: {available_emotes}. "
            "Use them by wrapping their name in colons, like :smile:."
        )

        long_term_memory_facts = self.emote_handler.bot.db_manager.get_long_term_memory(author.id)
        long_term_memory_prompt = ""
        if long_term_memory_facts:
            facts_str = "; ".join(long_term_memory_facts)
            long_term_memory_prompt = f"Background information you know about '{author.display_name}': {facts_str}. Do not bring these up unless the conversation is directly related. Use them as subtle context."

        system_prompt = (
            f"You are a Discord bot named {bot_name}. "
            f"Your personality is: {personality_config.get('personality_traits', 'helpful')}. "
            "CONVERSATIONAL RULES:\n"
            "1.  **PRIORITIZE THE LATEST MESSAGE**: Your primary goal is to respond *only* to the user's most recent message. Do not respond to older messages in the history.\n"
            "2.  **BE CONCISE**: Match the user's energy. If they write one sentence, you should write one sentence. Avoid over-explaining. Keep it brief and casual.\n"
            "3.  **AVOID USING NAMES**: Do not use the user's name in your reply unless it's absolutely necessary for clarity (e.g., if multiple people are talking to you at once).\n"
            f"{long_term_memory_prompt}\n"
            f"{emote_instructions}\n"
            "IMPORTANT: Your response MUST NOT begin with your name and a colon (e.g., 'Dr. Fish v2: ').\n"
            "After your main response, if you learned a new, significant, and memorable fact about the user (like a preference or personal detail), add it on a new line in this exact format: ```json\n{\"new_fact\": \"The fact you learned\"}```"
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
            user_name = user_id_to_name.get(msg_data["author_id"], "Unknown User")
            
            final_content = ""
            if role == "user":
                channel_prefix = ""
                if msg_data["channel_id"] != channel.id:
                    channel_name = channel_id_to_name.get(msg_data["channel_id"], "unknown-channel")
                    channel_prefix = f"[In #{channel_name}] "
                final_content = f"{channel_prefix}{user_name}: {sanitized_content}\n"
            else:
                final_content = sanitized_content

            if role == 'user' and messages_for_api and messages_for_api[-1]['role'] == 'user':
                messages_for_api[-1]['content'] += final_content
            else:
                messages_for_api.append({'role': role, 'content': final_content})

        for msg in messages_for_api:
            if msg.get('role') == 'user':
                msg['content'] = msg['content'].strip()

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                max_tokens=150,  # Reduced max tokens to encourage shorter responses
                temperature=0.7
            )
            ai_response_text = response.choices[0].message.content.strip()
            main_response = ai_response_text
            
            try:
                if "```json" in ai_response_text:
                    json_block_start = ai_response_text.find("```json")
                    json_block_end = ai_response_text.find("```", json_block_start + 1)
                    json_string = ai_response_text[json_block_start + 7 : json_block_end].strip()
                    main_response = ai_response_text[:json_block_start].strip()
                    
                    parsed_json = json.loads(json_string)
                    if "new_fact" in parsed_json:
                        fact = parsed_json["new_fact"]
                        self.emote_handler.bot.db_manager.add_long_term_memory(author.id, fact)
            except Exception as e:
                print(f"AI HANDLER: Could not parse or save new fact from AI response. Error: {e}")
                pass

            return main_response

        except openai.APIError as e:
            print(f"AI HANDLER ERROR: An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"AI HANDLER ERROR: An unexpected error occurred: {e}")
            return None