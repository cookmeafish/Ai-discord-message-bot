# modules/personality_manager.py

class PersonalityManager:
    def __init__(self, config: dict):
        self.config = config

    def get_channel_personality(self, channel_id: int):
        """Gets the specific personality for a channel, or the default one."""
        channel_id_str = str(channel_id)
        # Fallback to default if channel-specific settings don't exist
        return self.config.get('channel_settings', {}).get(channel_id_str, self.config.get('default_personality', {}))