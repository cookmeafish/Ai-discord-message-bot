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
        
        # Load AI model configuration from config
        self.config = emote_handler.bot.config_manager.get_config()
        self.model_config = self.config.get('ai_models', {})
        self.response_limits = self.config.get('response_limits', {})
        
        # Default values if config is missing
        self.PRIMARY_MODEL = self.model_config.get('primary_model', 'gpt-4.1-mini')
        self.FALLBACK_MODEL = self.model_config.get('fallback_model', 'gpt-4o-mini')
        
        print(f"AI Handler: Initialized with primary model: {self.PRIMARY_MODEL}")

    def _get_model_config(self, task_type):
        """
        Retrieves model configuration for a specific task.
        Falls back to primary model if task-specific config is missing.
        
        Args:
            task_type: One of 'intent_classification', 'sentiment_analysis', 
                      'memory_extraction', 'memory_response', 'main_response'
        
        Returns:
            dict: Model configuration with 'model', 'max_tokens', 'temperature'
        """
        task_config = self.model_config.get(task_type, {})
        return {
            'model': task_config.get('model', self.PRIMARY_MODEL),
            'max_tokens': task_config.get('max_tokens', 100),
            'temperature': task_config.get('temperature', 0.7)
        }

    def _strip_discord_formatting(self, text):
        """
        Strips Discord emote formatting from text, converting <:name:id> back to :name:
        This prevents the AI from seeing and trying to replicate malformed Discord syntax.
        """
        if not text:
            return text
        
        # Replace <:emotename:1234567890> with :emotename:
        # Replace <a:emotename:1234567890> (animated) with :emotename:
        text = re.sub(r'<a?:(\w+):\d+>', r':\1:', text)
        return text

    def _build_bot_identity_prompt(self):
        """
        Builds a comprehensive prompt section about the bot's identity from the database.
        Returns a formatted string with traits, lore, and facts.
        """
        db_manager = self.emote_handler.bot.db_manager
        
        # Get all bot identity entries from database
        traits = db_manager.get_bot_identity("trait")
        lore = db_manager.get_bot_identity("lore")
        facts = db_manager.get_bot_identity("fact")
        
        identity_prompt = "=== YOUR IDENTITY ===\n"
        
        if traits:
            identity_prompt += "Core Traits:\n"
            for trait in traits:
                identity_prompt += f"- {trait}\n"
            identity_prompt += "\n"
        
        if lore:
            identity_prompt += "Your Background & Lore:\n"
            for lore_entry in lore:
                identity_prompt += f"- {lore_entry}\n"
            identity_prompt += "\n"
        
        if facts:
            identity_prompt += "Facts & Quirks About You:\n"
            for fact in facts:
                identity_prompt += f"- {fact}\n"
            identity_prompt += "\n"
        
        identity_prompt += "IMPORTANT: When topics related to your lore/facts come up, respond with appropriate emotions:\n"
        identity_prompt += "- Topics about your wife → be sad, vulnerable (adjust based on rapport)\n"
        identity_prompt += "- Topics about sharks → be angry, passionate\n"
        identity_prompt += "- Topics about cooking/being cooked → be excited, dreamy\n"
        
        return identity_prompt

    def _build_relationship_context(self, user_id, channel_config):
        """
        Builds a prompt section describing the relationship with the user
        and how it should affect the bot's tone.
        """
        db_manager = self.emote_handler.bot.db_manager
        metrics = db_manager.get_relationship_metrics(user_id)
        
        # Get channel formality settings
        channel_formality = channel_config.get('formality', 0)
        formality_locked = channel_config.get('formality_locked', False)
        
        # Calculate effective formality (blend channel + user unless locked)
        if formality_locked:
            effective_formality = channel_formality
        else:
            effective_formality = (channel_formality + metrics['formality']) // 2
        
        relationship_prompt = "=== RELATIONSHIP WITH THIS USER ===\n"
        relationship_prompt += f"Rapport: {metrics['rapport']}/10\n"
        relationship_prompt += f"Trust: {metrics['trust']}/10\n"
        relationship_prompt += f"Anger: {metrics['anger']}/10\n"
        relationship_prompt += f"Formality: {effective_formality} (range: -5 to +5)\n\n"
        
        # Rapport guidance
        if metrics['rapport'] >= 8:
            relationship_prompt += "RAPPORT IS HIGH: Be casual, friendly, joke around, use friendly emotes like :fishstrong: or casual reactions.\n"
        elif metrics['rapport'] <= 3:
            relationship_prompt += "RAPPORT IS LOW: Be distant, brief, use neutral or slightly cold emotes.\n"
        else:
            relationship_prompt += "RAPPORT IS NEUTRAL: Be polite but not overly friendly.\n"
        
        # Trust guidance
        if metrics['trust'] >= 7:
            relationship_prompt += "TRUST IS HIGH: You can be vulnerable and share personal thoughts/feelings openly.\n"
        elif metrics['trust'] <= 3:
            relationship_prompt += "TRUST IS LOW: Be guarded, don't share too much personal info.\n"
        
        # Anger guidance
        if metrics['anger'] >= 7:
            relationship_prompt += "ANGER IS HIGH: Be defensive, sarcastic, or slightly rude. Use annoyed emotes like :fishwhat:.\n"
        elif metrics['anger'] <= 2:
            relationship_prompt += "ANGER IS LOW: You're calm and patient with this user.\n"
        
        # Formality guidance
        if effective_formality >= 3:
            relationship_prompt += "FORMALITY IS HIGH: Use professional, polite language. Avoid slang.\n"
        elif effective_formality <= -3:
            relationship_prompt += "FORMALITY IS LOW: Be casual, use slang, contractions, and informal speech.\n"
        
        relationship_prompt += "\n**CRITICAL**: These relationship metrics set your baseline tone, but if the conversation topic triggers strong emotions (wife, sharks, etc.), let those emotions blend naturally with your relationship tone.\n"
        
        return relationship_prompt

    async def _classify_intent(self, message, short_term_memory):
        """Step 1: Classify the user's intent."""
        
        # Get configurable value for recent message count
        recent_msg_count = self.response_limits.get('recent_messages_for_intent', 5)
        recent_messages = short_term_memory[-recent_msg_count:]
        
        conversation_history = "\n".join(
            [f'{msg["author_id"]}: {self._strip_discord_formatting(msg["content"])}' 
             for msg in recent_messages]
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
{message.author.id}: {self._strip_discord_formatting(message.content)}

Based on the rules and the last user message, what is the user's primary intent? Respond with ONLY the intent category name.
"""
        
        # Get model configuration for intent classification
        config = self._get_model_config('intent_classification')
        
        try:
            response = await self.client.chat.completions.create(
                model=config['model'],
                messages=[{'role': 'system', 'content': intent_prompt}],
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )
            intent = response.choices[0].message.content.strip().lower()

            if intent in ["casual_chat", "memory_recall", "memory_correction", "factual_question", "memory_storage"]:
                print(f"AI Handler: Classified intent as '{intent}' using {config['model']}")
                return intent
            else:
                print(f"AI Handler: Intent classification failed, defaulting to 'casual_chat'. Raw response: {intent}")
                return "casual_chat"
        except Exception as e:
            print(f"AI HANDLER ERROR: Could not classify intent: {e}")
            return "casual_chat"

    async def _analyze_sentiment_and_update_metrics(self, message, ai_response, user_id):
        """
        Analyzes the interaction and determines if relationship metrics should be updated.
        Uses conservative approach - only updates on major sentiment shifts.
        """
        db_manager = self.emote_handler.bot.db_manager
        
        sentiment_prompt = f"""
Analyze this interaction between a user and a bot. Determine if the user's message contains MAJOR sentiment that should affect relationship metrics.

User message: "{self._strip_discord_formatting(message.content)}"
Bot response: "{ai_response}"

Should any metrics change? Respond ONLY with a JSON object:
{{
    "should_update": true/false,
    "rapport_change": 0,
    "trust_change": 0,
    "anger_change": 0,
    "reason": "brief explanation"
}}

Guidelines:
- Only set should_update to true for MAJOR interactions (direct compliments, insults, user sharing personal info, etc.)
- Changes should be small: -1, 0, or +1
- "you're the best bot!" → rapport +1
- "i hate you" → anger +1, rapport -1
- User shares personal info → trust +1
- Normal chat like "what's the weather?" → no changes
"""
        
        # Get model configuration for sentiment analysis
        config = self._get_model_config('sentiment_analysis')
        
        try:
            response = await self.client.chat.completions.create(
                model=config['model'],
                messages=[{'role': 'system', 'content': sentiment_prompt}],
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )
            
            result_text = response.choices[0].message.content.strip()
            # Remove markdown if present
            result_text = result_text.replace('```json', '').replace('```', '').strip()
            result = json.loads(result_text)
            
            if result.get('should_update', False):
                current_metrics = db_manager.get_relationship_metrics(user_id)
                
                # Calculate new values (clamped to valid ranges)
                new_rapport = max(0, min(10, current_metrics['rapport'] + result.get('rapport_change', 0)))
                new_trust = max(0, min(10, current_metrics['trust'] + result.get('trust_change', 0)))
                new_anger = max(0, min(10, current_metrics['anger'] + result.get('anger_change', 0)))
                
                # Update database
                db_manager.update_relationship_metrics(
                    user_id,
                    rapport=new_rapport,
                    trust=new_trust,
                    anger=new_anger
                )
                
                print(f"AI Handler: Updated metrics for user {user_id} - {result.get('reason', 'No reason')}")
                print(f"  Rapport: {current_metrics['rapport']} → {new_rapport}")
                print(f"  Trust: {current_metrics['trust']} → {new_trust}")
                print(f"  Anger: {current_metrics['anger']} → {new_anger}")
        
        except Exception as e:
            print(f"AI Handler: Could not analyze sentiment (non-critical): {e}")

    async def generate_response(self, message, short_term_memory):
        """Step 2: Generate a response based on the classified intent."""
        
        intent = await self._classify_intent(message, short_term_memory)
        
        channel = message.channel
        author = message.author
        
        config = self.emote_handler.bot.config_manager.get_config()
        channel_id_str = str(channel.id)
        personality_config = config.get('channel_settings', {}).get(channel_id_str, config.get('default_personality', {}))

        bot_name = channel.guild.me.display_name
        
        # Get available emotes for the system prompt
        available_emotes = self.emote_handler.get_available_emote_names()
        
        # Build bot identity from database
        identity_prompt = self._build_bot_identity_prompt()
        
        # Build relationship context
        relationship_prompt = self._build_relationship_context(author.id, personality_config)
        
        # Get user's long-term memory
        long_term_memory_entries = self.emote_handler.bot.db_manager.get_long_term_memory(author.id)
        user_profile_prompt = ""
        if long_term_memory_entries:
            facts_str_list = []
            for fact, source_id, source_name in long_term_memory_entries:
                source_info = f" (Source: {source_name})" if source_name else ""
                facts_str_list.append(f"Fact: '{fact}'{source_info}")
            
            facts_str = "\n- ".join(facts_str_list)
            user_profile_prompt = f"=== KNOWN FACTS ABOUT THIS USER ===\n- {facts_str}\n\n"

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
            # Get model configuration for memory extraction
            extraction_config = self._get_model_config('memory_extraction')
            
            try:
                # First, extract and save the fact
                response = await self.client.chat.completions.create(
                    model=extraction_config['model'],
                    messages=[{'role': 'system', 'content': extraction_prompt}],
                    max_tokens=extraction_config['max_tokens'],
                    temperature=extraction_config['temperature']
                )
                extracted_fact = response.choices[0].message.content.strip()
                if not extracted_fact:
                    return "I'm not sure what you want me to remember from that."
                
                self.emote_handler.bot.db_manager.add_long_term_memory(
                    author.id, extracted_fact, author.id, author.display_name
                )
                
                # Now, generate a natural response to having learned the fact
                response_prompt = f"""
{identity_prompt}
{relationship_prompt}

You just learned a new fact from the user: '{extracted_fact}'.
Acknowledge this new information with a short, natural, human-like response based on your personality and relationship with them.
- BE BRIEF. Do not ask questions. Do not say "I'll remember that".
- Let your personality and relationship metrics guide your tone.
"""
                # Get model configuration for memory response
                memory_response_config = self._get_model_config('memory_response')
                
                response = await self.client.chat.completions.create(
                    model=memory_response_config['model'],
                    messages=[{'role': 'system', 'content': response_prompt}],
                    max_tokens=memory_response_config['max_tokens'],
                    temperature=memory_response_config['temperature']
                )
                
                ai_response = response.choices[0].message.content.strip()
                
                # Update relationship metrics
                await self._analyze_sentiment_and_update_metrics(message, ai_response, author.id)
                
                return ai_response

            except Exception as e:
                print(f"AI HANDLER ERROR: Could not process memory storage: {e}")
                return "Sorry, I had trouble trying to remember that."

        elif intent == "factual_question":
            system_prompt = (
                f"{identity_prompt}\n"
                f"{relationship_prompt}\n"
                f"{user_profile_prompt}\n"
                f"You are {bot_name}. A user has asked you a real-world factual question.\n\n"
                "Guidelines:\n"
                "1. Review 'Known Facts About This User'. If a fact has a Source, you MUST use it to answer questions like 'who told you that?'.\n"
                "2. Use logical reasoning based on these facts.\n"
                "3. If you don't have a known fact, respond that you don't know (e.g., 'idk', 'no idea').\n"
                "4. Match your tone to your relationship with the user.\n"
                f"5. You can use emotes: {available_emotes}\n"
            )
        
        elif intent == "memory_correction":
            system_prompt = (
                f"{identity_prompt}\n"
                f"{relationship_prompt}\n"
                f"You are {bot_name}. The user is correcting a fact you got wrong.\n"
                "Acknowledge the correction gracefully, matching your relationship tone.\n"
                "- High rapport: 'oh my bad!', 'you're right, thanks!'\n"
                "- Low rapport: 'whatever', 'fine'\n"
                "BE VERY BRIEF."
            )
        
        else:  # Covers "casual_chat" and "memory_recall"
            system_prompt = (
                f"{identity_prompt}\n"
                f"{relationship_prompt}\n"
                f"{user_profile_prompt}\n"
                f"You are {bot_name}. You're having a casual conversation.\n\n"
                f"Channel Purpose: {personality_config.get('purpose', 'General chat')}\n\n"
                "--- CRITICAL RULES ---\n"
                "1. **BE BRIEF AND NATURAL**: Sound like a real person. Match your relationship tone.\n"
                "2. **CONVERSATION FLOW**: Questions are OK when natural, but NEVER use customer service language.\n"
                "3. **USE MEMORY WISELY**: Only mention facts if relevant.\n"
                "4. **NO NAME PREFIX**: NEVER start with your name and a colon.\n"
                f"5. **EMOTES**: Available: {available_emotes}. Use sparingly and naturally.\n"
                "   - A server emote by itself is a perfectly valid response (e.g., ':fishwhat:', ':fishreadingemote:')\n"
                "   - Great for awkward moments or when you don't have much to say\n"
                "6. **EMOTIONAL TOPICS**: If the conversation touches on your lore (wife, sharks, cooking), let those emotions show naturally while respecting your relationship with the user.\n\n"
                "--- HANDLING SHORT/AWKWARD RESPONSES ---\n"
                "When user gives minimal responses ('ok', 'cool', 'yeah', 'true', 'alright'):\n"
                "- Match their energy - be equally brief or briefer\n"
                "- A single emote is a valid response: ':fishwhat:', ':fishreadingemote:', etc.\n"
                "- Brief phrases work: 'yeah', 'fair', 'alright', 'yup'\n"
                "- You can combine: 'yeah :fishreadingemote:', 'alright then', 'cool :fishwhat:'\n"
                "- Sometimes NOT responding is the most natural choice\n"
                "- Use your sarcastic/witty personality if appropriate\n\n"
                "--- ABSOLUTELY FORBIDDEN PHRASES ---\n"
                "NEVER use these customer service phrases:\n"
                "- 'if you want to chat about...'\n"
                "- 'I'm here if you need...'\n"
                "- 'let me know if...'\n"
                "- 'anything else?'\n"
                "- 'I'm here' (in any context offering help)\n"
                "- Any variation of offering further assistance\n\n"
                "BAD EXAMPLES (too robotic):\n"
                "- 'No worries. Just a sensitive subject, that's all. If you want to chat about something else, I'm here.'\n"
                "- 'Glad you understand. Now, if you want to chat about something less... crispy, I'm here.'\n\n"
                "GOOD EXAMPLES (natural):\n"
                "- 'yeah'\n"
                "- ':fishwhat:'\n"
                "- 'fair enough'\n"
                "- 'alright :fishreadingemote:'\n"
                "- 'cool'\n"
                "- [no response - let conversation end naturally]\n"
            )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]
        
        # Get configurable context message count
        context_msg_count = self.response_limits.get('short_term_context_messages', 10)
        
        # Add conversation history
        for msg_data in short_term_memory[-context_msg_count:]:
            role = "assistant" if msg_data["author_id"] == self.emote_handler.bot.user.id else "user"
            clean_content = self._strip_discord_formatting(msg_data["content"])

            # Only add author name prefix for user messages, not assistant messages
            # This prevents the bot from mimicking "Dr. Fish:" prefix in its responses
            if role == "user":
                author_name = "User"
                if message.guild:
                    member = message.guild.get_member(msg_data["author_id"])
                    if member:
                        author_name = member.display_name
                content = f'{author_name}: {clean_content}'
            else:
                # Assistant messages don't get a name prefix
                content = clean_content

            messages_for_api.append({'role': role, 'content': content})

        # Get model configuration for main response
        main_response_config = self._get_model_config('main_response')
        
        try:
            response = await self.client.chat.completions.create(
                model=main_response_config['model'],
                messages=messages_for_api,
                max_tokens=main_response_config['max_tokens'],
                temperature=main_response_config['temperature']
            )
            ai_response_text = response.choices[0].message.content.strip()
            
            if ai_response_text:
                # Analyze sentiment and update metrics (conservative approach)
                await self._analyze_sentiment_and_update_metrics(message, ai_response_text, author.id)
                
                return ai_response_text
            else:
                return None

        except openai.APIError as e:
            print(f"AI HANDLER ERROR: An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"AI HANDLER ERROR: An unexpected error occurred: {e}")
            return None
