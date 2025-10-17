# database/input_validator.py
"""
Input validation and sanitization for database operations.
Provides defense-in-depth protection against SQL injection and malicious inputs.
"""

import re

class InputValidator:
    """Validates and sanitizes user inputs before database operations."""

    # Maximum lengths to prevent DoS via massive strings
    MAX_FACT_LENGTH = 500
    MAX_NICKNAME_LENGTH = 100
    MAX_MESSAGE_CONTENT_LENGTH = 2000
    MAX_BOT_IDENTITY_CONTENT_LENGTH = 1000

    # SQL injection keywords to reject (defense in depth)
    # NOTE: This is additional protection - parameterized queries are the primary defense
    SQL_KEYWORDS = [
        'DROP TABLE', 'DELETE FROM', 'TRUNCATE', 'ALTER TABLE',
        'CREATE TABLE', 'INSERT INTO', 'UPDATE ', '--', ';--', '/*', '*/',
        'EXEC ', 'EXECUTE ', 'UNION SELECT', 'UNION ALL', ';DROP', ';DELETE'
    ]

    @staticmethod
    def validate_fact(fact: str) -> tuple[bool, str]:
        """
        Validates a user-provided fact string.

        Args:
            fact: The fact text to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        if not fact or not fact.strip():
            return (False, "Fact cannot be empty")

        if len(fact) > InputValidator.MAX_FACT_LENGTH:
            return (False, f"Fact too long (max {InputValidator.MAX_FACT_LENGTH} characters)")

        # Check for SQL injection attempts (defense in depth)
        fact_upper = fact.upper()
        for keyword in InputValidator.SQL_KEYWORDS:
            if keyword in fact_upper:
                return (False, "Invalid characters detected in fact")

        return (True, "")

    @staticmethod
    def validate_nickname(nickname: str) -> tuple[bool, str]:
        """
        Validates a user nickname.

        Args:
            nickname: The nickname to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        if not nickname or not nickname.strip():
            return (False, "Nickname cannot be empty")

        if len(nickname) > InputValidator.MAX_NICKNAME_LENGTH:
            return (False, f"Nickname too long (max {InputValidator.MAX_NICKNAME_LENGTH} characters)")

        return (True, "")

    @staticmethod
    def validate_message_content(content: str) -> tuple[bool, str]:
        """
        Validates message content.

        Args:
            content: The message content to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        if not content:
            return (True, "")  # Empty messages are allowed (e.g., image-only messages)

        if len(content) > InputValidator.MAX_MESSAGE_CONTENT_LENGTH:
            return (False, f"Message too long (max {InputValidator.MAX_MESSAGE_CONTENT_LENGTH} characters)")

        return (True, "")

    @staticmethod
    def validate_bot_identity_content(content: str) -> tuple[bool, str]:
        """
        Validates bot identity content (traits, lore, facts).

        Args:
            content: The content to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        if not content or not content.strip():
            return (False, "Content cannot be empty")

        if len(content) > InputValidator.MAX_BOT_IDENTITY_CONTENT_LENGTH:
            return (False, f"Content too long (max {InputValidator.MAX_BOT_IDENTITY_CONTENT_LENGTH} characters)")

        return (True, "")

    @staticmethod
    def validate_metric_key(key: str) -> bool:
        """
        Validates relationship metric keys to prevent SQL injection via column names.
        WHITELIST APPROACH: Only allow known column names.

        Args:
            key: The metric key to validate

        Returns:
            bool: True if key is valid, False otherwise
        """
        ALLOWED_METRICS = {'anger', 'rapport', 'trust', 'formality', 'fear', 'respect', 'affection', 'familiarity', 'intimidation'}
        return key in ALLOWED_METRICS

    @staticmethod
    def validate_bot_identity_category(category: str) -> bool:
        """
        Validates bot identity category to prevent SQL injection.
        WHITELIST APPROACH: Only allow known categories.

        Args:
            category: The category to validate

        Returns:
            bool: True if category is valid, False otherwise
        """
        ALLOWED_CATEGORIES = {'trait', 'lore', 'fact'}
        return category in ALLOWED_CATEGORIES

    @staticmethod
    def validate_user_id(user_id) -> tuple[bool, str]:
        """
        Validates a Discord user ID.

        Args:
            user_id: The user ID to validate (can be int or string)

        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            uid = int(user_id)
            if uid <= 0:
                return (False, "User ID must be positive")
            if uid > 9999999999999999999:  # Max Discord snowflake
                return (False, "User ID too large")
            return (True, "")
        except (ValueError, TypeError):
            return (False, "User ID must be a valid integer")

    @staticmethod
    def sanitize_sql_like_pattern(pattern: str) -> str:
        """
        Sanitizes a LIKE pattern by escaping special characters.
        Use this when building LIKE queries with user input.

        Args:
            pattern: The pattern to sanitize

        Returns:
            str: Sanitized pattern
        """
        # Escape SQL LIKE special characters: % and _
        sanitized = pattern.replace('\\', '\\\\')  # Escape backslash first
        sanitized = sanitized.replace('%', '\\%')
        sanitized = sanitized.replace('_', '\\_')
        return sanitized
