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

    async def detect_refinement(self, user_message, original_prompt, minutes_since_generation, recent_conversation=None):
        """
        Analyzes user message to determine if they want to refine the previous image.

        Args:
            user_message: The user's current message
            original_prompt: The prompt used to generate the previous image
            minutes_since_generation: How many minutes ago the image was generated
            recent_conversation: List of recent messages to detect topic changes

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
        print(f"Recent conversation provided: {len(recent_conversation) if recent_conversation else 0} messages")

        if not self.client:
            print("ImageRefiner: OpenAI client not set, cannot detect refinement")
            print(f"{'='*80}\n")
            return {"is_refinement": False, "confidence": 0.0, "changes_requested": ""}

        # Build conversation context string if provided
        conversation_context = ""
        if recent_conversation:
            conversation_context = "\nRECENT CONVERSATION (to detect topic changes):\n"
            for msg in recent_conversation[-5:]:  # Last 5 messages
                conversation_context += f"- {msg}\n"

        system_prompt = f"""You are analyzing a Discord message to determine if the user wants to refine/remake a recently generated image.

CONTEXT:
- The bot generated an image for this user
- Original prompt: "{original_prompt}"
- Time since generation: {minutes_since_generation} minutes ago
{conversation_context}
USER'S CURRENT MESSAGE: "{user_message}"

Determine if this message is requesting a REFINEMENT of the previous image.

**CRITICAL - CHECK FOR TOPIC CHANGE FIRST**:
Look at the recent conversation. If the user has:
- Asked unrelated questions ("what are you doing later?", "how are you?")
- Had a back-and-forth conversation about a different topic
- Moved on from the image entirely
Then the current message is likely responding to THAT conversation, NOT the image!

Example of topic change (NOT a refinement):
- Bot generates image
- User: "what are you doing later today?"
- Bot: "Probably lurking around..."
- User: "yikes aggressive"  ← This is about the bot's TEXT response, NOT the image!

**Indicators of refinement request** (ONLY if topic hasn't changed):
✅ Corrections: "no, I said...", "you forgot the...", "it's missing..."
✅ Additions: "also add...", "can you include...", "with a sword too"
✅ Modifications: "make it bigger", "change the color to...", "make it hold..."
✅ Add subject interacting with image: "make a gorilla drink that", "have a cat eat it"
✅ References to "that/it/the" about the IMAGE: "make X do Y with that", "add X to it"

**NOT a refinement request**:
❌ Response to bot's text message (not the image)
❌ Topic has changed since image was generated
❌ General conversation: "that's cool!", "I like it", "thanks", "nice"
❌ Emotional reactions: "yikes", "wow", "lol", "haha", "omg", "yikes aggressive"
❌ Comments about the bot: "you're weird", "that was aggressive", "ok then"
❌ Unrelated questions: "what's the weather?", "hey how are you"

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

        system_prompt = f"""You are intelligently modifying an image prompt based on user feedback.

ORIGINAL PROMPT: "{original_prompt}"

USER FEEDBACK: "{changes_requested}"

**YOUR TASK: Analyze both the original prompt and the user's feedback to understand their intent.**

Ask yourself: Is the user trying to REPLACE something, or MODIFY/ADD to it?

**REPLACEMENT** = User wants a DIFFERENT subject entirely
- The new thing is a DIFFERENT CATEGORY/TYPE than the original
- Example: taco → quesadilla (different food), dragon → phoenix (different creature), cat → dog (different animal)
- Action: Swap out the old subject completely, preserve all surrounding context (actions, other elements, setting)

**MODIFICATION** = User wants to CHANGE PROPERTIES of the existing subject
- The subject stays the same, but gains new attributes
- Example: dragon → blue dragon (same creature, new color), food → food on fire (same food, new state)
- Action: Keep the subject, add/change only the requested property

**EXAMPLES:**

Original: "a taco with dogs surrounding it and eating it"
Feedback: "make it a quesadilla"
Analysis: Taco and quesadilla are different foods → REPLACEMENT
New Prompt: "a quesadilla with dogs surrounding it and eating it"

Original: "a quesadilla with dogs surrounding it"
Feedback: "set it on fire"
Analysis: User wants the same quesadilla but burning → MODIFICATION
New Prompt: "a quesadilla on fire with dogs surrounding it"

Original: "a red dragon breathing fire"
Feedback: "I want a phoenix"
Analysis: Dragon and phoenix are different creatures → REPLACEMENT
New Prompt: "a red phoenix breathing fire"

Original: "a dragon"
Feedback: "make it blue"
Analysis: Same dragon, different color → MODIFICATION
New Prompt: "a blue dragon"

Original: "a cat sitting on a chair wearing a hat"
Feedback: "actually make it a dog"
Analysis: Cat and dog are different animals → REPLACEMENT
New Prompt: "a dog sitting on a chair wearing a hat"

Original: "a sombrero with fire"
Feedback: "brown please"
Analysis: Same sombrero, different color → MODIFICATION
New Prompt: "a brown sombrero with fire"

**ABSOLUTE RULES:**
1. **ANALYZE INTENT** - Understand what the user actually wants based on meaning, not keywords
2. **NEVER CREATE HYBRIDS** - If replacing, fully replace (no "taco-quesadilla", no "dragon with phoenix features")
3. **PRESERVE UNMENTIONED ELEMENTS** - Keep dogs, fire, location, actions, etc. unless user specifically changes them
4. **NO CREATIVITY** - Don't add anything the user didn't ask for

Return ONLY the modified prompt (no explanations, no quotes)."""

        try:
            # Calculate max_tokens dynamically based on original prompt length
            # Rough estimate: 1 token ≈ 3 characters, add buffer for modifications
            estimated_prompt_tokens = len(original_prompt) // 3  # Generous estimate
            min_tokens = 500  # Minimum for short prompts
            max_tokens = max(min_tokens, estimated_prompt_tokens + 100)  # Add buffer for modifications
            max_tokens = min(max_tokens, 1000)  # Cap at 1000 to avoid excessive costs

            print(f"ImageRefiner: Using max_tokens={max_tokens} for prompt modification (original ~{len(original_prompt)} chars)")

            response = await self.client.chat.completions.create(
                model=self.config.get('modification_model', 'gpt-4o'),
                messages=[{'role': 'system', 'content': system_prompt}],
                max_tokens=max_tokens,
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
