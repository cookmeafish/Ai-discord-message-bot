# modules/ai_handler.py

import openai
import re
from .emote_orchestrator import EmoteOrchestrator
from .personality_manager import PersonalityManager

class AIHandler:
    def __init__(self, api_key: str, emote_handler: EmoteOrchestrator, personality_manager: PersonalityManager):
        if not api_key:
            print("🔴 AI Handler Error: OpenAI API key is missing!")
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.emote_handler = emote_handler
        self.personality_manager = personality_manager
        print("✅ AI Handler: Initialized successfully.")

    async def generate_response(self, channel, author, message_history):
        print("   (Inside AI Handler) Generating response...")
        personality_config = self.personality_manager.get_channel_personality(channel.id)

        bot_name = channel.guild.me.display_name
        print(f"   (Inside AI Handler) Detected bot's current name as: {bot_name}")

        available_emotes = self.emote_handler.get_available_emote_names()
        emote_instructions = (
            f"You can use custom server emotes: {available_emotes}. "
            "Use them by wrapping their name in colons, like :smile:."
        )

        system_prompt = (
            f"You are a Discord bot. Your name is ALWAYS {bot_name}. Do not refer to yourself by any other name. "
            f"Your personality is: {personality_config.get('personality_traits', 'helpful')}. "
            f"Your lore: {personality_config.get('lore', '')}. "
            f"Facts to remember: {personality_config.get('facts', '')}. "
            f"You are in channel '{channel.name}'. "
            f"Your purpose here is: {personality_config.get('purpose', 'general chat')}. "
            "Keep responses concise for chat. Do not use markdown.\n"
            f"{emote_instructions}\n"
            # --- THIS IS THE NEW, FORCEFUL INSTRUCTION ---
            "IMPORTANT: Your response MUST NOT begin with your name and a colon. For example, never start with 'Dr. Fish v2: ' or 'AI-Bot: '."
            # ----------------------------------------------
        )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        
        for msg in message_history:
            if msg.author.id == self.emote_handler.bot.user.id:
                cleaned_content = re.sub(r'^\w+:\s*', '', msg.content)
                messages_for_api.append({'role': 'assistant', 'content': cleaned_content})
            else:
                content = f"{msg.author.display_name}: {msg.content}"
                messages_for_api.append({'role': 'user', 'content': content})

        try