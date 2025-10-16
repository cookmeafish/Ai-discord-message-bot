# modules/formatting_handler.py

import re

class FormattingHandler:
    """
    Detects and formats physical actions in italics for immersive roleplay.

    Features:
    - 50+ action verbs across 8 categories
    - Only formats short sentences (<15 words) that start with action verbs
    - Preserves existing formatting (doesn't re-format already italicized text)
    - Conservative approach: won't format sentences starting with "I" or containing dialogue
    """

    def __init__(self):
        """Initialize the formatting handler with action verb patterns."""
        # 50+ action verbs across 8 categories
        self.action_verbs = {
            # Movement
            'walks', 'walk', 'runs', 'run', 'jumps', 'jump', 'steps', 'step',
            'moves', 'move', 'approaches', 'approach', 'enters', 'enter', 'leaves', 'leave',
            'dashes', 'dash', 'sprints', 'sprint', 'strides', 'stride',

            # Gestures
            'waves', 'wave', 'points', 'point', 'nods', 'nod', 'shakes', 'shake',
            'gestures', 'gesture', 'beckons', 'beckon', 'shrugs', 'shrug',

            # Facial expressions
            'smiles', 'smile', 'grins', 'grin', 'frowns', 'frown', 'winks', 'wink',
            'blinks', 'blink', 'stares', 'stare', 'glares', 'glare',

            # Sounds
            'sighs', 'sigh', 'gasps', 'gasp', 'laughs', 'laugh', 'giggles', 'giggle',
            'chuckles', 'chuckle', 'groans', 'groan', 'yawns', 'yawn', 'coughs', 'cough',
            'sneezes', 'sneeze', 'hums', 'hum', 'whistles', 'whistle',

            # Looking
            'looks', 'look', 'glances', 'glance', 'peers', 'peer', 'gazes', 'gaze',
            'watches', 'watch', 'observes', 'observe',

            # Physical contact
            'touches', 'touch', 'grabs', 'grab', 'holds', 'hold', 'hugs', 'hug',
            'pats', 'pat', 'pushes', 'push', 'pulls', 'pull',

            # Posture/Position
            'sits', 'sit', 'stands', 'stand', 'leans', 'lean', 'kneels', 'kneel',
            'crouches', 'crouch', 'lies', 'lie', 'rises', 'rise',

            # Other actions
            'reaches', 'reach', 'stretches', 'stretch', 'turns', 'turn', 'spins', 'spin',
            'tilts', 'tilt', 'adjusts', 'adjust', 'fidgets', 'fidget', 'pauses', 'pause'
        }

        # Create regex pattern for action verbs
        verbs_pattern = '|'.join(sorted(self.action_verbs, key=len, reverse=True))

        # Pattern to match sentences starting with action verbs
        # Must start with verb, be short (<15 words), and not already italicized
        self.action_pattern = re.compile(
            r'(?<!\*)\b(' + verbs_pattern + r')\b[^.!?]*[.!?]',
            re.IGNORECASE
        )

    def format_actions(self, text, enable_formatting=True):
        """
        Applies italic formatting to physical actions in text.

        Args:
            text: The text to format
            enable_formatting: Whether to apply formatting (default: True)

        Returns:
            Formatted text with actions in italics
        """
        if not enable_formatting or not text:
            return text

        # Split text into sentences
        sentences = re.split(r'([.!?]+\s*)', text)
        formatted_sentences = []

        for i, part in enumerate(sentences):
            # Skip punctuation parts
            if re.match(r'^[.!?]+\s*$', part):
                formatted_sentences.append(part)
                continue

            # Skip if already contains asterisks (already formatted)
            if '*' in part:
                formatted_sentences.append(part)
                continue

            # Skip if contains quotes (dialogue)
            if '"' in part or "'" in part:
                formatted_sentences.append(part)
                continue

            # Skip if starts with "I" (personal statements)
            if part.strip().startswith('I '):
                formatted_sentences.append(part)
                continue

            # Check if sentence is short enough (<15 words)
            word_count = len(part.split())
            if word_count >= 15:
                formatted_sentences.append(part)
                continue

            # Check if starts with an action verb
            stripped = part.strip()
            if stripped:
                first_word = stripped.split()[0].lower().rstrip(',.!?')

                if first_word in self.action_verbs:
                    # Format this sentence with italics
                    formatted_part = f"*{part.strip()}*"
                    # Add back leading whitespace if any
                    if part != part.lstrip():
                        formatted_part = ' ' + formatted_part
                    formatted_sentences.append(formatted_part)
                else:
                    formatted_sentences.append(part)
            else:
                formatted_sentences.append(part)

        return ''.join(formatted_sentences)

    def is_action_sentence(self, sentence):
        """
        Checks if a sentence appears to be a physical action.

        Args:
            sentence: The sentence to check

        Returns:
            Boolean indicating if sentence is an action
        """
        if not sentence:
            return False

        # Already formatted
        if '*' in sentence:
            return False

        # Contains dialogue
        if '"' in sentence or "'" in sentence:
            return False

        # Starts with "I"
        if sentence.strip().startswith('I '):
            return False

        # Too long
        if len(sentence.split()) >= 15:
            return False

        # Check for action verb
        first_word = sentence.strip().split()[0].lower().rstrip(',.!?')
        return first_word in self.action_verbs
