# modules/ai_handler.py

import openai
import re
# No longer need asyncio for a lock here
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
        # The lock has been moved to the event handler to prevent duplicate event processing
        print("✅ AI Handler: Initialized successfully.")

    async def generate_response(self, channel, author, message_history):
        # The lock is no longer needed here. The events cog now prevents this
        # function from being called multiple times for the same message.
        print("   (Inside AI Handler) Generating response...")
        personality_config = self.personality_manager.get_channel_personality(channel.id)

        bot_name = channel.guild.me.display_name
        print(f"   (Inside AI Handler) Detected bot's current name as: {bot_name}")

        available_emotes = self.emote_handler.get_available_emote_names()
        emote_instructions = (
            f"You can use custom server emotes: {available_emotes}. "
            "Use them by wrapping their name in colons, like :smile:."
        )

        # Updated system prompt to include the user's display name for context
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
            # Use display_name (nickname) for all users in the history
            user_name = msg.author.display_name
            if msg.author.id == self.emote_handler.bot.user.id:
                # For the bot's own messages, just add the content
                messages_for_api.append({'role': 'assistant', 'content': msg.content})
            else:
                # For user messages, prepend their display name
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

