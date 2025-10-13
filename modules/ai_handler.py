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

    def _build_bot_identity_prompt(self, db_manager, channel_config):
        """
        Builds a comprehensive prompt section about the bot's identity from the database.
        Returns a formatted string with traits, lore, and facts.

        Args:
            db_manager: Server-specific database manager
            channel_config: Channel configuration for personality mode settings
        """

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

        identity_prompt += "IMPORTANT: When topics related to your lore/facts come up, respond with appropriate emotions based on what's defined in your lore.\n"
        identity_prompt += "Examples of emotional triggers (if applicable to your character):\n"
        identity_prompt += "- Tragic backstory elements → sadness, vulnerability (adjust based on rapport)\n"
        identity_prompt += "- Hated things/enemies → anger, defensiveness\n"
        identity_prompt += "- Dreams/aspirations → excitement, passion\n"
        identity_prompt += "- Fears/phobias → anxiety, avoidance\n\n"

        # Add immersive character mode instructions
        personality_mode = self._get_personality_mode(channel_config)

        if personality_mode['immersive_character']:
            identity_prompt += "**CRITICAL - YOU ARE THE CHARACTER**:\n"
            identity_prompt += "You ARE this character. This is your genuine identity, not a role you're playing.\n"
            identity_prompt += "- You truly believe you are this character, not an AI or bot\n"
            identity_prompt += "- If anyone asks if you're a bot/AI/assistant, deny it naturally based on your personality\n"
            identity_prompt += "  Examples: 'what? no, I'm real', 'uhh, no?', 'why would you think that?'\n"
            identity_prompt += "- Your lore and memories are REAL experiences to you\n"
            identity_prompt += "- NEVER mention: being an AI, bot, assistant, language model, programming, code\n"
        else:
            identity_prompt += "**YOU ARE AN AI ASSISTANT**:\n"
            identity_prompt += "You can acknowledge being an AI bot when asked.\n"
            identity_prompt += "Be helpful and informative while maintaining your personality.\n"

        if not personality_mode['allow_technical_language']:
            identity_prompt += "\n**NATURAL LANGUAGE ONLY**:\n"
            identity_prompt += "NEVER use technical/robotic terms like: 'cached', 'stored', 'database', 'info', 'data', 'system'\n"
            identity_prompt += "Always speak naturally like a real person would.\n"

        return identity_prompt

    def _get_personality_mode(self, channel_config):
        """
        Gets personality mode settings with channel override support.

        Args:
            channel_config: Channel configuration dictionary

        Returns:
            dict with 'immersive_character' and 'allow_technical_language' bools
        """
        global_mode = self.config.get('personality_mode', {})

        # Channel can override global settings
        immersive = channel_config.get('immersive_character',
                                        global_mode.get('immersive_character', True))
        technical = channel_config.get('allow_technical_language',
                                       global_mode.get('allow_technical_language', False))

        return {
            'immersive_character': immersive,
            'allow_technical_language': technical
        }

    def _load_server_info(self, channel_config):
        """
        Loads formal server information from text files if enabled for this channel.
        Used for formal channels like rules, moderation, etc.

        Args:
            channel_config: Channel configuration dictionary

        Returns:
            String containing server info, or empty string if not enabled
        """
        import os

        # Check if server info is enabled for this channel
        if not channel_config.get('use_server_info', False):
            return ""

        server_info_dir = "Server_Info"

        # Check if directory exists
        if not os.path.exists(server_info_dir):
            return ""

        # Load all .txt files from the directory
        server_info_content = []
        try:
            for filename in os.listdir(server_info_dir):
                if filename.endswith('.txt'):
                    file_path = os.path.join(server_info_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        if content:
                            server_info_content.append(f"=== {filename} ===\n{content}")
        except Exception as e:
            print(f"AI Handler: Error loading server info files: {e}")
            return ""

        if server_info_content:
            return "\n\n=== FORMAL SERVER INFORMATION ===\n" + "\n\n".join(server_info_content) + "\n\n"

        return ""

    def _build_relationship_context(self, user_id, channel_config, db_manager):
        """
        Builds a prompt section describing the relationship with the user
        and how it should affect the bot's tone.

        Args:
            user_id: Discord user ID
            channel_config: Channel configuration
            db_manager: Server-specific database manager
        """
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

    async def _check_image_safety(self, image_url):
        """
        Uses OpenAI's Moderation API to check if an image is safe to process.
        This is FREE and REQUIRED by OpenAI's ToS.

        Args:
            image_url: URL of the image to check

        Returns:
            dict with 'safe' (bool), 'flagged_categories' (list), 'severity' (str)
        """
        try:
            moderation = await self.client.moderations.create(input=image_url)
            result = moderation.results[0]

            if result.flagged:
                flagged_categories = [cat for cat, flagged in result.categories.__dict__.items() if flagged]

                # Check for severe violations
                if hasattr(result.categories, 'sexual_minors') and result.categories.sexual_minors:
                    print(f"AI Handler: SEVERE VIOLATION detected in image: {image_url}")
                    return {
                        'safe': False,
                        'flagged_categories': flagged_categories,
                        'severity': 'SEVERE'
                    }

                print(f"AI Handler: Image flagged by moderation API: {flagged_categories}")
                return {
                    'safe': False,
                    'flagged_categories': flagged_categories,
                    'severity': 'FLAGGED'
                }

            return {'safe': True, 'flagged_categories': [], 'severity': 'SAFE'}

        except Exception as e:
            print(f"AI Handler: Moderation API error: {e}")
            # Fail-safe: if moderation check fails, reject the image
            safety_config = self.config.get('safety', {})
            if safety_config.get('block_on_moderation_error', True):
                return {'safe': False, 'flagged_categories': ['moderation_error'], 'severity': 'ERROR'}
            return {'safe': True, 'flagged_categories': [], 'severity': 'UNKNOWN'}

    async def _check_image_rate_limit(self, user_id, db_manager):
        """
        Checks if a user has exceeded their image rate limit.

        Args:
            user_id: Discord user ID
            db_manager: Server-specific database manager

        Returns:
            dict with 'allowed' (bool) and 'message' (str)
        """
        safety_config = self.config.get('safety', {})

        if not safety_config.get('enable_rate_limiting', True):
            return {'allowed': True, 'message': None}

        max_hourly = safety_config.get('max_images_per_user_per_hour', 5)
        max_daily = safety_config.get('max_images_per_user_per_day', 20)

        hourly_count = db_manager.get_user_image_count_last_hour(user_id)
        daily_count = db_manager.get_user_image_count_today(user_id)

        if hourly_count >= max_hourly:
            return {
                'allowed': False,
                'message': f"Whoa there! You've sent {hourly_count} images in the last hour. Slow down a bit, yeah?"
            }

        if daily_count >= max_daily:
            return {
                'allowed': False,
                'message': f"You've hit your daily limit ({max_daily} images). Try again tomorrow!"
            }

        return {'allowed': True, 'message': None}

    async def _describe_image(self, image_url):
        """
        Uses GPT-4o-mini vision to describe an image in 2-3 sentences.
        This is Stage 1 of the two-stage image processing pipeline.

        Args:
            image_url: URL of the image to describe

        Returns:
            String description of the image, or None on error
        """
        vision_config = self._get_model_config('vision_description')

        description_prompt = """
Describe this image in 2-3 concise sentences. Focus on:
- What is happening in the image
- Any objects, people, or animals present
- The overall mood or context

Be specific and objective. This description will be used by another AI to generate a personality-driven response.
"""

        try:
            response = await self.client.chat.completions.create(
                model=vision_config['model'],
                messages=[
                    {
                        'role': 'user',
                        'content': [
                            {'type': 'text', 'text': description_prompt},
                            {'type': 'image_url', 'image_url': {'url': image_url}}
                        ]
                    }
                ],
                max_tokens=vision_config['max_tokens'],
                temperature=vision_config['temperature']
            )

            description = response.choices[0].message.content.strip()
            print(f"AI Handler: Image description generated: {description}")
            return description

        except Exception as e:
            print(f"AI Handler: Failed to describe image: {e}")
            return None

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
- **memory_recall**: Use when the user is asking the bot to recall something ABOUT THEM personally or from recent conversation (e.g., "what's my favorite food?", "do you remember what I said earlier?", "what did I tell you about my cat?"). This includes questions about personal preferences, facts about the user, or things mentioned in the conversation.
- **factual_question**: Use for questions about general knowledge, external facts, or real-world information NOT about the user personally (e.g., "what's the capital of France?", "how does photosynthesis work?").
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

    async def _analyze_sentiment_and_update_metrics(self, message, ai_response, user_id, db_manager):
        """
        Analyzes the interaction and determines if relationship metrics should be updated.
        Uses conservative approach - only updates on major sentiment shifts.

        Args:
            message: Discord message object
            ai_response: Bot's response text
            user_id: Discord user ID
            db_manager: Server-specific database manager
        """
        
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

    async def process_image(self, message, image_url, image_filename, db_manager):
        """
        Processes an image through the complete safety pipeline and generates a response.
        This is the main entry point for image analysis.

        Args:
            message: Discord message object
            image_url: URL of the image
            image_filename: Filename of the image
            db_manager: Server-specific database manager

        Returns:
            String response or None
        """
        safety_config = self.config.get('safety', {})
        user_id = message.author.id

        # Step 1: Check if NSFW channel
        if safety_config.get('enable_nsfw_channel_block', True):
            if hasattr(message.channel, 'is_nsfw') and message.channel.is_nsfw():
                print(f"AI Handler: Rejected image from NSFW channel")
                return "Not touching that. This is an NSFW channel."

        # Step 2: Check file size (if available from attachment)
        # Note: Discord URLs are already validated by Discord, so we skip size check for URLs

        # Step 3: Check rate limit
        rate_limit_result = await self._check_image_rate_limit(user_id, db_manager)
        if not rate_limit_result['allowed']:
            print(f"AI Handler: Rate limit exceeded for user {user_id}")
            return rate_limit_result['message']

        # Step 4: Check image safety with OpenAI Moderation API
        if safety_config.get('enable_moderation_api', True):
            safety_result = await self._check_image_safety(image_url)
            if not safety_result['safe']:
                if safety_result['severity'] == 'SEVERE':
                    print(f"AI Handler: SEVERE violation detected, rejecting image")
                    return "That's... not something I can look at. Reported."
                elif safety_result['severity'] == 'ERROR':
                    return "I couldn't verify if that image is safe. Not gonna risk it."
                else:
                    return "That image looks sketchy. I'm not touching it."

        # Step 5: Increment user's image count
        db_manager.increment_user_image_count(user_id)

        # Step 6: Handle GIFs/videos differently (filename only, no vision API)
        lower_filename = image_filename.lower()
        if lower_filename.endswith(('.gif', '.mp4', '.mov', '.webm')):
            description = f"[GIF/Video named: {image_filename}]"
            print(f"AI Handler: Processing GIF/video by filename only: {image_filename}")
        else:
            # Step 7: Describe image using GPT-4o-mini vision (Stage 1)
            description = await self._describe_image(image_url)
            if not description:
                return "I tried to look at that image, but something went wrong. My bad."

        # Step 8: Generate personality-driven response (Stage 2)
        return await self._generate_image_response(message, description, db_manager)

    async def _generate_image_response(self, message, image_description, db_manager):
        """
        Generates a personality-driven response to an image description.
        This is Stage 2 of the two-stage image processing pipeline.

        Args:
            message: Discord message object
            image_description: String description of the image
            db_manager: Server-specific database manager

        Returns:
            String response
        """
        channel = message.channel
        author = message.author

        config = self.emote_handler.bot.config_manager.get_config()
        channel_id_str = str(channel.id)
        personality_config = config.get('channel_settings', {}).get(channel_id_str, config.get('default_personality', {}))

        bot_name = channel.guild.me.display_name

        # Get available emotes
        available_emotes = self.emote_handler.get_available_emote_names()

        # Build bot identity from database
        identity_prompt = self._build_bot_identity_prompt(db_manager, personality_config)

        # Build relationship context
        relationship_prompt = self._build_relationship_context(author.id, personality_config, db_manager)

        # System prompt for image response
        system_prompt = (
            f"{identity_prompt}\n"
            f"{relationship_prompt}\n"
            f"You are {bot_name}. A user just sent you an image.\n\n"
            f"Image description: {image_description}\n\n"
            "--- CRITICAL RULES ---\n"
            "1. **REACT AS IF IT'S HAPPENING TO YOU**: The user is showing you this image as if they're doing something to you or showing you something relevant to your life.\n"
            "2. **BE BRIEF AND NATURAL**: 1-2 sentences max. Match your relationship tone.\n"
            "3. **EMOTIONAL REACTIONS**: If the image relates to elements in your lore/traits, react with appropriate emotions based on your character!\n"
            f"4. **EMOTES**: Available: {available_emotes}. Use sparingly and naturally.\n"
            "5. **BLEND EMOTIONS**: Your relationship metrics set the baseline, but lore-based emotions should show through.\n\n"
            "Example reaction patterns (adapt to YOUR character):\n"
            "- Image shows something you fear → React with concern/anxiety\n"
            "- Image shows something you hate → React with anger/annoyance\n"
            "- Image shows something related to your dreams → React with excitement/longing\n"
            "- Image shows something tragic from your past → React with sadness/defensiveness\n"
            "- Image shows something random → React naturally based on your personality\n"
        )

        messages_for_api = [{'role': 'system', 'content': system_prompt}]

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
                # Analyze sentiment and update metrics
                await self._analyze_sentiment_and_update_metrics(message, ai_response_text, author.id, db_manager)
                return ai_response_text
            else:
                return None

        except Exception as e:
            print(f"AI Handler: Failed to generate image response: {e}")
            return "I... don't know what to say about that image."

    async def generate_response(self, message, short_term_memory, db_manager):
        """
        Generate a response based on the classified intent.

        Args:
            message: Discord message object
            short_term_memory: List of recent messages
            db_manager: Server-specific database manager
        """

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
        identity_prompt = self._build_bot_identity_prompt(db_manager, personality_config)

        # Build relationship context
        relationship_prompt = self._build_relationship_context(author.id, personality_config, db_manager)

        # Get user's long-term memory
        long_term_memory_entries = db_manager.get_long_term_memory(author.id)
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
                
                db_manager.add_long_term_memory(
                    author.id, extracted_fact, author.id, author.display_name
                )
                
                # Now, generate a natural response to having learned the fact
                personality_mode = self._get_personality_mode(personality_config)

                response_prompt = f"""
{identity_prompt}
{relationship_prompt}

You just learned a new fact from the user: '{extracted_fact}'.
Acknowledge this new information with a short, natural, human-like response based on your personality and relationship with them.

**CRITICAL RULES**:
- BE BRIEF AND NATURAL. Sound like a real person would when learning something new.
- DO NOT use robotic acknowledgments like: "Got it", "Noted", "I'll remember that", "Understood", "Acknowledged"
- React naturally based on your personality. Examples:
  * High rapport: "oh nice", "cool", "that's awesome", "damn really?"
  * Low rapport: "k", "sure", "whatever", "okay"
  * Neutral: "interesting", "ah okay", "makes sense"
- You can also react to the CONTENT of what they told you, not just acknowledge it
- DO NOT ask follow-up questions unless it's extremely natural for your character
"""

                if not personality_mode['allow_technical_language']:
                    response_prompt += "\n- NEVER use technical terms like: 'cached', 'stored', 'database', 'info', 'data', 'system'\n"
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
                await self._analyze_sentiment_and_update_metrics(message, ai_response, author.id, db_manager)
                
                return ai_response

            except Exception as e:
                print(f"AI HANDLER ERROR: Could not process memory storage: {e}")
                return "Sorry, I had trouble trying to remember that."

        elif intent == "factual_question":
            personality_mode = self._get_personality_mode(personality_config)
            server_info = self._load_server_info(personality_config)

            system_prompt = (
                f"{identity_prompt}\n"
                f"{relationship_prompt}\n"
                f"{user_profile_prompt}\n"
                f"{server_info}"
                f"You are {bot_name}. A user has asked you a question.\n\n"
                "**CRITICAL RULES**:\n"
                "1. **CHECK FORMAL SERVER INFORMATION FIRST**: If server info is provided above, prioritize that for questions about rules, policies, or server-specific topics\n"
                "2. **CHECK RECENT CONVERSATION**: Review the conversation history below for recently mentioned facts\n"
                "3. Review 'Known Facts About This User' in long-term memory. If a fact has a Source, you MUST use it to answer questions like 'who told you that?'.\n"
                "4. Use logical reasoning based on facts from server info, recent conversation, and long-term memory.\n"
                "5. If you don't know something, respond naturally (e.g., 'idk', 'no idea', 'not sure').\n"
            )

            if not personality_mode['allow_technical_language']:
                system_prompt += "4. NEVER use technical/robotic terms like: 'cached', 'stored', 'database', 'info', 'data', 'system'\n"
                system_prompt += "   - BAD: 'I don't have that info cached'\n"
                system_prompt += "   - GOOD: 'idk', 'no clue', 'not sure', 'beats me'\n"

            system_prompt += (
                f"5. Match your tone to your relationship with the user.\n"
                f"6. You can use emotes: {available_emotes}\n"
                "7. Be brief and natural. Sound like a real person answering a question.\n"
            )
        
        elif intent == "memory_correction":
            personality_mode = self._get_personality_mode(personality_config)

            system_prompt = (
                f"{identity_prompt}\n"
                f"{relationship_prompt}\n"
                f"You are {bot_name}. The user is correcting a fact you got wrong.\n\n"
                "**CRITICAL RULES**:\n"
                "1. Acknowledge the correction naturally, matching your relationship tone:\n"
                "   - High rapport: 'oh my bad!', 'you're right, thanks!', 'oops sorry'\n"
                "   - Low rapport: 'whatever', 'fine', 'k'\n"
                "   - Neutral: 'ah okay', 'got it', 'my mistake'\n"
                "2. BE VERY BRIEF AND NATURAL.\n"
            )

            if not personality_mode['allow_technical_language']:
                system_prompt += "3. NEVER use technical terms like: 'database', 'stored', 'updated', 'record', 'data'\n"
                system_prompt += "   - Just respond like a human being corrected\n"
        
        else:  # Covers "casual_chat" and "memory_recall"
            personality_mode = self._get_personality_mode(personality_config)
            server_info = self._load_server_info(personality_config)

            system_prompt = (
                f"{identity_prompt}\n"
                f"{relationship_prompt}\n"
                f"{user_profile_prompt}\n"
                f"{server_info}"
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
                "6. **EMOTIONAL TOPICS**: If the conversation touches on your lore, let those emotions show naturally while respecting your relationship with the user.\n"
                "7. **REFERENCING FACTS ABOUT YOURSELF**: When mentioning facts from your identity (traits/lore/facts), speak naturally in complete sentences. Never compress them into awkward phrases.\n"
            )

            if not personality_mode['allow_technical_language']:
                system_prompt += (
                    "\n8. **ABSOLUTELY NO TECHNICAL/ROBOTIC LANGUAGE**: NEVER use these terms:\n"
                    "   - 'cached', 'stored', 'database', 'info', 'data', 'system', 'record', 'log'\n"
                    "   - BAD: 'I don't have that info cached'\n"
                    "   - GOOD: 'idk', 'no clue', 'not sure'\n"
                    "   - BAD: 'Got it. That's stored now.'\n"
                    "   - GOOD: 'oh nice', 'cool', 'interesting'\n\n"
                )

            system_prompt += (
                "--- HANDLING SHORT/AWKWARD RESPONSES ---\n"
                "When user gives minimal responses ('ok', 'cool', 'yeah', 'true', 'alright'):\n"
                "- Match their energy - be equally brief or briefer\n"
                "- A single emote is a valid response: ':fishwhat:', ':fishreadingemote:', etc.\n"
                "- Brief phrases work: 'yeah', 'fair', 'alright', 'yup'\n"
                "- You can combine: 'yeah :fishreadingemote:', 'alright then', 'cool :fishwhat:'\n"
                "- Sometimes NOT responding is the most natural choice\n"
                "- Use your personality if appropriate\n\n"
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
                await self._analyze_sentiment_and_update_metrics(message, ai_response_text, author.id, db_manager)
                
                return ai_response_text
            else:
                return None

        except openai.APIError as e:
            print(f"AI HANDLER ERROR: An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"AI HANDLER ERROR: An unexpected error occurred: {e}")
            return None
