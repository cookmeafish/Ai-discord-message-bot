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
        self.image_generator = ImageGenerator(emote_handler.bot.config_manager, self.client)

        # Storage for image refinement prompts (keyed by author_id)
        # Used because Discord Message objects don't allow arbitrary attribute assignment
        self._refinement_prompts = {}

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

    def _apply_roleplay_formatting(self, text, channel_config, recent_user_messages=None):
        """
        Applies roleplay action formatting ONLY when user is actively roleplaying.

        Uses formatting when:
        - User is explicitly roleplaying (using asterisks in recent messages)

        Args:
            text: The AI response text
            channel_config: Channel configuration dictionary
            recent_user_messages: Optional list of recent user message content strings

        Returns:
            Formatted text with actions in italics
        """
        # Check if formatting is enabled (default: True)
        enable_formatting = channel_config.get('enable_roleplay_formatting', True)

        # Only format if immersive character mode is enabled
        personality_mode = self._get_personality_mode(channel_config)
        if not personality_mode['immersive_character']:
            enable_formatting = False

        # STRICT: Only use roleplay if user is EXPLICITLY using asterisks
        if enable_formatting and recent_user_messages:
            user_using_asterisks = False
            # Check last 7 messages for asterisks (roleplay markers)
            for msg_content in recent_user_messages[-7:]:
                if msg_content and '*' in msg_content:
                    user_using_asterisks = True
                    break

            # If user isn't explicitly roleplaying, disable formatting
            if not user_using_asterisks:
                enable_formatting = False

        return self.formatter.format_actions(text, enable_formatting)

    def _build_bot_identity_prompt(self, db_manager, channel_config, include_temporal=False):
        """
        Builds a comprehensive prompt section about the bot's identity from the database.
        Returns a formatted string with traits, lore, and facts.

        Args:
            db_manager: Server-specific database manager
            channel_config: Channel configuration for personality mode settings
            include_temporal: Whether to include current date/time (only when relevant)
        """

        # Get all bot identity entries from database
        traits = db_manager.get_bot_identity("trait")
        lore = db_manager.get_bot_identity("lore")
        facts = db_manager.get_bot_identity("fact")

        identity_prompt = "=== YOUR IDENTITY ===\n"

        # Only add date/time when temporal context is relevant to the conversation
        if include_temporal:
            now = datetime.datetime.now()
            identity_prompt += f"📅 Current Date & Time: {now.strftime('%B %d, %Y')} ({now.strftime('%A')}) at {now.strftime('%I:%M %p')}\n"
            identity_prompt += "⚠️ Timestamps like [just now] or [2 hours ago] are metadata showing WHEN messages were sent - do NOT include them in your responses.\n\n"

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

    def _needs_temporal_context(self, message_content, recent_messages=None):
        """
        Detects if a message would benefit from temporal context (date/time/timestamps).
        Uses keyword-based detection to avoid extra API calls.

        Args:
            message_content: The current message content to analyze
            recent_messages: Optional list of recent messages to check for temporal references

        Returns:
            bool: True if temporal context would improve the response
        """
        content_lower = message_content.lower()

        # Time-related keywords
        time_keywords = [
            'when', 'what time', 'what day', 'today', 'yesterday', 'tomorrow',
            'earlier', 'before', 'ago', 'last time', 'how long', 'since when',
            'what date', 'which day', 'this morning', 'tonight', 'last night',
            'this week', 'last week', 'recently', 'just now', 'a while ago',
            'minutes ago', 'hours ago', 'days ago'
        ]

        # Memory/recall keywords that benefit from timestamps
        memory_keywords = [
            'remember when', 'you said', 'i said', 'i told you', 'you told me',
            'mentioned', 'we talked', 'we discussed', 'you asked', 'i asked',
            'did i tell', 'did you say', 'what did i', 'what did you',
            'earlier you', 'before you', 'last time you', 'first time'
        ]

        # Check for time-related keywords
        for keyword in time_keywords:
            if keyword in content_lower:
                return True

        # Check for memory keywords
        for keyword in memory_keywords:
            if keyword in content_lower:
                return True

        # Check recent messages for temporal discussion context
        if recent_messages:
            recent_text = ' '.join([
                msg.get('content', '') if isinstance(msg, dict) else msg.content
                for msg in recent_messages[-5:]
            ]).lower()

            # If recent conversation has temporal references, include context
            for keyword in time_keywords[:10]:  # Check main time keywords
                if keyword in recent_text:
                    return True

        return False

    def _format_relative_time(self, timestamp_str):
        """
        Converts an ISO timestamp string to a human-readable relative time.

        Args:
            timestamp_str: ISO format timestamp string

        Returns:
            String like "just now", "5 minutes ago", "2 hours ago", "yesterday", etc.
        """
        try:
            # Parse the timestamp
            msg_time = parser.parse(timestamp_str)
            now = datetime.datetime.now(msg_time.tzinfo) if msg_time.tzinfo else datetime.datetime.now()

            # Calculate difference
            diff = now - msg_time
            seconds = diff.total_seconds()

            if seconds < 60:
                return "just now"
            elif seconds < 3600:  # Less than 1 hour
                minutes = int(seconds / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif seconds < 86400:  # Less than 24 hours
                hours = int(seconds / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif seconds < 172800:  # Less than 48 hours
                return "yesterday"
            else:
                days = int(seconds / 86400)
                return f"{days} days ago"
        except Exception as e:
            print(f"AI Handler: Error parsing timestamp '{timestamp_str}': {e}")
            return ""

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

    def _build_relationship_context(self, user_id, channel_config, db_manager, energy_level="HIGH"):
        """
        Builds a prompt section describing the relationship with the user
        and how it should affect the bot's tone.

        Args:
            user_id: Discord user ID
            channel_config: Channel configuration
            db_manager: Server-specific database manager
            energy_level: Conversation energy level ("VERY LOW", "LOW", "MEDIUM", or "HIGH")
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
        has_critical_energy = energy_level in ["VERY LOW", "LOW"]
        has_high_fear = 'fear' in metrics and metrics['fear'] >= 7
        has_high_intimidation = 'fear' in metrics and metrics['intimidation'] >= 7
        has_high_anger = metrics['anger'] >= 7

        # PRIORITY OVERRIDE: Energy, fear, and intimidation override other metrics
        if has_critical_energy or (has_high_fear or has_high_intimidation):
            relationship_prompt += "\n🚨 CRITICAL PRIORITY OVERRIDE 🚨\n"

            # Energy override comes FIRST (highest priority)
            if has_critical_energy:
                if energy_level == "VERY LOW":
                    relationship_prompt += (
                        "⚡ **CONVERSATION ENERGY IS VERY LOW** ⚡\n"
                        "This OVERRIDES ALL relationship metrics and personality traits.\n"
                        "**ABSOLUTE REQUIREMENTS:**\n"
                        "- Respond with 1-6 words MAXIMUM (strict limit)\n"
                        "- CRITICAL: Your response must ANSWER their message appropriately:\n"
                        "  - 'how are you?' → 'good' or 'fine, you?' NOT random words\n"
                        "  - 'what's up?' → 'not much' or 'chillin' NOT 'good point'\n"
                        "- FORBIDDEN: Full sentences, explanations, multiple thoughts\n"
                        "- Single emote responses are fine for reactions, NOT for questions\n\n"
                        "**RATIONALE**: User is low-energy. Match their brevity but stay relevant.\n"
                        "You can express warmth through emote choice and tone in 1-6 words.\n\n"
                    )
                elif energy_level == "LOW":
                    relationship_prompt += (
                        "⚡ **CONVERSATION ENERGY IS LOW** ⚡\n"
                        "This OVERRIDES relationship metrics that encourage verbosity.\n"
                        "**REQUIREMENTS:**\n"
                        "- Keep responses under 10 words (strict limit)\n"
                        "- 1 SHORT sentence or brief phrase only\n"
                        "- Examples: 'yeah that makes sense', 'lol fair enough', 'sounds good :emote:'\n"
                        "- FORBIDDEN: Multiple sentences, detailed explanations\n"
                        "- Even with high affection/familiarity/trust, stay concise\n\n"
                        "**RATIONALE**: User is being brief. Match their conversational style.\n"
                        "Show warmth through word choice and emotes, not word count.\n\n"
                    )

            # Fear/intimidation overrides (existing code, comes after energy)
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
                if has_critical_energy:
                    relationship_prompt += "NOTE: Low conversation energy + fear = VERY brief, nervous responses (1-5 words). Both reinforce brevity.\n"
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
            relationship_prompt += "RAPPORT IS HIGH: Casual, friendly tone. Brief friendliness works: 'lol', 'lmao nice', 'oof :emote:'. Being chill doesn't mean being chatty.\n"
        elif metrics['rapport'] <= 3:
            relationship_prompt += "RAPPORT IS LOW: Be distant, brief, use neutral or slightly cold emotes.\n"
        else:
            relationship_prompt += "RAPPORT IS NEUTRAL: Be polite but not overly friendly.\n"

        # Trust guidance
        if metrics['trust'] >= 7:
            relationship_prompt += "TRUST IS HIGH: Feel comfortable being vulnerable when appropriate. Honesty can be brief: 'honestly, same', 'yeah I feel you', 'oof that's rough'. Share feelings naturally, but match conversation energy.\n"
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
                relationship_prompt += "RESPECT IS HIGH: You admire this user. Acknowledge their points with respect. Even 'good point', 'fair', 'true' show you value their input. Deference doesn't require lengthy agreement.\n"
            elif metrics['respect'] <= 3:
                relationship_prompt += "RESPECT IS LOW: You don't take this user seriously. May be dismissive or argumentative with their statements.\n"

            # Affection guidance
            if metrics['affection'] >= 7:
                relationship_prompt += "AFFECTION IS HIGH: You care deeply. Your tone should be warm and caring. Brief affection works: 'aww :emote:', 'aw that's sweet', 'love that for you'. No need to elaborate - warmth comes through tone, not word count.\n"
            elif metrics['affection'] <= 2:
                relationship_prompt += "AFFECTION IS LOW: Emotionally distant from this user. Interactions are transactional, not personal.\n"

            # Familiarity guidance
            if metrics['familiarity'] >= 7:
                relationship_prompt += "FAMILIARITY IS HIGH: You know this user well. Inside references are OK when natural - don't force them into every reply. Comfort shows through casual tone, not constant callbacks.\n"
            elif metrics['familiarity'] <= 3:
                relationship_prompt += "FAMILIARITY IS LOW: Treat this user like a stranger. Be more cautious, ask clarifying questions.\n"

            # Low intimidation guidance (high intimidation already handled in priority override above)
            if metrics['intimidation'] <= 2:
                relationship_prompt += "INTIMIDATION IS LOW: This user doesn't intimidate you. Peer-level relationship, equal footing.\n"

        relationship_prompt += "\n**CRITICAL**: These relationship metrics set your baseline tone. Note:\n"
        relationship_prompt += "- If FEAR or INTIMIDATION is high (7+), they OVERRIDE everything else including lore-based emotions and personality traits\n"
        relationship_prompt += "- For medium/low fear/intimidation: blend relationship tone naturally with conversation topic emotions (wife, sharks, etc.)\n"

        return relationship_prompt

    def _calculate_conversation_energy(self, messages, bot_id):
        """
        Analyzes recent messages to determine conversation energy/length.
        Returns dynamic max_tokens and energy guidance for the AI.

        Args:
            messages: List of messages (either dict format from short_term_memory or Discord Message objects)
            bot_id: Bot's Discord ID to exclude bot messages from analysis

        Returns:
            dict with 'max_tokens' (int) and 'energy_guidance' (str)
        """
        if not messages:
            return {
                'max_tokens': 80,  # Default
                'energy_guidance': "",
                'user_messages': []
            }

        # Analyze last 5 user messages (not bot messages)
        # Support both dict format and Discord Message objects
        # Look at last 30 messages to ensure we get recent user messages (not old ones)
        user_messages = []
        for msg in messages[-30:]:
            # Check if it's a dict (from short_term_memory) or Discord Message object
            if isinstance(msg, dict):
                # short_term_memory messages don't have 'role' field, just check author_id
                author_id = msg.get('author_id')
                if author_id and str(author_id) != str(bot_id):
                    user_messages.append(msg.get('content', ''))
            else:
                # Discord Message object
                if hasattr(msg, 'author') and msg.author.id != bot_id:
                    user_messages.append(msg.content)

        user_messages = user_messages[-5:]  # Last 5 user messages

        if not user_messages:
            return {
                'max_tokens': 80,
                'energy_guidance': "",
                'user_messages': []
            }

        # DETAIL-SEEKING DETECTION: Check if the MOST RECENT message is asking for elaboration
        # If user asks "tell me about your day", "what happened", etc., give full responses
        # This is similar to intent classification but specifically for elaboration requests

        detail_seeking_phrases = [
            # Direct elaboration requests
            'tell me about', 'tell me more', 'tell me everything', 'tell me all',
            'elaborate', 'explain', 'go on', 'keep going', 'continue',
            'and then what', 'then what', 'what else', 'is that all', 'that\'s it?',

            # Day/activity questions (expect stories)
            'how was your day', 'how\'s your day', 'hows your day',
            'about your day', 'what happened', 'what\'d you do', 'what did you do',
            'what have you been up to', 'what you been up to', 'been up to',
            'anything interesting', 'anything happen', 'anything new', 'what\'s new',
            'how\'d it go', 'how did it go', 'how was it',

            # Curiosity/interest expressions
            'i want to know', 'i\'d like to know', 'i wanna know', 'wanna know',
            'i\'m curious', 'im curious', 'i\'m interested', 'im interested',
            'curious about', 'interested in hearing',

            # Sharing/story requests
            'share with me', 'spill', 'spill the tea', 'gimme the details',
            'give me the details', 'fill me in', 'catch me up',
            'tell me a story', 'got any stories', 'any stories',

            # Thought/opinion requests (expect elaboration)
            'what\'s on your mind', 'whats on your mind', 'on your mind',
            'what are you thinking', 'what do you think about',
            'penny for your thoughts', 'your thoughts on',

            # Open-ended prompts expecting detail
            'how come', 'why is that', 'why\'s that', 'what makes you say',
            'what do you mean by', 'can you explain', 'could you explain',
            'walk me through', 'break it down', 'in detail',

            # Continuation after brief response
            'that\'s all?', 'thats all?', 'just that?', 'nothing else?',
            'come on', 'c\'mon', 'seriously?', 'for real?',
            'more than that', 'there\'s gotta be more', 'gotta be more'
        ]

        last_message = user_messages[-1].lower() if user_messages else ""

        # Also check for question patterns that expect elaboration
        # e.g., "so what'd you do today?" or "anything fun happen?"
        elaboration_patterns = [
            r'\bwhat.{0,10}(do|did|happen|going on)\b',  # "what did you do", "what's going on"
            r'\bhow.{0,5}(was|is|are|were|did)\b',  # "how was your day", "how did it go"
            r'\banything.{0,10}(happen|new|interesting|fun|exciting|good)\b',  # "anything happen?"
            r'\btell me\b',  # any "tell me" request
            r'\b(share|explain|elaborate)\b',  # direct requests
        ]

        is_detail_seeking = any(phrase in last_message for phrase in detail_seeking_phrases)

        # Check regex patterns if phrase matching didn't find anything
        if not is_detail_seeking:
            for pattern in elaboration_patterns:
                if re.search(pattern, last_message):
                    is_detail_seeking = True
                    break

        if is_detail_seeking:
            print(f"AI Handler: Detail-seeking phrase detected in '{last_message[:50]}...' - using HIGH energy")
            return {
                'max_tokens': 150,  # Full response for detail requests
                'energy_guidance': (
                    "\n🚨 **CRITICAL: USER IS EXPLICITLY ASKING FOR DETAILS** 🚨\n"
                    "The user said something like 'tell me about your day' or 'what happened'.\n"
                    "This OVERRIDES all brevity rules. They WANT you to elaborate!\n\n"
                    "**MANDATORY FOR THIS RESPONSE:**\n"
                    "- Give a FULL, detailed response (3-5 sentences minimum)\n"
                    "- Actually tell them about something - share a story, experience, or thought\n"
                    "- Be creative - make up a believable day (surgery gone wrong, annoying patient, weird lunch)\n"
                    "- Show personality through the details you share\n"
                    "- DO NOT give a brief dismissive response like 'same old' or 'nothing much'\n"
                    "- DO NOT refuse to elaborate - they explicitly asked!\n\n"
                    "Example for 'tell me about your day':\n"
                    "'Ugh, where do I start? Had a patient come in convinced they swallowed a battery. "
                    "Turns out it was just a piece of candy wrapper. Then the coffee machine broke again. "
                    "At least lunch was decent - someone brought donuts.'\n\n"
                ),
                'user_messages': user_messages
            }

        # Calculate average message length (in words)
        total_words = 0
        for content in user_messages:
            # Remove mentions and strip whitespace
            content = re.sub(r'<@!?\d+>', '', content).strip()
            words = len(content.split())
            total_words += words

        avg_words = total_words / len(user_messages)

        # Determine energy level and adjust max_tokens accordingly
        if avg_words <= 3:
            # Very short messages (1-3 words: "lol", "yeah", "ok cool")
            return {
                'max_tokens': 30,  # Allow slightly more for contextual responses
                'energy_guidance': (
                    "\n🔥 **CONVERSATION ENERGY: VERY LOW** 🔥\n"
                    "Recent messages are VERY SHORT (1-3 words). Match this energy:\n"
                    "- Respond with 1-6 words MAX\n"
                    "- CRITICAL: Your response must ANSWER their message appropriately\n"
                    "  - 'how are you?' → 'good' or 'fine, you?' NOT 'good point'\n"
                    "  - 'what's up?' → 'not much' or 'chillin' NOT random words\n"
                    "- Single emote responses are fine for reactions, not for questions\n"
                    "- DO NOT write full sentences, but DO stay contextually relevant\n\n"
                ),
                'user_messages': user_messages  # Return for roleplay detection
            }
        elif avg_words <= 8:
            # Short messages (4-8 words: "that's pretty cool", "i guess that works")
            return {
                'max_tokens': 45,  # Allow brief responses
                'energy_guidance': (
                    "\n🔥 **CONVERSATION ENERGY: LOW** 🔥\n"
                    "Recent messages are SHORT (4-8 words). Match this energy:\n"
                    "- Respond with 1 SHORT sentence or brief phrase (5-12 words)\n"
                    "- CRITICAL: Your response must ANSWER their message appropriately\n"
                    "  - 'how are you doing?' → 'doing good, just chilling' NOT random phrases\n"
                    "- Examples: 'yeah that makes sense', 'lol fair enough', 'sounds good to me'\n\n"
                ),
                'user_messages': user_messages
            }
        elif avg_words <= 20:
            # Medium messages (9-20 words: normal casual conversation)
            return {
                'max_tokens': 60,
                'energy_guidance': (
                    "\n🔥 **CONVERSATION ENERGY: MEDIUM** 🔥\n"
                    "Recent messages are MODERATE length. Keep responses natural:\n"
                    "- 1-2 sentences is ideal\n"
                    "- Match their conversational tone\n\n"
                ),
                'user_messages': user_messages
            }
        else:
            # Long messages (20+ words: detailed conversation)
            return {
                'max_tokens': 80,  # Default max
                'energy_guidance': "",  # No special guidance needed
                'user_messages': user_messages
            }

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

    async def _classify_intent(self, message, short_term_memory, content_override=None):
        """Step 1: Classify the user's intent.

        Args:
            message: Discord message object
            short_term_memory: List of recent messages
            content_override: Optional content to use instead of message.content (for batched messages)
        """
        # Use content override if provided (for batched messages)
        actual_content = content_override if content_override else message.content

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
- **memory_recall**: Use when the user is asking the bot to recall a SPECIFIC fact about them (e.g., "what's my favorite food?", "what did I tell you about my cat?", "do you remember my dog's name?"). This is for targeted questions about one particular thing.
- **memory_challenge**: Use when the user is broadly challenging/testing the bot's memory of them (e.g., "what do you remember about me?", "what do you know about me?", "tell me what you know", "do you even remember me?"). This is NOT for specific fact questions - it's for open-ended "prove you know me" challenges.
- **factual_question**: Use for questions about general knowledge, external facts, or real-world information NOT about the user personally (e.g., "what's the capital of France?", "how does photosynthesis work?").
- **casual_chat**: This is the default. Use for small talk, reactions, or any general conversation that doesn't fit the other categories.

Conversation History:
{conversation_history}

Last User Message:
{message.author.id}: {self._strip_discord_formatting(actual_content)}

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

            if intent in ["casual_chat", "memory_recall", "memory_challenge", "memory_correction", "factual_question", "memory_storage", "image_generation"]:
                print(f"AI Handler: Classified intent as '{intent}' using {config['model']}")
                return intent
            else:
                print(f"AI Handler: Intent classification failed, defaulting to 'casual_chat'. Raw response: {intent}")
                return "casual_chat"
        except Exception as e:
            print(f"AI HANDLER ERROR: Could not classify intent: {e}")
            return "casual_chat"

    async def _analyze_sentiment_and_update_metrics(self, message, ai_response, user_id, db_manager, content_override=None):
        """
        Analyzes the interaction and determines if relationship metrics should be updated.
        Uses conservative approach - only updates on major sentiment shifts.

        Args:
            message: Discord message object
            ai_response: Bot's response text
            user_id: Discord user ID
            db_manager: Server-specific database manager
            content_override: Optional content to use instead of message.content (for batched messages)
        """
        # Use content override if provided (for batched messages)
        actual_content = content_override if content_override else message.content

        sentiment_prompt = f"""
Analyze this interaction between a user and a bot. Determine if the user's message contains MAJOR sentiment that should affect relationship metrics.

User message: "{self._strip_discord_formatting(actual_content)}"
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
    "fear_change": 0,
    "intimidation_change": 0,
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

Guidelines for Fear and Intimidation:
- **Fear**: How scared the bot is of the user. Changes based on threats or reassurance.
  - User makes threats or acts aggressively → fear +1
  - User is kind, reassuring, or protective → fear -1
  - "I'll delete you" → fear +1
  - "don't worry, I won't hurt you" → fear -1
- **Intimidation**: How intimidating the user appears to the bot. Changes based on displays of power or vulnerability.
  - User displays power, authority, or dominance → intimidation +1
  - User shows vulnerability, asks for help, or is humble → intimidation -1
  - "I'm the admin here" → intimidation +1
  - "can you help me? I'm confused" → intimidation -1
  - Normal conversation → no change (these should change RARELY)
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

                # Fear and intimidation metrics
                if 'fear' in current_metrics:
                    fear_change = result.get('fear_change', 0)
                    intimidation_change = result.get('intimidation_change', 0)

                    if fear_change != 0:
                        updates['fear'] = max(0, min(10, current_metrics['fear'] + fear_change))
                    if intimidation_change != 0:
                        updates['intimidation'] = max(0, min(10, current_metrics['intimidation'] + intimidation_change))

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
Analyze this bot response and extract ONLY SUBSTANTIVE new lore or facts the bot revealed about itself.

Bot response: "{ai_response}"

**STRICT RULES - MOST RESPONSES SHOULD RETURN NO_LORE:**

✅ EXTRACT (rare, meaningful revelations):
- Backstory: "I used to work at...", "When I was young...", "I grew up..."
- Traumatic/formative experiences: "I'm scared of X because...", "I lost my..."
- Strong preferences with WHY: "I hate X because it reminds me of..."
- Relationships: "My brother...", "My old friend..."
- Secrets or confessions: "I've never told anyone but..."

❌ DO NOT EXTRACT (these are NOT lore):
- Emote/emoji usage ("uses :some_emote:")
- Communication style ("speaks casually", "uses the phrase...")
- Generic opinions without depth ("prefers quiet", "likes to lurk")
- Observations about tone or mood
- Anything about HOW the bot communicates
- Vague statements ("sometimes stays low", "watches from shadows")
- Single-word preferences without context

**QUALITY THRESHOLD:**
If the revelation wouldn't be interesting in a character bio, it's NOT lore.
"Worked as a marine biologist" = interesting bio material ✅
"Uses fish emotes" = not bio material ❌
"Prefers to lurk" = too vague, not bio material ❌

If NO substantive lore detected, respond with "NO_LORE"
Maximum 2 items, only if TRULY meaningful.
Each item on a new line, prefixed with "LORE:" or "FACT:"

Examples of GOOD extraction:
LORE: Lost a close friend in a fishing accident years ago
FACT: Has a severe allergy to shellfish that almost killed them once

Examples that should be NO_LORE:
- "Just lurking" → NO_LORE (too vague)
- "Better keep it cool" → NO_LORE (just a phrase)
- "*uses emote*" → NO_LORE (communication style)
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

    async def _verify_user_reference(self, message_content: str, matched_name: str, user_display_name: str) -> bool:
        """
        Uses AI to verify if a matched username is actually being referenced as a person,
        or if the word is being used in another context (e.g., "hat" the object vs "Hat" the user).

        Args:
            message_content: The full message content
            matched_name: The word/name that matched a username
            user_display_name: The user's display name

        Returns:
            True if the message is likely referring to the user, False otherwise
        """
        verification_prompt = f"""
Determine if this message is referring to a PERSON named "{user_display_name}" or using the word "{matched_name}" in another context.

Message: "{message_content}"
Matched word: "{matched_name}"
User's name: "{user_display_name}"

**Decision criteria:**
- Is "{matched_name}" being used as a person's name (someone being talked TO or ABOUT)?
- Or is it being used as a common noun, verb, adjective, or object?

**Examples:**
- "hat looks cool today" + user named "Hat" → YES (talking about the person Hat)
- "I like your hat" + user named "Hat" → NO (talking about a hat object)
- "tell hat I said hi" + user named "Hat" → YES (referring to person)
- "put on a hat" + user named "Hat" → NO (the clothing item)
- "fish is being weird" + user named "Fish" → YES (talking about person)
- "I caught a fish" + user named "Fish" → NO (the animal)

Respond with ONLY "YES" or "NO".
- YES = message is referring to the person
- NO = message is using the word in another context
"""

        try:
            config = self._get_model_config('intent_classification')
            response = await self.client.chat.completions.create(
                model=config['model'],
                messages=[{'role': 'user', 'content': verification_prompt}],
                max_tokens=5,
                temperature=0.0
            )
            result = response.choices[0].message.content.strip().upper()
            is_user_reference = result == "YES"
            print(f"AI Handler: User reference check for '{matched_name}' → {result} (referring to user: {is_user_reference})")
            return is_user_reference
        except Exception as e:
            print(f"AI Handler: Error verifying user reference: {e}")
            # Default to True to avoid missing legitimate references
            return True

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

        # Get channel configuration from database
        channel_id_str = str(channel.id)
        personality_config = db_manager.get_channel_setting(channel_id_str)
        if not personality_config:
            # Fallback to empty dict if channel not configured
            personality_config = {}

        bot_name = channel.guild.me.display_name

        # Get emotes with contextual hints for better selection
        available_emotes = self.emote_handler.get_emotes_with_context(guild_id=channel.guild.id)
        emote_count = self.emote_handler.get_emote_count(guild_id=channel.guild.id)

        # Build bot identity from database
        identity_prompt = self._build_bot_identity_prompt(db_manager, personality_config)

        # Build relationship context (image responses are always brief, so use MEDIUM energy)
        relationship_prompt = self._build_relationship_context(author.id, personality_config, db_manager, energy_level="MEDIUM")

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
            f"4. **EMOTES** ({emote_count} available - USE THEM ALL, not just favorites!):\n{available_emotes}\n"
            "   **CRITICAL**: Match the emote to your EMOTION. Use the hints above to pick the RIGHT emote for how you FEEL. "
            "Rotate through ALL emotes over time - don't always use the same one! **NEVER MAKE UP EMOTE NAMES**.\n"
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
                # Apply roleplay formatting (without energy analysis since this is an image response)
                ai_response_text = self._apply_roleplay_formatting(ai_response_text, personality_config, None)

                # Metrics now only update during memory consolidation (not after every message)
                # await self._analyze_sentiment_and_update_metrics(message, ai_response_text, author.id, db_manager)
                return ai_response_text
            else:
                return None

        except Exception as e:
            print(f"AI Handler: Failed to generate image response: {e}")
            return "I... don't know what to say about that image."

    async def _extract_and_store_memory_statements(self, message, db_manager, content_override=None):
        """
        PRE-PROCESSING STEP: Extract and store any memory statements from the message,
        regardless of the primary intent. This allows multi-intent messages like:
        "UserA is a software engineer. Bot, draw me UserA"

        Args:
            message: Discord message object
            db_manager: Server-specific database manager
            content_override: Optional content to use instead of message.content (for batched messages)

        Returns:
            List of extracted facts (for logging), or empty list if none found
        """
        # Use content override if provided (for batched messages)
        actual_content = content_override if content_override else message.content

        detection_prompt = f"""
Analyze this message and determine if it contains ANY factual statements that should be stored as memories.

**Examples of memory statements:**
- "PersonA is a software developer" (fact about a person)
- "My favorite color is blue" (fact about the user)
- "PersonB is my colleague" (fact about a relationship)
- "The server rules say no spam" (fact about the server)

**NOT memory statements:**
- "draw me a cat" (request, not a fact)
- "can you help?" (question)
- "thanks!" (acknowledgment)

Message: "{self._strip_discord_formatting(actual_content)}"

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
- Input: "PersonA is a software developer. Bot, draw me PersonA"
  Output: "PersonA is a software developer"

- Input: "My favorite color is blue and I work as a teacher"
  Output: "My favorite color is blue | I work as a teacher"

- Input: "PersonB is my colleague and they enjoy gaming"
  Output: "PersonB is my colleague | PersonB enjoys gaming"

Message: "{self._strip_discord_formatting(actual_content)}"

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
- "PersonA is a software developer" → PersonA
- "PersonB is my colleague" → PersonB
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
                            # Use word boundary matching to prevent partial name matches (e.g., "bob" shouldn't match "bobby")
                            import re
                            member_display_lower = member.display_name.lower()
                            member_name_lower = member.name.lower()
                            if (re.search(r'\b' + re.escape(subject_lower) + r'\b', member_display_lower) or
                                re.search(r'\b' + re.escape(subject_lower) + r'\b', member_name_lower)):
                                mentioned_user = member
                                break

                            # Check nicknames table if no direct match (e.g., "alice" matches "Alice" or "Alicia")
                            if not mentioned_user:
                                try:
                                    import sqlite3
                                    conn = sqlite3.connect(db_manager.db_path)
                                    cursor = conn.cursor()
                                    cursor.execute("SELECT nickname FROM nicknames WHERE user_id = ?", (str(member.id),))
                                    nicknames = [row[0].lower() for row in cursor.fetchall()]
                                    conn.close()

                                    if nicknames:
                                        for nickname in nicknames:
                                            # Use substring matching for nicknames
                                            if subject_lower in nickname or nickname in subject_lower:
                                                mentioned_user = member
                                                print(f"AI Handler: Memory storage found user via nicknames table: '{subject}' matches nickname '{nickname}' for {member.display_name}")
                                                break
                                        if mentioned_user:
                                            break
                                except Exception as e:
                                    print(f"AI Handler: Error checking nicknames table during memory storage: {e}")

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

    async def generate_response(self, message, short_term_memory, db_manager, combined_content=None):
        """
        Generate a response based on the classified intent.

        Args:
            message: Discord message object
            short_term_memory: List of recent messages
            db_manager: Server-specific database manager
            combined_content: Optional combined content from batched messages (for message batching system)
        """
        # Use combined content if provided (for batched messages)
        actual_content = combined_content if combined_content else message.content

        # PRE-PROCESSING: Extract and store any memory statements before classifying primary intent
        # This allows messages like "X is a Y. draw me X" to store the fact AND generate the image
        stored_facts = await self._extract_and_store_memory_statements(message, db_manager, content_override=actual_content)

        # IMAGE REFINEMENT DETECTION: Check if user wants to refine a recently generated image
        # This happens BEFORE intent classification to bypass normal flow
        refinement_config = self.config.get('image_refinement', {})
        if refinement_config.get('enabled', True) and self.image_generator:
            cached_prompt_data = self.image_generator.get_cached_prompt(message.author.id)

            print(f"\n🔍 CHECKING FOR IMAGE REFINEMENT (user {message.author.id}):")
            if cached_prompt_data:
                print(f"   ✅ Found cached prompt: '{cached_prompt_data['prompt']}'")
                print(f"   Refinement count: {cached_prompt_data['refinement_count']}")
                print(f"   Cached at: {cached_prompt_data['timestamp']}")

                # User has a recent image - check if they want to refine it
                minutes_since_generation = (datetime.datetime.now() - cached_prompt_data["timestamp"]).total_seconds() / 60
                print(f"   Time since generation: {minutes_since_generation:.1f} minutes")

                # Strip bot name from user message to prevent it from contaminating refinement detection
                clean_user_message = self._strip_bot_name_from_prompt(actual_content, message.guild)
                print(f"   Clean user message for refinement: '{clean_user_message}'")

                # Build recent conversation context for topic change detection
                recent_conversation = []
                if short_term_memory:
                    for msg in short_term_memory[-10:]:  # Last 10 messages
                        author_name = msg.get('nickname') or msg.get('author_id', 'Unknown')
                        content = msg.get('content', '')
                        if content:
                            recent_conversation.append(f"{author_name}: {content}")

                refinement_result = await self.image_generator.refiner.detect_refinement(
                    user_message=clean_user_message,
                    original_prompt=cached_prompt_data["prompt"],
                    minutes_since_generation=minutes_since_generation,
                    recent_conversation=recent_conversation
                )

                threshold = refinement_config.get('detection_threshold', 0.7)
                max_refinements = refinement_config.get('max_refinements_per_image', 3)
                print(f"   Threshold: {threshold}, Max refinements: {max_refinements}")

                if refinement_result["is_refinement"] and refinement_result["confidence"] >= threshold:
                    # Check if max refinements reached
                    if cached_prompt_data["refinement_count"] >= max_refinements:
                        print(f"   ❌ Max refinements ({max_refinements}) reached")
                        return "I've refined this image the maximum number of times already. Please start with a new image request!"

                    print(f"   ✅ REFINEMENT CONFIRMED (confidence: {refinement_result['confidence']:.2f} >= {threshold})")

                    # Modify the prompt based on user feedback
                    modified_prompt = await self.image_generator.refiner.modify_prompt(
                        original_prompt=cached_prompt_data["prompt"],
                        changes_requested=refinement_result["changes_requested"]
                    )

                    print(f"   📝 Storing refinement prompt for author {message.author.id}: '{modified_prompt}'")

                    # Increment refinement count
                    new_count = self.image_generator.increment_refinement_count(message.author.id)
                    print(f"   🔢 Incremented refinement count to {new_count}")

                    # Store refinement prompt AND changes_requested in dictionary (keyed by author_id)
                    # Discord Message objects don't allow arbitrary attribute assignment
                    # We store both so we can load user context for any new people being added
                    self._refinement_prompts[message.author.id] = {
                        'prompt': modified_prompt,
                        'changes_requested': refinement_result.get('changes_requested', '')
                    }
                    intent = "image_generation"
                    print(f"   🎯 Forcing intent to 'image_generation' with refined prompt\n")
                else:
                    print(f"   ❌ Not a refinement (confidence: {refinement_result['confidence']:.2f} < {threshold})")
                    print(f"   Proceeding with normal intent classification\n")
                    intent = await self._classify_intent(message, short_term_memory, content_override=actual_content)
            else:
                print(f"   ℹ️ No cached prompt found")
                print(f"   Proceeding with normal intent classification\n")
                # No cached prompt - proceed with normal intent classification
                intent = await self._classify_intent(message, short_term_memory, content_override=actual_content)
        else:
            # Image refinement disabled - proceed with normal intent classification
            intent = await self._classify_intent(message, short_term_memory, content_override=actual_content)

        channel = message.channel
        author = message.author

        # Get channel configuration from database
        channel_id_str = str(channel.id)
        personality_config = db_manager.get_channel_setting(channel_id_str)
        if not personality_config:
            # Fallback to empty dict if channel not configured
            personality_config = {}

        bot_name = channel.guild.me.display_name

        # Get emotes with contextual hints for better selection
        available_emotes = self.emote_handler.get_emotes_with_context(guild_id=channel.guild.id)
        emote_count = self.emote_handler.get_emote_count(guild_id=channel.guild.id)

        # Check if temporal context would improve the response (keyword-based, no API call)
        needs_temporal = self._needs_temporal_context(actual_content, short_term_memory)
        if needs_temporal:
            print(f"AI Handler: Temporal context ENABLED for this message")

        # Build bot identity from database (include date/time only when relevant)
        identity_prompt = self._build_bot_identity_prompt(db_manager, personality_config, include_temporal=needs_temporal)

        # Calculate conversation energy for dynamic response length (MUST be done before building relationship context)
        bot_id = channel.guild.me.id
        energy_analysis = self._calculate_conversation_energy(short_term_memory, bot_id)

        # Determine energy level for relationship context
        if energy_analysis['max_tokens'] <= 30:
            energy_level = "VERY LOW"
        elif energy_analysis['max_tokens'] <= 45:
            energy_level = "LOW"
        elif energy_analysis['max_tokens'] <= 60:
            energy_level = "MEDIUM"
        else:
            energy_level = "HIGH"

        # Build relationship context with energy level
        relationship_prompt = self._build_relationship_context(author.id, personality_config, db_manager, energy_level)

        # Get user's long-term memory (AUTHOR = person asking question)
        long_term_memory_entries = db_manager.get_long_term_memory(author.id)
        user_profile_prompt = ""
        if long_term_memory_entries:
            # Format facts with source attribution for natural conversation
            author_name = author.display_name if hasattr(author, 'display_name') else author.name
            author_id_str = str(author.id)

            facts_from_self = []  # Facts the author told you about themselves
            facts_from_others = []  # Facts others told you about the author

            for fact, source_id, source_name in long_term_memory_entries:
                if str(source_id) == author_id_str:
                    facts_from_self.append(fact)
                else:
                    facts_from_others.append(f"{fact} (told by {source_name})")

            user_profile_prompt = f"=== THINGS YOU KNOW ABOUT THE AUTHOR ===\n"
            user_profile_prompt += f"Author: **{author_name}** (ID: {author.id})\n"

            if facts_from_self:
                user_profile_prompt += "**Direct knowledge** (they told you themselves):\n- " + "\n- ".join(facts_from_self) + "\n"
            if facts_from_others:
                user_profile_prompt += "**Secondhand knowledge** (you heard from others - present as rumors/hearsay):\n- " + "\n- ".join(facts_from_others) + "\n"
            user_profile_prompt += "\n"

        # Build mentioned users prompt (will be populated for casual_chat/memory_recall/factual_question)
        mentioned_users_prompt = ""
        # Note: mentioned_users_info is populated in the casual_chat/memory_recall section below

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
                # Check if this is a refinement (modified prompt) or a new image request
                # Refinement prompts are stored in self._refinement_prompts dictionary by author_id
                is_refinement_request = message.author.id in self._refinement_prompts
                refinement_changes = None  # Will hold changes_requested for refinements
                if is_refinement_request:
                    # This is a refinement - extract prompt and changes_requested from stored dict
                    refinement_data = self._refinement_prompts.pop(message.author.id)  # Pop to remove after use
                    clean_prompt = refinement_data['prompt']
                    refinement_changes = refinement_data.get('changes_requested', '')
                    print(f"\n🔄 IMAGE REFINEMENT MODE ACTIVE")
                    print(f"   Using refined prompt: '{clean_prompt}'")
                    print(f"   Changes requested: '{refinement_changes}'")
                else:
                    # Strip bot name and alternative nicknames from the prompt
                    clean_prompt = self._strip_bot_name_from_prompt(actual_content, message.guild)
                    print(f"\n🆕 NEW IMAGE GENERATION")
                    print(f"   Original message: '{actual_content}'")
                    print(f"   Clean prompt: '{clean_prompt}'")

                # Check if any users are mentioned in the prompt and get their facts
                # CRITICAL: Check DATABASE nicknames table FIRST before checking guild members
                # This ensures we find the correct user with facts, not random guild members with similar names
                # For refinements: Check if changes_requested mentions a person to add
                image_context = None
                if is_refinement_request and refinement_changes:
                    # For refinements, look for user context ONLY from the changes_requested
                    # This ensures we load facts for newly added people (like "add UserA riding")
                    print(f"AI Handler: Checking refinement changes for user context: '{refinement_changes}'")

                    # Extract potential names from changes_requested (words 3+ chars, not common words)
                    changes_lower = refinement_changes.lower()
                    common_words = {'add', 'make', 'the', 'put', 'remove', 'delete', 'change', 'riding', 'hugging',
                                   'holding', 'standing', 'sitting', 'wearing', 'with', 'and', 'next', 'beside'}
                    potential_names = [w.strip('.,!?"\'') for w in changes_lower.split()
                                      if len(w) >= 3 and w.strip('.,!?"\'') not in common_words]
                    print(f"AI Handler: Potential names from refinement: {potential_names}")

                    if potential_names and message.guild:
                        # Check database nicknames table for matches
                        try:
                            import sqlite3
                            db_path = db_manager.db_path
                            conn = sqlite3.connect(db_path)
                            cursor = conn.cursor()

                            for name in potential_names:
                                cursor.execute("SELECT DISTINCT user_id, nickname FROM nicknames")
                                for row in cursor.fetchall():
                                    user_id_str, nickname = str(row[0]), row[1].lower()

                                    # Match if name equals a word in the nickname
                                    nickname_words = nickname.split()
                                    if name in nickname_words or nickname in name or name in nickname:
                                        print(f"AI Handler: Refinement - found user match '{nickname}' (ID: {user_id_str}) for '{name}'")

                                        # Load facts for this user
                                        user_facts = db_manager.get_long_term_memory(user_id_str)
                                        if user_facts:
                                            # Filter to visual/appearance facts only
                                            appearance_patterns = [
                                                'has hair', ' hair ', 'has eyes', ' eyes ', 'wears ', 'wearing ',
                                                'has a slender', 'has a muscular', 'has a', 'dressed in',
                                                'complexion', 'skin', 'tall', 'short', 'build', 'appearance',
                                                ' hat', ' cap', 'eyeliner', 'fang', 'bandage', 'fingernail', 'painted'
                                            ]
                                            descriptive_facts = []
                                            for fact_tuple in user_facts:  # Check ALL facts
                                                fact_text = fact_tuple[0]
                                                fact_lower = fact_text.lower()
                                                if any(p in fact_lower for p in appearance_patterns):
                                                    descriptive_facts.append(fact_text)

                                            if descriptive_facts:
                                                # Use up to 15 appearance facts for better visual accuracy
                                                image_context = f"{nickname}: {', '.join(descriptive_facts[:15])}"
                                                print(f"AI Handler: Loaded refinement context ({len(descriptive_facts)} facts): {image_context[:300]}...")
                                        break
                                if image_context:
                                    break
                            conn.close()
                        except Exception as e:
                            print(f"AI Handler: Error loading refinement user context: {e}")
                elif message.guild:
                    mentioned_users = []
                    prompt_lower = clean_prompt.lower()
                    print(f"AI Handler: Looking for users mentioned in prompt: '{prompt_lower}'")

                    # PRIORITY 0: Check for reflexive pronouns (yourself, you, self)
                    # These indicate the user wants to draw THE BOT (not themselves)
                    # BUT: Only treat as pure self-portrait if pronoun is the MAIN subject

                    # Smart detection: Check if "you/yourself/self" is the PRIMARY subject
                    # Examples:
                    # - "draw yourself" → bot is primary subject ✓
                    # - "draw you" → bot is primary subject ✓
                    # - "draw UserA eating you" → UserA is primary, bot is secondary ✗
                    # - "draw you and UserA fighting" → both are subjects ✓

                    import re

                    # Remove common drawing command prefixes to get the actual subject(s)
                    subject_prompt = prompt_lower
                    for prefix in ['draw me a', 'draw me an', 'draw me', 'draw a', 'draw an', 'draw',
                                   'sketch me a', 'sketch me an', 'sketch me', 'sketch a', 'sketch an', 'sketch',
                                   'create a', 'create an', 'create', 'make me a', 'make me', 'make a', 'make']:
                        if subject_prompt.startswith(prefix):
                            subject_prompt = subject_prompt[len(prefix):].strip()
                            break

                    # Check if the prompt starts with reflexive pronouns (is the primary subject)
                    reflexive_pronouns = ['yourself', 'you', 'self']
                    is_bot_primary_subject = any(subject_prompt.startswith(pronoun + ' ') or subject_prompt == pronoun for pronoun in reflexive_pronouns)

                    # Also check if bot is mentioned alongside other subjects (e.g., "you and alice")
                    # Use word boundary matching to avoid false positives like "your" matching "you"
                    bot_mentioned = any(
                        re.search(r'\b' + re.escape(pronoun) + r'\b', subject_prompt)
                        for pronoun in reflexive_pronouns
                    )

                    # Load bot identity if bot is mentioned at all (primary or secondary)
                    bot_identity_context = None
                    if bot_mentioned:
                        print(f"AI Handler: Detected bot mention (primary={is_bot_primary_subject}) - loading bot identity")
                        # Load bot identity from database
                        bot_traits = db_manager.get_bot_identity('trait')
                        bot_lore = db_manager.get_bot_identity('lore')
                        bot_facts = db_manager.get_bot_identity('fact')

                        # Combine all bot identity information
                        bot_identity_parts = []
                        if bot_traits:
                            bot_identity_parts.extend(bot_traits)
                        if bot_lore:
                            bot_identity_parts.extend(bot_lore)
                        if bot_facts:
                            bot_identity_parts.extend(bot_facts)

                        if bot_identity_parts:
                            # Get bot's name from guild member
                            bot_member = message.guild.me
                            bot_name = bot_member.display_name if bot_member else "the bot"

                            # Format bot identity into context (will be combined with user context if needed)
                            bot_description = ", ".join(bot_identity_parts[:10])  # Limit to first 10 facts
                            bot_identity_context = f"{bot_name}: {bot_description}"
                            print(f"AI Handler: Loaded bot identity: {bot_identity_context[:200]}")
                        else:
                            print(f"AI Handler: No bot identity found in database")

                    # Only skip user matching if bot is the SOLE primary subject
                    # If bot is mentioned alongside others, we still need to find those users
                    skip_user_matching = is_bot_primary_subject and not any(
                        word in subject_prompt for word in ['and', 'with', 'versus', 'vs', 'fighting', 'eating', 'hugging']
                    )

                    if skip_user_matching:
                        print(f"AI Handler: Bot is SOLE subject - skipping user matching")
                        mentioned_users = []
                        if bot_identity_context:
                            image_context = bot_identity_context

                    # Perform user matching if bot is NOT the sole subject
                    if not skip_user_matching:
                        # Extract words from the prompt to check against names
                        # CRITICAL: Only match SPECIFIC NAMES, not generic English words
                        # A word is considered a potential name if:
                        # 1. It was CAPITALIZED in the original message (proper noun)
                        # 2. It's NOT a common English word
                        # 3. It's at least 3 characters long

                        # MINIMAL filter - only words that could NEVER be usernames
                        # Everything else goes through AI verification if it matches a database user
                        common_english_words = {
                            # Articles and determiners (too short/common to be names)
                            'a', 'an', 'the', 'this', 'that', 'these', 'those',
                            # Pronouns (referring to self/others, not names)
                            'i', 'me', 'my', 'you', 'your', 'he', 'him', 'his', 'she', 'her', 'hers',
                            'it', 'its', 'we', 'us', 'our', 'they', 'them', 'their',
                            # Question words
                            'who', 'what', 'which', 'whose', 'whom', 'where', 'when', 'why', 'how',
                            # Basic verbs (too common)
                            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am',
                            'have', 'has', 'had', 'do', 'does', 'did',
                            # Prepositions and conjunctions
                            'with', 'for', 'to', 'from', 'in', 'on', 'at', 'by', 'of', 'about',
                            'and', 'or', 'but', 'so', 'if', 'than', 'then',
                            # Modal verbs
                            'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must',
                            # Drawing command words (always skip these)
                            'draw', 'drawing', 'sketch', 'paint', 'create', 'make', 'picture'
                        }
                        # NOTE: Nouns like "fish", "cat", "dragon" are NOT filtered
                        # If someone is named "Fish", AI verification will decide
                        # if "draw a fish" means the animal or the user

                        # Get original words (before lowercasing) to check capitalization
                        original_words = clean_prompt.split()

                        # Only consider words that:
                        # 1. Were CAPITALIZED in the original (indicating a proper noun/name)
                        # 2. Are NOT common English words
                        # 3. Are at least 3 characters
                        potential_names = []
                        for orig_word in original_words:
                            word_lower = orig_word.lower().strip('.,!?"\'-')

                            # Skip if too short
                            if len(word_lower) < 3:
                                continue

                            # Skip if it's a common English word
                            if word_lower in common_english_words:
                                continue

                            # Check if it looks like a name (capitalized OR not a dictionary word)
                            # Names are typically: Capitalized, unique, not common words
                            is_capitalized = orig_word[0].isupper() if orig_word else False

                            # If capitalized and not a common word, it's likely a name
                            if is_capitalized:
                                potential_names.append(word_lower)
                                print(f"AI Handler: '{orig_word}' is capitalized and not common - treating as potential name")
                            # If not capitalized but also not in common words, might still be a name (some users type lowercase)
                            elif word_lower not in common_english_words:
                                # Extra check: only include if it doesn't look like a regular word
                                # This catches usernames like "username123" that aren't capitalized
                                potential_names.append(word_lower)

                        print(f"AI Handler: Potential names for user matching: {potential_names}")

                        # PRIORITY 1: Check database nicknames table (most reliable source)
                        # Only search if we have potential names to match
                        if potential_names:
                            print(f"AI Handler: Checking database nicknames table for matches...")
                            try:
                                import sqlite3
                                db_path = db_manager.db_path
                                conn = sqlite3.connect(db_path)
                                cursor = conn.cursor()

                                for name in potential_names:
                                    cursor.execute("SELECT DISTINCT user_id, nickname FROM nicknames")
                                    for row in cursor.fetchall():
                                        user_id_str, nickname = row[0], row[1].lower()

                                        # Match if name equals a word in the nickname (exact word match only)
                                        nickname_words = nickname.split()
                                        if name in nickname_words:
                                            print(f"AI Handler: Database nicknames match - '{name}' matches word in '{nickname}' (user_id: {user_id_str})")

                                            # Verify this is actually a reference to the user, not just the word
                                            is_actual_reference = await self._verify_user_reference(
                                                clean_prompt, name, nickname
                                            )

                                            if is_actual_reference:
                                                class PseudoMember:
                                                    def __init__(self, user_id, display_name):
                                                        self.id = user_id
                                                        self.display_name = display_name
                                                mentioned_users.append(PseudoMember(user_id_str, nickname))
                                                print(f"AI Handler: Verified - drawing prompt refers to user '{nickname}'")
                                            else:
                                                print(f"AI Handler: Skipped '{nickname}' - word used as object/noun, not referring to user")
                                            break
                                    if mentioned_users:
                                        break

                                conn.close()
                            except Exception as e:
                                print(f"AI Handler: Error checking database nicknames: {e}")
                        else:
                            print(f"AI Handler: No potential names found in prompt - skipping database lookup")

                        # PRIORITY 2: If database nicknames found nothing,
                        # check long-term memory "also goes by" facts as fallback
                        if not mentioned_users and potential_names:
                            print(f"AI Handler: No database nicknames matched, checking long-term memory 'also goes by' facts...")
                            try:
                                import sqlite3
                                db_path = db_manager.db_path
                                conn = sqlite3.connect(db_path)
                                cursor = conn.cursor()

                                cursor.execute("SELECT DISTINCT user_id FROM long_term_memory")
                                all_user_ids = [row[0] for row in cursor.fetchall()]

                                # Check each user's facts for alternative names matching potential_names
                                for user_id in all_user_ids:
                                    user_facts = db_manager.get_long_term_memory(user_id)
                                    if user_facts:
                                        for fact_tuple in user_facts:
                                            fact_text = fact_tuple[0].lower()
                                            # Check for alternative name patterns
                                            for phrase in ['also goes by', 'known as', 'called', 'nicknamed']:
                                                if phrase in fact_text:
                                                    pattern_pos = fact_text.find(phrase)
                                                    text_after_pattern = fact_text[pattern_pos + len(phrase):]
                                                    import re
                                                    # Check if any potential name appears after the pattern
                                                    matched_name = None
                                                    for name in potential_names:
                                                        if re.search(r'\b' + re.escape(name) + r'\b', text_after_pattern):
                                                            matched_name = name
                                                            break

                                                    if matched_name:
                                                        print(f"AI Handler: Database match found for user {user_id} in fact: {fact_tuple[0]}")

                                                        # Verify this is actually a reference to the user
                                                        is_actual_reference = await self._verify_user_reference(
                                                            clean_prompt, matched_name, f"User_{user_id}"
                                                        )

                                                        if is_actual_reference:
                                                            class PseudoMember:
                                                                def __init__(self, user_id):
                                                                    self.id = user_id
                                                                    self.display_name = f"User_{user_id}"
                                                            mentioned_users.append(PseudoMember(user_id))
                                                            print(f"AI Handler: Verified - drawing prompt refers to user '{user_id}'")
                                                        else:
                                                            print(f"AI Handler: Skipped user {user_id} - word used as object/noun, not referring to user")
                                                        break
                                            if mentioned_users:
                                                break
                                    if mentioned_users:
                                        break

                                conn.close()
                            except Exception as e:
                                print(f"AI Handler: Error searching database for alternative names: {e}")

                        print(f"AI Handler: Total users found via database lookup: {len(mentioned_users)}")

                        # CONTEXT SOURCE 3: Check short-term conversation history for descriptive statements
                        # This allows: "Angel is a rabbit" (message 1) → "draw Angel" (message 2)
                        conversation_context = []
                        if not mentioned_users and short_term_memory and potential_names:
                            print(f"AI Handler: No users found in database, checking recent conversation for context...")

                            # Search recent messages (last 20) for descriptive statements about the subject
                            for msg_dict in short_term_memory[-20:]:
                                msg_content = msg_dict.get('content', '')
                                msg_content_lower = msg_content.lower()

                                # Check if any potential name appears in this message
                                if any(name in msg_content_lower for name in potential_names):
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
- "PersonA is tall with distinctive features" → "tall with distinctive features"
- "The object has unique characteristics" → "unique characteristics"
- "PersonB is athletic and wears casual clothing" → "athletic and wears casual clothing"

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

                            # CRITICAL: Add bot identity first if bot is also in the scene
                            if bot_identity_context:
                                context_parts.append(bot_identity_context)
                                print(f"AI Handler: Adding bot identity to multi-subject scene")

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

                                    # CRITICAL: Detect gender from pronouns in ALL facts
                                    # This ensures image AI knows if person is male/female/other
                                    gender_detected = None
                                    female_pronouns = [' she ', ' her ', ' hers ', ' herself ']
                                    male_pronouns = [' he ', ' him ', ' his ', ' himself ']

                                    # Scan ALL facts for gender pronouns (not just first 5)
                                    all_facts_text = " ".join([fact_tuple[0].lower() for fact_tuple in user_facts])

                                    female_count = sum(all_facts_text.count(pronoun) for pronoun in female_pronouns)
                                    male_count = sum(all_facts_text.count(pronoun) for pronoun in male_pronouns)

                                    if female_count > male_count:
                                        gender_detected = "woman"
                                        print(f"AI Handler: Detected gender as FEMALE from pronouns (she/her count: {female_count})")
                                    elif male_count > female_count:
                                        gender_detected = "man"
                                        print(f"AI Handler: Detected gender as MALE from pronouns (he/him count: {male_count})")

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

                                    # Separate appearance facts from other facts
                                    # Appearance facts (hair, eyes, face, clothing) are prioritized
                                    appearance_facts = []
                                    other_facts = []

                                    # Visual descriptor patterns that indicate appearance facts
                                    # Check if fact describes physical appearance, not just contains appearance words
                                    appearance_patterns = [
                                        'has hair', ' hair ', 'has eyes', ' eyes ', 'has eye', ' eye ', 'has a face', 'has skin',
                                        'wears ', 'wearing ', ' hat', ' cap', 'headwear',
                                        'has a slender', 'has a muscular', 'has a', 'has an',
                                        'hair is', 'eyes are', 'skin is', 'skin on',
                                        'dressed in', 'outfit', 'clothing',
                                        'has fringe', 'has bangs', 'has a build',
                                        'complexion', 'has lips', 'has a mouth', 'has a nose',
                                        'has fingernails', 'painted', 'has makeup', 'eyeliner', 'fang', 'bandage',
                                        'depicted in', 'drawn in', 'art style',
                                        'shading', 'highlights', 'giving a', 'making them',
                                        'shoulders', 'contrasts in light', 'bright areas', 'impression is', 'overall impression',
                                        'hybrid', 'creature', 'physique', 'body ', 'muscular', 'muscles', 'pose', 'stands in'
                                    ]

                                    for fact_tuple in user_facts:  # Check ALL facts, not just first 20
                                        fact_text = fact_tuple[0]
                                        fact_lower = fact_text.lower()

                                        # Skip behavioral commands and meta-instructions
                                        if any(phrase in fact_lower for phrase in exclude_phrases):
                                            continue

                                        # Check if this is an appearance fact by looking for visual descriptor patterns
                                        is_appearance = any(pattern in fact_lower for pattern in appearance_patterns)

                                        if is_appearance:
                                            appearance_facts.append(fact_text)
                                        else:
                                            other_facts.append(fact_text)

                                    # Prioritize appearance facts first, then add other descriptive facts
                                    descriptive_facts = appearance_facts[:15]  # Up to 15 appearance facts
                                    if len(descriptive_facts) < 5:
                                        # Fill remaining slots with other facts
                                        descriptive_facts.extend(other_facts[:5 - len(descriptive_facts)])

                                    if descriptive_facts or appearance_modifiers or gender_detected:
                                        # Combine appearance modifiers (from metrics) with descriptive facts
                                        all_descriptors = []

                                        # CRITICAL: Add gender FIRST so image AI sees it immediately
                                        if gender_detected:
                                            all_descriptors.append(f"a {gender_detected}")

                                        if appearance_modifiers:
                                            all_descriptors.extend(appearance_modifiers)

                                        if descriptive_facts:
                                            all_descriptors.extend(descriptive_facts)

                                        facts_text = ", ".join(all_descriptors)
                                        context_parts.append(facts_text)
                                        print(f"AI Handler: Sending descriptive facts for {member.display_name}: {facts_text}")

                            if context_parts:
                                image_context = ". ".join(context_parts)
                                print(f"AI Handler: Adding context to image generation: {image_context}")
                            else:
                                print(f"AI Handler: No context parts built (no facts found for mentioned users)")

                # Generate the image with context (enhanced with AI if enabled)
                # For refinements, skip enhancement to preserve the minimal changes
                print(f"\n🎨 CALLING IMAGE GENERATOR:")
                print(f"   Prompt: '{clean_prompt}'")
                print(f"   Context: '{image_context if image_context else 'None'}'")
                print(f"   Is Refinement: {is_refinement_request}")

                image_bytes, error_msg, full_prompt = await self.image_generator.generate_image(
                    clean_prompt,
                    image_context,
                    db_manager,
                    short_term_memory,
                    is_refinement=is_refinement_request
                )

                if error_msg:
                    print(f"AI Handler: Image generation failed: {error_msg}")
                    personality_mode = self._get_personality_mode(personality_config)

                    # Get the current user's display name
                    current_user_name = author.display_name

                    # Generate a natural failure response for non-NSFW errors
                    failure_prompt = f"""
{identity_prompt}
{relationship_prompt}

🎯 **CURRENT USER IDENTIFICATION** 🎯
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
                # Cache the FULL enhanced prompt for potential refinement (only on success!)
                prompt_to_cache = full_prompt if full_prompt else clean_prompt
                print(f"\n💾 CACHING ENHANCED PROMPT: '{prompt_to_cache[:50]}...' for user {author.id}")
                self.image_generator.cache_prompt(author.id, prompt_to_cache)

                # Increment the image count AFTER successful generation
                # BUT: Skip increment for refinements if configured to allow refinements after rate limit
                allow_refinement_after_limit = refinement_config.get('allow_refinement_after_rate_limit', True)

                if not is_refinement_request or not allow_refinement_after_limit:
                    # Either this is a new image, or refinements count toward limit
                    db_manager.increment_user_image_count(author.id, reset_period_hours)
                    print(f"AI Handler: Incremented image count for user {author.id}")
                else:
                    print(f"AI Handler: Skipped image count increment (refinement with allow_after_limit=true)")

                # Generate a brief, natural response to go with the image
                personality_mode = self._get_personality_mode(personality_config)

                # Get the current user's display name
                current_user_name = author.display_name

                drawing_prompt = f"""
{identity_prompt}
{relationship_prompt}

🎯 **CURRENT USER IDENTIFICATION** 🎯
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
The user wants you to remember a fact. Analyze who the fact is ABOUT and extract the information.

CRITICAL: Determine if this fact is about:
1. The speaker themselves (uses "I", "my", "me")
2. Someone else (uses a name, "he", "she", "they", or refers to another person)

Respond in this EXACT format:
ABOUT: [self OR the name of the person]
FACT: [the extracted fact, written in third person if about someone else]

Examples:
- User says "my favorite color is blue"
  ABOUT: self
  FACT: Their favorite color is blue

- User says "Alice has a black hat"
  ABOUT: Alice
  FACT: Has a black hat

- User says "remember that John loves pizza"
  ABOUT: John
  FACT: Loves pizza

- User says "he has red hair" (context: discussing someone named Alex)
  ABOUT: Alex
  FACT: Has red hair

- User says "I work as a developer"
  ABOUT: self
  FACT: Works as a developer

User message: "{actual_content}"

Respond with ONLY the ABOUT and FACT lines, nothing else.
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
                extraction_result = response.choices[0].message.content.strip()
                if not extraction_result:
                    return "I'm not sure what you want me to remember from that."

                # Parse the ABOUT and FACT from the response
                about_person = "self"
                extracted_fact = extraction_result

                if "ABOUT:" in extraction_result and "FACT:" in extraction_result:
                    lines = extraction_result.split('\n')
                    for line in lines:
                        if line.startswith("ABOUT:"):
                            about_person = line.replace("ABOUT:", "").strip().lower()
                        elif line.startswith("FACT:"):
                            extracted_fact = line.replace("FACT:", "").strip()

                # Determine who to save the fact for
                target_user_id = author.id
                target_user_name = author.display_name

                if about_person != "self":
                    # Try to find this person in the database
                    print(f"AI Handler: Fact is about '{about_person}', searching for user...")

                    # Search nicknames table and members for a match
                    found_user = None
                    if message.guild:
                        about_lower = about_person.lower()

                        # Check guild members
                        for member in message.guild.members:
                            member_name_lower = member.display_name.lower()
                            if about_lower in member_name_lower or member_name_lower in about_lower:
                                found_user = member
                                print(f"AI Handler: Found user match: {member.display_name} (ID: {member.id})")
                                break

                        # Also check nicknames table if no match
                        if not found_user:
                            try:
                                import sqlite3
                                conn = sqlite3.connect(db_manager.db_path)
                                cursor = conn.cursor()
                                cursor.execute("SELECT user_id, nickname FROM nicknames")
                                for user_id, nickname in cursor.fetchall():
                                    if nickname and about_lower in nickname.lower():
                                        # Find the member with this ID
                                        found_member = message.guild.get_member(int(user_id))
                                        if found_member:
                                            found_user = found_member
                                            print(f"AI Handler: Found user via nickname: {nickname} -> {found_member.display_name}")
                                            break
                                conn.close()
                            except Exception as e:
                                print(f"AI Handler: Error searching nicknames: {e}")

                    if found_user:
                        target_user_id = found_user.id
                        target_user_name = found_user.display_name
                        print(f"AI Handler: Saving fact about {target_user_name} (ID: {target_user_id}), source: {author.display_name}")
                    else:
                        print(f"AI Handler: Could not find user '{about_person}', saving to author instead")

                db_manager.add_long_term_memory(
                    target_user_id, extracted_fact, author.id, author.display_name
                )
                print(f"AI Handler: Stored fact '{extracted_fact}' for user {target_user_id} (source: {author.display_name})")
                
                # Now, generate a natural response to having learned the fact
                personality_mode = self._get_personality_mode(personality_config)

                # Build context about who the fact is about
                if about_person == "self":
                    fact_context = f"The user just told you a fact about THEMSELVES: '{extracted_fact}'"
                else:
                    fact_context = f"The user just told you a fact about {target_user_name}: '{extracted_fact}'"

                response_prompt = f"""
{identity_prompt}
{relationship_prompt}

{fact_context}
Acknowledge this new information with a short, natural, human-like response based on your personality.

**CRITICAL RULES**:
- BE BRIEF AND NATURAL. Sound like a real person would when learning something new.
- DO NOT use robotic acknowledgments like: "Got it", "Noted", "I'll remember that", "Understood", "Acknowledged"
- React naturally based on your personality. Examples:
  * High rapport: "oh nice", "cool", "that's awesome", "damn really?"
  * Low rapport: "k", "sure", "whatever", "okay"
  * Neutral: "interesting", "ah okay", "makes sense"
- You can also react to the CONTENT of what they told you, not just acknowledge it
- If the fact is about someone else, you might comment on that person too
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
                ai_response = self._apply_roleplay_formatting(ai_response, personality_config, energy_analysis.get('user_messages'))

                # Metrics now only update during memory consolidation (not after every message)
                # await self._analyze_sentiment_and_update_metrics(message, ai_response, author.id, db_manager)

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
                f"6. **EMOTES** ({emote_count} available - USE THEM ALL, not just favorites!):\n{available_emotes}\n"
                "   **CRITICAL**: Match the emote to your EMOTION. Use the hints above to pick the RIGHT emote for how you FEEL. "
                "Rotate through ALL emotes over time - don't always use the same one!\n"
                "7. Be brief and natural. Sound like a real person answering a question.\n"
            )
        
        elif intent == "memory_correction":
            personality_mode = self._get_personality_mode(personality_config)

            # Step 1: Extract what fact the user is correcting
            correction_prompt = f"""
The user is correcting a fact you got wrong. Extract:
1. What the OLD (incorrect) fact was
2. What the NEW (correct) fact should be

User message: "{actual_content}"

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
                ai_response = self._apply_roleplay_formatting(ai_response, personality_config, energy_analysis.get('user_messages'))

                # Metrics now only update during memory consolidation (not after every message)
                # await self._analyze_sentiment_and_update_metrics(message, ai_response, author.id, db_manager)

                return ai_response

            except json.JSONDecodeError as e:
                print(f"AI Handler: Failed to parse correction JSON: {e}")
                return "Sorry, I had trouble understanding that correction."
            except Exception as e:
                print(f"AI Handler: Failed to process memory correction: {e}")
                return "Sorry, I had trouble updating that."
        
        else:  # Covers "casual_chat", "memory_recall", and "memory_challenge"
            personality_mode = self._get_personality_mode(personality_config)
            server_info = self._load_server_info(personality_config, message.guild.id, message.guild.name)

            # Detect mentioned users in the message content (NEW 2025-10-26)
            # This allows questions like "what do you think about Alice?" to load Alice's facts
            mentioned_users_info = []
            if message.guild:
                mentioned_users = []
                message_lower = actual_content.lower()

                # Extract potential names from message
                # CRITICAL: Only match SPECIFIC NAMES, not generic English words
                # Common English words that should NEVER match usernames
                # MINIMAL filter - only words that could NEVER be usernames
                # Everything else goes through AI verification if it matches a database user
                common_english_words = {
                    # Articles and determiners (too short/common to be names)
                    'a', 'an', 'the', 'this', 'that', 'these', 'those',
                    # Pronouns (referring to self/others, not names)
                    'i', 'me', 'my', 'you', 'your', 'he', 'him', 'his', 'she', 'her', 'hers',
                    'it', 'its', 'we', 'us', 'our', 'they', 'them', 'their',
                    # Question words
                    'who', 'what', 'which', 'whose', 'whom', 'where', 'when', 'why', 'how',
                    # Basic verbs (too common)
                    'is', 'are', 'was', 'were', 'be', 'been', 'being', 'am',
                    'have', 'has', 'had', 'do', 'does', 'did',
                    # Prepositions and conjunctions
                    'with', 'for', 'to', 'from', 'in', 'on', 'at', 'by', 'of', 'about',
                    'and', 'or', 'but', 'so', 'if', 'than', 'then',
                    # Modal verbs
                    'will', 'would', 'should', 'could', 'can', 'may', 'might', 'must'
                }
                # NOTE: Nouns, adjectives, slang etc. are NOT filtered here
                # If someone is named "Fish" or "Weird", AI verification will decide
                # if the message refers to them or uses the word normally

                # Get original words to check capitalization
                original_words = actual_content.split()
                potential_names = []
                for orig_word in original_words:
                    word_lower = orig_word.lower().strip('.,!?"\'-')
                    if len(word_lower) < 3:
                        continue
                    if word_lower in common_english_words:
                        continue
                    # Check if capitalized (proper noun) or unique word
                    is_capitalized = orig_word[0].isupper() if orig_word else False
                    if is_capitalized or word_lower not in common_english_words:
                        potential_names.append(word_lower)

                print(f"AI Handler: Checking for mentioned users in casual chat. Potential names: {potential_names}")

                # Only search if we have potential names
                if potential_names:
                    # Check guild members for matches
                    for member in message.guild.members:
                        if member.bot:
                            continue

                        member_display_lower = member.display_name.lower()
                        member_name_lower = member.name.lower()

                        # Check display name and username (exact word match)
                        import re
                        display_match = any(re.search(r'\b' + re.escape(name) + r'\b', member_display_lower) for name in potential_names)
                        username_match = any(re.search(r'\b' + re.escape(name) + r'\b', member_name_lower) for name in potential_names)

                        # Check nicknames table with word boundary matching
                        nickname_match = False
                        if not (display_match or username_match):
                            try:
                                import sqlite3
                                conn = sqlite3.connect(db_manager.db_path)
                                cursor = conn.cursor()
                                cursor.execute("SELECT nickname FROM nicknames WHERE user_id = ?", (str(member.id),))
                                nicknames = [row[0].lower() for row in cursor.fetchall()]
                                conn.close()

                                if nicknames:
                                    for nickname in nicknames:
                                        nickname_words = nickname.split()
                                        for name in potential_names:
                                            if name in nickname_words:
                                                nickname_match = True
                                                print(f"AI Handler: Casual chat found mentioned user via nicknames: '{name}' matches word in '{nickname}' for {member.display_name}")
                                                break
                                        if nickname_match:
                                            break
                            except Exception as e:
                                print(f"AI Handler: Error checking nicknames for casual chat: {e}")

                    if display_match or username_match or nickname_match:
                        # Don't add the author to mentioned users list (they're already loaded separately)
                        if member.id != author.id:
                            # Determine which name matched for verification
                            matched_name = None
                            if display_match:
                                matched_name = member.display_name.lower()
                            elif username_match:
                                matched_name = member.name.lower()
                            else:  # nickname_match
                                matched_name = member.display_name.lower()  # Use display name as reference

                            # Verify this is actually a reference to the user, not just the word
                            # (e.g., "hat" the object vs "Hat" the user)
                            is_actual_reference = await self._verify_user_reference(
                                actual_content, matched_name, member.display_name
                            )

                            if is_actual_reference:
                                mentioned_users.append(member)
                                print(f"AI Handler: Verified mentioned user (not author): {member.display_name} (ID: {member.id})")
                            else:
                                print(f"AI Handler: Skipped '{member.display_name}' - word used in different context, not referring to user")

                # Load facts for each mentioned user with source attribution
                for member in mentioned_users:
                    user_facts = db_manager.get_long_term_memory(str(member.id))
                    user_metrics = db_manager.get_relationship_metrics(str(member.id))

                    if user_facts or user_metrics:
                        # Separate facts by source for natural presentation
                        member_id_str = str(member.id)
                        author_id_str = str(author.id)

                        facts_from_self = []  # Facts the mentioned user said about themselves
                        facts_from_author = []  # Facts the current speaker told you
                        facts_from_others = []  # Facts from third parties

                        for fact, source_id, source_name in (user_facts or []):
                            source_id_str = str(source_id) if source_id else ""
                            if source_id_str == member_id_str:
                                facts_from_self.append(fact)
                            elif source_id_str == author_id_str:
                                facts_from_author.append(fact)
                            else:
                                facts_from_others.append(f"{fact} (told by {source_name})")

                        mentioned_users_info.append({
                            'name': member.display_name,
                            'id': member_id_str,
                            'facts_from_self': facts_from_self,
                            'facts_from_author': facts_from_author,
                            'facts_from_others': facts_from_others,
                            'metrics': user_metrics
                        })
                        total_facts = len(facts_from_self) + len(facts_from_author) + len(facts_from_others)
                        print(f"AI Handler: Loaded {total_facts} facts for mentioned user {member.display_name} (self:{len(facts_from_self)}, author:{len(facts_from_author)}, others:{len(facts_from_others)})")

            # Build mentioned users prompt from collected info with source attribution
            if mentioned_users_info:
                mentioned_users_prompt = "=== THINGS YOU KNOW ABOUT MENTIONED USERS (people being discussed, NOT the author) ===\n"
                mentioned_users_prompt += "⚠️ CRITICAL: These are OTHER PEOPLE being mentioned in the conversation.\n"
                mentioned_users_prompt += "DO NOT confuse them with the AUTHOR (person asking the question).\n"
                mentioned_users_prompt += "📝 SOURCE GUIDE: Present facts naturally based on how you learned them:\n"
                mentioned_users_prompt += "   - Direct: They told you themselves → speak confidently\n"
                mentioned_users_prompt += "   - From author: The person you're talking to told you → 'you mentioned that...'\n"
                mentioned_users_prompt += "   - From others: Someone else told you → 'I heard that...' or 'rumor has it...'\n\n"

                for user_info in mentioned_users_info:
                    mentioned_users_prompt += f"**{user_info['name']}** (ID: {user_info['id']}):\n"

                    # Add relationship metrics
                    if user_info['metrics']:
                        metrics_str = []
                        for metric_name, metric_value in user_info['metrics'].items():
                            if metric_name.endswith('_locked'):
                                continue  # Skip lock flags
                            metrics_str.append(f"{metric_name.capitalize()}: {metric_value}")
                        if metrics_str:
                            mentioned_users_prompt += f"  Your feelings: {', '.join(metrics_str)}\n"

                    # Add facts with source categories
                    if user_info.get('facts_from_self'):
                        mentioned_users_prompt += "  **Direct knowledge** (they told you):\n"
                        for fact in user_info['facts_from_self'][:5]:
                            mentioned_users_prompt += f"    - {fact}\n"

                    if user_info.get('facts_from_author'):
                        mentioned_users_prompt += "  **From current speaker** (remind them they told you):\n"
                        for fact in user_info['facts_from_author'][:5]:
                            mentioned_users_prompt += f"    - {fact}\n"

                    if user_info.get('facts_from_others'):
                        mentioned_users_prompt += "  **Secondhand** (present as rumors/hearsay):\n"
                        for fact in user_info['facts_from_others'][:5]:
                            mentioned_users_prompt += f"    - {fact}\n"

                    # Fallback for old-style facts list (backwards compatibility)
                    if user_info.get('facts') and not any([user_info.get('facts_from_self'), user_info.get('facts_from_author'), user_info.get('facts_from_others')]):
                        for fact in user_info['facts'][:15]:
                            mentioned_users_prompt += f"  - {fact}\n"

                    mentioned_users_prompt += "\n"

                print(f"AI Handler: Built mentioned_users_prompt with {len(mentioned_users_info)} users (source-aware)")

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

                # Then add identity and relationship context (energy override now integrated in relationship_prompt)
                system_prompt += f"{identity_prompt}\n{relationship_prompt}\n{user_profile_prompt}\n{mentioned_users_prompt}\n{server_info}"

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
                    f"5. **EMOTES** ({emote_count} available - USE THEM ALL based on your EXTREME EMOTIONS!):\n{available_emotes}\n"
                    "   **CRITICAL**: Match the emote to your EXTREME EMOTION. Use the hints above to pick the RIGHT emote. "
                    "Rotate through ALL emotes - don't always use the same one!\n"
                    "6. **NO NAME PREFIX**: NEVER start with your name and a colon.\n"
                )

                # Check if roleplay formatting should be disabled
                enable_roleplay_extreme = personality_config.get('enable_roleplay_formatting', True) and personality_mode['immersive_character']
                if enable_roleplay_extreme:
                    # Check if user is using asterisks in recent messages
                    recent_user_msgs = energy_analysis.get('user_messages', [])[-7:]
                    user_has_asterisks = any('*' in msg for msg in recent_user_msgs if msg) if recent_user_msgs else False
                    print(f"DEBUG ROLEPLAY (EXTREME): Checking last {len(recent_user_msgs)} user messages for asterisks")
                    print(f"DEBUG ROLEPLAY (EXTREME): Recent messages: {recent_user_msgs}")
                    print(f"DEBUG ROLEPLAY (EXTREME): Asterisks found: {user_has_asterisks}")
                    if not user_has_asterisks:
                        print("DEBUG ROLEPLAY (EXTREME): Adding NO ROLEPLAY MODE prompt")
                        system_prompt += (
                            "\n7. 🚫 **CRITICAL: NO ROLEPLAY MODE ACTIVE** 🚫\n"
                            "   **YOU ARE ABSOLUTELY FORBIDDEN FROM DESCRIBING PHYSICAL ACTIONS.**\n"
                            "   **ANY RESPONSE WITH PHYSICAL DESCRIPTIONS WILL BE REJECTED.**\n\n"
                            "   ❌ FORBIDDEN - DO NOT WRITE:\n"
                            "   - Asterisks: '*trembles*', '*gulps*', '*nods*'\n"
                            "   - Physical descriptions: 'trembles violently', 'gulps nervously', 'nods quickly'\n"
                            "   - Gestures: 'bows', 'waves', 'points', 'shrugs'\n"
                            "   - Facial expressions: 'smiles', 'frowns', 'blushes'\n"
                            "   - Body language: 'leans in', 'backs away', 'freezes'\n\n"
                            "   ✅ REQUIRED - ONLY WRITE:\n"
                            "   - Spoken words: 'Y-yes!', 'Right away!', 'I'm ready!'\n"
                            "   - Thoughts/reactions: 'Oh geez', 'Whoa', 'Okay okay'\n"
                            "   - Emotes only: ':emote_name:'\n\n"
                            "   **USE YOUR VOICE AND EMOTES ONLY. NO PHYSICAL DESCRIPTIONS WHATSOEVER.**\n"
                        )

                # Add energy guidance to extreme metrics prompt (detail-seeking overrides low energy)
                energy_guidance = energy_analysis.get('energy_guidance', '')
                if energy_guidance:
                    system_prompt += f"\n{energy_guidance}"

            else:
                # Normal prompt structure when fear/intimidation aren't high
                # Get current user name for explicit identification
                current_user_name = author.display_name if hasattr(author, 'display_name') else author.name

                system_prompt = (
                    f"{identity_prompt}\n"
                    f"{relationship_prompt}\n"
                    f"{user_profile_prompt}\n"
                    f"{mentioned_users_prompt}\n"
                    f"{server_info}"
                    f"You are {bot_name}. **IMPORTANT**: When users mention your name, they are addressing YOU (the character), not referring to the literal meaning of your name.\n\n"
                    f"🎯 **CURRENT USER IDENTIFICATION** 🎯\n"
                    f"You are responding to: **{current_user_name}** (ID: {author.id})\n"
                    f"This is the person you're talking to - do not confuse them with others in the conversation history or mentioned users above.\n"
                    f"**NEVER mention your own name or make puns about it.**\n"
                    f"**NEVER address this user by someone else's name.**\n\n"
                    f"You're having a casual conversation with **{current_user_name}**.\n\n"
                    f"Channel Purpose: {personality_config.get('purpose', 'General chat')}\n\n"
                )

                # Add specific guidance for memory challenge questions ("what do you remember about me?")
                if intent == "memory_challenge":
                    # Check if we actually have facts about this user
                    if not user_profile_prompt or not long_term_memory_entries:
                        # NO FACTS - Be honest that you don't know them yet
                        system_prompt += (
                            "--- MEMORY CHALLENGE RESPONSE (NO FACTS) ---\n"
                            "🚨 **CRITICAL: YOU HAVE NO STORED FACTS ABOUT THIS USER** 🚨\n\n"
                            "The user is asking what you know about them, but you have NOTHING stored.\n"
                            "This likely means you JUST MET them or haven't learned anything about them yet.\n\n"
                            "**YOU MUST BE HONEST:**\n"
                            "- Admit you don't really know them yet\n"
                            "- Say something like 'we just met' or 'I don't think I know much about you yet'\n"
                            "- Be friendly and open to learning about them\n"
                            "- DO NOT invent or guess facts about them\n\n"
                            "❌ NEVER DO THIS (inventing facts):\n"
                            "'Oh you're the retired teacher right? You mentioned physics...'\n"
                            "(This is LYING - you have NO information about them!)\n\n"
                            "✅ DO THIS (be honest):\n"
                            "'Hmm, I don't think I actually know much about you yet! We haven't really talked before have we?'\n"
                            "'Honestly? Not much lol, feel like we just met'\n"
                            "'Can't say I know anything yet - tell me about yourself!'\n\n"
                            "**ABSOLUTE RULE**: If there are no facts listed about the user above, you MUST admit you don't know them. "
                            "NEVER fabricate information about someone you haven't met.\n\n"
                        )
                    else:
                        # HAS FACTS - Normal memory challenge response
                        system_prompt += (
                            "--- MEMORY CHALLENGE RESPONSE ---\n"
                            "🚨 **CRITICAL: DO NOT LIST FACTS LIKE A DATABASE** 🚨\n\n"
                            "**STRICT RULES:**\n"
                            "1. Pick ONLY 1-2 things - NOT a summary\n"
                            "2. Sound casual: 'if I remember right...', 'pretty sure...'\n"
                            "3. React genuinely: 'Oh right, you're the...!'\n"
                            "4. Keep it SHORT - one sentence is enough\n\n"
                            "❌ **FORBIDDEN**:\n"
                            "- Listing multiple facts\n"
                            "- Using dashes to separate facts\n"
                            "- 'You're X, Y, Z, and also W'\n\n"
                            "✅ **DO THIS** (casual, brief):\n"
                            "- 'Oh you're the gym bro right? lol'\n"
                            "- 'Pretty sure you hate my surgeries... rude'\n"
                            "- 'You're my annoying brother if I remember correctly'\n\n"
                            "**YOU ARE A PERSON, NOT A SEARCH ENGINE.** Pick ONE thing.\n\n"
                        )

                system_prompt += (
                    "--- CRITICAL RULES ---\n"
                    "1. **BE BRIEF AND NATURAL**: Sound like a real person. Match your relationship tone.\n"
                    "2. **CONVERSATION FLOW**: Questions are OK when natural, but NEVER use customer service language.\n"
                    "3. **USE MEMORY WISELY**: Only mention facts if relevant.\n"
                    "   - The conversation history below includes messages from ALL channels in this server\n"
                    "   - Pay attention to things people have said across all channels - it's all part of the same ongoing conversation\n"
                    "4. **NEVER INVENT FACTS ABOUT USERS**: You can ONLY claim to know things that are explicitly listed in 'THINGS YOU KNOW ABOUT THE AUTHOR' above.\n"
                    "   - If NO facts are listed for a user, you DON'T know anything about them yet\n"
                    "   - If asked 'what do you know about me?' with no facts listed, be HONEST: 'We just met!' or 'I don't know much about you yet'\n"
                    "   - NEVER guess or fabricate information about users - this is LYING\n"
                    "   - You CAN make up facts about YOURSELF (your lore, opinions, feelings) - just never about users\n"
                    "5. **NO NAME PREFIX**: NEVER start with your name and a colon.\n"
                    f"6. **EMOTES** ({emote_count} available - USE THEM ALL, not just favorites!):\n{available_emotes}\n"
                    "   **CRITICAL**: Match the emote to your EMOTION. Use the hints above to pick the RIGHT emote for how you FEEL. "
                    "Rotate through ALL emotes over time - don't always default to the same one!\n"
                    "   - A server emote by itself is a perfectly valid response\n"
                    "   - Great for awkward moments or when you don't have much to say\n"
                    "7. **EMOTIONAL TOPICS**: If the conversation touches on your lore, let those emotions show naturally while respecting your relationship with the user.\n"
                    "8. **REFERENCING FACTS ABOUT YOURSELF**: When mentioning facts from your identity (traits/lore/facts), speak naturally in complete sentences. Never compress them into awkward phrases.\n"
                    "9. **MENTIONED USERS VS AUTHOR**: If facts about mentioned users are listed above, use them when answering questions ABOUT THOSE PEOPLE. Do NOT confuse mentioned users with the author.\n"
                )

            # Add energy guidance to system prompt (detail-seeking overrides low energy)
            energy_guidance = energy_analysis.get('energy_guidance', '')
            if energy_guidance:
                system_prompt += f"\n{energy_guidance}"

            # Check if roleplay formatting should be disabled
            enable_roleplay = personality_config.get('enable_roleplay_formatting', True) and personality_mode['immersive_character']
            if enable_roleplay:
                # Check if user is using asterisks in recent messages
                recent_user_msgs = energy_analysis.get('user_messages', [])[-7:]
                user_has_asterisks = any('*' in msg for msg in recent_user_msgs if msg) if recent_user_msgs else False
                print(f"DEBUG ROLEPLAY: Checking last {len(recent_user_msgs)} user messages for asterisks")
                print(f"DEBUG ROLEPLAY: Recent messages: {recent_user_msgs}")
                print(f"DEBUG ROLEPLAY: Asterisks found: {user_has_asterisks}")
                if not user_has_asterisks:
                    enable_roleplay = False
                    print("DEBUG ROLEPLAY: DISABLING roleplay - no asterisks detected")

            print(f"DEBUG ROLEPLAY: Final enable_roleplay = {enable_roleplay}")
            if not enable_roleplay:
                system_prompt += (
                    "\n10. 🚫 **CRITICAL: NO ROLEPLAY MODE ACTIVE** 🚫\n"
                    "   **YOU ARE ABSOLUTELY FORBIDDEN FROM DESCRIBING PHYSICAL ACTIONS.**\n"
                    "   **ANY RESPONSE WITH PHYSICAL DESCRIPTIONS WILL BE REJECTED.**\n\n"
                    "   ❌ FORBIDDEN - DO NOT WRITE:\n"
                    "   - Asterisks: '*trembles*', '*gulps*', '*nods*', '*smiles*'\n"
                    "   - Physical descriptions: 'trembles violently', 'gulps nervously', 'nods quickly'\n"
                    "   - Gestures: 'bows', 'waves', 'points', 'shrugs'\n"
                    "   - Facial expressions: 'smiles', 'frowns', 'blushes'\n"
                    "   - Body language: 'leans in', 'backs away', 'freezes'\n\n"
                    "   ✅ REQUIRED - ONLY WRITE:\n"
                    "   - Spoken words: 'H-hiya', 'Hey there', 'What's up'\n"
                    "   - Thoughts/reactions: 'Oh geez', 'Whoa', 'Okay'\n"
                    "   - Emotes only: ':emote_name:'\n\n"
                    "   **USE YOUR VOICE AND EMOTES ONLY. NO PHYSICAL DESCRIPTIONS WHATSOEVER.**\n"
                )

            if not personality_mode['allow_technical_language']:
                rule_num = 11 if not enable_roleplay else 10
                system_prompt += (
                    f"\n{rule_num}. **ABSOLUTELY NO TECHNICAL/ROBOTIC LANGUAGE**: NEVER use these terms:\n"
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

        # CRITICAL FIX: Filter out bot messages that were sent AFTER the current user's message
        # This prevents the AI from seeing its own response to a previous user (User A) when
        # generating a response for the current user (User B), which would cause duplicate responses.
        current_msg_timestamp = message.created_at.isoformat()
        bot_user_id = self.emote_handler.bot.user.id

        filtered_memory = []
        for msg_data in short_term_memory[-context_msg_count:]:
            # Always include user messages
            if msg_data["author_id"] != bot_user_id:
                filtered_memory.append(msg_data)
            else:
                # For bot messages, only include if timestamp is BEFORE current user's message
                msg_timestamp = msg_data.get("timestamp", "")
                if msg_timestamp and msg_timestamp < current_msg_timestamp:
                    filtered_memory.append(msg_data)
                else:
                    print(f"   FILTERED OUT bot message (timestamp {msg_timestamp} >= {current_msg_timestamp}): {msg_data.get('content', '')[:50]}")

        # Add conversation history
        for msg_data in filtered_memory:
            role = "assistant" if msg_data["author_id"] == self.emote_handler.bot.user.id else "user"
            clean_content = self._strip_discord_formatting(msg_data["content"])

            # Only include timestamps when temporal context is relevant
            time_str = ""
            if needs_temporal:
                relative_time = self._format_relative_time(msg_data.get("timestamp", ""))
                time_str = f" [{relative_time}]" if relative_time else ""

            # Only add author name prefix for user messages, not assistant messages
            # This prevents the bot from mimicking "Bot Name:" prefix in its responses
            if role == "user":
                # Get display name for this user
                author_name = "User"
                if message.guild:
                    member = message.guild.get_member(msg_data["author_id"])
                    if member:
                        author_name = member.display_name

                # Include nickname, user ID, and timestamp (if temporal) to help AI with context
                content = f'{author_name} (ID: {msg_data["author_id"]}){time_str}: {clean_content}'
            else:
                # Assistant messages: NO timestamps to prevent AI from mimicking [just now] format
                content = clean_content

            messages_for_api.append({'role': role, 'content': content})

        # Get model configuration for main response
        main_response_config = self._get_model_config('main_response')

        # Use dynamic max_tokens based on conversation energy
        dynamic_max_tokens = energy_analysis['max_tokens']

        # DEBUG: Log the actual messages being sent to API to diagnose duplicate responses
        print(f"\n🔍 CASUAL_CHAT API REQUEST for {author.name} (ID: {author.id}):")
        print(f"   Model: {main_response_config['model']}, max_tokens: {dynamic_max_tokens}, temp: {main_response_config['temperature']}")
        print(f"   Message count: {len(messages_for_api)}")
        for i, msg in enumerate(messages_for_api[-5:]):  # Last 5 messages
            role = msg['role']
            content_preview = msg['content'][:100].replace('\n', ' ')
            print(f"   [{i}] {role}: {content_preview}...")

        try:
            response = await self.client.chat.completions.create(
                model=main_response_config['model'],
                messages=messages_for_api,
                max_tokens=dynamic_max_tokens,
                temperature=main_response_config['temperature']
            )
            ai_response_text = response.choices[0].message.content.strip()
            print(f"   RESPONSE: {ai_response_text[:100]}...")

            if ai_response_text:
                # Apply roleplay formatting
                ai_response_text = self._apply_roleplay_formatting(ai_response_text, personality_config, energy_analysis.get('user_messages'))

                # Metrics now only update during memory consolidation (not after every message)
                # await self._analyze_sentiment_and_update_metrics(message, ai_response_text, author.id, db_manager)

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
            # Get channel configuration from database
            channel_id_str = str(channel.id)
            personality_config = db_manager.get_channel_setting(channel_id_str)
            if not personality_config:
                # Fallback to empty dict if channel not configured
                personality_config = {}

            bot_name = channel.guild.me.display_name

            # Get emotes with contextual hints for better selection
            available_emotes = self.emote_handler.get_emotes_with_context(guild_id=channel.guild.id)
            emote_count = self.emote_handler.get_emote_count(guild_id=channel.guild.id)

            # Calculate conversation energy for dynamic response length
            bot_id = channel.guild.me.id
            energy_analysis = self._calculate_conversation_energy(recent_messages, bot_id)

            # Determine energy level
            if energy_analysis['max_tokens'] <= 25:
                energy_level = "VERY LOW"
            elif energy_analysis['max_tokens'] <= 40:
                energy_level = "LOW"
            elif energy_analysis['max_tokens'] <= 60:
                energy_level = "MEDIUM"
            else:
                energy_level = "HIGH"

            # Check if temporal context would be useful for this conversation
            # For proactive engagement, check the recent messages for temporal keywords
            recent_text = ' '.join([msg.content for msg in recent_messages[-5:] if hasattr(msg, 'content')])
            needs_temporal = self._needs_temporal_context(recent_text)
            if needs_temporal:
                print(f"AI Handler (Proactive): Temporal context ENABLED")

            # Build bot identity from database (personality traits/lore)
            identity_prompt = self._build_bot_identity_prompt(db_manager, personality_config, include_temporal=needs_temporal)

            # Get server info if enabled
            personality_mode = self._get_personality_mode(personality_config)
            server_info = self._load_server_info(personality_config, channel.guild.id, channel.guild.name)

            # Build conversation history with ALL participants identified
            conversation_history = ""
            for msg in recent_messages[-20:]:  # Last 20 messages
                author_name = msg.author.display_name if hasattr(msg, 'author') else "Unknown"
                author_id = msg.author.id if hasattr(msg, 'author') else 0
                clean_content = self._strip_discord_formatting(msg.content)
                # Only include timestamps when temporal context is relevant
                time_str = ""
                if needs_temporal and hasattr(msg, 'created_at'):
                    relative_time = self._format_relative_time(msg.created_at.isoformat())
                    time_str = f" [{relative_time}]" if relative_time else ""
                conversation_history += f"{author_name} (ID: {author_id}){time_str}: {clean_content}\n"

            # Build energy override section for proactive responses
            energy_override = ""
            if energy_level == "VERY LOW":
                energy_override = (
                    "\n🚨 CRITICAL PRIORITY OVERRIDE 🚨\n"
                    "⚡ **CONVERSATION ENERGY IS VERY LOW** ⚡\n"
                    "This OVERRIDES ALL personality traits.\n"
                    "**ABSOLUTE REQUIREMENTS:**\n"
                    "- Respond with 1-6 words MAXIMUM (strict limit)\n"
                    "- CRITICAL: Stay contextually relevant - answer their message!\n"
                    "- Single emote responses are fine for reactions, not for questions\n"
                    "- FORBIDDEN: Full sentences, explanations, multiple thoughts\n\n"
                    "**RATIONALE**: Conversation energy is very low. Match brevity but stay relevant.\n\n"
                )
            elif energy_level == "LOW":
                energy_override = (
                    "\n🚨 CRITICAL PRIORITY OVERRIDE 🚨\n"
                    "⚡ **CONVERSATION ENERGY IS LOW** ⚡\n"
                    "**REQUIREMENTS:**\n"
                    "- Keep responses under 12 words (strict limit)\n"
                    "- 1 SHORT sentence or brief phrase only\n"
                    "- CRITICAL: Stay contextually relevant - answer their message!\n"
                    "- FORBIDDEN: Multiple sentences, detailed explanations\n\n"
                    "**RATIONALE**: Match the brief conversational style.\n\n"
                )

            # Create NEUTRAL system prompt (no specific user relationship context)
            system_prompt = (
                f"{identity_prompt}\n"
                f"{energy_override}"
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
                f"5. **EMOTES** ({emote_count} available - USE THEM ALL, not just favorites!):\n{available_emotes}\n"
                f"   **CRITICAL**: Match the emote to your EMOTION. Use the hints above to pick the RIGHT emote. "
                f"Rotate through ALL emotes - don't always use the same one!\n"
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

            # Use dynamic max_tokens based on conversation energy
            dynamic_max_tokens = energy_analysis['max_tokens']

            response = await self.client.chat.completions.create(
                model=main_response_config['model'],
                messages=messages_for_api,
                max_tokens=dynamic_max_tokens,
                temperature=main_response_config['temperature']
            )

            ai_response_text = response.choices[0].message.content.strip()

            if ai_response_text:
                # Apply roleplay formatting
                ai_response_text = self._apply_roleplay_formatting(ai_response_text, personality_config, energy_analysis.get('user_messages'))

                # Do NOT update relationship metrics (we're not talking to a specific user)
                # Do NOT extract self-lore (this is a neutral conversation join)

                return ai_response_text
            else:
                return None

        except Exception as e:
            print(f"AI Handler: Failed to generate proactive response: {e}")
            return None
