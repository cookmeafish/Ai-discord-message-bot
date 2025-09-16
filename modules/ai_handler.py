# modules/ai_handler.py

import openai
import re
from .emote_orchestrator import EmoteOrchestrator
# We no longer import the old PersonalityManager

class AIHandler:
    # The __init__ method no longer accepts a personality_manager
    def __init__(self, api_key: str, emote_handler: EmoteOrchestrator):
        if not api_key:
            print("🔴 AI Handler Error: OpenAI API key is missing!")
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.emote_handler = emote_handler
        # The self.personality_manager attribute is removed.
        print("✅ AI Handler: Initialized successfully.")

    async def generate_response(self, channel, author, message_history):
        print("   (Inside AI Handler) Generating response...")
        
        # --- TEMPORARY PERSONALITY LOGIC ---
        # This is a placeholder. Instead of using the old manager, we now get the config
        # directly through the bot instance attached to the emote_handler.
        # This will be replaced by a call to the db_manager once it's built.
        config = self.emote_handler.bot.config_manager.get_config()
        channel_id_str = str(channel.id)
        personality_config = config.get('channel_settings', {}).get(channel_id_str, config.get('default_personality', {}))
        # --- END OF TEMPORARY LOGIC ---

        bot_name = channel.guild.me.display_name
        print(f"   (Inside AI Handler) Detected bot's current name as: {bot_name}")

        available_emotes = self.emote_handler.get_available_emote_names()
        emote_instructions = (
            f"You can use custom server emotes: {available_emotes}. "
            "Use them by wrapping their name in colons, like :smile:."
        )

        system_prompt = (
            f"You are a Discord bot. Your name is ALWAYS {bot_name}. Do not refer to yourself by any other name. "
            f"The user you are currently speaking to is named '{author.display_name}'. You should be friendly and refer to them by their name when it feels natural. "
            f"Your personality is: {personality_config.get('personality_traits', 'helpful')}. "
            f"Your lore: {personality_config.get('lore', '')}. "
            f"Facts to remember: {personality_config.get('facts', '')}. "
            f"You are in channel '{channel.name}'. "
            f"Your purpose here is: {personality_config.get('purpose', 'general chat')}. "
            "Keep responses concise for chat. Do not use markdown.\n"
            f"{emote_instructions}\n"
            "IMPORTANT: Your response MUST NOT begin with your name and a colon. For example, never start with 'Dr. Fish v2: ' or 'AI-Bot: '."
        )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        
        for msg in message_history:
            user_name = msg.author.display_name
            if msg.author.id == self.emote_handler.bot.user.id:
                messages_for_api.append({'role': 'assistant', 'content': msg.content})
            else:
                content = f"{user_name}: {msg.content}"
                messages_for_api.append({'role': 'user', 'content': content})

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
