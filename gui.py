# gui.py (Updated)

import customtkinter as ctk
import json
import subprocess
import os
import sys
from dotenv import set_key, get_key

CONFIG_FILE = 'config.json'
ENV_FILE = '.env'

class BotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Discord Bot Control Panel")
        self.geometry("850x650")
        self.bot_process = None

        self.load_config()
        self.load_secrets()

        # --- Main Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Left Frame (Global & Default Personality) ---
        self.left_frame = ctk.CTkFrame(self, width=350)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nswe")

        ctk.CTkLabel(self.left_frame, text="Global Settings", font=("Roboto", 18, "bold")).pack(pady=(10, 15))

        # Bot Token
        ctk.CTkLabel(self.left_frame, text="Discord Bot Token:").pack(padx=10, anchor="w")
        self.token_entry = ctk.CTkEntry(self.left_frame, width=320, show="*")
        self.token_entry.pack(padx=10, pady=(0, 10))
        self.token_entry.insert(0, self.discord_token)

        # OpenAI API Key
        ctk.CTkLabel(self.left_frame, text="OpenAI API Key:").pack(padx=10, anchor="w")
        self.openai_key_entry = ctk.CTkEntry(self.left_frame, width=320, show="*")
        self.openai_key_entry.pack(padx=10, pady=(0, 10))
        self.openai_key_entry.insert(0, self.openai_api_key)

        # Random Reply Chance
        ctk.CTkLabel(self.left_frame, text="Random Reply Chance (e.g., 0.05 for 5%):").pack(padx=10, anchor="w")
        self.reply_chance_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.reply_chance_entry.pack(padx=10, pady=(0, 20))
        self.reply_chance_entry.insert(0, str(self.config.get('random_reply_chance', 0.05)))

        # Default Personality Section
        ctk.CTkLabel(self.left_frame, text="Default Personality", font=("Roboto", 16, "bold")).pack(pady=(10, 5))

        ctk.CTkLabel(self.left_frame, text="Bot Name:").pack(padx=10, anchor="w")
        self.default_name_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.default_name_entry.pack(padx=10, pady=2)
        self.default_name_entry.insert(0, self.config.get('default_personality', {}).get('name', 'AI-Bot'))

        ctk.CTkLabel(self.left_frame, text="Personality Traits:").pack(padx=10, anchor="w", pady=(5,0))
        self.default_traits_textbox = ctk.CTkTextbox(self.left_frame, height=50)
        self.default_traits_textbox.pack(fill="x", padx=10, pady=2)
        self.default_traits_textbox.insert("1.0", self.config.get('default_personality', {}).get('personality_traits', 'helpful, friendly, curious'))

        ctk.CTkLabel(self.left_frame, text="Background Lore:").pack(padx=10, anchor="w", pady=(5,0))
        self.default_lore_textbox = ctk.CTkTextbox(self.left_frame, height=50)
        self.default_lore_textbox.pack(fill="x", padx=10, pady=2)
        self.default_lore_textbox.insert("1.0", self.config.get('default_personality', {}).get('lore', 'I am a helpful AI living on this Discord server.'))

        # --- Right Frame (Channel-Specific Settings) ---
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nswe")

        ctk.CTkLabel(self.right_frame, text="Channel-Specific Personalities", font=("Roboto", 18, "bold")).pack(pady=(10, 15))
        ctk.CTkLabel(self.right_frame, text="Activate the bot in specific channels with unique instructions.", wraplength=450).pack(pady=(0, 10), padx=10)

        ctk.CTkLabel(self.right_frame, text="Channel ID to Activate/Modify:").pack(padx=10, anchor="w")
        self.channel_id_entry = ctk.CTkEntry(self.right_frame)
        self.channel_id_entry.pack(fill="x", padx=10, pady=2)

        ctk.CTkLabel(self.right_frame, text="Channel-Specific Purpose/Instructions:").pack(padx=10, anchor="w", pady=(10,0))
        self.channel_purpose_textbox = ctk.CTkTextbox(self.right_frame, height=100)
        self.channel_purpose_textbox.pack(fill="x", expand=True, padx=10, pady=2)
        self.channel_purpose_textbox.insert("1.0", "Example: Strictly answer user questions based on the server rules. Be formal and direct.")

        # Display active channels
        ctk.CTkLabel(self.right_frame, text="Currently Active Channels:", font=("Roboto", 12, "bold")).pack(pady=(10, 5), padx=10, anchor="w")
        self.active_channels_frame = ctk.CTkScrollableFrame(self.right_frame, height=150)
        self.active_channels_frame.pack(fill="x", padx=10)
        self.update_active_channels_display()


        # --- Bottom Frame (Controls) ---
        self.bottom_frame = ctk.CTkFrame(self, height=60)
        self.bottom_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="we")

        self.save_button = ctk.CTkButton(self.bottom_frame, text="Save Config", command=self.save_all_configs)
        self.save_button.pack(side="left", padx=20, pady=10)

        self.start_button = ctk.CTkButton(self.bottom_frame, text="Start Bot", command=self.start_bot, fg_color="#28a745", hover_color="#218838")
        self.start_button.pack(side="right", padx=20, pady=10)

        self.stop_button = ctk.CTkButton(self.bottom_frame, text="Stop Bot", command=self.stop_bot, fg_color="#dc3545", hover_color="#c82333")
        self.stop_button.pack(side="right")

    def update_active_channels_display(self):
        for widget in self.active_channels_frame.winfo_children():
            widget.destroy()
        settings = self.config.get('channel_settings', {})
        if not settings:
            ctk.CTkLabel(self.active_channels_frame, text="No specific channels configured yet.").pack(anchor="w")
            return
        for channel_id, channel_config in settings.items():
            purpose = channel_config.get('purpose', 'Default purpose')
            display_text = f"ID: {channel_id} - Purpose: {purpose[:50]}..."
            ctk.CTkLabel(self.active_channels_frame, text=display_text, wraplength=400, justify="left").pack(anchor="w", pady=2)

    def load_secrets(self):
        """Loads secrets from the .env file."""
        if not os.path.exists(ENV_FILE):
            # Create the file if it doesn't exist
            with open(ENV_FILE, 'w') as f:
                f.write("DISCORD_TOKEN=\n")
                f.write("OPENAI_API_KEY=\n")
        
        self.discord_token = get_key(ENV_FILE, "DISCORD_TOKEN") or ""
        self.openai_api_key = get_key(ENV_FILE, "OPENAI_API_KEY") or ""


    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "random_reply_chance": 0.05,
                "default_personality": {
                    "name": "AI-Bot",
                    "personality_traits": "helpful, friendly, curious",
                    "lore": "I am a helpful AI living on this Discord server.",
                    "facts": "I use OpenAI's API to think. My configuration is managed by a local GUI.",
                    "purpose": "To chat with users and assist with server tasks."
                },
                "channel_settings": {}
            }

    def save_all_configs(self):
        """Saves both secrets to .env and settings to config.json."""
        # Save secrets to .env
        set_key(ENV_FILE, "DISCORD_TOKEN", self.token_entry.get())
        set_key(ENV_FILE, "OPENAI_API_KEY", self.openai_key_entry.get())
        print("Secrets saved to .env!")

        # Save the rest to config.json
        try:
            self.config['random_reply_chance'] = float(self.reply_chance_entry.get())
        except ValueError:
            self.config['random_reply_chance'] = 0.05

        self.config['default_personality'] = {
            "name": self.default_name_entry.get(),
            "personality_traits": self.default_traits_textbox.get("1.0", "end-1c"),
            "lore": self.default_lore_textbox.get("1.0", "end-1c"),
            "facts": "I use OpenAI's API to think. My configuration is managed by a local GUI.",
            "purpose": "To chat with users and assist with server tasks."
        }

        channel_id = self.channel_id_entry.get()
        channel_purpose = self.channel_purpose_textbox.get("1.0", "end-1c")
        if channel_id.isdigit():
            if channel_id not in self.config.get('channel_settings', {}):
                self.config.setdefault('channel_settings', {})[channel_id] = self.config['default_personality'].copy()
            self.config['channel_settings'][channel_id]['purpose'] = channel_purpose

        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        print("Configuration saved to config.json!")
        self.update_active_channels_display()

    def get_python_executable(self):
        return sys.executable

    def start_bot(self):
        if self.bot_process is None or self.bot_process.poll() is not None:
            print("Starting bot...")
            python_exec = self.get_python_executable()
            # ***IMPORTANT: Run main.py now, not bot.py***
            self.bot_process = subprocess.Popen([python_exec, 'main.py'])
            print(f"Bot process started with PID: {self.bot_process.pid}")
        else:
            print("Bot is already running.")

    def stop_bot(self):
        if self.bot_process and self.bot_process.poll() is None:
            print("Stopping bot...")
            self.bot_process.terminate()
            self.bot_process.wait()
            self.bot_process = None
            print("Bot process stopped.")
        else:
            print("Bot is not running.")

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = BotGUI()
    app.mainloop()