# modules/image_generator.py

import os
import io
import asyncio
from typing import Optional, Tuple
from together import Together


class ImageGenerator:
    """
    Handles AI image generation using Together.ai API.
    Generates childlike, crayon-style drawings based on user prompts.
    """

    def __init__(self, config_manager=None):
        """
        Initialize the image generator with Together.ai API.

        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        self.config_manager = config_manager
        self.api_key = os.getenv("TOGETHER_API_KEY")

        if not self.api_key:
            print("WARNING: TOGETHER_API_KEY not found in environment variables. Image generation will be disabled.")
            self.client = None
        else:
            self.client = Together(api_key=self.api_key)

        # Load configuration or use defaults
        self.enabled = True
        self.max_per_day = 5
        self.style_prefix = "Kindergarten art style, simple childlike drawing, colorful and playful, 2D sketch"
        self.model = "black-forest-labs/FLUX.1-schnell"

        if config_manager:
            config = config_manager.get_config()
            img_gen_config = config.get('image_generation', {})
            self.enabled = img_gen_config.get('enabled', True)
            self.max_per_day = img_gen_config.get('max_per_user_per_day', 5)
            self.style_prefix = img_gen_config.get('style_prefix', self.style_prefix)
            self.model = img_gen_config.get('model', self.model)

    def is_available(self) -> bool:
        """
        Check if image generation is available.

        Returns:
            bool: True if API key is set and feature is enabled
        """
        return self.client is not None and self.enabled

    def _build_prompt(self, user_prompt: str) -> str:
        """
        Build the full prompt with childlike style prefix.

        Args:
            user_prompt: The user's drawing request

        Returns:
            str: Full prompt with style prefix
        """
        # Clean up the user prompt
        user_prompt = user_prompt.strip()

        # Remove common prefixes like "draw", "sketch", "make me"
        for prefix in ["draw me a", "draw me an", "draw a", "draw an", "draw",
                       "sketch me a", "sketch me an", "sketch a", "sketch an", "sketch",
                       "make me a picture of", "make me a drawing of", "make a picture of",
                       "can you draw", "could you draw", "please draw"]:
            if user_prompt.lower().startswith(prefix):
                user_prompt = user_prompt[len(prefix):].strip()
                break

        # Build full prompt
        full_prompt = f"{self.style_prefix}, {user_prompt}"
        return full_prompt

    async def generate_image(self, user_prompt: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Generate an image based on the user's prompt.

        Args:
            user_prompt: The user's drawing request

        Returns:
            Tuple of (image_bytes, error_message):
                - image_bytes: PNG image data if successful, None if failed
                - error_message: Error description if failed, None if successful
        """
        if not self.is_available():
            return None, "Image generation is currently unavailable. API key not configured."

        try:
            # Build the full prompt
            full_prompt = self._build_prompt(user_prompt)
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
