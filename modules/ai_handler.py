# modules/ai_handler.py

import openai
import re
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

    async def generate_response(self, message, short_term_memory, recent_messages):
        print("   (Inside AI Handler) Generating response...")
        
        channel = message.channel
        author = message.author
        
        config = self.emote_handler.bot.config_manager.get_config()
        channel_id_str = str(channel.id)
        personality_config = config.get('channel_settings', {}).get(channel_id_str, config.get('default_personality', {}))

        bot_name = channel.guild.me.display_name
        bot_id = self.emote_handler.bot.user.id
        bot_mention_string = f'<@{bot_id}>'
        print(f"   (Inside AI Handler) Detected bot's current name as: {bot_name}")

        available_emotes = self.emote_handler.get_available_emote_names()
        emote_instructions = (
            f"You can use custom server emotes: {available_emotes}. "
            "Use them by wrapping their name in colons, like :smile:."
        )

        system_prompt = (
            f"You are a Discord bot. Your name is ALWAYS {bot_name}. Do not refer to yourself by any other name. "
            f"The user you are currently speaking to is named '{author.display_name}'. Only refer to them by name if the context of the conversation requires it for clarity. Avoid using their name in every message to make the conversation feel more natural. "
            f"Your personality is: {personality_config.get('personality_traits', 'helpful')}. "
            f"Your lore: {personality_config.get('lore', '')}. "
            f"Facts to remember: {personality_config.get('facts', '')}. "
            f"You are in channel '{channel.name}'. "
            f"Your purpose here is: {personality_config.get('purpose', 'general chat')}.\n"
            "You will be given a conversation history. Messages marked with [Memory] are from a broader 24-hour context across different channels. Prioritize the most recent messages for immediate context, but use the [Memory] messages to maintain awareness of other conversations."
            "Keep responses concise for chat. Do not use markdown.\n"
            f"{emote_instructions}\n"
            "IMPORTANT: Your response MUST NOT begin with your name and a colon. For example, never start with 'Dr. Fish v2: ' or 'AI-Bot: '."
        )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        
        user_id_to_name = {member.id: member.display_name for member in channel.guild.members}
        user_id_to_name[self.emote_handler.bot.user.id] = bot_name

        channel_id_to_name = {ch.id: ch.name for ch in channel.guild.channels if hasattr(ch, 'name')}

        combined_context = {}

        for msg_data in short_term_memory:
            combined_context[msg_data["message_id"]] = {
                "is_bot": msg_data["author_id"] == bot_id,
                "author_id": msg_data["author_id"],
                "channel_id": msg_data["channel_id"],
                "content": msg_data["content"],
                "timestamp": msg_data["timestamp"],
                "source": "memory"
            }

        for msg in recent_messages:
            if msg.id == message.id:
                continue
            combined_context[msg.id] = {
                "is_bot": msg.author.id == bot_id,
                "author_id": msg.author.id,
                "channel_id": msg.channel.id,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "source": "recent"
            }

        sorted_context = sorted(combined_context.values(), key=lambda x: x["timestamp"])

        # Build the final message list, merging consecutive user messages
        for msg_data in sorted_context:
            sanitized_content = self._sanitize_content_for_ai(
                msg_data["content"].replace(bot_mention_string, f'@{bot_name}')
            )

            if msg_data["is_bot"]:
                messages_for_api.append({'role': 'assistant', 'content': sanitized_content})
            else:
                user_name = user_id_to_name.get(msg_data["author_id"], "Unknown User")
                source_prefix = "[Memory] " if msg_data["source"] == "memory" else ""
                channel_prefix = ""
                if msg_data["channel_id"] != channel.id:
                    channel_name = channel_id_to_name.get(msg_data["channel_id"], "unknown-channel")
                    channel_prefix = f"[In #{channel_name}] "
                
                full_prefix = f"{source_prefix}{channel_prefix}"
                final_content = f"{full_prefix}{user_name}: {sanitized_content}\n"
                
                if messages_for_api[-1]['role'] == 'user':
                    messages_for_api[-1]['content'] += final_content
                else:
                    messages_for_api.append({'role': 'user', 'content': final_content})

        # Add the current triggering message, merging if necessary
        current_user_name = author.display_name
        current_sanitized_content = self._sanitize_content_for_ai(
            message.content.replace(bot_mention_string, f'@{bot_name}')
        )
        current_final_content = f"{current_user_name}: {current_sanitized_content}"

        if messages_for_api[-1]['role'] == 'user':
            messages_for_api[-1]['content'] += f"\n{current_final_content}"
        else:
            messages_for_api.append({'role': 'user', 'content': current_final_content})

        # Clean up trailing newlines from content
        for msg in messages_for_api:
            if msg.get('role') == 'user':
                msg['content'] = msg['content'].strip()

        try:
            print("   (Inside AI Handler) Sending request to OpenAI...")
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                max_tokens=200,
                temperature=0.7
            )
            print("   (Inside AI Handler) OpenAI request successful.")
            return response.choices[0].message.content.strip()
        except openai.APIError as e:
            print(f"   (Inside AI Handler) An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"   (Inside AI Handler) An unexpected error occurred: {e}")
            return None