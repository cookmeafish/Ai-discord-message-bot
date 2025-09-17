diff
# modules/ai_handler.py

import openai
import re
from .emote_orchestrator import EmoteOrchestrator

class AIHandler:
    def __init__(self, api_key: str, emote_handler: EmoteOrchestrator):
        if not api_key:
            print("🔴 AI Handler Error: OpenAI API key is missing!")
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.emote_handler = emote_handler
        print("✅ AI Handler: Initialized successfully.")

    def _sanitize_content_for_ai(self, content: str) -> str:
        """
        Sanitizes message content before sending it to the AI.
        - Replaces custom Discord emote strings back to their simple :name: format.
        This prevents the AI from seeing and copying malformed emote strings from history.
        Example: Replaces '<:fishreadingemote:1263029060716597320>' with ':fishreadingemote:'
        """
        # This regex captures the emote name from both animated (<a:name:id>) and static (<:name:id>) emotes.
        return re.sub(r'<a?:(\w+):\d+>', r':\1:', content)

-     async def generate_response(self, channel, author, message_history, current_message): # modified code
+     async def generate_response(self, message, short_term_memory, recent_messages): # new code
        print("   (Inside AI Handler) Generating response...")
        
+         channel = message.channel # new code
+         author = message.author # new code
+  # new code
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
-             f"Your purpose here is: {personality_config.get('purpose', 'general chat')}. "
+             f"Your purpose here is: {personality_config.get('purpose', 'general chat')}.\n" # modified code
+             "You will be given two sources of context: 'Short-Term Memory' from the last 24 hours across all channels, and 'Recent Messages' from the current channel. " # new code
+             "Prioritize the 'Recent Messages' for immediate context, but use the 'Short-Term Memory' to inform your responses about topics discussed in other channels or earlier in the day. " # new code
            "Keep responses concise for chat. Do not use markdown.\n"
            f"{emote_instructions}\n"
            "IMPORTANT: Your response MUST NOT begin with your name and a colon. For example, never start with 'Dr. Fish v2: ' or 'AI-Bot: '."
        )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        
        # Create a mapping of user IDs to display names from the guild members
        user_id_to_name = {member.id: member.display_name for member in channel.guild.members}
        user_id_to_name[self.emote_handler.bot.user.id] = bot_name

        # Create a mapping of channel IDs to channel names
        channel_id_to_name = {ch.id: ch.name for ch in channel.guild.channels}

-         for msg_data in message_history: # modified code
+         # Format Short-Term Memory for the AI # new code
+         memory_context_str = "--- Short-Term Memory (Last 24 Hours) ---\n" # new code
+         for msg_data in short_term_memory: # new code
            user_name = user_id_to_name.get(msg_data["author_id"], "Unknown User")
            channel_name = channel_id_to_name.get(msg_data["channel_id"], "unknown-channel")
-  # modified code
            processed_content = msg_data["content"].replace(bot_mention_string, f'@{bot_name}')
            sanitized_content = self._sanitize_content_for_ai(processed_content)
-  # modified code
-             # Add channel context if the message is from a different channel # modified code
            context_prefix = ""
            if msg_data["channel_id"] != channel.id:
                context_prefix = f"[In #{channel_name}] "
-  # modified code
-             if msg_data["author_id"] == self.emote_handler.bot.user.id: # modified code
-                 messages_for_api.append({'role': 'assistant', 'content': sanitized_content}) # modified code
-             else: # modified code
-                 content = f"{context_prefix}{user_name}: {sanitized_content}" # modified code
-                 messages_for_api.append({'role': 'user', 'content': content}) # modified code
-  # new code
-         # Add the current message to the context # new code
-         user_name = author.display_name # new code
-         processed_content = current_message.content.replace(bot_mention_string, f'@{bot_name}') # new code
-         sanitized_content = self._sanitize_content_for_ai(processed_content) # new code
-         content = f"{user_name}: {sanitized_content}" # new code
-         messages_for_api.append({'role': 'user', 'content': content}) # new code
+             memory_context_str += f"{context_prefix}{user_name}: {sanitized_content}\n" # new code
+         messages_for_api.append({'role': 'user', 'content': memory_context_str}) # new code
+  # new code
+         # Format Recent Messages for the AI # new code
+         recent_context_str = "--- Recent Messages (Current Channel) ---\n" # new code
+         for msg in recent_messages: # new code
+             user_name = msg.author.display_name # new code
+             processed_content = msg.content.replace(bot_mention_string, f'@{bot_name}') # new code
+             sanitized_content = self._sanitize_content_for_ai(processed_content) # new code
+             if msg.author.id == bot_id: # new code
+                 messages_for_api.append({'role': 'assistant', 'content': sanitized_content}) # new code
+             else: # new code
+                 recent_context_str += f"{user_name}: {sanitized_content}\n" # new code
+         messages_for_api.append({'role': 'user', 'content': recent_context_str}) # new code

        try:
            print("   (Inside AI Handler) Sending request to OpenAI...")
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                max_tokens=200,
                temperature=0.7
            )
            print("   (Inside AI Handler) ✅ OpenAI request successful.")
            return response.choices[0].message.content.strip()
        except openai.APIError as e:
            print(f"   (Inside AI Handler) 🔴 An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"   (Inside AI Handler) 🔴 An unexpected error occurred: {e}")
            return None