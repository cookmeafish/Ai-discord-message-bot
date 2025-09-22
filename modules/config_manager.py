# modules/config_manager.py

import json
import os
from dotenv import load_dotenv

class ConfigManager:
    """
    Manages loading secrets from .env and reading/writing settings to config.json.
    """
    def __init__(self, config_path='config.json'):
        load_dotenv()
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        """Loads the config file from disk."""
        if not os.path.exists(self.config_path):
            default_config = {
                "random_reply_chance": 0.05,
                "default_personality": {
                    "personality_traits": "chill, low-energy, concise, casual",
                    "purpose": "To hang out and chat with users."
                },
                "channel_settings": {}
            }
            self._save_config(default_config)
            return default_config
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _save_config(self, data):
        """Saves the config data to the file."""
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=4)

    def get_secret(self, key_name):
        """Gets a secret from environment variables."""
        return os.getenv(key_name)

    def get_config(self):
        """Returns the current configuration."""
        return self.config

    def update_config(self, new_data):
        """Updates the config with new data and saves it."""
        self.config.update(new_data)
        self._save_config(self.config)
        print("ConfigManager: Configuration updated and saved.")

    def add_or_update_channel_setting(self, channel_id: str, purpose: str = None, random_reply_chance: float = None):
        """Activates the bot in a channel, copying the default personality and allowing overrides."""
        if 'channel_settings' not in self.config:
            self.config['channel_settings'] = {}
        
        new_setting = self.config['default_personality'].copy()
        
        if purpose:
            new_setting['purpose'] = purpose
        
        if random_reply_chance is not None:
            new_setting['random_reply_chance'] = random_reply_chance
        else:
            new_setting['random_reply_chance'] = self.config.get('random_reply_chance', 0.05)
        
        self.config['channel_settings'][channel_id] = new_setting
        self._save_config(self.config)
        print(f"ConfigManager: Activated channel {channel_id}.")
        return new_setting

    def update_channel_personality(self, channel_id: str, new_traits: str):
        """Updates the personality traits for a specific active channel."""
        if 'channel_settings' in self.config and channel_id in self.config['channel_settings']:
            self.config['channel_settings'][channel_id]['personality_traits'] = new_traits
            self._save_config(self.config)
            print(f"ConfigManager: Updated personality for channel {channel_id}.")
            return True
        return False

    def remove_channel_setting(self, channel_id: str):
        """Deactivates the bot in a channel."""
        if 'channel_settings' in self.config and channel_id in self.config['channel_settings']:
            del self.config['channel_settings'][channel_id]
            self._save_config(self.config)
            print(f"ConfigManager: Deactivated channel {channel_id}.")
            return True
        return False