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
You are an expert intent classification model. Analyze the last message from the user ({message.author.id}) in the context of the recent conversation history. Your primary goal is to accurately determine the user's intent.

Follow these strict rules for classification:
- **memory_storage**: The user is stating a fact and wants the bot to remember it for later (e.g., "my favorite color is blue", "just so you know, my cat is named Whiskers").
- **memory_correction**: ONLY classify as this if the user's message DIRECTLY CONTRADICTS a statement made by the bot in the provided conversation history. If there is no bot statement to correct, this is the wrong category.
- **factual_question**: Use for questions about verifiable, real-world facts.
- **memory_recall**: Use when the user is asking the bot to remember or state a known fact about a user or the past.
- **casual_chat**: This is the default. Use for small talk, reactions, or any general conversation that doesn't fit the other categories.

Conversation History:
{conversation_history}

Last User Message:
{message.author.id}: {message.content}

Based on the rules and the last user message, what is the user's primary intent? Respond with ONLY the intent category name.
"""
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{'role': 'system', 'content': intent_prompt}],
                max_tokens=15,
                temperature=0.0
            )
            intent = response.choices[0].message.content.strip().lower()

            if intent in ["casual_chat", "memory_recall", "memory_correction", "factual_question", "memory_storage"]:
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
        
        long_term_memory_entries = self.emote_handler.bot.db_manager.get_long_term_memory(author.id)
        user_profile_prompt = ""
        if long_term_memory_entries:
            facts_str_list = []
            for fact, source_id, source_name in long_term_memory_entries:
                # If the source is unknown, don't mention it.
                source_info = f" (Source: {source_name})" if source_name else ""
                facts_str_list.append(f"Fact: '{fact}'{source_info}")
            
            facts_str = "\n- ".join(facts_str_list)
            user_profile_prompt = f"--- Known Facts ---\n- {facts_str}\n\n"

        # --- Dynamic System Prompt based on Intent ---
        system_prompt = ""
        if intent == "memory_storage":
            extraction_prompt = f"""
The user wants you to remember a fact about them or the world. Analyze the user's message and extract the core piece of information as a concise statement.
- If the user says 'my favorite color is blue', the fact is 'My favorite color is blue'.
- If the user says 'my cat is named Whiskers', the fact is 'My cat is named Whiskers'.
- If the user says 'remember that I work as a software engineer', the fact is 'I work as a software engineer'.

User message: "{message.content}"

Respond with ONLY the extracted fact.
"""
            try:
                # First, extract and save the fact
                response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{'role': 'system', 'content': extraction_prompt}],
                    max_tokens=60,
                    temperature=0.0
                )
                extracted_fact = response.choices[0].message.content.strip()
                if not extracted_fact:
                    return "I'm not sure what you want me to remember from that."
                
                self.emote_handler.bot.db_manager.add_long_term_memory(
                    author.id, extracted_fact, author.id, author.display_name
                )
                
                # Now, generate a natural response to having learned the fact
                response_prompt = f"""
You are {bot_name}, a chill Discord bot. You just learned a new fact from the user: '{extracted_fact}'.
Acknowledge this new information with a short, natural, human-like response. Your response should be related to the fact.
For example, if you learned 'my favorite food is tamales', you could say 'my mouth is watering just thinking about it' or 'tamales are the best'.
- Your Traits: {personality_config.get('personality_traits', 'helpful')}
- BE BRIEF. Do not ask questions. Do not say "I'll remember that".
"""
                response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{'role': 'system', 'content': response_prompt}],
                    max_tokens=40,
                    temperature=0.7
                )
                return response.choices[0].message.content.strip()

            except Exception as e:
                print(f"AI HANDLER ERROR: Could not process memory storage: {e}")
                return "Sorry, I had trouble trying to remember that."

        elif intent == "factual_question":
            system_prompt = (
                f"You are {bot_name}, a casual Discord chatbot. A user has asked you a real-world factual question. "
                f"{user_profile_prompt}"
                "You must first determine the nature of the question.\n"
                "1. Review the 'Known Facts' provided. **If a fact has a Source, you MUST use it to answer questions like 'who told you that?'.**\n"
                "2. Use logical reasoning based on these facts to answer. For example, if you know a cafe 'closed down', you must infer that it is not 'open'.\n"
                "3. If you don't have a known fact, you MUST respond that you don't know (e.g., 'idk', 'no idea').\n"
                "Under NO circumstances should you invent an answer."
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
                f"{user_profile_prompt}"
                "--- CRITICAL RULES ---\n"
                "1. **BE BRIEF AND NATURAL**: Your replies should be very short and sound like a real person. Avoid robotic phrases.\n"
                "2. **NO FOLLOW-UP QUESTIONS**: You must not ask any questions.\n"
                "3. **USE MEMORY WISELY**: If a fact has a Source, you know who told you. Only mention facts if they are relevant.\n"
                "4. **NO NAME PREFIX**: NEVER start your response with your name and a colon.\n"
            )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        for msg_data in short_term_memory[-10:]:
            role = "assistant" if msg_data["author_id"] == self.emote_handler.bot.user.id else "user"
            author_name = "User"
            if message.guild:
                member = message.guild.get_member(msg_data["author_id"])
                if member:
                    author_name = member.display_name
            
            content = f'{author_name}: {msg_data["content"]}'
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