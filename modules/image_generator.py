# modules/image_generator.py

import os
import io
import asyncio
import re
from typing import Optional, Tuple, List, Dict
from together import Together


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

    def is_available(self) -> bool:
        """
        Check if image generation is available.

        Returns:
            bool: True if API key is set and feature is enabled
        """
        return self.client is not None and self.enabled

    async def _get_enhanced_visual_description(
        self,
        user_prompt: str,
        db_manager,
        short_term_memory: List[Dict] = None
    ) -> Optional[str]:
        """
        Consult GPT-4 to get an enhanced visual description of the subject.

        This method:
        1. Extracts the subject from the user's prompt
        2. Checks database (long-term memory) for facts about the subject
        3. Checks short-term memory for recent descriptions
        4. Consults GPT-4 to combine all sources and fill gaps with general knowledge
        5. Returns a detailed visual description optimized for image generation

        Args:
            user_prompt: The cleaned drawing request (e.g., "Donald Trump", "a dragon")
            db_manager: Database manager for accessing long-term memory
            short_term_memory: Recent conversation messages

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

            # Gather context from database (long-term memory)
            database_context = []
            subject_words = [word.lower() for word in subject.split() if len(word) > 2]

            if subject_words:
                # Search long-term memory for any facts mentioning the subject
                # This is a simple approach - we could make it more sophisticated
                all_facts = db_manager.get_all_long_term_memory()
                for fact_tuple in all_facts:
                    fact_text = fact_tuple[0]
                    fact_lower = fact_text.lower()
                    # Check if any subject words appear in this fact
                    if any(word in fact_lower for word in subject_words):
                        database_context.append(fact_text)
                        print(f"Image Generator: Found database fact: {fact_text}")

            # Gather context from short-term memory (recent conversation)
            conversation_context = []
            if short_term_memory:
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

            # Build the AI prompt to enhance the description
            context_parts = []
            if database_context:
                context_parts.append(f"**Database facts:**\n" + "\n".join([f"- {fact}" for fact in database_context[:5]]))
            if conversation_context:
                context_parts.append(f"**Recent conversation:**\n" + "\n".join([f"- {msg}" for msg in conversation_context[:5]]))

            combined_context = "\n\n".join(context_parts) if context_parts else "No specific context available."

            enhancement_prompt = f"""You are helping to create a detailed visual description for an image generation AI.

**Subject to draw:** {subject}

**Available context:**
{combined_context}

**Task:**
Create a detailed, visual description of "{subject}" that combines:
1. Any facts from the database/conversation above
2. Your general knowledge about what "{subject}" looks like
3. Specific visual details that would help an image AI draw accurately

**Requirements:**
- Focus on VISUAL details only (appearance, colors, clothing, style, physical features)
- Be specific and detailed (not vague)
- Combine database facts with general knowledge seamlessly
- If it's a person, include: age range, hair, facial features, typical clothing/style
- If it's an object/creature, include: shape, colors, distinctive features
- Keep it under 100 words
- Don't mention the database or conversation - just provide the description

**Example output:**
"A man in his late 70s with distinctive orange-blonde hair styled in a combover, blue eyes, wearing a dark navy suit with a red tie, confident posture"

**Your visual description:**"""

            print("Image Generator: Consulting GPT-4 for enhanced description...")

            # Get model config from config_manager
            config = self.config_manager.get_config() if self.config_manager else {}
            model_config = config.get('ai_models', {}).get('vision_description', {
                'model': 'gpt-4o-mini',
                'max_tokens': 150,
                'temperature': 0.3
            })

            response = await self.openai_client.chat.completions.create(
                model=model_config.get('model', 'gpt-4o-mini'),
                messages=[{'role': 'user', 'content': enhancement_prompt}],
                max_tokens=model_config.get('max_tokens', 150),
                temperature=model_config.get('temperature', 0.3)
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
            # Instead of "zekke. Is a handsome man" (AI thinks zekke is separate)
            # We want "a handsome, strong, feared man (zekke is: Head Event Manager...)"
            full_prompt = f"{self.style_prefix}, {context}"
        else:
            full_prompt = f"{self.style_prefix}, {user_prompt}"
        return full_prompt

    async def generate_image(
        self,
        user_prompt: str,
        context: str = None,
        db_manager=None,
        short_term_memory: List[Dict] = None
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Generate an image based on the user's prompt with optional context.

        Args:
            user_prompt: The user's drawing request
            context: Optional context about the subject (e.g., facts about a person)
            db_manager: Database manager for enhanced descriptions (optional)
            short_term_memory: Recent conversation for enhanced descriptions (optional)

        Returns:
            Tuple of (image_bytes, error_message):
                - image_bytes: PNG image data if successful, None if failed
                - error_message: Error description if failed, None if successful
        """
        if not self.is_available():
            return None, "Image generation is currently unavailable. API key not configured."

        try:
            # Try to get enhanced description if enabled and dependencies available
            enhanced_context = None
            if self.enhance_with_ai and db_manager and self.openai_client:
                print("Image Generator: Attempting AI-enhanced description...")
                enhanced_context = await self._get_enhanced_visual_description(
                    user_prompt,
                    db_manager,
                    short_term_memory
                )

            # Use enhanced context if available, otherwise fall back to provided context
            final_context = enhanced_context if enhanced_context else context

            # Build the full prompt with context
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
                    return image_bytes, None
                # Or it might return a URL
                elif hasattr(image_data, 'url') and image_data.url is not None:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        img_response = await client.get(image_data.url)
                        if img_response.status_code == 200:
                            return img_response.content, None
                        else:
                            return None, f"Failed to download image from URL: {img_response.status_code}"
                else:
                    return None, "Unexpected response format from Together.ai API"
            else:
                return None, "No image data in API response"

        except Exception as e:
            error_msg = f"Error generating image: {str(e)}"
            print(error_msg)
            return None, error_msg

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
