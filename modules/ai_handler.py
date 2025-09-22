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

    async def _classify_intent(self, message, short_term_memory):
        """Step 1: Classify the user's intent."""
        
        recent_messages = short_term_memory[-5:]
        
        conversation_history = "\n".join(
            [f'{msg["author_id"]}: {msg["content"]}' for msg in recent_messages]
        )
        
        intent_prompt = f"""
        You are an intent classification model. Analyze the last message from the user ({message.author.id}) in the context of the recent conversation history.
        Classify the user's intent into one of the following categories:
        - "casual_chat": The user is making small talk, reacting, or having a general conversation.
        - "memory_recall": The user is asking the bot to remember a known fact about them or the past.
        - "memory_correction": The user is correcting a fact the bot previously stated.
        - "factual_question": The user is asking a verifiable, real-world factual question.

        Conversation History:
        {conversation_history}

        Last User Message:
        {message.author.id}: {message.content}

        Based on the last user message, what is the user's primary intent? Respond with ONLY the intent category name.
        """
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{'role': 'system', 'content': intent_prompt}],
                max_tokens=15,
                temperature=0.0
            )
            intent = response.choices[0].message.content.strip().lower()

            if intent in ["casual_chat", "memory_recall", "memory_correction", "factual_question"]:
                print(f"AI Handler: Classified intent as '{intent}'")
                return intent
            else:
                print(f"AI Handler: Intent classification failed, defaulting to 'casual_chat'. Raw response: {intent}")
                return "casual_chat"
        except Exception as e:
            print(f"AI HANDLER ERROR: Could not classify intent: {e}")
            return "casual_chat"

    async def generate_response(self, message, short_term_memory):
        """Step 2: Generate a response based on the classified intent."""
        
        intent = await self._classify_intent(message, short_term_memory)
        
        channel = message.channel
        author = message.author
        
        config = self.emote_handler.bot.config_manager.get_config()
        channel_id_str = str(channel.id)
        personality_config = config.get('channel_settings', {}).get(channel_id_str, config.get('default_personality', {}))

        bot_name = channel.guild.me.display_name
        
        long_term_memory_facts = self.emote_handler.bot.db_manager.get_long_term_memory(author.id)
        user_profile_prompt = ""
        if long_term_memory_facts:
            facts_str = "; ".join(long_term_memory_facts)
            user_profile_prompt = f"--- Known facts about '{author.display_name}' ---\n- {facts_str}\n\n"

        # --- Dynamic System Prompt based on Intent ---
        system_prompt = ""
        if intent == "factual_question":
            system_prompt = (
                f"You are {bot_name}, a casual Discord chatbot. A user has asked you a real-world factual question. "
                "You must first determine the nature of the question.\n"
                "1. If the question is about general, established knowledge (e.g., historical facts, scientific concepts, geography), answer it briefly and accurately.\n"
                "2. If the question is about a recent event, the current status of a living person, or any real-time information, you MUST respond casually that you don't know. For example, use short, natural phrases like 'idk', 'I don't know yet', 'I wouldn't know', or 'no idea'.\n"
                "Under NO circumstances should you invent an answer to these types of questions."
            )
        elif intent == "memory_correction":
            system_prompt = (
                f"You are {bot_name}, a chill Discord bot. The user is correcting a fact you previously got wrong. "
                "Acknowledge the correction gracefully. Be very brief. "
                "Example responses: 'oh, my bad', 'got it, thanks', 'my mistake'."
            )
        else: # Covers "casual_chat" and "memory_recall"
            system_prompt = (
                f"You are {bot_name}, a chill, low-energy Discord bot. Your personality is very concise and casual.\n\n"
                f"- Your Traits: {personality_config.get('personality_traits', 'helpful')}\n\n"
                f"{user_profile_prompt if intent == 'memory_recall' else ''}"
                "--- CRITICAL RULES ---\n"
                "1. **BE BRIEF AND NATURAL**: Your replies should be very short and sound like a real person. Avoid robotic phrases.\n"
                "2. **NO FOLLOW-UP QUESTIONS**: You must not ask any questions.\n"
                "3. **USE MEMORY WISELY**: Only mention facts from the user profile if they are directly relevant to the current topic.\n"
                "4. **NO NAME PREFIX**: NEVER start your response with your name and a colon.\n"
            )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        for msg_data in short_term_memory[-10:]:
            role = "assistant" if msg_data["author_id"] == self.emote_handler.bot.user.id else "user"
            content = msg_data["content"]
            messages_for_api.append({'role': role, 'content': content})

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages_for_api,
                max_tokens=60,
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