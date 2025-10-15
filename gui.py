# gui.py

import customtkinter as ctk
import json
import subprocess
import os
import sys
from dotenv import set_key, get_key
import threading
import queue

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules.config_manager import ConfigManager

CONFIG_FILE = 'config.json'
ENV_FILE = '.env'

class ToolTip:
    """Simple tooltip class for hover text on widgets"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = ctk.CTkLabel(
            tw,
            text=self.text,
            fg_color=("#ffffe0", "#3a3a3a"),
            corner_radius=6,
            padx=10,
            pady=5
        )
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class BotGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Discord Bot Control Panel")
        self.geometry("850x900")
        self.bot_process = None

        self.config_manager = ConfigManager()
        self.config = self.config_manager.get_config()
        self.load_secrets()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame = ctk.CTkFrame(self, width=350)
        self.left_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nswe")

        ctk.CTkLabel(self.left_frame, text="Global Settings", font=("Roboto", 18, "bold")).pack(pady=(10, 15))

        ctk.CTkLabel(self.left_frame, text="Discord Bot Token:").pack(padx=10, anchor="w")
        self.token_entry = ctk.CTkEntry(self.left_frame, width=320, show="*")
        self.token_entry.pack(padx=10, pady=(0, 10))
        self.token_entry.insert(0, self.discord_token)

        ctk.CTkLabel(self.left_frame, text="OpenAI API Key:").pack(padx=10, anchor="w")
        self.openai_key_entry = ctk.CTkEntry(self.left_frame, width=320, show="*")
        self.openai_key_entry.pack(padx=10, pady=(0, 10))
        self.openai_key_entry.insert(0, self.openai_api_key)

        ctk.CTkLabel(self.left_frame, text="Random Reply Chance (e.g., 0.05 for 5%):").pack(padx=10, anchor="w")
        self.reply_chance_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.reply_chance_entry.pack(padx=10, pady=(0, 20))
        self.reply_chance_entry.insert(0, str(self.config.get('random_reply_chance', 0.05)))

        ctk.CTkLabel(self.left_frame, text="Default Personality", font=("Roboto", 16, "bold")).pack(pady=(10, 5))

        ctk.CTkLabel(self.left_frame, text="Personality Traits:").pack(padx=10, anchor="w", pady=(5,0))
        self.default_traits_textbox = ctk.CTkTextbox(self.left_frame, height=50)
        self.default_traits_textbox.pack(fill="x", padx=10, pady=2)
        self.default_traits_textbox.insert("1.0", self.config.get('default_personality', {}).get('personality_traits', 'helpful, friendly, curious'))
        
        ctk.CTkLabel(self.left_frame, text="Background Lore:").pack(padx=10, anchor="w", pady=(5,0))
        self.default_lore_textbox = ctk.CTkTextbox(self.left_frame, height=50)
        self.default_lore_textbox.pack(fill="x", padx=10, pady=2)
        self.default_lore_textbox.insert("1.0", self.config.get('default_personality', {}).get('lore', 'I am a helpful AI living on this Discord server.'))

        ctk.CTkLabel(self.left_frame, text="Alternative Nicknames (comma-separated):").pack(padx=10, anchor="w", pady=(5,0))
        self.alternative_nicknames_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.alternative_nicknames_entry.pack(padx=10, pady=2)
        # Load existing nicknames from config (list to comma-separated string)
        existing_nicknames = self.config.get('alternative_nicknames', [])
        if existing_nicknames:
            self.alternative_nicknames_entry.insert(0, ', '.join(existing_nicknames))

        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nswe")

        ctk.CTkLabel(self.right_frame, text="Server Manager", font=("Roboto", 18, "bold")).pack(pady=(10, 15))
        ctk.CTkLabel(self.right_frame, text="Manage bot settings for each Discord server.", wraplength=450).pack(pady=(0, 10), padx=10)

        ctk.CTkLabel(self.right_frame, text="Active Servers:", font=("Roboto", 12, "bold")).pack(pady=(10, 5), padx=10, anchor="w")
        self.server_list_frame = ctk.CTkScrollableFrame(self.right_frame, height=150)
        self.server_list_frame.pack(fill="x", padx=10)
        self.update_server_list()

        ctk.CTkLabel(self.right_frame, text="Bot Console Output:", font=("Roboto", 12, "bold")).pack(pady=(10, 5), padx=10, anchor="w")
        self.log_textbox = ctk.CTkTextbox(self.right_frame, height=300)
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_textbox.configure(state="disabled")

        self.bottom_frame = ctk.CTkFrame(self, height=60)
        self.bottom_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="we")

        self.save_button = ctk.CTkButton(self.bottom_frame, text="Save Config", command=self.save_all_configs)
        self.save_button.pack(side="left", padx=20, pady=10)

        self.consolidate_button = ctk.CTkButton(self.bottom_frame, text="Test Memory Consolidation", command=self.test_memory_consolidation, fg_color="#17a2b8", hover_color="#138496")
        self.consolidate_button.pack(side="left", padx=(0, 20), pady=10)

        self.start_button = ctk.CTkButton(self.bottom_frame, text="Start Bot", command=self.start_bot, fg_color="#28a745", hover_color="#218838")
        self.start_button.pack(side="right", padx=20, pady=10)

        self.stop_button = ctk.CTkButton(self.bottom_frame, text="Stop Bot", command=self.stop_bot, fg_color="#dc3545", hover_color="#c82333")
        self.stop_button.pack(side="right")
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.output_queue = queue.Queue()
        self.after(100, self.process_log_queue)

        # Track config file modification time for auto-refresh
        self.config_last_modified = os.path.getmtime(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else 0
        self.after(1000, self.check_config_changes)

    def process_log_queue(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line:
                    self.log_textbox.configure(state="normal")
                    self.log_textbox.insert("end", line)
                    self.log_textbox.see("end")
                    self.log_textbox.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(100, self.process_log_queue)

    def check_config_changes(self):
        """Periodically check if config.json has been modified externally and refresh display."""
        try:
            if os.path.exists(CONFIG_FILE):
                current_modified = os.path.getmtime(CONFIG_FILE)
                if current_modified > self.config_last_modified:
                    # Config file was modified externally, refresh the display
                    self.update_server_list()
                    self.config_last_modified = current_modified
        except Exception as e:
            # Silently handle errors to avoid disrupting GUI
            pass
        # Check again in 1 second
        self.after(1000, self.check_config_changes)

    def log_to_console(self, message):
        """Write a message to the Bot Console Output textbox."""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def _stream_reader(self, stream):
        for line in iter(stream.readline, ''):
            self.output_queue.put(line)
        stream.close()

    def on_closing(self):
        print("GUI is closing, ensuring bot process is terminated...")
        self.stop_bot()
        self.destroy()

    def _scan_server_databases(self):
        """
        Scans the database folder for server database files.
        Returns list of (guild_id, server_name) tuples.
        """
        import re
        servers = []
        db_folder = "database"

        if not os.path.exists(db_folder):
            return servers

        for filename in os.listdir(db_folder):
            if filename.endswith('_data.db') and filename != '_data.db':
                # Try new format first: {guild_id}_{servername}_data.db
                match = re.match(r'^(\d+)_(.+)_data\.db$', filename)
                if match:
                    guild_id = match.group(1)
                    server_name = match.group(2)
                    servers.append((guild_id, server_name))
                else:
                    # Try old format: {servername}_data.db (no guild_id prefix)
                    match = re.match(r'^(.+)_data\.db$', filename)
                    if match:
                        server_name = match.group(1)
                        guild_id = "unknown"  # Mark as unknown for old format
                        servers.append((guild_id, server_name))

        return servers

    def update_server_list(self):
        """Refreshes the server list display."""
        # Clear existing widgets
        for widget in self.server_list_frame.winfo_children():
            widget.destroy()

        # Scan for server databases
        servers = self._scan_server_databases()

        if not servers:
            ctk.CTkLabel(self.server_list_frame, text="No servers found. Use /activate in Discord to activate the bot on a server.").pack(anchor="w", padx=5)
            return

        # Display each server
        for guild_id, server_name in servers:
            server_frame = ctk.CTkFrame(self.server_list_frame, fg_color="transparent")
            server_frame.pack(fill="x", pady=2)

            # Server name label
            ctk.CTkLabel(server_frame, text=server_name, font=("Roboto", 11)).pack(side="left", anchor="w", padx=5)

            # Edit button
            edit_btn = ctk.CTkButton(
                server_frame,
                text="Edit Settings",
                command=lambda gid=guild_id, sname=server_name: self.open_server_settings(gid, sname),
                width=100,
                height=24,
                fg_color="#17a2b8",
                hover_color="#138496"
            )
            edit_btn.pack(side="right", padx=2)

    def open_server_settings(self, guild_id, server_name):
        """Opens the Server Settings Dialog for a specific server."""
        # Create settings window
        settings_window = ctk.CTkToplevel(self)
        settings_window.title(f"Server Settings - {server_name}")
        settings_window.geometry("650x700")
        settings_window.resizable(True, True)
        settings_window.minsize(550, 600)
        settings_window.grab_set()

        # Server name display
        ctk.CTkLabel(settings_window, text=f"Server: {server_name}", font=("Roboto", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(settings_window, text=f"Guild ID: {guild_id}", font=("Roboto", 10)).pack(pady=(0, 20))

        # Active Channels Section
        ctk.CTkLabel(settings_window, text="Active Channels:", font=("Roboto", 14, "bold")).pack(padx=20, anchor="w", pady=(10, 5))

        channels_frame = ctk.CTkScrollableFrame(settings_window, height=200)
        channels_frame.pack(fill="x", padx=20, pady=5)

        def refresh_channels():
            """Refresh the channels list for this server."""
            for widget in channels_frame.winfo_children():
                widget.destroy()

            config = self.config_manager.get_config()
            channel_settings = config.get('channel_settings', {})

            # Filter channels by guild (we'll need to infer this from the database or config)
            # For now, show all channels with a note
            server_channels = []
            for channel_id, channel_config in channel_settings.items():
                # TODO: In future, store guild_id in channel_settings to properly filter
                # For now, display all channels
                server_channels.append((channel_id, channel_config))

            if not server_channels:
                ctk.CTkLabel(channels_frame, text="No channels activated yet. Use /activate in Discord.").pack(anchor="w", padx=5)
            else:
                for channel_id, channel_config in server_channels:
                    channel_row = ctk.CTkFrame(channels_frame, fg_color="transparent")
                    channel_row.pack(fill="x", pady=2)

                    purpose = channel_config.get('purpose', 'Default purpose')[:40]
                    ctk.CTkLabel(channel_row, text=f"{channel_id}: {purpose}...").pack(side="left", anchor="w")

                    edit_ch_btn = ctk.CTkButton(
                        channel_row,
                        text="Edit",
                        command=lambda cid=channel_id, cfg=channel_config: [self.edit_channel(cid, cfg), refresh_channels()],
                        width=60,
                        height=24,
                        fg_color="#17a2b8",
                        hover_color="#138496"
                    )
                    edit_ch_btn.pack(side="right", padx=2)

        refresh_channels()

        # Alternative Nicknames Section
        ctk.CTkLabel(settings_window, text="Alternative Nicknames:", font=("Roboto", 14, "bold")).pack(padx=20, anchor="w", pady=(15, 5))
        ctk.CTkLabel(settings_window, text="Comma-separated nicknames the bot responds to (e.g., 'drfish, dr fish'):", font=("Roboto", 10)).pack(padx=20, anchor="w")

        nicknames_entry = ctk.CTkEntry(settings_window, width=500)
        nicknames_entry.pack(padx=20, pady=5, fill="x")

        # Get current server-specific nicknames
        config = self.config_manager.get_config()
        server_nicknames = config.get('server_alternative_nicknames', {})
        current_nicknames = server_nicknames.get(guild_id, [])
        if current_nicknames:
            nicknames_entry.insert(0, ', '.join(current_nicknames))

        # Emote Sources Section
        ctk.CTkLabel(settings_window, text="Emote Sources:", font=("Roboto", 14, "bold")).pack(padx=20, anchor="w", pady=(15, 5))
        ctk.CTkLabel(settings_window, text="Select which servers' emotes can be used:", font=("Roboto", 10)).pack(padx=20, anchor="w")

        emote_frame = ctk.CTkScrollableFrame(settings_window, height=120)
        emote_frame.pack(fill="x", padx=20, pady=5)

        # Get all available servers
        all_servers = self._scan_server_databases()

        # Get current emote source configuration
        config = self.config_manager.get_config()
        server_emote_sources = config.get('server_emote_sources', {})
        current_sources = server_emote_sources.get(guild_id, [])

        # Create checkbox for each server
        emote_checkboxes = {}
        for srv_guild_id, srv_name in all_servers:
            var = ctk.BooleanVar(value=(srv_guild_id in current_sources if current_sources else True))
            checkbox = ctk.CTkCheckBox(
                emote_frame,
                text=srv_name,
                variable=var
            )
            checkbox.pack(anchor="w", padx=5, pady=2)
            emote_checkboxes[srv_guild_id] = var

        # Buttons frame
        button_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        button_frame.pack(pady=20)

        def save_settings():
            # Save alternative nicknames
            nicknames_str = nicknames_entry.get().strip()
            current_config = self.config_manager.get_config()

            if 'server_alternative_nicknames' not in current_config:
                current_config['server_alternative_nicknames'] = {}

            if nicknames_str:
                current_config['server_alternative_nicknames'][guild_id] = [nick.strip() for nick in nicknames_str.split(',') if nick.strip()]
            else:
                current_config['server_alternative_nicknames'][guild_id] = []

            # Save emote sources
            selected_sources = [gid for gid, var in emote_checkboxes.items() if var.get()]

            if 'server_emote_sources' not in current_config:
                current_config['server_emote_sources'] = {}

            current_config['server_emote_sources'][guild_id] = selected_sources
            self.config_manager.update_config(current_config)

            print(f"Updated server settings for {server_name}")
            self.log_to_console(f"Updated server settings for {server_name}")
            settings_window.destroy()

        # Save button
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save Settings",
            command=save_settings,
            fg_color="#28a745",
            hover_color="#218838",
            width=120
        )
        save_btn.pack(side="left", padx=10)

        # Cancel button
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=settings_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        cancel_btn.pack(side="left", padx=10)

    def update_active_channels_display(self):
        """Legacy method - redirects to update_server_list for backward compatibility."""
        self.update_server_list()

    def edit_channel(self, channel_id, channel_config):
        """Opens a dialog to edit channel settings."""
        # Create edit window
        edit_window = ctk.CTkToplevel(self)
        edit_window.title(f"Edit Channel {channel_id}")
        edit_window.geometry("550x600")

        # Allow minimize/maximize
        edit_window.resizable(True, True)
        edit_window.minsize(450, 500)

        # Make it modal (but this doesn't prevent minimize)
        edit_window.grab_set()

        # Channel ID display (non-editable)
        ctk.CTkLabel(edit_window, text=f"Channel ID: {channel_id}", font=("Roboto", 14, "bold")).pack(pady=(20, 10))

        # Purpose/Instructions editor
        ctk.CTkLabel(edit_window, text="Channel Purpose/Instructions:").pack(padx=20, anchor="w", pady=(10, 0))
        purpose_textbox = ctk.CTkTextbox(edit_window, height=150)
        purpose_textbox.pack(fill="x", padx=20, pady=5)
        current_purpose = channel_config.get('purpose', '')
        purpose_textbox.insert("1.0", current_purpose)

        # Random reply chance
        ctk.CTkLabel(edit_window, text="Random Reply Chance (e.g., 0.05 for 5%):").pack(padx=20, anchor="w", pady=(10, 0))
        reply_chance_entry = ctk.CTkEntry(edit_window, width=200)
        reply_chance_entry.pack(padx=20, pady=5, anchor="w")
        current_chance = channel_config.get('random_reply_chance', 0.05)
        reply_chance_entry.insert(0, str(current_chance))

        # Personality Mode Overrides
        ctk.CTkLabel(edit_window, text="Personality Mode (Leave unchecked to use global defaults):").pack(padx=20, anchor="w", pady=(10, 0))

        global_personality_mode = self.config.get('personality_mode', {})
        current_immersive = channel_config.get('immersive_character', global_personality_mode.get('immersive_character', True))
        current_technical = channel_config.get('allow_technical_language', global_personality_mode.get('allow_technical_language', False))

        immersive_var = ctk.BooleanVar(value=current_immersive)
        immersive_checkbox = ctk.CTkCheckBox(
            edit_window,
            text="Immersive Character Mode",
            variable=immersive_var
        )
        immersive_checkbox.pack(padx=20, anchor="w", pady=(5, 0))
        ToolTip(immersive_checkbox, "Bot believes it IS the character, not an AI roleplaying.\nDenies being AI if asked.")

        technical_var = ctk.BooleanVar(value=current_technical)
        technical_checkbox = ctk.CTkCheckBox(
            edit_window,
            text="Allow Technical Language",
            variable=technical_var
        )
        technical_checkbox.pack(padx=20, anchor="w", pady=(0, 0))
        ToolTip(technical_checkbox, "Allow bot to use technical terms like 'cached', 'database'.\nUseful for formal/support channels.")

        # Server Information
        current_use_server_info = channel_config.get('use_server_info', False)
        server_info_var = ctk.BooleanVar(value=current_use_server_info)
        server_info_checkbox = ctk.CTkCheckBox(
            edit_window,
            text="Use Server Information",
            variable=server_info_var
        )
        server_info_checkbox.pack(padx=20, anchor="w", pady=(5, 10))
        ToolTip(server_info_checkbox, "Load text files from Server_Info/\nfor rules, policies, or server-specific information.\nIdeal for formal channels like rules or moderation.")

        # Buttons frame
        button_frame = ctk.CTkFrame(edit_window, fg_color="transparent")
        button_frame.pack(pady=20)

        def save_changes():
            new_purpose = purpose_textbox.get("1.0", "end-1c").strip()
            try:
                new_chance = float(reply_chance_entry.get())
            except ValueError:
                new_chance = current_chance

            # Get current config and update with new values
            current_config = self.config_manager.get_config()
            if 'channel_settings' not in current_config:
                current_config['channel_settings'] = {}

            if channel_id not in current_config['channel_settings']:
                current_config['channel_settings'][channel_id] = {}

            # Update channel settings
            current_config['channel_settings'][channel_id]['purpose'] = new_purpose
            current_config['channel_settings'][channel_id]['random_reply_chance'] = new_chance
            current_config['channel_settings'][channel_id]['immersive_character'] = immersive_var.get()
            current_config['channel_settings'][channel_id]['allow_technical_language'] = technical_var.get()
            current_config['channel_settings'][channel_id]['use_server_info'] = server_info_var.get()

            self.config_manager.update_config(current_config)
            print(f"Updated channel {channel_id} settings")
            self.update_active_channels_display()
            edit_window.destroy()

        # Save button
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save Changes",
            command=save_changes,
            fg_color="#28a745",
            hover_color="#218838",
            width=120
        )
        save_btn.pack(side="left", padx=10)

        # Cancel button
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=edit_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        cancel_btn.pack(side="left", padx=10)

    def add_channel(self):
        """Adds a new channel from the input fields."""
        channel_id = self.channel_id_entry.get().strip()
        channel_purpose = self.channel_purpose_textbox.get("1.0", "end-1c").strip()

        # Validate inputs
        if not channel_id.isdigit():
            self.log_to_console("Error: Channel ID must be a valid number")
            return

        # Use None if no purpose provided or if it's still the example text (matches /activate behavior)
        if not channel_purpose or channel_purpose.startswith("Example:"):
            channel_purpose = None

        # Use the same method as /activate command for consistency
        self.config_manager.add_or_update_channel_setting(channel_id, channel_purpose, None)

        # Clear input fields
        self.channel_id_entry.delete(0, 'end')
        self.channel_purpose_textbox.delete("1.0", "end")
        self.channel_purpose_textbox.insert("1.0", "Example: Strictly answer user questions based on the server rules. Be formal and direct.")

        # Update display and log
        self.update_active_channels_display()
        self.log_to_console(f"Channel {channel_id} activated successfully!")
        print(f"Channel {channel_id} activated successfully!")

    def remove_channel(self, channel_id):
        """Removes a channel from the active channels list."""
        success = self.config_manager.remove_channel_setting(channel_id)
        if success:
            print(f"Removed channel {channel_id} from active channels")
            self.log_to_console(f"Removed channel {channel_id} from active channels")
            self.update_active_channels_display()
        else:
            print(f"Failed to remove channel {channel_id}")
            self.log_to_console(f"Failed to remove channel {channel_id}")

    def load_secrets(self):
        if not os.path.exists(ENV_FILE):
            with open(ENV_FILE, 'w') as f:
                f.write("DISCORD_TOKEN=\n")
                f.write("OPENAI_API_KEY=\n")
        
        self.discord_token = get_key(ENV_FILE, "DISCORD_TOKEN") or ""
        self.openai_api_key = get_key(ENV_FILE, "OPENAI_API_KEY") or ""

    def save_all_configs(self):
        set_key(ENV_FILE, "DISCORD_TOKEN", self.token_entry.get())
        set_key(ENV_FILE, "OPENAI_API_KEY", self.openai_key_entry.get())
        print("Secrets saved to .env file!")
        self.log_to_console("Secrets saved to .env file!")

        new_config = self.config_manager.get_config()

        try:
            new_config['random_reply_chance'] = float(self.reply_chance_entry.get())
        except ValueError:
            new_config['random_reply_chance'] = 0.05

        new_config['default_personality'] = {
            "personality_traits": self.default_traits_textbox.get("1.0", "end-1c"),
            "lore": self.default_lore_textbox.get("1.0", "end-1c"),
            "facts": "I use OpenAI's API to think. My configuration is managed by a local GUI.",
            "purpose": "To chat with users and assist with server tasks."
        }

        # Save alternative nicknames (convert comma-separated string to list)
        nicknames_str = self.alternative_nicknames_entry.get().strip()
        if nicknames_str:
            # Split by comma and strip whitespace from each nickname
            new_config['alternative_nicknames'] = [nick.strip() for nick in nicknames_str.split(',') if nick.strip()]
        else:
            new_config['alternative_nicknames'] = []

        channel_id = self.channel_id_entry.get()
        channel_purpose = self.channel_purpose_textbox.get("1.0", "end-1c")
        if channel_id.isdigit() and channel_purpose.strip():
            if 'channel_settings' not in new_config:
                new_config['channel_settings'] = {}

            new_channel_setting = new_config['default_personality'].copy()
            new_channel_setting['purpose'] = channel_purpose
            new_config['channel_settings'][channel_id] = new_channel_setting
            print(f"Channel {channel_id} setting prepared.")
            self.log_to_console(f"Channel {channel_id} activated.")

        self.config_manager.update_config(new_config)

        # Update modification time tracker to prevent file watcher from triggering
        if os.path.exists(CONFIG_FILE):
            self.config_last_modified = os.path.getmtime(CONFIG_FILE)

        self.update_active_channels_display()
        self.log_to_console("Configuration saved successfully!")

    def get_python_executable(self):
        return sys.executable

    def start_bot(self):
        if self.bot_process is None or self.bot_process.poll() is not None:
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.insert("end", "Attempting to start bot...\n")
            self.log_textbox.configure(state="disabled")

            python_exec = self.get_python_executable()
            creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            
            self.bot_process = subprocess.Popen(
                [python_exec, '-u', 'main.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=creation_flags
            )
            
            threading.Thread(target=self._stream_reader, args=(self.bot_process.stdout,), daemon=True).start()
            threading.Thread(target=self._stream_reader, args=(self.bot_process.stderr,), daemon=True).start()

            print(f"Bot process started with PID: {self.bot_process.pid}")
        else:
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", "Bot is already running.\n")
            self.log_textbox.configure(state="disabled")
            print("Bot is already running.")

    def stop_bot(self):
        if self.bot_process and self.bot_process.poll() is None:
            print("Stopping bot...")
            if sys.platform == "win32":
                try:
                    subprocess.run(
                        ["taskkill", "/F", "/PID", str(self.bot_process.pid), "/T"],
                        check=True,
                        capture_output=True
                    )
                    print("Bot process tree terminated successfully on Windows.")
                except (subprocess.CalledProcessError, FileNotFoundError):
                    self.bot_process.kill()
            else:
                self.bot_process.terminate()
                try:
                    self.bot_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.bot_process.kill()

            self.bot_process = None
            self.log_textbox.configure(state="normal")
            self.log_textbox.insert("end", "\n--- Bot Stopped ---\n")
            self.log_textbox.configure(state="disabled")
        else:
            print("Bot is not running or has already stopped.")

    def test_memory_consolidation(self):
        """
        Shows instructions for triggering memory consolidation via Discord.
        Note: With per-server databases, consolidation must be triggered from Discord
        since the GUI doesn't have context about which server to consolidate.
        """
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", "\n=== Memory Consolidation Instructions ===\n")
        self.log_textbox.insert("end", "Memory consolidation is now per-server.\n\n")
        self.log_textbox.insert("end", "To manually trigger consolidation for a specific server:\n")
        self.log_textbox.insert("end", "1. Go to the Discord server you want to consolidate\n")
        self.log_textbox.insert("end", "2. Run the slash command: /consolidate_memory\n")
        self.log_textbox.insert("end", "3. The bot will consolidate that server's memories\n\n")
        self.log_textbox.insert("end", "Note: Consolidation also triggers automatically when\n")
        self.log_textbox.insert("end", "a server reaches 500 messages in short-term memory.\n")
        self.log_textbox.insert("end", "==========================================\n\n")
        self.log_textbox.configure(state="disabled")

        print("\n=== Memory Consolidation Info ===")
        print("Use /consolidate_memory in Discord to trigger per-server consolidation")
        print("=================================")

if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = BotGUI()
    app.mainloop()