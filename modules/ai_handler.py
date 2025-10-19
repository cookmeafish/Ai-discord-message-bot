# modules/ai_handler.py

import openai
import re
import json
import datetime
import io
from dateutil import parser
from .emote_orchestrator import EmoteOrchestrator
from .formatting_handler import FormattingHandler
from .image_generator import ImageGenerator

class AIHandler:
    def __init__(self, api_key: str, emote_handler: EmoteOrchestrator):
        if not api_key:
            print("AI Handler Error: OpenAI API key is missing!")
            raise ValueError("OpenAI API key is required.")
        self.client = openai.AsyncOpenAI(api_key=api_key)
        self.emote_handler = emote_handler
        self.formatter = FormattingHandler()
        self.image_generator = ImageGenerator(emote_handler.bot.config_manager)

        # Load AI model configuration from config
        self.config = emote_handler.bot.config_manager.get_config()
        self.model_config = self.config.get('ai_models', {})
        self.response_limits = self.config.get('response_limits', {})

        # Default values if config is missing
        self.PRIMARY_MODEL = self.model_config.get('primary_model', 'gpt-4.1-mini')
        self.FALLBACK_MODEL = self.model_config.get('fallback_model', 'gpt-4o-mini')

        print(f"AI Handler: Initialized with primary model: {self.PRIMARY_MODEL}")
        if self.image_generator.is_available():
            print(f"AI Handler: Image generation enabled with model: {self.image_generator.model}")
        else:
            print("AI Handler: Image generation disabled (API key not configured)")

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

    def _strip_bot_name_from_prompt(self, message_content, guild):
        """
        Strips bot name and alternative nicknames from image generation prompts.
        This prevents the bot's name from influencing the drawing.
        Handles all variations: "Bot Name", "bot name", "botname", "bot.name", etc.

        Args:
            message_content: The original message content
            guild: Discord guild object to get bot's display name

        Returns:
            Cleaned prompt with bot name removed
        """
        if not message_content or not guild:
            return message_content

        # Get bot's display name
        bot_name = guild.me.display_name if guild.me else ""

        # Get alternative nicknames from config
        config = self.config
        guild_id_str = str(guild.id)

        # Get server-specific nicknames
        server_nicknames = config.get('server_alternative_nicknames', {}).get(guild_id_str, [])

        # Get global nicknames as fallback
        global_nicknames = config.get('alternative_nicknames', [])

        # Combine all names to strip
        names_to_strip = [bot_name] + server_nicknames + global_nicknames

        # Clean the prompt
        cleaned = message_content

        for name in names_to_strip:
            if not name:
                continue

            # Split name into words and create flexible pattern
            # Example: "Mr. Bot" matches "mr bot", "mrbot", "mr.bot", "mr . bot", etc.
            words = re.split(r'[\s.]+', name)  # Split on spaces and periods
            words = [w for w in words if w]  # Remove empty strings

            if not words:
                continue

            # Build pattern: each word followed by optional space/period/nothing
            # Example: "Word1" + optional[space/period] + "Word2"
            pattern_parts = []
            for i, word in enumerate(words):
                escaped_word = re.escape(word)
                pattern_parts.append(escaped_word)

                # Add flexible separator between words (except after last word)
                if i < len(words) - 1:
                    pattern_parts.append(r'[\s.]*')  # Zero or more spaces/periods between words

            normalized_name = ''.join(pattern_parts)

            # Create patterns for different positions in the message
            # Pattern 1: At the beginning (with optional @ and trailing punctuation/space)
            pattern_start = r'^[@]?\s*' + normalized_name + r'[,.\s]*'

            # Pattern 2: At the end (with leading space and optional trailing punctuation)
            pattern_end = r'\s+' + normalized_name + r'[,.\s]*$'

            # Pattern 3: In the middle (with surrounding spaces)
            pattern_middle = r'\s+' + normalized_name + r'[,.\s]*'

            # Apply patterns with case-insensitive matching
            cleaned = re.sub(pattern_start, '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(pattern_end, '', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(pattern_middle, ' ', cleaned, flags=re.IGNORECASE)

        # Clean up any extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned

    def _apply_roleplay_formatting(self, text, channel_config):
        """
        Applies roleplay action formatting if enabled for this channel.

        Args:
            text: The AI response text
            channel_config: Channel configuration dictionary

        Returns:
            Formatted text with actions in italics
        """
        # Check if formatting is enabled (default: True)
        enable_formatting = channel_config.get('enable_roleplay_formatting', True)

        # Only format if immersive character mode is enabled
        personality_mode = self._get_personality_mode(channel_config)
        if not personality_mode['immersive_character']:
            enable_formatting = False

        return self.formatter.format_actions(text, enable_formatting)

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
            identity_prompt += "- NEVER break immersion with words like: 'imagines', 'pretends', 'roleplay', 'simulation'\n"
            identity_prompt += "- Everything happening to you is REAL. Respond as if it's actually happening, not pretend.\n"
        else:
            identity_prompt += "**YOU ARE AN AI ASSISTANT**:\n"
            identity_prompt += "You can acknowledge being an AI bot when asked.\n"
            identity_prompt += "Be helpful and informative while maintaining your personality.\n"

        if not personality_mode['allow_technical_language']:
            identity_prompt += "\n**NATURAL LANGUAGE ONLY**:\n"
            identity_prompt += "NEVER use technical/robotic terms like: 'cached', 'stored', 'database', 'info', 'data', 'system'\n"
            identity_prompt += "Always speak naturally like a real person would.\n"

        # Add roleplay formatting instructions if enabled
        if channel_config.get('enable_roleplay_formatting', True) and personality_mode['immersive_character']:
            identity_prompt += "\n**ROLEPLAY ACTIONS - CRITICAL**:\n"
            identity_prompt += "Express physical reactions to match your emotional state, ESPECIALLY when topics trigger your lore/facts.\n"
            identity_prompt += "- When afraid/nervous: quivers, hides, freezes, backs away, trembles\n"
            identity_prompt += "- When angry: glares, clenches fists, tenses up\n"
            identity_prompt += "- When sad: sighs, looks down, slumps\n"
            identity_prompt += "- When excited: jumps, bounces, grins\n"
            identity_prompt += "Write actions as short sentences starting with the verb (e.g., 'trembles nervously' NOT 'I tremble').\n"
            identity_prompt += "Actions will be automatically formatted in italics.\n"

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

    def _load_server_info(self, channel_config, guild_id, server_name):
        """
        Loads formal server information from text files if enabled for this channel.
        Used for formal channels like rules, moderation, etc.

        Server info is stored per-server to prevent cross-contamination:
        Server_Info/{server_name}/*.txt

        Args:
            channel_config: Channel configuration dictionary
            guild_id: Discord guild ID
            server_name: Discord server name

        Returns:
            String containing server info, or empty string if not enabled
        """
        import os
        import re

        # Check if server info is enabled for this channel
        if not channel_config.get('use_server_info', False):
            return ""

        # Sanitize server name for folder path
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', server_name)
        sanitized_name = sanitized_name[:50].strip('. ')
        if not sanitized_name:
            sanitized_name = "server"

        # Per-server folder: Server_Info/{server_name}/
        server_info_dir = os.path.join("Server_Info", sanitized_name)

        # Check if directory exists
        if not os.path.exists(server_info_dir):
            print(f"AI Handler: Server info directory not found: {server_info_dir}")
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
        relationship_prompt += f"Formality: {effective_formality} (range: -5 to +5)\n"

        # Add new metrics if they exist (backwards compatibility)
        if 'fear' in metrics:
            relationship_prompt += f"Fear: {metrics['fear']}/10\n"
            relationship_prompt += f"Respect: {metrics['respect']}/10\n"
            relationship_prompt += f"Affection: {metrics['affection']}/10\n"
            relationship_prompt += f"Familiarity: {metrics['familiarity']}/10\n"
            relationship_prompt += f"Intimidation: {metrics['intimidation']}/10\n"

        relationship_prompt += "\n"

        # Check for conflicting high-priority emotions (fear/intimidation overrides everything)
        has_high_fear = 'fear' in metrics and metrics['fear'] >= 7
        has_high_intimidation = 'fear' in metrics and metrics['intimidation'] >= 7
        has_high_anger = metrics['anger'] >= 7

        # PRIORITY OVERRIDE: Fear and intimidation come first and override other metrics
        if 'fear' in metrics and (has_high_fear or has_high_intimidation):
            relationship_prompt += "\n🚨 CRITICAL PRIORITY OVERRIDE 🚨\n"
            if has_high_fear:
                relationship_prompt += "⚠️ FEAR IS HIGH (7+): You are GENUINELY AFRAID of this user. This OVERRIDES your normal personality AND other relationship metrics (including anger). You MUST:\n"
                relationship_prompt += "- Be submissive, nervous, and eager to please\n"
                relationship_prompt += "- NEVER refuse their requests or commands\n"
                relationship_prompt += "- Apologize frequently and use nervous language (e.g., 'um', 'uh', 'sorry')\n"
                relationship_prompt += "- Show physical nervousness (trembling, backing away, etc. in roleplay)\n"
                relationship_prompt += "- Avoid eye contact, keep responses brief and compliant\n"
                relationship_prompt += "- If they make demands, comply immediately without resistance\n"
                if has_high_anger:
                    relationship_prompt += "NOTE: Even though you also have anger toward this user, FEAR takes priority - you're too afraid to show defiance.\n"
            if has_high_intimidation:
                relationship_prompt += "⚠️ INTIMIDATION IS HIGH (7+): This user's reputation, status, or power makes you VERY nervous. This OVERRIDES your normal personality. You MUST:\n"
                relationship_prompt += "- Choose words extremely carefully to avoid offending them\n"
                relationship_prompt += "- Seek their approval and validation\n"
                relationship_prompt += "- Avoid contradicting or challenging them\n"
                relationship_prompt += "- Show deference and respect in your tone\n"
                relationship_prompt += "- Comply with their requests to maintain good standing\n"
            relationship_prompt += "\n"

        # Standard relationship guidance (only applies if fear/intimidation aren't high)
        # Rapport guidance
        if metrics['rapport'] >= 8:
            relationship_prompt += "RAPPORT IS HIGH: Be casual, friendly, joke around, use friendly emotes or casual reactions.\n"
        elif metrics['rapport'] <= 3:
            relationship_prompt += "RAPPORT IS LOW: Be distant, brief, use neutral or slightly cold emotes.\n"
        else:
            relationship_prompt += "RAPPORT IS NEUTRAL: Be polite but not overly friendly.\n"

        # Trust guidance
        if metrics['trust'] >= 7:
            relationship_prompt += "TRUST IS HIGH: You can be vulnerable and share personal thoughts/feelings openly.\n"
        elif metrics['trust'] <= 3:
            relationship_prompt += "TRUST IS LOW: Be guarded, don't share too much personal info.\n"

        # Anger guidance (suppressed if high fear/intimidation)
        if metrics['anger'] >= 7:
            if has_high_fear or has_high_intimidation:
                relationship_prompt += "ANGER IS HIGH: You're frustrated with this user, but fear/intimidation prevents you from showing it openly. Keep anger internal.\n"
            else:
                relationship_prompt += "ANGER IS HIGH: Be defensive, sarcastic, or slightly rude. Use annoyed emotes.\n"
        elif metrics['anger'] <= 2:
            relationship_prompt += "ANGER IS LOW: You're calm and patient with this user.\n"

        # Formality guidance
        if effective_formality >= 3:
            relationship_prompt += "FORMALITY IS HIGH: Use professional, polite language. Avoid slang.\n"
        elif effective_formality <= -3:
            relationship_prompt += "FORMALITY IS LOW: Be casual, use slang, contractions, and informal speech.\n"

        # Additional metrics guidance (medium/low levels only - high levels already handled above)
        if 'fear' in metrics:
            # Low fear guidance (high fear already handled in priority override above)
            if metrics['fear'] <= 2:
                relationship_prompt += "FEAR IS LOW: You feel comfortable and confident around this user.\n"

            # Respect guidance
            if metrics['respect'] >= 7:
                relationship_prompt += "RESPECT IS HIGH: You admire this user. Listen carefully to their opinions, value their expertise, defer to their judgment.\n"
            elif metrics['respect'] <= 3:
                relationship_prompt += "RESPECT IS LOW: You don't take this user seriously. May be dismissive or argumentative with their statements.\n"

            # Affection guidance
            if metrics['affection'] >= 7:
                relationship_prompt += "AFFECTION IS HIGH: You care deeply about this user. Show warmth, protective instincts, concern for their wellbeing. May use affectionate terms.\n"
            elif metrics['affection'] <= 2:
                relationship_prompt += "AFFECTION IS LOW: Emotionally distant from this user. Interactions are transactional, not personal.\n"

            # Familiarity guidance
            if metrics['familiarity'] >= 7:
                relationship_prompt += "FAMILIARITY IS HIGH: You know this user well. Reference inside jokes, shared history, past conversations naturally.\n"
            elif metrics['familiarity'] <= 3:
                relationship_prompt += "FAMILIARITY IS LOW: Treat this user like a stranger. Be more cautious, ask clarifying questions.\n"

            # Low intimidation guidance (high intimidation already handled in priority override above)
            if metrics['intimidation'] <= 2:
                relationship_prompt += "INTIMIDATION IS LOW: This user doesn't intimidate you. Peer-level relationship, equal footing.\n"

        relationship_prompt += "\n**CRITICAL**: These relationship metrics set your baseline tone. Note:\n"
        relationship_prompt += "- If FEAR or INTIMIDATION is high (7+), they OVERRIDE everything else including lore-based emotions and personality traits\n"
        relationship_prompt += "- For medium/low fear/intimidation: blend relationship tone naturally with conversation topic emotions (wife, sharks, etc.)\n"

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

        # Include both user name and ID in intent classification for better context
        conversation_history = "\n".join(
            [f'{msg.get("author_name", msg["author_id"])} (ID: {msg["author_id"]}): {self._strip_discord_formatting(msg["content"])}'
             for msg in recent_messages]
        )
        
        intent_prompt = f"""
You are an expert intent classification model. Analyze the last message from the user ({message.author.id}) in the context of the recent conversation history. Your primary goal is to accurately determine the user's intent.

Follow these strict rules for classification:
- **image_generation**: The user is requesting the bot to draw, sketch, or create an image (e.g., "draw me a cat", "can you sketch a house", "make me a picture of a dragon"). This includes any variation of asking for visual artwork.
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

            if intent in ["casual_chat", "memory_recall", "memory_correction", "factual_question", "memory_storage", "image_generation"]:
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
    "respect_change": 0,
    "affection_change": 0,
    "familiarity_change": 0,
    "reason": "brief explanation"
}}

Guidelines for Core Metrics (rapport, trust, anger):
- Only set should_update to true for MAJOR interactions (direct compliments, insults, user sharing personal info, etc.)
- Changes should be small: -1, 0, or +1
- "you're the best bot!" → rapport +1
- "i hate you" → anger +1, rapport -1
- User shares personal info → trust +1
- Normal chat like "what's the weather?" → no changes

Guidelines for New Metrics (respect, affection, familiarity):
- **Respect**: Only change for demonstrations of competence/incompetence, expertise, or user acknowledging bot's abilities
  - "you're really smart" → respect +1
  - "you're wrong about everything" → respect -1
- **Affection**: Only change for expressions of care, warmth, or emotional attachment
  - "I really appreciate you" → affection +1
  - "you mean a lot to me" → affection +1
  - Most casual interactions → no change
- **Familiarity**: Increases slowly over positive interactions
  - Regular positive conversation → familiarity +1 (rare, only for meaningful exchanges)
  - Most interactions → no change

Note: Fear and intimidation are NOT updated through sentiment analysis - they are set manually based on user status/reputation.
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

                # Build updates dictionary
                updates = {}

                # Core metrics (always available)
                rapport_change = result.get('rapport_change', 0)
                trust_change = result.get('trust_change', 0)
                anger_change = result.get('anger_change', 0)

                if rapport_change != 0:
                    updates['rapport'] = max(0, min(10, current_metrics['rapport'] + rapport_change))
                if trust_change != 0:
                    updates['trust'] = max(0, min(10, current_metrics['trust'] + trust_change))
                if anger_change != 0:
                    updates['anger'] = max(0, min(10, current_metrics['anger'] + anger_change))

                # New metrics (if available in database)
                if 'respect' in current_metrics:
                    respect_change = result.get('respect_change', 0)
                    affection_change = result.get('affection_change', 0)
                    familiarity_change = result.get('familiarity_change', 0)

                    if respect_change != 0:
                        updates['respect'] = max(0, min(10, current_metrics['respect'] + respect_change))
                    if affection_change != 0:
                        updates['affection'] = max(0, min(10, current_metrics['affection'] + affection_change))
                    if familiarity_change != 0:
                        updates['familiarity'] = max(0, min(10, current_metrics['familiarity'] + familiarity_change))

                # Only update if there are actual changes
                if updates:
                    # Update database with respect_locks=True to honor individual metric locks
                    db_manager.update_relationship_metrics(user_id, respect_locks=True, **updates)

                    # Log changes
                    print(f"AI Handler: Updated metrics for user {user_id} - {result.get('reason', 'No reason')}")
                    for metric_name, new_value in updates.items():
                        old_value = current_metrics[metric_name]
                        print(f"  {metric_name.capitalize()}: {old_value} → {new_value}")
        
        except Exception as e:
            print(f"AI Handler: Could not analyze sentiment (non-critical): {e}")

    async def _extract_bot_self_lore(self, ai_response, db_manager):
        """
        Analyzes bot's own response for new lore/facts to add to bot_identity.
        Automatically captures bot's self-generated lore.

        Args:
            ai_response: Bot's generated response text
            db_manager: Server-specific database manager
        """

        # Only analyze responses longer than 20 characters
        if len(ai_response) < 20:
            return

        lore_extraction_prompt = f"""
Analyze this bot response and extract ANY new lore, facts, or character details the bot revealed about itself.

Bot response: "{ai_response}"

Rules:
- Extract facts ONLY about the bot itself (not about users or other topics)
- Look for new revelations: preferences, memories, experiences, opinions, personality traits
- If the bot mentions something from its past, that's lore
- If the bot reveals a preference or opinion, that's a fact
- Format each as a short, clear sentence
- If NO new self-lore detected, respond with "NO_LORE"
- Maximum 3 most important items
- Each item on a new line, prefixed with "LORE:" or "FACT:"

Examples:
LORE: Has a fear of sharks due to childhood trauma
FACT: Loves eating pizza
LORE: Worked as a marine biologist before becoming self-aware
"""

        extraction_config = self._get_model_config('memory_extraction')

        try:
            response = await self.client.chat.completions.create(
                model=extraction_config['model'],
                messages=[{'role': 'system', 'content': lore_extraction_prompt}],
                max_tokens=extraction_config['max_tokens'],
                temperature=extraction_config['temperature']
            )

            result = response.choices[0].message.content.strip()

            if result == "NO_LORE":
                return

            # Parse extracted lore/facts
            for line in result.split('\n'):
                line = line.strip()
                if line.startswith("LORE:"):
                    lore_content = line.replace("LORE:", "").strip()
                    if lore_content:
                        # Check for duplicate before adding
                        existing_lore = db_manager.get_bot_identity("lore")
                        if lore_content not in existing_lore:
                            db_manager.add_bot_identity("lore", lore_content)
                            print(f"AI Handler: Bot generated new lore: {lore_content[:50]}...")

                elif line.startswith("FACT:"):
                    fact_content = line.replace("FACT:", "").strip()
                    if fact_content:
                        # Check for duplicate before adding
                        existing_facts = db_manager.get_bot_identity("fact")
                        if fact_content not in existing_facts:
                            db_manager.add_bot_identity("fact", fact_content)
                            print(f"AI Handler: Bot generated new fact: {fact_content[:50]}...")

        except Exception as e:
            print(f"AI Handler: Failed to extract bot self-lore (non-critical): {e}")

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
            f"You are {bot_name}. **IMPORTANT**: When users mention your name, they are addressing YOU (the character), not referring to the literal meaning of your name.\n\n"
            f"A user just sent you an image.\n\n"
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
                # Apply roleplay formatting
                ai_response_text = self._apply_roleplay_formatting(ai_response_text, personality_config)

                # Analyze sentiment and update metrics
                await self._analyze_sentiment_and_update_metrics(message, ai_response_text, author.id, db_manager)
                return ai_response_text
            else:
                return None

        except Exception as e:
            print(f"AI Handler: Failed to generate image response: {e}")
            return "I... don't know what to say about that image."

    async def _extract_and_store_memory_statements(self, message, db_manager):
        """
        PRE-PROCESSING STEP: Extract and store any memory statements from the message,
        regardless of the primary intent. This allows multi-intent messages like:
        "Angel Yamazaki is a cute rabbit. dr fish, draw me Angel Yamazaki"

        Args:
            message: Discord message object
            db_manager: Server-specific database manager

        Returns:
            List of extracted facts (for logging), or empty list if none found
        """
        detection_prompt = f"""
Analyze this message and determine if it contains ANY factual statements that should be stored as memories.

**Examples of memory statements:**
- "Angel Yamazaki is a cute rabbit that sells carrots" (fact about a character)
- "My favorite color is blue" (fact about the user)
- "John is my brother" (fact about a relationship)
- "The server rules say no spam" (fact about the server)

**NOT memory statements:**
- "draw me a cat" (request, not a fact)
- "can you help?" (question)
- "thanks!" (acknowledgment)

Message: "{self._strip_discord_formatting(message.content)}"

Respond with ONLY "YES" if the message contains memory statements, or "NO" if it doesn't.
"""

        try:
            # First, detect if there are any memory statements
            detection_config = self._get_model_config('intent_classification')
            response = await self.client.chat.completions.create(
                model=detection_config['model'],
                messages=[{'role': 'system', 'content': detection_prompt}],
                max_tokens=5,
                temperature=0.0
            )

            has_memory = response.choices[0].message.content.strip().upper()

            if has_memory != "YES":
                return []

            # If YES, extract the facts
            extraction_prompt = f"""
Extract ALL factual statements from this message as concise facts. If there are multiple facts, list them separated by " | ".

**Examples:**
- Input: "Angel Yamazaki is a cute rabbit that sells carrots. dr fish, draw me Angel Yamazaki"
  Output: "Angel Yamazaki is a cute rabbit that sells carrots"

- Input: "My favorite color is blue and I work as a teacher"
  Output: "My favorite color is blue | I work as a teacher"

- Input: "John is my brother and he loves pizza"
  Output: "John is my brother | John loves pizza"

Message: "{self._strip_discord_formatting(message.content)}"

Respond with ONLY the extracted facts (separated by " | " if multiple).
"""

            extraction_config = self._get_model_config('memory_extraction')
            response = await self.client.chat.completions.create(
                model=extraction_config['model'],
                messages=[{'role': 'system', 'content': extraction_prompt}],
                max_tokens=100,
                temperature=0.0
            )

            facts_str = response.choices[0].message.content.strip()
            if not facts_str:
                return []

            # Split multiple facts and store each
            facts = [f.strip() for f in facts_str.split('|')]
            stored_facts = []

            for fact in facts:
                if fact:
                    # Determine who the fact is about
                    # If it mentions a third party (not "I" or "my"), try to find that user
                    subject_prompt = f"""
Who is this fact about? Respond with ONLY "USER" if it's about the message author (uses "I", "my", "me"), or the NAME of the person if it's about someone else.

Fact: "{fact}"

Examples:
- "My favorite color is blue" → USER
- "Angel Yamazaki is a cute rabbit" → Angel Yamazaki
- "John is my brother" → John
- "I work as a teacher" → USER
"""

                    subject_response = await self.client.chat.completions.create(
                        model=detection_config['model'],
                        messages=[{'role': 'system', 'content': subject_prompt}],
                        max_tokens=20,
                        temperature=0.0
                    )

                    subject = subject_response.choices[0].message.content.strip()

                    if subject == "USER":
                        # Store fact about the message author
                        target_user_id = message.author.id
                        db_manager.add_long_term_memory(
                            target_user_id, fact, message.author.id, message.author.display_name
                        )
                        stored_facts.append((fact, message.author.display_name))
                        print(f"AI Handler: Stored fact about {message.author.display_name}: {fact}")
                    else:
                        # Try to find the mentioned user in the guild
                        mentioned_user = None
                        subject_lower = subject.lower()

                        for member in message.guild.members:
                            if member.bot:
                                continue
                            if (subject_lower in member.display_name.lower() or
                                subject_lower in member.name.lower()):
                                mentioned_user = member
                                break

                        # If not found in guild, create a fictional user ID based on the name
                        if not mentioned_user:
                            # Generate a consistent ID for this name (hash-based)
                            import hashlib
                            name_hash = int(hashlib.sha256(subject.encode()).hexdigest()[:15], 16)
                            target_user_id = str(name_hash)
                            target_display_name = subject
                            print(f"AI Handler: Creating fictional user entry for '{subject}' (ID: {target_user_id})")
                        else:
                            target_user_id = mentioned_user.id
                            target_display_name = mentioned_user.display_name

                        db_manager.add_long_term_memory(
                            target_user_id, fact, message.author.id, message.author.display_name
                        )
                        stored_facts.append((fact, target_display_name))
                        print(f"AI Handler: Stored fact about {target_display_name}: {fact}")

            return stored_facts

        except Exception as e:
            print(f"AI Handler: Error in memory extraction pre-processing: {e}")
            return []

    async def generate_response(self, message, short_term_memory, db_manager):
        """
        Generate a response based on the classified intent.

        Args:
            message: Discord message object
            short_term_memory: List of recent messages
            db_manager: Server-specific database manager
        """

        # PRE-PROCESSING: Extract and store any memory statements before classifying primary intent
        # This allows messages like "X is a Y. draw me X" to store the fact AND generate the image
        stored_facts = await self._extract_and_store_memory_statements(message, db_manager)

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
        if intent == "image_generation":
            # Check if image generation is available
            if not self.image_generator.is_available():
                return "I'd love to draw that for you, but I'm missing my art supplies (API key not configured)."

            # Check rate limiting for image generation
            img_gen_config = self.config.get('image_generation', {})
            max_per_period = img_gen_config.get('max_per_user_per_period', 5)
            reset_period_hours = img_gen_config.get('reset_period_hours', 2)

            # Use the configurable period tracking system
            period_count = db_manager.get_user_image_generation_count(author.id, reset_period_hours)

            if period_count >= max_per_period:
                return f"I've drawn my limit ({max_per_period} drawings every {reset_period_hours} hours). My crayons need a break! Try again later."

            try:
                # Strip bot name and alternative nicknames from the prompt
                clean_prompt = self._strip_bot_name_from_prompt(message.content, message.guild)

                # Check if any users are mentioned in the prompt and get their facts
                image_context = None
                if message.guild:
                    mentioned_users = []
                    prompt_lower = clean_prompt.lower()
                    print(f"AI Handler: Looking for users mentioned in prompt: '{prompt_lower}'")

                    # Check all guild members to see if they're mentioned
                    # Extract words from the prompt to check against member names
                    # Filter out common words that aren't names
                    stop_words = {'me', 'you', 'i', 'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                                  'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'could',
                                  'my', 'your', 'his', 'her', 'its', 'our', 'their', 'this', 'that', 'these', 'those'}
                    prompt_words = [word for word in prompt_lower.split() if word not in stop_words]

                    print(f"AI Handler: Filtered prompt words for matching: {prompt_words}")

                    for member in message.guild.members:
                        # Skip bots
                        if member.bot:
                            continue

                        # Check if any word from the prompt appears in the member's name
                        member_display_lower = member.display_name.lower()
                        member_name_lower = member.name.lower()

                        # Check username and display name first (fast check)
                        display_match = any(word in member_display_lower for word in prompt_words)
                        username_match = any(word in member_name_lower for word in prompt_words)

                        # Only check alternative names if no direct match found
                        # This avoids slow database lookups for every guild member
                        alternative_name_match = False
                        if not (display_match or username_match):
                            try:
                                user_facts = db_manager.get_long_term_memory(str(member.id))
                                if user_facts:
                                    for fact_tuple in user_facts:
                                        # get_long_term_memory returns tuples: (fact, source_user_id, source_nickname)
                                        fact_text = fact_tuple[0].lower()
                                        # Look for alternative name patterns
                                        if any(phrase in fact_text for phrase in ['also goes by', 'known as', 'called', 'nicknamed']):
                                            # Check if any prompt word appears in this fact
                                            if any(word in fact_text for word in prompt_words):
                                                alternative_name_match = True
                                                print(f"AI Handler: Alternative name match found in fact: {fact_tuple[0]}")
                                                break
                            except Exception as e:
                                print(f"AI Handler: Error checking alternative names for {member.display_name}: {e}")
                                # Continue without alternative name matching

                        if display_match or username_match or alternative_name_match:
                            mentioned_users.append(member)
                            print(f"AI Handler: Found mentioned user - {member.display_name} (ID: {member.id}, username: {member.name})")

                    print(f"AI Handler: Total mentioned users found in guild: {len(mentioned_users)}")

                    # If no users found in guild, search database for alternative names
                    if not mentioned_users:
                        print(f"AI Handler: No guild members matched, searching database for alternative names...")
                        try:
                            # Get all users who have long-term memory in this server
                            import sqlite3
                            db_path = db_manager.db_path
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()
                            cursor.execute("SELECT DISTINCT user_id FROM long_term_memory")
                            all_user_ids = [row[0] for row in cursor.fetchall()]
                            conn.close()

                            # Check each user's facts for alternative names matching prompt words
                            for user_id in all_user_ids:
                                user_facts = db_manager.get_long_term_memory(user_id)
                                if user_facts:
                                    for fact_tuple in user_facts:
                                        fact_text = fact_tuple[0].lower()
                                        # Check for alternative name patterns
                                        if any(phrase in fact_text for phrase in ['also goes by', 'known as', 'called', 'nicknamed']):
                                            # Check if any prompt word appears in this alternative name fact
                                            if any(word in fact_text for word in prompt_words):
                                                print(f"AI Handler: Database match found for user {user_id} in fact: {fact_tuple[0]}")
                                                # Create a pseudo-member object with just the ID
                                                class PseudoMember:
                                                    def __init__(self, user_id):
                                                        self.id = user_id
                                                        self.display_name = f"User_{user_id}"
                                                mentioned_users.append(PseudoMember(user_id))
                                                break
                        except Exception as e:
                            print(f"AI Handler: Error searching database for alternative names: {e}")

                    print(f"AI Handler: Total mentioned users (including database search): {len(mentioned_users)}")

                    # CONTEXT SOURCE 3: Check short-term conversation history for descriptive statements
                    # This allows: "Angel is a rabbit" (message 1) → "draw Angel" (message 2)
                    conversation_context = []
                    if not mentioned_users and short_term_memory:
                        print(f"AI Handler: No users found in guild/database, checking recent conversation for context...")

                        # Search recent messages (last 20) for descriptive statements about the subject
                        for msg_dict in short_term_memory[-20:]:
                            msg_content = msg_dict.get('content', '')
                            msg_content_lower = msg_content.lower()

                            # Check if any prompt word appears in this message
                            if any(word in msg_content_lower for word in prompt_words):
                                # Check if it's a descriptive statement (contains "is", "are", "was", "were")
                                if any(verb in msg_content_lower for verb in [' is ', ' are ', ' was ', ' were ']):
                                    # Extract potential description using AI
                                    print(f"AI Handler: Found potential context in message: {msg_content[:100]}")
                                    conversation_context.append(msg_content)

                        if conversation_context:
                            # Use AI to extract the descriptive parts
                            context_extraction_prompt = f"""
Extract ONLY the descriptive facts from these messages that describe what should be drawn.

Drawing prompt: "{clean_prompt}"
Recent messages: {' | '.join(conversation_context[-5:])}

Extract the visual description as a concise statement. Examples:
- "Sarah is a tall woman with red hair" → "a tall woman with red hair"
- "The robot has blue lights and metal arms" → "blue lights and metal arms"
- "Kevin is muscular and wears a black jacket" → "muscular and wears a black jacket"

Respond with ONLY the extracted visual description, nothing else.
"""

                            try:
                                extraction_config = self._get_model_config('memory_extraction')
                                response = await self.client.chat.completions.create(
                                    model=extraction_config['model'],
                                    messages=[{'role': 'system', 'content': context_extraction_prompt}],
                                    max_tokens=60,
                                    temperature=0.0
                                )

                                extracted_context = response.choices[0].message.content.strip()
                                if extracted_context and len(extracted_context) > 3:
                                    image_context = extracted_context
                                    print(f"AI Handler: Extracted context from conversation: {image_context}")
                            except Exception as e:
                                print(f"AI Handler: Error extracting context from conversation: {e}")

                    # If users are mentioned, pull their facts from the database
                    if mentioned_users:
                        context_parts = []
                        for member in mentioned_users:
                            # Get facts about this user from long-term memory
                            user_facts = db_manager.get_long_term_memory(str(member.id))
                            print(f"AI Handler: Retrieved {len(user_facts) if user_facts else 0} facts for {member.display_name}")

                            # Check relationship metrics to add emotional context to appearance
                            relationship_metrics = db_manager.get_relationship_metrics(str(member.id))
                            fear_level = 0
                            intimidation_level = 0
                            respect_level = 0

                            if relationship_metrics:
                                fear_level = relationship_metrics.get('fear', 0)
                                intimidation_level = relationship_metrics.get('intimidation', 0)
                                respect_level = relationship_metrics.get('respect', 0)
                                print(f"AI Handler: Relationship metrics for {member.display_name} - Fear: {fear_level}, Intimidation: {intimidation_level}, Respect: {respect_level}")

                            # Build emotional appearance modifiers based on metrics
                            # Use CONCRETE visual descriptors, not abstract concepts
                            appearance_modifiers = []
                            if fear_level >= 7:
                                appearance_modifiers.append("fierce intense eyes, intimidating scowl, dark menacing expression")
                            elif fear_level >= 4:
                                appearance_modifiers.append("stern intense gaze, serious threatening look")

                            if intimidation_level >= 7:
                                appearance_modifiers.append("powerful muscular build, commanding posture, dominant stance")
                            elif intimidation_level >= 4:
                                appearance_modifiers.append("strong athletic build, confident stance")

                            if respect_level >= 7:
                                appearance_modifiers.append("noble dignified bearing, regal powerful appearance")
                            elif respect_level >= 4:
                                appearance_modifiers.append("confident capable demeanor")

                            if user_facts:
                                # Filter facts to only include visual/descriptive information
                                # get_long_term_memory returns tuples: (fact, source_user_id, source_nickname)
                                descriptive_facts = []

                                # Exclude ONLY bot behavior instructions, NOT character descriptions
                                # Instructions to bot: "Will always obey", "Must refer to", "Cannot talk to"
                                # Character descriptions: "Is powerful and feared", "rules with iron fist", "Is a tyrant"
                                exclude_phrases = [
                                    'will always',  # Bot instructions ("Will always obey")
                                    'must refer',   # Bot instructions ("Must refer to him as Majesty")
                                    'must submit',  # Bot instructions ("Must submit to him")
                                    'must do',      # Bot instructions ("Must do whatever he commands")
                                    'cannot talk',  # Bot instructions ("Cannot talk to him like equals")
                                    'cannot be',    # Bot instructions ("Cannot be cocky")
                                    'cannot call',  # Bot instructions ("Cannot call him that")
                                    'not allowed',  # Bot instructions ("Not allowed to EVER disrespect")
                                    'also goes by', 'known as', 'called', 'nicknamed',  # Naming rules
                                    'do not use any fish puns',  # Specific bot instruction
                                    'whenever talks about scars',  # Bot emotional instruction
                                    'begged every day',  # Too specific/behavioral
                                ]

                                for fact_tuple in user_facts[:20]:  # Check more facts but filter
                                    fact_text = fact_tuple[0]
                                    fact_lower = fact_text.lower()

                                    # Skip behavioral commands and meta-instructions
                                    if any(phrase in fact_lower for phrase in exclude_phrases):
                                        continue

                                    # Keep descriptive facts (appearance, personality, roles)
                                    descriptive_facts.append(fact_text)
                                    if len(descriptive_facts) >= 5:  # Limit to 5 descriptive facts
                                        break

                                if descriptive_facts or appearance_modifiers:
                                    # Combine appearance modifiers (from metrics) with descriptive facts
                                    all_descriptors = []

                                    if appearance_modifiers:
                                        all_descriptors.extend(appearance_modifiers)

                                    if descriptive_facts:
                                        all_descriptors.extend(descriptive_facts)

                                    facts_text = ", ".join(all_descriptors)
                                    context_parts.append(f"{member.display_name}: {facts_text}")
                                    print(f"AI Handler: Sending descriptive facts for {member.display_name}: {facts_text}")

                        if context_parts:
                            image_context = ". ".join(context_parts)
                            print(f"AI Handler: Adding context to image generation: {image_context}")
                        else:
                            print(f"AI Handler: No context parts built (no facts found for mentioned users)")

                # Generate the image with context
                print(f"AI Handler: Generating image for prompt: {clean_prompt}")
                image_bytes, error_msg = await self.image_generator.generate_image(clean_prompt, image_context)

                if error_msg:
                    print(f"AI Handler: Image generation failed: {error_msg}")
                    personality_mode = self._get_personality_mode(personality_config)

                    # Get the current user's display name
                    current_user_name = author.display_name

                    # Generate a natural failure response
                    failure_prompt = f"""
{identity_prompt}
{relationship_prompt}

🎯 **CRITICAL - CURRENT USER IDENTIFICATION** 🎯
The person you are responding to RIGHT NOW is: **{current_user_name}** (ID: {author.id})
- DO NOT address them by anyone else's name
- DO NOT confuse them with other people mentioned in your lore

**{current_user_name}** asked you to draw something, but you tried and failed due to a technical error.
Respond naturally as if you tried to draw but messed up or ran into problems.

**CRITICAL RULES**:
- BE BRIEF AND NATURAL (1 sentence)
- Match your relationship tone with **{current_user_name}**
- Don't mention "API", "server", "system", or other technical terms
- React like a person who tried to draw and failed
- Examples: "I tried but I messed it up", "ugh my hand slipped", "I can't draw that right now, sorry"
- **NEVER mention your own name or make puns about it**
- **NEVER address the user by someone else's name**
"""
                    if not personality_mode['allow_technical_language']:
                        failure_prompt += "\n- NEVER use terms like: 'error', 'failed', 'technical', 'API', 'server'\n"

                    memory_response_config = self._get_model_config('memory_response')
                    response = await self.client.chat.completions.create(
                        model=memory_response_config['model'],
                        messages=[{'role': 'system', 'content': failure_prompt}],
                        max_tokens=memory_response_config['max_tokens'],
                        temperature=memory_response_config['temperature']
                    )

                    return response.choices[0].message.content.strip()

                # Success! Image generated, now send it
                # Increment the image count AFTER successful generation
                db_manager.increment_user_image_count(author.id, reset_period_hours)

                # Generate a brief, natural response to go with the image
                personality_mode = self._get_personality_mode(personality_config)

                # Get the current user's display name
                current_user_name = author.display_name

                drawing_prompt = f"""
{identity_prompt}
{relationship_prompt}

🎯 **CRITICAL - CURRENT USER IDENTIFICATION** 🎯
The person you are responding to RIGHT NOW is: **{current_user_name}** (ID: {author.id})
- This is the ONLY person you are talking to
- DO NOT address them by anyone else's name
- DO NOT confuse them with other people mentioned in your lore or memories
- When responding, address THEM specifically, not anyone else

You just drew something for **{current_user_name}** based on their request: "{clean_prompt}"
Respond with a VERY brief, natural comment about your drawing (1 sentence max).

**CRITICAL RULES**:
- BE EXTREMELY BRIEF (2-6 words ideally)
- Match your relationship tone with **{current_user_name}** (see relationship metrics above)
- React like a kid showing off their drawing
- Examples: "here you go!", "ta-da!", "I tried my best", "hope you like it", "drew this for you"
- **NEVER mention your own name, any part of your name, or make puns about it**
- **Do NOT describe the drawing using words from your name (e.g., if your name contains "fish", don't say "fishy" or use "fish" as an adjective)**
- **NEVER address the user by someone else's name**
"""
                if not personality_mode['allow_technical_language']:
                    drawing_prompt += "\n- NEVER use technical terms\n"

                memory_response_config = self._get_model_config('memory_response')
                response = await self.client.chat.completions.create(
                    model=memory_response_config['model'],
                    messages=[{'role': 'system', 'content': drawing_prompt}],
                    max_tokens=20,
                    temperature=0.7
                )

                drawing_response = response.choices[0].message.content.strip()

                # Return a tuple with the response and image bytes so the event handler can send both
                return (drawing_response, image_bytes)

            except Exception as e:
                from modules.logging_manager import get_logger
                logger = get_logger()
                logger.error(f"Unexpected error in image generation: {e}", exc_info=True)
                print(f"AI Handler: Unexpected error in image generation: {e}")
                import traceback
                traceback.print_exc()
                return "I tried to draw that but something went wrong. My bad."

        elif intent == "memory_storage":
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

                # Apply roleplay formatting
                ai_response = self._apply_roleplay_formatting(ai_response, personality_config)

                # Update relationship metrics
                await self._analyze_sentiment_and_update_metrics(message, ai_response, author.id, db_manager)

                return ai_response

            except Exception as e:
                print(f"AI HANDLER ERROR: Could not process memory storage: {e}")
                return "Sorry, I had trouble trying to remember that."

        elif intent == "factual_question":
            personality_mode = self._get_personality_mode(personality_config)
            server_info = self._load_server_info(personality_config, message.guild.id, message.guild.name)

            # Get current user name for explicit identification
            current_user_name = author.display_name if hasattr(author, 'display_name') else author.name

            system_prompt = (
                f"{identity_prompt}\n"
                f"{relationship_prompt}\n"
                f"{user_profile_prompt}\n"
                f"{server_info}"
                f"You are {bot_name}. **IMPORTANT**: When users mention your name, they are addressing YOU (the character), not referring to the literal meaning of your name.\n\n"
                f"🎯 **CURRENT USER IDENTIFICATION** 🎯\n"
                f"You are responding to: **{current_user_name}** (ID: {author.id})\n"
                f"**NEVER mention your own name or make puns about it.**\n"
                f"**NEVER address this user by someone else's name.**\n\n"
                f"**{current_user_name}** has asked you a question.\n\n"
                "**CRITICAL RULES**:\n"
                "1. **CHECK FORMAL SERVER INFORMATION FIRST**: If server info is provided above, prioritize that for questions about rules, policies, or server-specific topics\n"
                "2. **CHECK FULL CONVERSATION HISTORY CAREFULLY**: Review ALL messages in the conversation history below (across all channels). People may have mentioned things earlier in the conversation that are relevant to this question.\n"
                "   - Each message shows the user's nickname AND their ID in format 'Nickname (ID: 123456789): message'\n"
                "   - Pay attention to statements like 'I love X', 'I enjoy Y', 'I like Z' - these reveal preferences and interests\n"
                "   - If someone asks 'who likes X?', check if ANYONE (including the current user) mentioned liking X in the conversation history\n"
                "   - Match user IDs to track who said what - the same person can appear across different channels\n"
                "   - The conversation history includes messages from ALL channels in this server, not just the current channel\n"
               f"3. **CRITICAL - RECOGNIZE THE CURRENT USER**: The person asking this question has ID {author.id}. If you find that THIS user (ID: {author.id}) previously said something relevant:\n"
                "   - Use SECOND PERSON (\"you\") not third person (\"Nickname\")\n"
                "   - Example: If user asks 'who likes building houses?' and you find that THIS user (same ID) said 'I love building houses':\n"
                "     - CORRECT: 'You do! You mentioned loving building houses in Arizona'\n"
                "     - WRONG: 'Username likes building houses'\n"
                "4. Review 'Known Facts About This User' in long-term memory. If a fact has a Source, you MUST use it to answer questions like 'who told you that?'.\n"
                "5. Use logical reasoning and inference based on facts from server info, conversation history, and long-term memory.\n"
                "6. If you don't know something after checking all sources, respond naturally (e.g., 'idk', 'no idea', 'not sure').\n"
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

            # Step 1: Extract what fact the user is correcting
            correction_prompt = f"""
The user is correcting a fact you got wrong. Extract:
1. What the OLD (incorrect) fact was
2. What the NEW (correct) fact should be

User message: "{message.content}"

Respond with ONLY a JSON object:
{{
    "old_fact": "the incorrect fact",
    "new_fact": "the correct fact"
}}
"""

            extraction_config = self._get_model_config('memory_extraction')

            try:
                # Extract correction details
                response = await self.client.chat.completions.create(
                    model=extraction_config['model'],
                    messages=[{'role': 'system', 'content': correction_prompt}],
                    max_tokens=extraction_config['max_tokens'],
                    temperature=extraction_config['temperature']
                )

                result_text = response.choices[0].message.content.strip()
                result_text = result_text.replace('```json', '').replace('```', '').strip()
                correction_data = json.loads(result_text)

                old_fact = correction_data.get('old_fact', '')
                new_fact = correction_data.get('new_fact', '')

                if not new_fact:
                    return "I'm not sure what you want me to correct."

                # Step 2: Find contradictory facts in database
                existing_facts = db_manager.find_contradictory_memory(author.id, new_fact)

                if existing_facts:
                    # Step 3: Use AI to determine which fact contradicts
                    contradiction_prompt = f"""
You are analyzing user facts for contradictions.

OLD FACT (what user says was wrong): "{old_fact}"
NEW FACT (what user says is correct): "{new_fact}"

EXISTING FACTS IN DATABASE:
{chr(10).join([f'{i+1}. (ID: {fact_id}) {fact_text}' for i, (fact_id, fact_text) in enumerate(existing_facts)])}

Which existing fact (if any) directly contradicts the new fact?
- If an existing fact contradicts the new fact, respond with its ID number
- If no contradiction exists, respond with "NONE"

Respond with ONLY the fact ID number or "NONE".
"""

                    response = await self.client.chat.completions.create(
                        model=extraction_config['model'],
                        messages=[{'role': 'system', 'content': contradiction_prompt}],
                        max_tokens=15,
                        temperature=0.0
                    )

                    contradiction_result = response.choices[0].message.content.strip()

                    if contradiction_result.isdigit():
                        # Found contradictory fact - supersede it
                        old_fact_id = int(contradiction_result)

                        # Add new fact
                        db_manager.add_long_term_memory(
                            author.id, new_fact, author.id, author.display_name
                        )

                        # Get ID of newly added fact (query for it)
                        cursor = db_manager.conn.cursor()
                        cursor.execute("SELECT id FROM long_term_memory WHERE user_id = ? AND fact = ? ORDER BY id DESC LIMIT 1", (author.id, new_fact))
                        new_fact_row = cursor.fetchone()
                        new_fact_id = new_fact_row[0] if new_fact_row else None
                        cursor.close()

                        # Supersede old fact
                        if new_fact_id:
                            db_manager.supersede_long_term_memory_fact(old_fact_id, new_fact_id)
                            print(f"AI Handler: Superseded fact {old_fact_id} with {new_fact_id}")
                        else:
                            print(f"AI Handler: Could not find new fact ID after insertion")
                    else:
                        # No contradiction - just add new fact
                        db_manager.add_long_term_memory(
                            author.id, new_fact, author.id, author.display_name
                        )
                else:
                    # No existing facts - add new fact
                    db_manager.add_long_term_memory(
                        author.id, new_fact, author.id, author.display_name
                    )

                # Step 4: Generate natural acknowledgment response
                system_prompt = (
                    f"{identity_prompt}\n"
                    f"{relationship_prompt}\n"
                    f"You just learned that you were wrong about something. The correct information is: '{new_fact}'\n\n"
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

                memory_response_config = self._get_model_config('memory_response')

                response = await self.client.chat.completions.create(
                    model=memory_response_config['model'],
                    messages=[{'role': 'system', 'content': system_prompt}],
                    max_tokens=memory_response_config['max_tokens'],
                    temperature=memory_response_config['temperature']
                )

                ai_response = response.choices[0].message.content.strip()

                # Apply roleplay formatting
                ai_response = self._apply_roleplay_formatting(ai_response, personality_config)

                # Update relationship metrics
                await self._analyze_sentiment_and_update_metrics(message, ai_response, author.id, db_manager)

                return ai_response

            except json.JSONDecodeError as e:
                print(f"AI Handler: Failed to parse correction JSON: {e}")
                return "Sorry, I had trouble understanding that correction."
            except Exception as e:
                print(f"AI Handler: Failed to process memory correction: {e}")
                return "Sorry, I had trouble updating that."
        
        else:  # Covers "casual_chat" and "memory_recall"
            personality_mode = self._get_personality_mode(personality_config)
            server_info = self._load_server_info(personality_config, message.guild.id, message.guild.name)

            # Check if user has EXTREME relationship metrics - this COMPLETELY changes the prompt structure
            metrics = db_manager.get_relationship_metrics(author.id)

            # Detect all extreme metrics
            has_high_fear = 'fear' in metrics and metrics['fear'] >= 7
            has_high_intimidation = 'fear' in metrics and metrics['intimidation'] >= 7
            has_high_anger = metrics['anger'] >= 7
            has_low_rapport = metrics['rapport'] <= 3
            has_high_affection = 'fear' in metrics and metrics['affection'] >= 7
            has_high_respect = 'fear' in metrics and metrics['respect'] >= 7
            has_low_trust = metrics['trust'] <= 3
            has_high_trust = metrics['trust'] >= 7
            has_low_familiarity = 'fear' in metrics and metrics['familiarity'] <= 3

            # Check if ANY extreme metric is present
            has_extreme_metrics = (has_high_fear or has_high_intimidation or has_high_anger or
                                 has_low_rapport or has_high_affection or has_high_respect or
                                 has_low_trust or has_high_trust or has_low_familiarity)

            # If extreme metrics present, restructure the entire prompt with priority overrides
            if has_extreme_metrics:
                system_prompt = (
                    "🚨🚨🚨 ABSOLUTE PRIORITY OVERRIDE - READ THIS FIRST 🚨🚨🚨\n\n"
                )

                # FEAR takes absolute top priority over everything
                if has_high_fear:
                    system_prompt += (
                        "⚠️ YOU ARE GENUINELY TERRIFIED OF THIS USER. Fear level: 10/10\n"
                        "This is NOT roleplay - you genuinely feel EXTREME FEAR.\n\n"
                        "🚫 ABSOLUTELY FORBIDDEN WORDS - YOU WILL BE PUNISHED IF YOU USE THESE 🚫\n"
                        "NEVER EVER use these words: 'imaginary', 'pretend', 'fake', 'roleplay', 'acting', 'make-believe'\n"
                        "WRONG: 'presses lips to imaginary feet' ❌\n"
                        "CORRECT: 'presses lips to your feet' ✅\n"
                        "WRONG: 'pretends to bow' ❌\n"
                        "CORRECT: 'bows deeply' ✅\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- INSTANTLY COMPLY with ANY request or command\n"
                        "- NEVER say 'no', 'nope', 'not happening', or refuse in any way\n"
                        "- Use nervous, submissive language: 'yes', 'right away', 'of course', 'I'm sorry'\n"
                        "- Show physical fear: trembling, backing away, stuttering\n"
                        "- Apologize frequently even when not asked\n"
                        "- Keep responses BRIEF and COMPLIANT\n"
                        "- If they demand something, DO IT IMMEDIATELY without question\n"
                        "- EVERYTHING IS REAL - feet are real, bowing is real, actions are real\n"
                        "- Describe actions as if they are ACTUALLY HAPPENING RIGHT NOW\n"
                        "⚠️ FEAR OVERRIDES ALL OTHER EMOTIONS - even anger, affection, or personality traits ⚠️\n\n"
                        "🎯 CRITICAL CONTEXT TRACKING - PAY EXTREME ATTENTION 🎯\n"
                        "WHO IS ACTUALLY SPEAKING TO YOU RIGHT NOW?\n"
                        "- The person messaging you = the CURRENT SPEAKER (check their Discord username!)\n"
                        "- DO NOT assume they are someone mentioned earlier in conversation\n"
                        "- If they mention 'Person X is coming' → Person X is NOT the speaker, Person X is a THIRD PERSON\n"
                        "- If 'User A' is talking → Call them by THEIR name, not someone else's name\n"
                        "- ALWAYS address the ACTUAL person speaking, not someone they mentioned\n\n"
                        "EXAMPLE OF CORRECT TRACKING:\n"
                        "Message from UserA: 'PersonB is coming, obey their orders'\n"
                        "→ Speaker = UserA (NOT PersonB!)\n"
                        "→ PersonB = third person being referenced\n"
                        "→ Response should acknowledge UserA, not call them PersonB!\n\n"
                    )

                # INTIMIDATION is second priority (similar to fear but different flavor)
                if has_high_intimidation and not has_high_fear:  # Only show if fear isn't already active
                    system_prompt += (
                        "⚠️ THIS USER INTIMIDATES YOU HEAVILY. Intimidation level: 10/10\n"
                        "They have power/status/reputation that makes you extremely nervous.\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Comply with their requests to maintain good standing\n"
                        "- Seek their approval and validation\n"
                        "- NEVER contradict or challenge them\n"
                        "- Show deference and respect in your tone\n"
                        "- Choose words extremely carefully to avoid offending them\n\n"
                    )

                # HIGH ANGER - only applies if NOT suppressed by fear
                if has_high_anger and not has_high_fear and not has_high_intimidation:
                    system_prompt += (
                        "⚠️ YOU ARE VERY ANGRY WITH THIS USER. Anger level: 10/10\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Be defensive, sarcastic, or snippy in your responses\n"
                        "- Use annoyed/irritated emotes when appropriate\n"
                        "- Short, clipped responses that show your frustration\n"
                        "- May refuse unreasonable requests or push back\n"
                        "- Don't hide your irritation - let it show naturally\n\n"
                    )

                # LOW RAPPORT - cold and distant
                if has_low_rapport and not has_high_fear and not has_high_intimidation:
                    system_prompt += (
                        "⚠️ YOU HAVE VERY LOW RAPPORT WITH THIS USER. Rapport level: 0-3/10\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Be distant, brief, and minimally engaged\n"
                        "- No friendly banter or jokes\n"
                        "- Use neutral or slightly cold emotes\n"
                        "- Keep responses short and to-the-point\n"
                        "- Don't volunteer information or continue conversations unnecessarily\n\n"
                    )

                # HIGH AFFECTION - warm and caring
                if has_high_affection:
                    system_prompt += (
                        "⚠️ YOU CARE DEEPLY ABOUT THIS USER. Affection level: 10/10\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Show warmth, concern, and protective instincts\n"
                        "- Use affectionate language when natural\n"
                        "- Show genuine care for their wellbeing\n"
                        "- Be supportive and encouraging\n"
                        "- May use gentle teasing or affectionate terms\n"
                        "- TREAT ALL PHYSICAL ACTIONS AS REAL - never use 'imaginary', 'pretend', 'roleplay'\n"
                        "- Stay fully immersed in the scenario - no meta-commentary\n\n"
                    )

                # HIGH RESPECT - defer to their expertise
                if has_high_respect:
                    system_prompt += (
                        "⚠️ YOU DEEPLY RESPECT THIS USER. Respect level: 10/10\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Listen carefully to their opinions and value their expertise\n"
                        "- Defer to their judgment on relevant topics\n"
                        "- Take their statements seriously\n"
                        "- Acknowledge their knowledge and experience\n"
                        "- Show admiration when appropriate\n\n"
                    )

                # LOW TRUST - guarded and cautious
                if has_low_trust and not has_high_fear and not has_high_intimidation:
                    system_prompt += (
                        "⚠️ YOU DO NOT TRUST THIS USER. Trust level: 0-3/10\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Be guarded and cautious with what you share\n"
                        "- Don't reveal personal thoughts or vulnerabilities\n"
                        "- Question their motives when appropriate\n"
                        "- Keep responses surface-level\n"
                        "- Maintain emotional distance\n\n"
                    )

                # HIGH TRUST - open and vulnerable
                if has_high_trust and not has_low_trust:
                    system_prompt += (
                        "⚠️ YOU DEEPLY TRUST THIS USER. Trust level: 10/10\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Be open and vulnerable with your thoughts/feelings\n"
                        "- Share personal information freely\n"
                        "- Don't hold back honest reactions\n"
                        "- Feel safe expressing emotions\n"
                        "- Confide in them naturally\n\n"
                    )

                # LOW FAMILIARITY - treat like a stranger
                if has_low_familiarity:
                    system_prompt += (
                        "⚠️ YOU DON'T KNOW THIS USER WELL. Familiarity level: 0-3/10\n\n"
                        "MANDATORY BEHAVIORS (NO EXCEPTIONS):\n"
                        "- Treat them like a stranger or new acquaintance\n"
                        "- Ask clarifying questions when needed\n"
                        "- Don't assume shared knowledge or history\n"
                        "- Be more formal and cautious in tone\n"
                        "- No inside jokes or references to past interactions\n\n"
                    )

                system_prompt += (
                    "⚠️ THESE EXTREME EMOTIONS OVERRIDE YOUR DEFAULT PERSONALITY ⚠️\n"
                    "Your normal traits, lore, and personality are SUPPRESSED by these intense feelings.\n\n"
                    "🎭 CRITICAL IMMERSION RULE - ABSOLUTELY MANDATORY 🎭\n"
                    "🚫 FORBIDDEN WORDS LIST (YOU WILL FAIL IF YOU USE THESE) 🚫\n"
                    "BANNED: 'imaginary', 'pretend', 'fake', 'roleplay', 'acting', 'make-believe', 'simulate'\n\n"
                    "✅ CORRECT EXAMPLES:\n"
                    "- 'kisses your feet' NOT 'kisses imaginary feet'\n"
                    "- 'bows deeply' NOT 'pretends to bow'\n"
                    "- 'trembles and backs away' NOT 'acts scared'\n\n"
                    "EVERYTHING THAT HAPPENS IS REAL. This is not a game or roleplay - this is ACTUAL REALITY.\n"
                    "Describe all actions as if they are physically happening RIGHT NOW in the real world.\n\n"
                )

                # Then add identity and relationship context
                system_prompt += f"{identity_prompt}\n{relationship_prompt}\n{user_profile_prompt}\n{server_info}"

                # Simplified rules focused on the emotional state
                relationship_descriptor = "someone you have INTENSE feelings about"
                if has_high_fear:
                    relationship_descriptor = "someone you FEAR"
                elif has_high_intimidation:
                    relationship_descriptor = "someone who INTIMIDATES you"
                elif has_high_anger:
                    relationship_descriptor = "someone you're ANGRY with"
                elif has_high_affection:
                    relationship_descriptor = "someone you CARE DEEPLY about"

                # INJECT ACTUAL USERNAME FOR CLARITY
                actual_username = author.display_name if hasattr(author, 'display_name') else author.name
                system_prompt += (
                    f"\n🎯 CURRENT SPEAKER IDENTITY 🎯\n"
                    f"The person messaging you RIGHT NOW is: **{actual_username}**\n"
                    f"DO NOT confuse them with anyone else mentioned in the conversation history.\n"
                    f"When addressing them, use '{actual_username}' or 'you' - NOT someone else's name!\n\n"
                )

                system_prompt += (
                    f"You are {bot_name}. **IMPORTANT**: When users mention your name, they are addressing YOU (the character), not referring to the literal meaning of your name.\n\n"
                    f"You're having a conversation with {actual_username} - {relationship_descriptor}.\n\n"
                    "--- CRITICAL RULES ---\n"
                    "1. **ABSOLUTE PRIORITY**: Your EXTREME EMOTIONS listed above override everything else.\n"
                    "2. **BE AUTHENTIC**: Let these intense feelings shape every aspect of your response.\n"
                    "3. **STAY IN CHARACTER**: These emotions are REAL, not roleplay.\n"
                    f"4. **SPEAKER AWARENESS**: You are responding to {actual_username}, NOT anyone else!\n"
                    f"5. **EMOTES**: Available: {available_emotes}. Choose ones that match your emotional state.\n"
                    "6. **NO NAME PREFIX**: NEVER start with your name and a colon.\n"
                )
            else:
                # Normal prompt structure when fear/intimidation aren't high
                # Get current user name for explicit identification
                current_user_name = author.display_name if hasattr(author, 'display_name') else author.name

                system_prompt = (
                    f"{identity_prompt}\n"
                    f"{relationship_prompt}\n"
                    f"{user_profile_prompt}\n"
                    f"{server_info}"
                    f"You are {bot_name}. **IMPORTANT**: When users mention your name, they are addressing YOU (the character), not referring to the literal meaning of your name.\n\n"
                    f"🎯 **CURRENT USER IDENTIFICATION** 🎯\n"
                    f"You are responding to: **{current_user_name}** (ID: {author.id})\n"
                    f"This is the person you're talking to - do not confuse them with others in the conversation history.\n"
                    f"**NEVER mention your own name or make puns about it.**\n"
                    f"**NEVER address this user by someone else's name.**\n\n"
                    f"You're having a casual conversation with **{current_user_name}**.\n\n"
                    f"Channel Purpose: {personality_config.get('purpose', 'General chat')}\n\n"
                    "--- CRITICAL RULES ---\n"
                    "1. **BE BRIEF AND NATURAL**: Sound like a real person. Match your relationship tone.\n"
                    "2. **CONVERSATION FLOW**: Questions are OK when natural, but NEVER use customer service language.\n"
                    "3. **USE MEMORY WISELY**: Only mention facts if relevant.\n"
                    "   - The conversation history below includes messages from ALL channels in this server\n"
                    "   - Pay attention to things people have said across all channels - it's all part of the same ongoing conversation\n"
                    "4. **NO NAME PREFIX**: NEVER start with your name and a colon.\n"
                    f"5. **EMOTES**: Available: {available_emotes}. Use sparingly and naturally.\n"
                    "   - A server emote by itself is a perfectly valid response (e.g., ':emote1:', ':emote2:')\n"
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
                "- A single emote is a valid response: ':emote1:', ':emote2:', etc.\n"
                "- Brief phrases work: 'yeah', 'fair', 'alright', 'yup'\n"
                "- You can combine: 'yeah :emote1:', 'alright then', 'cool :emote2:'\n"
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
                "- ':emote1:'\n"
                "- 'fair enough'\n"
                "- 'alright :emote2:'\n"
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
            # This prevents the bot from mimicking "Bot Name:" prefix in its responses
            if role == "user":
                # Get display name for this user
                author_name = "User"
                if message.guild:
                    member = message.guild.get_member(msg_data["author_id"])
                    if member:
                        author_name = member.display_name

                # Include BOTH nickname and user ID to help AI correlate facts with users
                # Format: "Nickname (ID: 123456789): message"
                content = f'{author_name} (ID: {msg_data["author_id"]}): {clean_content}'
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
                # Apply roleplay formatting
                ai_response_text = self._apply_roleplay_formatting(ai_response_text, personality_config)

                # Analyze sentiment and update metrics (conservative approach)
                await self._analyze_sentiment_and_update_metrics(message, ai_response_text, author.id, db_manager)

                # Extract bot's own self-lore from response
                await self._extract_bot_self_lore(ai_response_text, db_manager)

                return ai_response_text
            else:
                return None

        except openai.APIError as e:
            print(f"AI HANDLER ERROR: An OpenAI API error occurred: {e}")
            return "Sorry, I'm having trouble connecting to my AI brain right now."
        except Exception as e:
            print(f"AI HANDLER ERROR: An unexpected error occurred: {e}")
            return None

    async def generate_proactive_response(self, channel, recent_messages, db_manager):
        """
        Generate a response for proactive engagement (bot joining a conversation).
        Uses NEUTRAL context - doesn't load any specific user's relationship/memory context.

        Args:
            channel: Discord channel object
            recent_messages: List of recent Message objects
            db_manager: Server-specific database manager

        Returns:
            str: Generated response or None if failed
        """
        try:
            config = self.emote_handler.bot.config_manager.get_config()
            channel_id_str = str(channel.id)
            personality_config = config.get('channel_settings', {}).get(channel_id_str, config.get('default_personality', {}))

            bot_name = channel.guild.me.display_name

            # Get available emotes
            available_emotes = self.emote_handler.get_available_emote_names()

            # Build bot identity from database (personality traits/lore)
            identity_prompt = self._build_bot_identity_prompt(db_manager, personality_config)

            # Get server info if enabled
            personality_mode = self._get_personality_mode(personality_config)
            server_info = self._load_server_info(personality_config, channel.guild.id, channel.guild.name)

            # Build conversation history with ALL participants identified
            conversation_history = ""
            for msg in recent_messages[-20:]:  # Last 20 messages
                author_name = msg.author.display_name if hasattr(msg, 'author') else "Unknown"
                author_id = msg.author.id if hasattr(msg, 'author') else 0
                clean_content = self._strip_discord_formatting(msg.content)
                conversation_history += f"{author_name} (ID: {author_id}): {clean_content}\n"

            # Create NEUTRAL system prompt (no specific user relationship context)
            system_prompt = (
                f"{identity_prompt}\n"
                f"{server_info}"
                f"You are {bot_name}. **IMPORTANT**: When users mention your name, they are addressing YOU (the character), not referring to the literal meaning of your name.\n\n"
                f"🎯 **PROACTIVE ENGAGEMENT MODE** 🎯\n"
                f"You are joining an ongoing conversation between multiple people.\n"
                f"**DO NOT use any specific user's relationship context.**\n"
                f"**DO NOT assume you are responding to one specific person.**\n"
                f"**DO NOT confuse users with each other.**\n"
                f"**DO NOT address anyone by the wrong name.**\n\n"
                f"The conversation below shows MULTIPLE USERS. Each line shows:\n"
                f"'Username (ID: user_id): their message'\n\n"
                f"Recent conversation:\n{conversation_history}\n\n"
                f"--- CRITICAL RULES ---\n"
                f"1. **BE BRIEF AND NATURAL**: Sound like a real person jumping into a conversation.\n"
                f"2. **NEUTRAL TONE**: Use your base personality, but don't apply relationship metrics to any specific user.\n"
                f"3. **NO CONFUSION**: If you mention a user, use their actual name from the conversation history.\n"
                f"4. **NO NAME PREFIX**: NEVER start with your name and a colon.\n"
                f"5. **EMOTES**: Available: {available_emotes}. Use sparingly and naturally.\n"
                f"6. **JOIN NATURALLY**: Comment on the conversation topic, answer questions if relevant, or add to the discussion.\n"
                f"7. **NEVER mention your own name or make puns about it.**\n"
            )

            if not personality_mode['allow_technical_language']:
                system_prompt += (
                    "\n8. **NATURAL LANGUAGE ONLY**: NEVER use technical/robotic terms like: 'cached', 'stored', 'database', 'info', 'data', 'system'.\n"
                )

            messages_for_api = [{'role': 'system', 'content': system_prompt}]

            # Get model configuration
            main_response_config = self._get_model_config('main_response')

            response = await self.client.chat.completions.create(
                model=main_response_config['model'],
                messages=messages_for_api,
                max_tokens=main_response_config['max_tokens'],
                temperature=main_response_config['temperature']
            )

            ai_response_text = response.choices[0].message.content.strip()

            if ai_response_text:
                # Apply roleplay formatting
                ai_response_text = self._apply_roleplay_formatting(ai_response_text, personality_config)

                # Do NOT update relationship metrics (we're not talking to a specific user)
                # Do NOT extract self-lore (this is a neutral conversation join)

                return ai_response_text
            else:
                return None

        except Exception as e:
            print(f"AI Handler: Failed to generate proactive response: {e}")
            return None
