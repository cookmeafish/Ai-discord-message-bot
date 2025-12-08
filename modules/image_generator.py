# modules/image_generator.py

import os
import io
import asyncio
import re
from typing import Optional, Tuple, List, Dict
from together import Together
from datetime import datetime, timedelta


class ImageGenerator:
    """
    Handles AI image generation using Together.ai API.
    Generates childlike, crayon-style drawings based on user prompts.
    """

    def __init__(self, config_manager=None, openai_client=None):
        """
        Initialize the image generator with Together.ai API.

        Args:
            config_manager: ConfigManager instance for accessing configuration
            openai_client: OpenAI client for AI-enhanced descriptions (optional)
        """
        self.config_manager = config_manager
        self.openai_client = openai_client
        self.api_key = os.getenv("TOGETHER_API_KEY")

        if not self.api_key:
            print("WARNING: TOGETHER_API_KEY not found in environment variables. Image generation will be disabled.")
            self.client = None
        else:
            self.client = Together(api_key=self.api_key)

        # Load configuration or use defaults
        self.enabled = True
        self.max_per_day = 5
        self.style_prefix = "High quality detailed illustration, clean image, visual only"
        self.model = "black-forest-labs/FLUX.1-schnell"
        self.enhance_with_ai = True

        if config_manager:
            config = config_manager.get_config()
            img_gen_config = config.get('image_generation', {})
            self.enabled = img_gen_config.get('enabled', True)
            self.max_per_day = img_gen_config.get('max_per_user_per_day', 5)
            self.style_prefix = img_gen_config.get('style_prefix', self.style_prefix)
            self.model = img_gen_config.get('model', self.model)
            self.enhance_with_ai = img_gen_config.get('enhance_with_ai_description', True)

        # Prompt cache for image refinement
        # Format: {user_id: {"prompt": str, "timestamp": datetime, "refinement_count": int}}
        self.recent_prompts = {}

        # Initialize image refiner
        from modules.image_refiner import ImageRefiner
        self.refiner = ImageRefiner(config_manager) if config_manager else None
        if self.refiner and self.openai_client:
            self.refiner.set_openai_client(self.openai_client)

    def is_available(self) -> bool:
        """
        Check if image generation is available.

        Returns:
            bool: True if API key is set and feature is enabled
        """
        return self.client is not None and self.enabled

    # ==================== PROMPT CACHING FOR IMAGE REFINEMENT ====================

    def cache_prompt(self, user_id: int, prompt: str):
        """
        Cache the prompt used for image generation to enable refinement.

        Args:
            user_id: Discord user ID
            prompt: The prompt that was used to generate the image
        """
        self.recent_prompts[user_id] = {
            "prompt": prompt,
            "timestamp": datetime.now(),
            "refinement_count": 0
        }
        print(f"ImageGenerator: Cached prompt for user {user_id}: '{prompt[:50]}...'")

    def get_cached_prompt(self, user_id: int) -> Optional[Dict]:
        """
        Get the cached prompt for a user if within the cache duration window.

        Args:
            user_id: Discord user ID

        Returns:
            dict: {"prompt": str, "timestamp": datetime, "refinement_count": int} or None if expired/not found
        """
        if user_id not in self.recent_prompts:
            return None

        cached = self.recent_prompts[user_id]
        cache_duration = timedelta(minutes=self.config_manager.get_config().get('image_refinement', {}).get('cache_duration_minutes', 10))

        # Check if cache has expired
        if datetime.now() - cached["timestamp"] > cache_duration:
            print(f"ImageGenerator: Cached prompt expired for user {user_id}")
            del self.recent_prompts[user_id]
            return None

        return cached

    def increment_refinement_count(self, user_id: int) -> int:
        """
        Increment the refinement count for a user's cached prompt.

        Args:
            user_id: Discord user ID

        Returns:
            int: New refinement count
        """
        if user_id in self.recent_prompts:
            self.recent_prompts[user_id]["refinement_count"] += 1
            return self.recent_prompts[user_id]["refinement_count"]
        return 0

    def clear_cache(self, user_id: int):
        """
        Clear the cached prompt for a user.

        Args:
            user_id: Discord user ID
        """
        if user_id in self.recent_prompts:
            del self.recent_prompts[user_id]
            print(f"ImageGenerator: Cleared prompt cache for user {user_id}")

    async def _get_enhanced_visual_description(
        self,
        user_prompt: str,
        db_manager,
        short_term_memory: List[Dict] = None,
        provided_context: str = None
    ) -> Optional[str]:
        """
        Consult GPT-4 to get an enhanced visual description of the subject.

        This method:
        1. Extracts the subject from the user's prompt
        2. Uses provided_context (database facts from ai_handler) as PRIMARY source
        3. Checks short-term memory for recent descriptions
        4. Consults GPT-4 to enhance visual details (avoiding conflicting generic knowledge)
        5. Returns a detailed visual description optimized for image generation

        Args:
            user_prompt: The cleaned drawing request (e.g., "Donald Trump", "a dragon")
            db_manager: Database manager for accessing long-term memory
            short_term_memory: Recent conversation messages
            provided_context: Pre-extracted database facts from ai_handler (PRIORITY SOURCE)

        Returns:
            str: Enhanced visual description, or None if enhancement fails/disabled
        """
        # Check if enhancement is enabled and OpenAI client is available
        if not self.enhance_with_ai or not self.openai_client:
            print("Image Generator: AI description enhancement disabled or OpenAI client not available")
            return None

        try:
            # Clean the prompt to extract just the subject
            subject = user_prompt.strip()

            # Remove common command prefixes to get the actual subject
            for prefix in ["draw me a", "draw me an", "draw me", "draw a", "draw an", "draw",
                           "sketch me a", "sketch me an", "sketch me", "sketch a", "sketch an", "sketch",
                           "make me a picture of", "make me a drawing of", "make a picture of",
                           "can you draw", "could you draw", "please draw",
                           "generate a", "generate an", "generate",
                           "create a", "create an", "create"]:
                if subject.lower().startswith(prefix):
                    subject = subject[len(prefix):].strip()
                    break

            print(f"Image Generator: Enhancing description for subject: '{subject}'")

            # PRIORITY: Use provided_context from ai_handler (already contains database facts)
            # This ensures we use the comprehensive fact extraction done by ai_handler
            database_context = []
            if provided_context:
                database_context.append(provided_context)
                print(f"Image Generator: Using provided database context: {provided_context[:200]}...")

            # CRITICAL FIX: For simple generic subjects (1-2 words without specific names),
            # SKIP conversation context entirely to prevent contamination
            # Common generic subjects should NOT be influenced by random conversation
            subject_word_count = len(subject.split())
            is_simple_subject = subject_word_count <= 3 and not provided_context

            # Gather context from short-term memory (recent conversation)
            # BUT ONLY for complex subjects or when we have database context
            subject_words = [word.lower() for word in subject.split() if len(word) > 2]
            conversation_context = []
            if short_term_memory and subject_words and not is_simple_subject:
                print(f"Image Generator: Checking {len(short_term_memory)} recent messages for context")
                # Check last 20 messages for descriptions of the subject
                for msg_dict in short_term_memory[-20:]:
                    msg_content = msg_dict.get('content', '')
                    msg_content_lower = msg_content.lower()

                    # Check if any subject words appear in this message
                    if any(word in msg_content_lower for word in subject_words):
                        # Check if it's a descriptive statement (contains "is", "are", "was", "were", "has", "have")
                        if any(verb in msg_content_lower for verb in [' is ', ' are ', ' was ', ' were ', ' has ', ' have ']):
                            conversation_context.append(msg_content)
                            print(f"Image Generator: Found conversation context: {msg_content[:100]}")
            elif is_simple_subject:
                print(f"Image Generator: SKIPPING conversation context for simple subject '{subject}' to prevent contamination")

            # Build the AI prompt to enhance the description
            context_parts = []
            if database_context:
                context_parts.append(f"**CRITICAL DATABASE FACTS (USE THESE FIRST):**\n" + "\n".join([f"- {fact}" for fact in database_context]))
            if conversation_context:
                context_parts.append(f"**Recent conversation:**\n" + "\n".join([f"- {msg}" for msg in conversation_context[:5]]))

            combined_context = "\n\n".join(context_parts) if context_parts else "No specific context available."

            # Detect if this is a multi-subject or action scene
            # Action words indicate a scene with interactions, not just a portrait
            action_words = [
                'fighting', 'fight', 'battling', 'battle', 'running', 'run', 'walking', 'walk',
                'sitting', 'sit', 'standing', 'stand', 'talking', 'talk', 'eating', 'eat',
                'hugging', 'hug', 'kissing', 'kiss', 'dancing', 'dance', 'playing', 'play',
                'with', 'and', 'beside', 'next to', 'holding', 'hold', 'versus', 'vs',
                'chasing', 'chase', 'riding', 'ride', 'flying', 'fly', 'swimming', 'swim',
                'arguing', 'argue', 'laughing', 'laugh', 'crying', 'cry', 'meeting', 'meet'
            ]

            subject_lower = subject.lower()
            is_action_scene = any(action in subject_lower for action in action_words)

            # Also check if multiple people are mentioned (indicates multi-subject scene)
            # Count words that might be names (capitalized words or words in database context)
            potential_subjects = 0
            if provided_context:
                # If we have database context with multiple people's facts separated by periods
                potential_subjects = provided_context.count('. ') + 1  # Rough estimate

            is_multi_subject = potential_subjects >= 2 or is_action_scene

            if is_multi_subject or is_action_scene:
                print(f"Image Generator: Detected MULTI-SUBJECT or ACTION SCENE - will preserve full scene description")

            # Determine if database facts describe a specific person/entity
            # This helps GPT-4 know whether to add generic knowledge or just enhance visual details
            has_specific_person_facts = False
            if database_context and provided_context:
                # CRITICAL FIX (2025-10-27): If we have ANY substantial database facts about a subject,
                # treat them as a specific database person to prevent GPT-4 from hallucinating random details.
                # Even if facts don't describe appearance, we should use "database user mode" instead of
                # "generic mode" to avoid adding conflicting made-up details (e.g., "red hair girl" for a database user).

                # If database context has substantial text (50+ chars), it's a specific person
                if len(provided_context.strip()) >= 50:
                    has_specific_person_facts = True
                    print(f"Image Generator: Database has substantial facts ({len(provided_context)} chars) - treating as SPECIFIC PERSON to prevent hallucination")
                else:
                    # Fallback: Check identity markers for very short contexts
                    identity_markers = ['he is', 'she is', 'they are', 'ruler', 'manager', 'friend', 'powerful', 'feared',
                                       'handsome', 'beautiful', 'strong', 'intelligent', 'user', 'person', 'man', 'woman']
                    context_lower = provided_context.lower()
                    if any(marker in context_lower for marker in identity_markers):
                        has_specific_person_facts = True
                        print(f"Image Generator: Database describes a SPECIFIC PERSON (identity markers detected) - will avoid conflicting generic knowledge")

            # Build prompt based on scene type
            if is_multi_subject or is_action_scene:
                # NEW: Multi-subject or action scene - preserve ENTIRE scene with all people and actions
                enhancement_prompt = f"""You are helping to create a detailed visual description for an image generation AI.

**Scene to draw:** {subject}

**Available context:**
{combined_context}

**CRITICAL INSTRUCTION:**
This is a MULTI-PERSON SCENE or ACTION SCENE. You must describe the ENTIRE scene, including:
1. **ALL people mentioned** - describe each person's appearance
2. **The action/interaction** - preserve what they're doing (fighting, sitting, talking, etc.)
3. **The composition** - how they're positioned relative to each other

**Task:**
Create a detailed, visual description of the COMPLETE SCENE:
1. **Identify ALL subjects** in the prompt (there may be 2+ people/entities)
2. **For EACH person**: Use database facts (if provided) OR your knowledge of famous people/characters
3. **Describe the action**: Preserve the interaction (e.g., "fighting" → "engaged in combat", "sitting with" → "seated beside")
4. **Scene composition**: Describe their positions and dynamic interaction

**Requirements:**
- Describe EVERY person mentioned, don't skip anyone
- Keep the action/interaction central to the description
- Use database facts for specific people, general knowledge for famous people/characters
- Be specific about poses, expressions, and spatial relationships
- Keep it under 150 words
- Don't mention "database" or "context" - just provide the scene description naturally
- **CONTENT SAFETY**: Avoid words like "muscular", "bare", "naked", "revealing" - keep descriptions PG-rated and focused on clothed appearances

**Example output for "UserA fighting UserB":**
"A fierce confrontation between two figures: UserA (a powerful woman with long dark hair, intense eyes, wearing combat gear) engaged in dynamic combat with UserB (a tall man with short blonde hair, determined expression, athletic build), both in aggressive fighting stances, fists raised, facing each other with tension and energy"

**Example output for "PersonX sitting with PersonY":**
"Two figures seated side by side: PersonX (elderly person with distinctive features, formal attire) sitting beside PersonY (middle-aged person with professional appearance, warm expression), both positioned at a table in conversation"

**Your visual description of the COMPLETE SCENE:**"""
            elif has_specific_person_facts:
                # Database describes a specific person - DON'T add conflicting generic knowledge
                enhancement_prompt = f"""You are helping to create a detailed visual description for an image generation AI.

**Subject to draw:** {subject}

**Available context:**
{combined_context}

**CRITICAL INSTRUCTION:**
The database facts describe a SPECIFIC REAL PERSON named "{subject}". This is NOT a character from media/games/shows.

**Task:**
Create a detailed, visual description using ONLY the database facts provided:
1. **USE ONLY DATABASE FACTS** - Do not add knowledge about unrelated characters with the same name
2. **DO NOT** assume this is a character from any media, game, anime, or show you know about
3. **ONLY** enhance visual details that are implied by the database facts (e.g., "feared man" → "intimidating gaze, strong posture")
4. If database says "handsome, strong man" → describe facial features, build, and style that match these traits
5. If database says "ruler" → describe regal clothing, commanding presence

**CRITICAL: If database facts contain NO visual appearance details** (no hair, eyes, clothing, facial features):
- Create a **GENERIC NEUTRAL HUMAN** appearance
- Use phrases like "a person" or "an individual" (do NOT invent specific hair colors, eye colors, or detailed features)
- Example: "A person with a neutral expression" instead of "A red-haired girl with green eyes"
- Focus on body language/posture that matches personality traits in the database
- **NEVER** invent specific physical features (hair color, eye color, etc.) that aren't in the database

**Requirements:**
- **NEVER** add information that contradicts or replaces the database identity
- Focus ONLY on translating abstract traits ("powerful", "feared", "YouTuber") into concrete visual details (posture, expression, clothing style)
- Keep it under 100 words
- Don't mention "database" - just provide the description naturally
- **CONTENT SAFETY**: Avoid words like "muscular", "bare", "naked", "revealing" - keep descriptions PG-rated and focused on clothed appearances

**Example output (with visual facts):**
"A handsome, strong man with a commanding presence that inspires fear, intelligent eyes showing wisdom, wearing regal dark clothing befitting a ruler, powerful build, stern facial features"

**Example output (NO visual facts, only personality/behavior):**
"A person with a confident posture and an intimidating presence, dressed casually, with an expression that commands respect"

**Your visual description:**"""
            else:
                # No specific database person facts - can use full generic knowledge
                enhancement_prompt = f"""🚨🚨🚨 CRITICAL: DESCRIBE ONLY "{subject}" - NOTHING ELSE 🚨🚨🚨

**SUBJECT TO DRAW:** "{subject}"

⚠️ ABSOLUTE RULES - VIOLATION = REJECTED:
1. **ONE SUBJECT ONLY** - If user asks for "{subject}", describe ONLY that ONE thing
2. **NO EXTRA PEOPLE** - NEVER add romantic partners, companions, friends, couples, etc.
3. **NO EXTRA SCENES** - Don't add coffee shops, restaurants, dates, or any setting not requested
4. **NO ROMANTIC CONTEXT** - "handsome" means ATTRACTIVE APPEARANCE, not "on a date with someone"
5. **LITERAL INTERPRETATION** - "draw X handsomely" = draw X looking attractive, ALONE

**WHAT "HANDSOMELY/BEAUTIFULLY" MEANS:**
- It describes HOW to draw the subject (attractively)
- It does NOT mean "add a romantic partner" or "put them on a date"
- Example: "draw Alice handsomely" = Alice looking handsome, ALONE, not Alice with a partner

**WHAT TO INCLUDE:**
- Physical appearance of "{subject}" ONLY
- If subject is a PERSON: face, hair, clothing, expression, pose
- If subject is an OBJECT: colors, textures, materials
- Style/mood requested (handsome, cute, scary, etc.)

**WHAT TO NEVER INCLUDE:**
❌ Additional people not mentioned in "{subject}"
❌ Romantic partners, couples, companions
❌ Coffee shops, restaurants, date scenes
❌ Any scene, background, or setting not explicitly requested
❌ Anything beyond what the user literally asked for

**OUTPUT:** A description of "{subject}" ALONE (under 80 words).

Your description:"""

            print("Image Generator: Consulting GPT-4 for enhanced description...")

            # Get model config from config_manager
            config = self.config_manager.get_config() if self.config_manager else {}
            model_config = config.get('ai_models', {}).get('vision_description', {
                'model': 'gpt-4o-mini',
                'max_tokens': 300,
                'temperature': 0.3
            })

            # Use 300 tokens for initial drawings (enough for detailed descriptions)
            max_tokens = model_config.get('max_tokens', 300)

            response = await self.openai_client.chat.completions.create(
                model=model_config.get('model', 'gpt-4o-mini'),
                messages=[{'role': 'user', 'content': enhancement_prompt}],
                max_tokens=max_tokens,
                temperature=0.0  # Zero temperature for deterministic, literal output
            )

            enhanced_description = response.choices[0].message.content.strip()
            print(f"Image Generator: Enhanced description: {enhanced_description}")

            return enhanced_description

        except Exception as e:
            print(f"Image Generator: Error enhancing description: {e}")
            return None

    def _build_prompt(self, user_prompt: str, context: str = None) -> str:
        """
        Build the full prompt with style prefix and optional context.

        Args:
            user_prompt: The user's drawing request
            context: Optional context about the subject (e.g., facts about a person)

        Returns:
            str: Full prompt with style prefix and context
        """
        # Clean up the user prompt
        user_prompt = user_prompt.strip()

        # Remove common command prefixes
        # Order matters: check longer patterns first
        for prefix in ["draw me a", "draw me an", "draw me", "draw a", "draw an", "draw",
                       "sketch me a", "sketch me an", "sketch me", "sketch a", "sketch an", "sketch",
                       "make me a picture of", "make me a drawing of", "make a picture of",
                       "can you draw", "could you draw", "please draw",
                       "generate a", "generate an", "generate",
                       "create a", "create an", "create"]:
            if user_prompt.lower().startswith(prefix):
                user_prompt = user_prompt[len(prefix):].strip()
                break

        # Build full prompt with optional context
        if context:
            # Integrate context directly with the subject for better results
            # Instead of "alice. Is a handsome man" (AI thinks alice is separate)
            # We want "a handsome, strong, feared man (alice is: Head Event Manager...)"
            full_prompt = f"{self.style_prefix}, {context}"
        else:
            full_prompt = f"{self.style_prefix}, {user_prompt}"
        return full_prompt

    async def generate_image(
        self,
        user_prompt: str,
        context: str = None,
        db_manager=None,
        short_term_memory: List[Dict] = None,
        is_refinement: bool = False
    ) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        """
        Generate an image based on the user's prompt with optional context.

        Args:
            user_prompt: The user's drawing request
            context: Optional context about the subject (e.g., facts about a person)
            db_manager: Database manager for enhanced descriptions (optional)
            short_term_memory: Recent conversation for enhanced descriptions (optional)
            is_refinement: If True, skip AI enhancement (prompt already refined minimally)

        Returns:
            Tuple of (image_bytes, error_message, full_prompt):
                - image_bytes: PNG image data if successful, None if failed
                - error_message: Error description if failed, None if successful
                - full_prompt: The complete prompt that was sent to the image API (for caching)
        """
        if not self.is_available():
            return None, "Image generation is currently unavailable. API key not configured.", None

        try:
            # Try to get enhanced description if enabled and dependencies available
            # SKIP enhancement for refinements - the prompt has already been carefully modified
            enhanced_context = None
            if is_refinement:
                print("Image Generator: SKIPPING AI enhancement (refinement mode - using prompt as-is)")
            elif self.enhance_with_ai and db_manager and self.openai_client:
                print("Image Generator: Attempting AI-enhanced description...")
                enhanced_context = await self._get_enhanced_visual_description(
                    user_prompt,
                    db_manager,
                    short_term_memory,
                    context  # Pass database context from ai_handler as priority source
                )

            # Use enhanced context if available, otherwise fall back to provided context
            final_context = enhanced_context if enhanced_context else context

            # Build the full prompt with context
            # For refinements, the prompt already has style_prefix from original generation - don't add again
            # Also, modify_prompt() now integrates user context DIRECTLY into the prompt,
            # so we should NOT append it again here (would cause duplicate descriptions)
            if is_refinement:
                full_prompt = user_prompt  # Already has style_prefix AND user context from modify_prompt()
                print(f"Image Generator: Using refinement prompt as-is (user context already integrated)")
            else:
                full_prompt = self._build_prompt(user_prompt, final_context)
            print(f"Generating image with prompt: {full_prompt}")

            # Generate image using Together.ai
            # Run in thread pool since Together SDK is synchronous
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.images.generate(
                    prompt=full_prompt,
                    model=self.model,
                    width=512,
                    height=512,
                    steps=4,  # FLUX.1-schnell is optimized for 4 steps
                    n=1
                )
            )

            # Get the image URL from response
            if hasattr(response, 'data') and len(response.data) > 0:
                image_data = response.data[0]

                # Together.ai returns base64 encoded image in b64_json format OR a URL
                # Check which format is provided
                if hasattr(image_data, 'b64_json') and image_data.b64_json is not None:
                    import base64
                    image_bytes = base64.b64decode(image_data.b64_json)
                    # Return image bytes, no error, and the full prompt that was used
                    return image_bytes, None, full_prompt
                # Or it might return a URL
                elif hasattr(image_data, 'url') and image_data.url is not None:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        img_response = await client.get(image_data.url)
                        if img_response.status_code == 200:
                            return img_response.content, None, full_prompt
                        else:
                            return None, f"Failed to download image from URL: {img_response.status_code}", None
                else:
                    return None, "Unexpected response format from Together.ai API", None
            else:
                return None, "No image data in API response", None

        except Exception as e:
            error_msg = f"Error generating image: {str(e)}"
            print(error_msg)
            return None, error_msg, None

    def get_rate_limit_info(self) -> dict:
        """
        Get rate limit configuration.

        Returns:
            dict: Rate limit information
        """
        return {
            "max_per_day": self.max_per_day,
            "enabled": self.enabled
        }
