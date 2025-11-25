# modules/image_refiner.py

import openai
import json
from datetime import datetime, timedelta

class ImageRefiner:
    """
    Detects when users want to refine/remake previously generated images
    and intelligently modifies the original prompt based on user feedback.
    """

    def __init__(self, config_manager):
        """
        Initialize the image refiner.

        Args:
            config_manager: ConfigManager instance for accessing configuration
        """
        self.config = config_manager.get_config().get('image_refinement', {})
        self.client = None  # Will be set by image generator

    def set_openai_client(self, client):
        """Set the OpenAI client (called by image generator during initialization)"""
        self.client = client

    async def detect_refinement(self, user_message, original_prompt, minutes_since_generation):
        """
        Analyzes user message to determine if they want to refine the previous image.

        Args:
            user_message: The user's current message
            original_prompt: The prompt used to generate the previous image
            minutes_since_generation: How many minutes ago the image was generated

        Returns:
            dict: {
                "is_refinement": bool,
                "confidence": float (0.0-1.0),
                "changes_requested": str (description of requested changes)
            }
        """
        print(f"\n{'='*80}")
        print(f"IMAGE REFINEMENT DETECTION - START")
        print(f"{'='*80}")
        print(f"User message: '{user_message}'")
        print(f"Original prompt: '{original_prompt}'")
        print(f"Minutes since generation: {minutes_since_generation:.1f}")

        if not self.client:
            print("ImageRefiner: OpenAI client not set, cannot detect refinement")
            print(f"{'='*80}\n")
            return {"is_refinement": False, "confidence": 0.0, "changes_requested": ""}

        system_prompt = f"""You are analyzing a Discord message to determine if the user wants to refine/remake a recently generated image.

CONTEXT:
- The bot just generated an image for this user
- Original prompt: "{original_prompt}"
- Time since generation: {minutes_since_generation} minutes ago

USER'S MESSAGE: "{user_message}"

Determine if this message is requesting a REFINEMENT of the previous image.

Indicators of refinement request:
✅ Corrections: "no, I said...", "you forgot the...", "it's missing..."
✅ Additions: "also add...", "can you include...", "with a sword too"
✅ Modifications: "make it bigger", "change the color to...", "make it hold..."
✅ Critiques: "that's wrong", "not what I wanted", "redo it with..."

NOT a refinement request:
❌ General conversation: "that's cool!", "I like it", "thanks"
❌ Unrelated message: "what's the weather?", "hey how are you"
❌ New image request: "now draw a dog", "draw something else"

Respond with JSON:
{{
  "is_refinement": true/false,
  "confidence": 0.0-1.0,
  "changes_requested": "brief description of what user wants changed" (if is_refinement=true, otherwise empty string)
}}

Return ONLY valid JSON, no explanations."""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.get('detection_model', 'gpt-4o-mini'),
                messages=[{'role': 'system', 'content': system_prompt}],
                max_tokens=self.config.get('detection_max_tokens', 100),
                temperature=self.config.get('detection_temperature', 0.0)
            )

            result_text = response.choices[0].message.content.strip()

            # Parse JSON response
            try:
                result = json.loads(result_text)
                is_refinement = result.get('is_refinement', False)
                confidence = float(result.get('confidence', 0.0))
                changes = result.get('changes_requested', '')

                # Clamp confidence to valid range
                confidence = max(0.0, min(1.0, confidence))

                print(f"✅ REFINEMENT DETECTION RESULT:")
                print(f"   is_refinement: {is_refinement}")
                print(f"   confidence: {confidence:.2f}")
                print(f"   changes_requested: {changes}")
                print(f"{'='*80}\n")

                return {
                    "is_refinement": is_refinement,
                    "confidence": confidence,
                    "changes_requested": changes
                }
            except json.JSONDecodeError:
                print(f"❌ ImageRefiner: Failed to parse JSON response: {result_text}")
                print(f"{'='*80}\n")
                return {"is_refinement": False, "confidence": 0.0, "changes_requested": ""}

        except Exception as e:
            print(f"❌ ImageRefiner: Error detecting refinement: {e}")
            print(f"{'='*80}\n")
            return {"is_refinement": False, "confidence": 0.0, "changes_requested": ""}

    async def modify_prompt(self, original_prompt, changes_requested):
        """
        Uses GPT-4o to intelligently modify the original prompt based on user feedback.

        Args:
            original_prompt: The original image generation prompt
            changes_requested: Description of what the user wants changed

        Returns:
            str: Modified prompt for image generation
        """
        print(f"\n{'='*80}")
        print(f"PROMPT MODIFICATION - START")
        print(f"{'='*80}")
        print(f"Original prompt: '{original_prompt}'")
        print(f"Changes requested: '{changes_requested}'")

        if not self.client:
            print("❌ ImageRefiner: OpenAI client not set, cannot modify prompt")
            print(f"{'='*80}\n")
            return original_prompt

        system_prompt = f"""You are making MINIMAL modifications to an image prompt.

ORIGINAL PROMPT: "{original_prompt}"

USER FEEDBACK: "{changes_requested}"

**YOUR ONLY JOB:** Make the SMALLEST possible change to satisfy the feedback.

**ABSOLUTE RULES - VIOLATIONS WILL BE REJECTED:**
1. **NO NEW PEOPLE** - Never add humans, chefs, handlers, characters, etc.
2. **NO NEW SCENES** - Never add kitchens, backgrounds, settings, etc.
3. **NO CREATIVITY** - Only change exactly what was requested
4. **LITERAL INTERPRETATION** - "plate it with wings" = put it on a plate with chicken wings, NOT add wing accessories

**Examples:**
- Original: "a hot sauce bottle"
  Feedback: "plate it with wings"
  New Prompt: "a hot sauce bottle on a plate with chicken wings"
  WRONG: "chefs in a kitchen with hot sauce" ❌

- Original: "a dragon"
  Feedback: "make it blue"
  New Prompt: "a blue dragon"
  WRONG: "a blue dragon in a magical forest with a wizard" ❌

- Original: "an ice turtle"
  Feedback: "give it a red tail"
  New Prompt: "an ice turtle with a red tail"
  WRONG: "an ice turtle with handlers in the arctic" ❌

Return ONLY the minimally modified prompt (no explanations)."""

        try:
            response = await self.client.chat.completions.create(
                model=self.config.get('modification_model', 'gpt-4o'),
                messages=[{'role': 'system', 'content': system_prompt}],
                max_tokens=self.config.get('modification_max_tokens', 100),
                temperature=0.0  # Zero temperature for deterministic, non-creative output
            )

            modified_prompt = response.choices[0].message.content.strip()

            # Remove quotes if AI added them
            modified_prompt = modified_prompt.strip('"\'')

            print(f"✅ MODIFIED PROMPT: '{modified_prompt}'")
            print(f"{'='*80}\n")

            return modified_prompt

        except Exception as e:
            print(f"❌ ImageRefiner: Error modifying prompt: {e}")
            print(f"{'='*80}\n")
            return original_prompt  # Fallback to original if modification fails
