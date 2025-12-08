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
✅ Gender corrections: "she is a girl", "he's a boy", "they're female", "make them male", "wrong gender"
✅ Additions: "also add...", "can you include...", "with a sword too"
✅ Modifications: "make it bigger", "change the color to...", "make it hold..."
✅ **Adding actions**: "make her eat", "have him hold", "make them do X", "eating a Y"
✅ Removals: "remove the...", "get rid of...", "no background", "without the..."
✅ Add subject interacting with image: "make a gorilla drink that", "have a cat eat it"
✅ References to "that/it/the" about the IMAGE: "make X do Y with that", "add X to it"
✅ Simple statements about the subject: "she is X", "he has Y", "it should be Z" (these are CORRECTIONS)

**IMPORTANT - Mixed messages**: If the message starts with casual reaction ("omg so cute", "wow nice") but THEN includes a refinement request ("make her eat X", "add a Y"), it IS a refinement! Focus on the REQUEST part, ignore the reaction part.

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

    async def modify_prompt(self, original_prompt, changes_requested, user_context=None):
        """
        Uses GPT-4o to intelligently modify the original prompt based on user feedback.

        Args:
            original_prompt: The original image generation prompt
            changes_requested: Description of what the user wants changed
            user_context: Optional dict of {name: description} for people mentioned in changes

        Returns:
            str: Modified prompt for image generation
        """
        print(f"\n{'='*80}")
        print(f"PROMPT MODIFICATION - START")
        print(f"{'='*80}")
        print(f"Original prompt: '{original_prompt}'")
        print(f"Changes requested: '{changes_requested}'")
        if user_context:
            print(f"User context provided: {list(user_context.keys())}")

        if not self.client:
            print("❌ ImageRefiner: OpenAI client not set, cannot modify prompt")
            print(f"{'='*80}\n")
            return original_prompt

        # Build user context section if we have info about mentioned people
        user_context_section = ""
        if user_context:
            user_context_section = "\n\n**PERSON DESCRIPTIONS (USE THESE FOR ANY NEW PEOPLE ADDED):**\n"
            for name, description in user_context.items():
                user_context_section += f"- **{name}**: {description}\n"
            user_context_section += "\n**CRITICAL**: When adding a person, include their description from above DIRECTLY in the prompt. Don't just say 'a person' - describe them!"

        system_prompt = f"""You are intelligently modifying an image prompt based on user feedback.

ORIGINAL PROMPT: "{original_prompt}"

USER FEEDBACK: "{changes_requested}"
{user_context_section}

**YOUR TASK: Analyze both the original prompt and the user's feedback to understand their intent.**

Ask yourself: Is the user trying to REMOVE, REPLACE, MODIFY, or ADD?

**REMOVAL** = User wants to DELETE/REMOVE something from the image
- Keywords: "remove", "get rid of", "no", "without", "delete", "take away"
- **IDENTIFY THE MAIN SUBJECT FIRST**: In most prompts, the PERSON/CHARACTER is the main subject, NOT backgrounds/objects
- Action: DELETE the unwanted element, KEEP the main subject (usually the person/character)
- **CRITICAL**: If prompt has "person + background element", the PERSON is the main subject!
  - "person near tree" → main subject = PERSON
  - "character in castle" → main subject = CHARACTER
  - "girl with flowers" → main subject = GIRL
- When user says "remove the [background]", KEEP the person, remove only the background
- DO NOT remove the person and keep only the background - that's backwards!

**REPLACEMENT** = User wants a DIFFERENT subject entirely
- The new thing is a DIFFERENT CATEGORY/TYPE than the original
- Example: taco → quesadilla (different food), dragon → phoenix (different creature)
- Action: Swap out the old subject completely, preserve surrounding context

**MODIFICATION** = User wants to CHANGE PROPERTIES of the existing subject
- The subject stays the same, but gains new attributes
- Example: dragon → blue dragon (same creature, new color)
- Action: Keep the subject, add/change only the requested property

**ADDING AN ACTION** = User wants the existing subject to DO something
- Keywords: "make them", "make her", "make him", "have them", "eating", "holding", "wearing", "doing"
- **CRITICAL**: KEEP the existing subject description EXACTLY, just add the action
- The CHARACTER must remain the same - don't generate a different person!
- Example: "girl in red dress" + "make her eat a shoe" = "girl in red dress eating a shoe"
- Example: "knight in armor" + "have him hold a flower" = "knight in armor holding a flower"

**ADDING A PERSON** = User wants to add someone to the scene
- If person descriptions are provided above, USE THEM in the modified prompt
- **CRITICAL: PUT THE PERSON FIRST** - Image AI focuses on whatever appears first
- Keep person description SHORT (max 30 words)

**CRITICAL REMOVAL EXAMPLES:**

Original: "a knight in silver armor standing near a waterfall"
Feedback: "remove the waterfall"
Analysis: Main subject = KNIGHT. Remove waterfall, keep knight.
New Prompt: "a knight in silver armor standing"
WRONG: "a waterfall" (kept background, removed person - BACKWARDS!)

Original: "a wizard casting spells in front of a tower"
Feedback: "remove the tower"
Analysis: Main subject = WIZARD. Remove tower, keep wizard.
New Prompt: "a wizard casting spells"
WRONG: "a tower" (kept building, removed person - BACKWARDS!)

**KEY PRINCIPLE**: PERSON/CHARACTER is almost always the main subject. Background elements (waterfalls, buildings, scenery) are NOT the main subject.

**ADDING ACTION EXAMPLES:**

Original: "a cute girl in red dress with brown hair"
Feedback: "make her eat a shoe"
Analysis: ADDING ACTION - keep the girl, add action
New Prompt: "a cute girl in red dress with brown hair eating a shoe"
WRONG: "a person eating a shoe" (lost the character description!)
WRONG: "a man eating food" (changed the character entirely!)

Original: "a warrior in golden armor"
Feedback: "have him ride a dragon"
Analysis: ADDING ACTION - keep the warrior, add action
New Prompt: "a warrior in golden armor riding a dragon"

**ABSOLUTE RULES:**
1. **PRESERVE CHARACTER IDENTITY** - The CHARACTER (appearance, clothing, gender) MUST stay EXACTLY the same
2. **PRESERVE MAIN SUBJECT** - When removing backgrounds, the main subject (person, character) MUST remain
3. **REMOVAL ≠ REPLACEMENT** - "Remove X" means DELETE X, not substitute X with Y
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
