# modules/config_manager.py

import json
import os
from dotenv import load_dotenv

class ConfigManager:
    """
    Manages loading secrets from .env and settings from config.json.
    """
    def __init__(self, config_path='config.json'):
        # Load environment variables from .env file
        load_dotenv()
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        """Loads settings from the config file."""
        if not os.path.exists(self.config_path):
            print(f"WARNING: {self.config_path} not found. Using default empty config.")
            return {}
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def get_secret(self, key_name):
        """Gets a secret from environment variables."""
        return os.getenv(key_name)

    def get_config(self):
        """Returns the loaded config.json data."""
        # We can also inject the secrets here if needed, but it's safer
        # to keep them separate.
        return self.config