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

        ctk.CTkLabel(self.left_frame, text="Together.ai API Key (for image generation):").pack(padx=10, anchor="w")
        self.together_key_entry = ctk.CTkEntry(self.left_frame, width=320, show="*")
        self.together_key_entry.pack(padx=10, pady=(0, 10))
        self.together_key_entry.insert(0, get_key(ENV_FILE, "TOGETHER_API_KEY") or "")

        ctk.CTkLabel(self.left_frame, text="Random Reply Chance (e.g., 0.05 for 5%):").pack(padx=10, anchor="w")
        self.reply_chance_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.reply_chance_entry.pack(padx=10, pady=(0, 10))
        self.reply_chance_entry.insert(0, str(self.config.get('random_reply_chance', 0.05)))

        # Image Generation Settings
        img_gen_config = self.config.get('image_generation', {})
        self.image_gen_enabled_var = ctk.BooleanVar(value=img_gen_config.get('enabled', True))
        image_gen_checkbox = ctk.CTkCheckBox(
            self.left_frame,
            text="Enable Image Generation",
            variable=self.image_gen_enabled_var
        )
        image_gen_checkbox.pack(padx=10, anchor="w", pady=(5, 0))
        ToolTip(image_gen_checkbox, "Allow bot to generate childlike drawings when users ask.\nRequires Together.ai API key above.\nImages cost $0.002 each (~$2 per 1,000 images).")

        ctk.CTkLabel(self.left_frame, text="Max Images Per User Per Period:").pack(padx=10, anchor="w", pady=(5, 0))
        self.max_images_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.max_images_entry.pack(padx=10, pady=(0, 5))
        self.max_images_entry.insert(0, str(img_gen_config.get('max_per_user_per_period', 5)))

        ctk.CTkLabel(self.left_frame, text="Reset Period (hours):").pack(padx=10, anchor="w", pady=(5, 0))
        self.reset_period_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.reset_period_entry.pack(padx=10, pady=(0, 10))
        self.reset_period_entry.insert(0, str(img_gen_config.get('reset_period_hours', 2)))

        # Daily Status Update Settings
        ctk.CTkLabel(self.left_frame, text="Daily Status Updates", font=("Roboto", 16, "bold")).pack(pady=(10, 5))

        status_config = self.config.get('status_updates', {})
        self.status_enabled_var = ctk.BooleanVar(value=status_config.get('enabled', False))
        status_checkbox = ctk.CTkCheckBox(
            self.left_frame,
            text="Enable Daily Status Updates",
            variable=self.status_enabled_var
        )
        status_checkbox.pack(padx=10, anchor="w", pady=(5, 0))
        ToolTip(status_checkbox, "Bot generates a funny AI status once per day\nbased on its personality (e.g., 'Thinking about fish...').")

        ctk.CTkLabel(self.left_frame, text="Status Update Time (24h format, e.g., 14:30):").pack(padx=10, anchor="w", pady=(5, 0))
        self.status_time_entry = ctk.CTkEntry(self.left_frame, width=320)
        self.status_time_entry.pack(padx=10, pady=(0, 5))
        self.status_time_entry.insert(0, status_config.get('update_time', '12:00'))

        ctk.CTkLabel(self.left_frame, text="Source Server for Status Generation:").pack(padx=10, anchor="w", pady=(5, 0))

        # We'll populate this dropdown dynamically
        self.status_source_server_var = ctk.StringVar(value=status_config.get('source_server_name', 'Most Active Server'))
        self.status_source_dropdown = ctk.CTkComboBox(
            self.left_frame,
            variable=self.status_source_server_var,
            values=['Most Active Server'],  # Will be updated dynamically
            width=320,
            state="readonly"
        )
        self.status_source_dropdown.pack(padx=10, pady=(0, 10))
        ToolTip(self.status_source_dropdown, "Choose which server's personality/lore to use for status generation.\n'Most Active Server' automatically picks the busiest one.")

        # Proactive Engagement Settings removed - now configured per-channel only
        # Use Server Manager > Active Channels to configure proactive engagement per channel

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
        self.server_list_frame = ctk.CTkScrollableFrame(self.right_frame, height=75)
        self.server_list_frame.pack(fill="x", padx=10)
        self.update_server_list()

        ctk.CTkLabel(self.right_frame, text="Bot Console Output:", font=("Roboto", 12, "bold")).pack(pady=(10, 5), padx=10, anchor="w")
        self.log_textbox = ctk.CTkTextbox(self.right_frame, height=150)
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log_textbox.configure(state="disabled")

        self.bottom_frame = ctk.CTkFrame(self, height=60)
        self.bottom_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="we")

        self.save_button = ctk.CTkButton(self.bottom_frame, text="Save Config", command=self.save_all_configs)
        self.save_button.pack(side="left", padx=20, pady=10)

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
        Supports:
        - New structure: database/{server_name}/{guild_id}_data.db
        - Legacy structures for backward compatibility
        """
        import re
        servers = []
        db_folder = "database"

        if not os.path.exists(db_folder):
            return servers

        for item in os.listdir(db_folder):
            item_path = os.path.join(db_folder, item)

            # Check if it's a directory
            if os.path.isdir(item_path):
                # Look for database files in this folder
                for filename in os.listdir(item_path):
                    # New format: {guild_id}_data.db
                    match = re.match(r'^(\d+)_data\.db$', filename)
                    if match:
                        guild_id = match.group(1)
                        server_name = item  # Folder name is server name
                        servers.append((guild_id, server_name))
                        break
                    # Legacy format: data.db
                    elif filename == "data.db":
                        # Try to extract guild_id from folder name
                        folder_match = re.match(r'^(\d+)_(.+)$', item)
                        if folder_match:
                            guild_id = folder_match.group(1)
                            server_name = folder_match.group(2)
                        elif item.isdigit():
                            guild_id = item
                            server_name = f"Server {guild_id}"
                        else:
                            guild_id = "unknown"
                            server_name = item
                        servers.append((guild_id, server_name))
                        break

            # Very old flat structure: database/{guild_id}_{servername}_data.db
            elif item.endswith('_data.db') and item != '_data.db':
                match = re.match(r'^(\d+)_(.+)_data\.db$', item)
                if match:
                    guild_id = match.group(1)
                    server_name = match.group(2)
                    servers.append((guild_id, server_name))
                else:
                    # Ancient format: {servername}_data.db (no guild_id)
                    match = re.match(r'^(.+)_data\.db$', item)
                    if match:
                        server_name = match.group(1)
                        guild_id = "unknown"
                        servers.append((guild_id, server_name))

        return servers

    def update_server_list(self):
        """Refreshes the server list display."""
        # Clear existing widgets
        for widget in self.server_list_frame.winfo_children():
            widget.destroy()

        # Scan for server databases
        servers = self._scan_server_databases()

        # Update status source dropdown with available servers
        self._update_status_source_dropdown(servers)

        if not servers:
            ctk.CTkLabel(self.server_list_frame, text="No servers found. Use /activate in Discord to activate the bot on a server.").pack(anchor="w", padx=5)
            return

        # Display each server
        for guild_id, server_name in servers:
            server_frame = ctk.CTkFrame(self.server_list_frame, fg_color="transparent")
            server_frame.pack(fill="x", pady=2)

            # Server name label
            ctk.CTkLabel(server_frame, text=server_name, font=("Roboto", 13)).pack(side="left", anchor="w", padx=5)

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

    def _update_status_source_dropdown(self, servers):
        """Update the status source dropdown with available servers."""
        server_names = ['Most Active Server'] + [server_name for _, server_name in servers]
        self.status_source_dropdown.configure(values=server_names)

    def open_server_settings(self, guild_id, server_name):
        """Opens the Server Settings Dialog for a specific server."""
        # Create settings window
        settings_window = ctk.CTkToplevel(self)
        settings_window.title(f"Server Settings - {server_name}")
        settings_window.geometry("600x500")
        settings_window.resizable(True, True)
        settings_window.minsize(500, 400)

        # Bring window to front
        settings_window.lift()
        settings_window.focus_force()
        settings_window.attributes('-topmost', True)
        settings_window.after(100, lambda: settings_window.attributes('-topmost', False))
        # Don't use grab_set() here so child windows can appear on top

        # Server name display
        ctk.CTkLabel(settings_window, text=f"Server: {server_name}", font=("Roboto", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(settings_window, text=f"Guild ID: {guild_id}", font=("Roboto", 12)).pack(pady=(0, 10))
        ctk.CTkLabel(settings_window, text="Select a setting category to configure:", font=("Roboto", 12)).pack(pady=(0, 20))

        # Buttons frame for all categories
        buttons_frame = ctk.CTkFrame(settings_window, fg_color="transparent")
        buttons_frame.pack(fill="both", expand=True, padx=40, pady=20)

        # Active Channels Button
        channels_btn = ctk.CTkButton(
            buttons_frame,
            text="Active Channels",
            command=lambda: self.open_channels_manager(guild_id, server_name),
            fg_color="#0d6efd",
            hover_color="#0b5ed7",
            text_color="white",
            height=50,
            font=("Roboto", 14, "bold")
        )
        channels_btn.pack(fill="x", pady=10)

        # Alternative Nicknames Button
        nicknames_btn = ctk.CTkButton(
            buttons_frame,
            text="Alternative Nicknames",
            command=lambda: self.open_nicknames_manager(guild_id, server_name),
            fg_color="#198754",
            hover_color="#157347",
            text_color="white",
            height=50,
            font=("Roboto", 14, "bold")
        )
        nicknames_btn.pack(fill="x", pady=10)

        # Emote Sources Button
        emotes_btn = ctk.CTkButton(
            buttons_frame,
            text="Emote Sources",
            command=lambda: self.open_emotes_manager(guild_id, server_name),
            fg_color="#fd7e14",
            hover_color="#e06610",
            text_color="white",
            height=50,
            font=("Roboto", 14, "bold")
        )
        emotes_btn.pack(fill="x", pady=10)

        # User Management Button
        users_btn = ctk.CTkButton(
            buttons_frame,
            text="User Management",
            command=lambda: self.open_user_manager_for_server(guild_id, server_name),
            fg_color="#6f42c1",
            hover_color="#59359a",
            text_color="white",
            height=50,
            font=("Roboto", 14, "bold")
        )
        users_btn.pack(fill="x", pady=10)

        # Status Update Settings Button
        status_btn = ctk.CTkButton(
            buttons_frame,
            text="Status Update Settings",
            command=lambda: self.open_status_settings(guild_id, server_name),
            fg_color="#20c997",
            hover_color="#1aa179",
            text_color="white",
            height=50,
            font=("Roboto", 14, "bold")
        )
        status_btn.pack(fill="x", pady=10)

        # Close button at bottom
        close_btn = ctk.CTkButton(
            settings_window,
            text="Close",
            command=settings_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        close_btn.pack(pady=20)

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

        # Channel ID and Name display
        channel_name = channel_config.get('channel_name', 'Unknown')
        ctk.CTkLabel(edit_window, text=f"Channel: #{channel_name}", font=("Roboto", 14, "bold")).pack(pady=(20, 5))
        ctk.CTkLabel(edit_window, text=f"Channel ID: {channel_id}", font=("Roboto", 10)).pack(pady=(0, 10))

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
        server_info_checkbox.pack(padx=20, anchor="w", pady=(5, 0))
        ToolTip(server_info_checkbox, "Load text files from Server_Info/\nfor rules, policies, or server-specific information.\nIdeal for formal channels like rules or moderation.")

        # Roleplay Formatting
        current_roleplay_formatting = channel_config.get('enable_roleplay_formatting', global_personality_mode.get('enable_roleplay_formatting', True))
        roleplay_formatting_var = ctk.BooleanVar(value=current_roleplay_formatting)
        roleplay_formatting_checkbox = ctk.CTkCheckBox(
            edit_window,
            text="Enable Roleplay Formatting",
            variable=roleplay_formatting_var
        )
        roleplay_formatting_checkbox.pack(padx=20, anchor="w", pady=(5, 0))
        ToolTip(roleplay_formatting_checkbox, "Format physical actions in italics (e.g., *walks over*).\nOnly works when Immersive Character Mode is enabled.\nMakes roleplay more immersive and natural.")

        # Proactive Engagement Settings
        ctk.CTkLabel(edit_window, text="Proactive Engagement Settings:", font=("Roboto", 12, "bold")).pack(padx=20, anchor="w", pady=(10, 5))

        current_allow_proactive = channel_config.get('allow_proactive_engagement', True)
        allow_proactive_var = ctk.BooleanVar(value=current_allow_proactive)
        allow_proactive_checkbox = ctk.CTkCheckBox(
            edit_window,
            text="Allow Proactive Engagement",
            variable=allow_proactive_var
        )
        allow_proactive_checkbox.pack(padx=20, anchor="w", pady=(5, 0))
        ToolTip(allow_proactive_checkbox, "Allow bot to randomly join conversations in this channel.\nDisable for serious/formal channels like rules or announcements.")

        ctk.CTkLabel(edit_window, text="Check Interval (minutes):").pack(padx=20, anchor="w", pady=(5, 0))
        proactive_interval_entry = ctk.CTkEntry(edit_window, width=200)
        proactive_interval_entry.pack(padx=20, pady=(0, 5), anchor="w")
        current_interval = channel_config.get('proactive_check_interval', 30)
        proactive_interval_entry.insert(0, str(current_interval))

        ctk.CTkLabel(edit_window, text="Engagement Threshold (0.0-1.0, higher = more selective):").pack(padx=20, anchor="w", pady=(5, 0))
        proactive_threshold_entry = ctk.CTkEntry(edit_window, width=200)
        proactive_threshold_entry.pack(padx=20, pady=(0, 10), anchor="w")
        current_threshold = channel_config.get('proactive_threshold', 0.7)
        proactive_threshold_entry.insert(0, str(current_threshold))

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
            current_config['channel_settings'][channel_id]['enable_roleplay_formatting'] = roleplay_formatting_var.get()
            current_config['channel_settings'][channel_id]['allow_proactive_engagement'] = allow_proactive_var.get()

            # Save proactive engagement settings
            try:
                new_interval = int(proactive_interval_entry.get())
                current_config['channel_settings'][channel_id]['proactive_check_interval'] = new_interval
            except ValueError:
                current_config['channel_settings'][channel_id]['proactive_check_interval'] = 30

            try:
                new_threshold = float(proactive_threshold_entry.get())
                # Clamp between 0.0 and 1.0
                new_threshold = max(0.0, min(1.0, new_threshold))
                current_config['channel_settings'][channel_id]['proactive_threshold'] = new_threshold
            except ValueError:
                current_config['channel_settings'][channel_id]['proactive_threshold'] = 0.7

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
        set_key(ENV_FILE, "TOGETHER_API_KEY", self.together_key_entry.get())
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

        # Save image generation settings
        if 'image_generation' not in new_config:
            new_config['image_generation'] = {}

        new_config['image_generation']['enabled'] = self.image_gen_enabled_var.get()
        try:
            new_config['image_generation']['max_per_user_per_period'] = int(self.max_images_entry.get())
        except ValueError:
            new_config['image_generation']['max_per_user_per_period'] = 5

        try:
            new_config['image_generation']['reset_period_hours'] = int(self.reset_period_entry.get())
        except ValueError:
            new_config['image_generation']['reset_period_hours'] = 2

        # Preserve other image_generation settings
        if 'style_prefix' not in new_config['image_generation']:
            new_config['image_generation']['style_prefix'] = "Childlike crayon drawing, kindergarten art style, simple 2D sketch"
        if 'model' not in new_config['image_generation']:
            new_config['image_generation']['model'] = "black-forest-labs/FLUX.1-schnell"
        if 'width' not in new_config['image_generation']:
            new_config['image_generation']['width'] = 512
        if 'height' not in new_config['image_generation']:
            new_config['image_generation']['height'] = 512
        if 'steps' not in new_config['image_generation']:
            new_config['image_generation']['steps'] = 4

        # Save status update settings
        if 'status_updates' not in new_config:
            new_config['status_updates'] = {}

        new_config['status_updates']['enabled'] = self.status_enabled_var.get()
        new_config['status_updates']['update_time'] = self.status_time_entry.get().strip()
        new_config['status_updates']['source_server_name'] = self.status_source_server_var.get()

        # Note: Proactive engagement is now configured per-channel only
        # Global proactive_engagement settings removed from GUI
        # Use Server Manager > Active Channels to configure per channel

        # Note: Channel activation is now handled through Server Manager UI or /activate command in Discord
        # Legacy manual channel addition code removed

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

    def open_channels_manager(self, guild_id, server_name):
        """Opens the Active Channels manager for a specific server."""
        # Create channels window
        channels_window = ctk.CTkToplevel(self)
        channels_window.title(f"Active Channels - {server_name}")
        channels_window.geometry("700x600")
        channels_window.resizable(True, True)
        channels_window.minsize(600, 500)

        # Bring window to front (do this BEFORE grab_set)
        channels_window.lift()
        channels_window.focus_force()
        channels_window.attributes('-topmost', True)
        channels_window.after(100, lambda: channels_window.attributes('-topmost', False))
        channels_window.after(200, channels_window.grab_set)  # Grab after window is visible

        # Title
        ctk.CTkLabel(channels_window, text=f"Active Channels - {server_name}", font=("Roboto", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(channels_window, text="Channels activated for this server via /activate command", font=("Roboto", 10)).pack(pady=(0, 20))

        # Channels list frame
        channels_frame = ctk.CTkScrollableFrame(channels_window, height=400)
        channels_frame.pack(fill="both", expand=True, padx=20, pady=5)

        def refresh_channels():
            """Refresh the channels list for this server."""
            for widget in channels_frame.winfo_children():
                widget.destroy()

            config = self.config_manager.get_config()
            channel_settings = config.get('channel_settings', {})

            # Filter channels by guild_id
            server_channels = []
            for channel_id, channel_config in channel_settings.items():
                channel_guild_id = channel_config.get('guild_id', None)

                # Match channels that belong to this guild
                if channel_guild_id == guild_id:
                    server_channels.append((channel_id, channel_config))
                # For backward compatibility: if no guild_id is stored, show in all servers
                # (user can delete from wrong servers or re-activate to set proper guild_id)
                elif channel_guild_id is None:
                    server_channels.append((channel_id, channel_config))

            if not server_channels:
                ctk.CTkLabel(channels_frame, text="No channels activated yet. Use /activate in Discord.").pack(anchor="w", padx=5, pady=20)
            else:
                for channel_id, channel_config in server_channels:
                    channel_row = ctk.CTkFrame(channels_frame, fg_color="transparent")
                    channel_row.pack(fill="x", pady=2)

                    # Display channel name if available, otherwise show channel ID
                    channel_name = channel_config.get('channel_name', '')
                    # If channel_name is empty, generic, or just "Channel", show ID instead
                    if not channel_name or channel_name == 'Unknown' or channel_name.startswith('Channel '):
                        display_name = channel_id  # Just show the ID without "Channel ID:" prefix
                    else:
                        display_name = channel_name

                    purpose = channel_config.get('purpose', 'Default purpose')[:50]
                    # Format: either "#channel-name: purpose" or "ID [long-id]: purpose"
                    if channel_name and not channel_name.startswith('Channel '):
                        label_text = f"#{display_name}: {purpose}..."
                    else:
                        label_text = f"ID {display_name}: {purpose}..."

                    ctk.CTkLabel(channel_row, text=label_text, width=350, anchor="w").pack(side="left", anchor="w", padx=5)

                    # Delete button
                    delete_ch_btn = ctk.CTkButton(
                        channel_row,
                        text="Delete",
                        command=lambda cid=channel_id: [self.remove_channel(cid), refresh_channels()],
                        width=70,
                        height=28,
                        fg_color="#dc3545",
                        hover_color="#c82333"
                    )
                    delete_ch_btn.pack(side="right", padx=2)

                    # Edit button
                    edit_ch_btn = ctk.CTkButton(
                        channel_row,
                        text="Edit",
                        command=lambda cid=channel_id, cfg=channel_config: [self.edit_channel(cid, cfg), refresh_channels()],
                        width=70,
                        height=28,
                        fg_color="#17a2b8",
                        hover_color="#138496"
                    )
                    edit_ch_btn.pack(side="right", padx=2)

        refresh_channels()

        # Track config file changes and auto-refresh
        last_modified = [os.path.getmtime(CONFIG_FILE) if os.path.exists(CONFIG_FILE) else 0]

        def check_for_updates():
            """Check if config file changed and refresh if needed."""
            try:
                if os.path.exists(CONFIG_FILE):
                    current_modified = os.path.getmtime(CONFIG_FILE)
                    if current_modified > last_modified[0]:
                        last_modified[0] = current_modified
                        refresh_channels()
            except:
                pass
            # Check again in 500ms
            if channels_window.winfo_exists():
                channels_window.after(500, check_for_updates)

        # Start the update checker
        channels_window.after(500, check_for_updates)

        # Close button
        close_btn = ctk.CTkButton(
            channels_window,
            text="Close",
            command=channels_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        close_btn.pack(pady=20)

    def open_nicknames_manager(self, guild_id, server_name):
        """Opens the Alternative Nicknames manager for a specific server."""
        # Create nicknames window
        nicknames_window = ctk.CTkToplevel(self)
        nicknames_window.title(f"Alternative Nicknames - {server_name}")
        nicknames_window.geometry("600x400")
        nicknames_window.resizable(True, True)
        nicknames_window.minsize(500, 300)

        # Bring window to front (do this BEFORE grab_set)
        nicknames_window.lift()
        nicknames_window.focus_force()
        nicknames_window.attributes('-topmost', True)
        nicknames_window.after(100, lambda: nicknames_window.attributes('-topmost', False))
        nicknames_window.after(200, nicknames_window.grab_set)  # Grab after window is visible

        # Title
        ctk.CTkLabel(nicknames_window, text=f"Alternative Nicknames - {server_name}", font=("Roboto", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(nicknames_window, text="Comma-separated nicknames the bot responds to (e.g., 'drfish, dr fish')", font=("Roboto", 10)).pack(pady=(0, 20), padx=20)

        # Nicknames entry
        ctk.CTkLabel(nicknames_window, text="Alternative Nicknames:", font=("Roboto", 12, "bold")).pack(padx=20, anchor="w", pady=(10, 5))

        nicknames_entry = ctk.CTkEntry(nicknames_window, width=500, height=40, font=("Roboto", 12))
        nicknames_entry.pack(padx=20, pady=10, fill="x")

        # Get current server-specific nicknames
        config = self.config_manager.get_config()
        server_nicknames = config.get('server_alternative_nicknames', {})
        current_nicknames = server_nicknames.get(guild_id, [])
        if current_nicknames:
            nicknames_entry.insert(0, ', '.join(current_nicknames))

        # Info label
        info_frame = ctk.CTkFrame(nicknames_window, fg_color="transparent")
        info_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            info_frame,
            text="The bot will respond when mentioned by these nicknames in addition to @mentions and replies.\nSeparate multiple nicknames with commas.",
            font=("Roboto", 10),
            text_color="gray",
            justify="left"
        ).pack(anchor="w")

        # Buttons frame
        button_frame = ctk.CTkFrame(nicknames_window, fg_color="transparent")
        button_frame.pack(pady=20)

        def save_nicknames():
            nicknames_str = nicknames_entry.get().strip()
            current_config = self.config_manager.get_config()

            if 'server_alternative_nicknames' not in current_config:
                current_config['server_alternative_nicknames'] = {}

            if nicknames_str:
                current_config['server_alternative_nicknames'][guild_id] = [nick.strip() for nick in nicknames_str.split(',') if nick.strip()]
            else:
                current_config['server_alternative_nicknames'][guild_id] = []

            self.config_manager.update_config(current_config)
            print(f"Updated alternative nicknames for {server_name}")
            self.log_to_console(f"Updated alternative nicknames for {server_name}")
            nicknames_window.destroy()

        # Save button
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            command=save_nicknames,
            fg_color="#28a745",
            hover_color="#218838",
            width=120
        )
        save_btn.pack(side="left", padx=10)

        # Cancel button
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=nicknames_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        cancel_btn.pack(side="left", padx=10)

    def open_emotes_manager(self, guild_id, server_name):
        """Opens the Emote Sources manager for a specific server."""
        # Create emotes window
        emotes_window = ctk.CTkToplevel(self)
        emotes_window.title(f"Emote Sources - {server_name}")
        emotes_window.geometry("600x500")
        emotes_window.resizable(True, True)
        emotes_window.minsize(500, 400)

        # Bring window to front (do this BEFORE grab_set)
        emotes_window.lift()
        emotes_window.focus_force()
        emotes_window.attributes('-topmost', True)
        emotes_window.after(100, lambda: emotes_window.attributes('-topmost', False))
        emotes_window.after(200, emotes_window.grab_set)  # Grab after window is visible

        # Title
        ctk.CTkLabel(emotes_window, text=f"Emote Sources - {server_name}", font=("Roboto", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(emotes_window, text="Select which servers' emotes the bot can use in this server", font=("Roboto", 10)).pack(pady=(0, 20))

        # Emote sources frame
        emote_frame = ctk.CTkScrollableFrame(emotes_window, height=300)
        emote_frame.pack(fill="both", expand=True, padx=20, pady=5)

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
                text=f"{srv_name} ({srv_guild_id})",
                variable=var,
                font=("Roboto", 12)
            )
            checkbox.pack(anchor="w", padx=5, pady=5)
            emote_checkboxes[srv_guild_id] = var

        # Buttons frame
        button_frame = ctk.CTkFrame(emotes_window, fg_color="transparent")
        button_frame.pack(pady=20)

        def save_emotes():
            selected_sources = [gid for gid, var in emote_checkboxes.items() if var.get()]
            current_config = self.config_manager.get_config()

            if 'server_emote_sources' not in current_config:
                current_config['server_emote_sources'] = {}

            current_config['server_emote_sources'][guild_id] = selected_sources
            self.config_manager.update_config(current_config)

            print(f"Updated emote sources for {server_name}")
            self.log_to_console(f"Updated emote sources for {server_name}")
            emotes_window.destroy()

        # Save button
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            command=save_emotes,
            fg_color="#28a745",
            hover_color="#218838",
            width=120
        )
        save_btn.pack(side="left", padx=10)

        # Cancel button
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=emotes_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        cancel_btn.pack(side="left", padx=10)

    def open_status_settings(self, guild_id, server_name):
        """Opens the Status Update Settings dialog for a specific server."""
        # Create status settings window
        status_window = ctk.CTkToplevel(self)
        status_window.title(f"Status Settings - {server_name}")
        status_window.geometry("550x300")
        status_window.resizable(True, True)
        status_window.minsize(500, 250)

        # Bring window to front
        status_window.lift()
        status_window.focus_force()
        status_window.attributes('-topmost', True)
        status_window.after(100, lambda: status_window.attributes('-topmost', False))
        status_window.after(200, status_window.grab_set)

        # Title
        ctk.CTkLabel(status_window, text=f"Status Update Settings - {server_name}", font=("Roboto", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(status_window, text="Configure how status updates affect this server", font=("Roboto", 10)).pack(pady=(0, 20))

        # Get current config
        config = self.config_manager.get_config()
        server_status_settings = config.get('server_status_settings', {})
        current_add_to_memory = server_status_settings.get(guild_id, {}).get('add_to_memory', True)

        # Add to memory toggle
        add_to_memory_var = ctk.BooleanVar(value=current_add_to_memory)
        add_to_memory_checkbox = ctk.CTkCheckBox(
            status_window,
            text="Add daily status to short-term memory",
            variable=add_to_memory_var,
            font=("Roboto", 13)
        )
        add_to_memory_checkbox.pack(padx=40, anchor="w", pady=(20, 10))
        ToolTip(add_to_memory_checkbox, "When enabled, the bot's daily status message is added to this\nserver's short-term memory so it can reference it in conversations.")

        # Info frame
        info_frame = ctk.CTkFrame(status_window, fg_color="transparent")
        info_frame.pack(fill="both", expand=True, padx=40, pady=20)

        ctk.CTkLabel(
            info_frame,
            text="The bot generates a funny status once per day (configured in Global Settings).\nThis toggle controls whether that status is logged to this server's memory.",
            font=("Roboto", 10),
            text_color="gray",
            justify="left",
            wraplength=450
        ).pack(anchor="w")

        # Buttons frame
        button_frame = ctk.CTkFrame(status_window, fg_color="transparent")
        button_frame.pack(pady=20)

        def save_status_settings():
            current_config = self.config_manager.get_config()

            if 'server_status_settings' not in current_config:
                current_config['server_status_settings'] = {}

            if guild_id not in current_config['server_status_settings']:
                current_config['server_status_settings'][guild_id] = {}

            current_config['server_status_settings'][guild_id]['add_to_memory'] = add_to_memory_var.get()

            self.config_manager.update_config(current_config)
            print(f"Updated status settings for {server_name}")
            self.log_to_console(f"Updated status settings for {server_name}")
            status_window.destroy()

        # Save button
        save_btn = ctk.CTkButton(
            button_frame,
            text="Save",
            command=save_status_settings,
            fg_color="#28a745",
            hover_color="#218838",
            width=120
        )
        save_btn.pack(side="left", padx=10)

        # Cancel button
        cancel_btn = ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=status_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        cancel_btn.pack(side="left", padx=10)

    def open_user_manager_for_server(self, guild_id, server_name):
        """Opens the User Manager window pre-filtered for a specific server."""
        from database.db_manager import DBManager

        # Construct database path
        server_folder = os.path.join("database", server_name)
        db_filename = os.path.join(server_folder, f"{guild_id}_data.db")

        if not os.path.exists(db_filename):
            self.log_to_console(f"Error: Database file not found for server {server_name}")
            return

        # Create user manager window
        user_window = ctk.CTkToplevel(self)
        user_window.title(f"User Manager - {server_name}")
        user_window.geometry("700x700")
        user_window.resizable(True, True)
        user_window.minsize(650, 600)

        # Aggressively bring window to front and keep it there longer
        user_window.attributes('-topmost', True)
        user_window.lift()
        user_window.focus_force()
        user_window.after(50, user_window.lift)
        user_window.after(100, user_window.lift)
        user_window.after(150, user_window.lift)
        user_window.after(500, lambda: user_window.attributes('-topmost', False))
        # Don't use grab_set() so all windows can be managed independently

        # Title
        ctk.CTkLabel(user_window, text=f"User Relationship Manager - {server_name}", font=("Roboto", 18, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(user_window, text="View and edit relationship metrics for users in this server", font=("Roboto", 12)).pack(pady=(0, 20))

        # User list frame
        ctk.CTkLabel(user_window, text="Users:", font=("Roboto", 12, "bold")).pack(padx=20, anchor="w", pady=(15, 5))

        # Column headers
        headers_frame = ctk.CTkFrame(user_window, fg_color="transparent")
        headers_frame.pack(fill="x", padx=20)

        ctk.CTkLabel(headers_frame, text="Username", font=("Roboto", 10, "bold"), width=140).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="User ID", font=("Roboto", 10, "bold"), width=130).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Rapport", font=("Roboto", 10, "bold"), width=65).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Anger", font=("Roboto", 10, "bold"), width=65).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Trust", font=("Roboto", 10, "bold"), width=65).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Formality", font=("Roboto", 10, "bold"), width=75).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Actions", font=("Roboto", 10, "bold"), width=75).pack(side="left", padx=2)

        # Scrollable user list
        user_list_frame = ctk.CTkScrollableFrame(user_window, height=500)
        user_list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        def refresh_users():
            """Refresh the user list for this server."""
            # Clear existing widgets
            for widget in user_list_frame.winfo_children():
                widget.destroy()

            # Load users from database
            try:
                db_manager = DBManager(db_path=db_filename)
                users = db_manager.get_all_users_with_metrics()

                if not users:
                    db_manager.close()
                    ctk.CTkLabel(user_list_frame, text="No users found in this server's database.").pack(pady=20)
                    return

                # Display each user
                for user_data in users:
                    user_row = ctk.CTkFrame(user_list_frame, fg_color="transparent")
                    user_row.pack(fill="x", pady=2)

                    user_id = user_data['user_id']

                    # Fetch most recent username from nicknames table
                    cursor = db_manager.conn.cursor()
                    cursor.execute("SELECT nickname FROM nicknames WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
                    username_result = cursor.fetchone()
                    username = username_result[0] if username_result else "Unknown"

                    # Display username and user ID
                    ctk.CTkLabel(user_row, text=username, width=140).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_id), width=130).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['rapport']), width=65).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['anger']), width=65).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['trust']), width=65).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['formality']), width=75).pack(side="left", padx=2)

                    edit_btn = ctk.CTkButton(
                        user_row,
                        text="Edit",
                        command=lambda ud=user_data, dbf=db_filename: self.open_user_edit_dialog(ud, dbf, refresh_users),
                        width=75,
                        height=24,
                        font=("Roboto", 11),
                        fg_color="#17a2b8",
                        hover_color="#138496"
                    )
                    edit_btn.pack(side="left", padx=2)

                db_manager.close()

            except Exception as e:
                ctk.CTkLabel(user_list_frame, text=f"Error loading users: {str(e)}").pack(pady=20)
                print(f"Error loading users: {e}")

        # Load users immediately
        refresh_users()

        # Close button
        close_btn = ctk.CTkButton(
            user_window,
            text="Close",
            command=user_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        close_btn.pack(pady=20)

    def open_user_manager(self):
        """Opens the User Manager window to view and edit user relationship metrics."""
        from database.db_manager import DBManager

        # Create user manager window
        user_window = ctk.CTkToplevel(self)
        user_window.title("User Manager")
        user_window.geometry("700x700")
        user_window.resizable(True, True)
        user_window.minsize(650, 600)

        # Bring window to front
        user_window.lift()
        user_window.focus_force()
        user_window.attributes('-topmost', True)
        user_window.after(100, lambda: user_window.attributes('-topmost', False))

        # Title
        ctk.CTkLabel(user_window, text="User Relationship Manager", font=("Roboto", 18, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(user_window, text="View and edit relationship metrics for users in each server", font=("Roboto", 10)).pack(pady=(0, 20))

        # Server selector
        ctk.CTkLabel(user_window, text="Select Server:", font=("Roboto", 12, "bold")).pack(padx=20, anchor="w")

        server_selector_frame = ctk.CTkFrame(user_window, fg_color="transparent")
        server_selector_frame.pack(fill="x", padx=20, pady=5)

        servers = self._scan_server_databases()
        if not servers:
            ctk.CTkLabel(user_window, text="No servers found. Use /activate in Discord to set up a server first.").pack(pady=20)
            return

        server_names = [f"{server_name} ({guild_id})" for guild_id, server_name in servers]
        selected_server_var = ctk.StringVar(value=server_names[0] if server_names else "")

        server_dropdown = ctk.CTkComboBox(
            server_selector_frame,
            variable=selected_server_var,
            values=server_names,
            width=400,
            state="readonly"
        )
        server_dropdown.pack(side="left", padx=5)

        # User list frame
        ctk.CTkLabel(user_window, text="Users:", font=("Roboto", 12, "bold")).pack(padx=20, anchor="w", pady=(15, 5))

        # Column headers
        headers_frame = ctk.CTkFrame(user_window, fg_color="transparent")
        headers_frame.pack(fill="x", padx=20)

        ctk.CTkLabel(headers_frame, text="Username", font=("Roboto", 10, "bold"), width=140).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="User ID", font=("Roboto", 10, "bold"), width=130).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Rapport", font=("Roboto", 10, "bold"), width=65).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Anger", font=("Roboto", 10, "bold"), width=65).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Trust", font=("Roboto", 10, "bold"), width=65).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Formality", font=("Roboto", 10, "bold"), width=75).pack(side="left", padx=2)
        ctk.CTkLabel(headers_frame, text="Actions", font=("Roboto", 10, "bold"), width=75).pack(side="left", padx=2)

        # Scrollable user list
        user_list_frame = ctk.CTkScrollableFrame(user_window, height=400)
        user_list_frame.pack(fill="both", expand=True, padx=20, pady=5)

        def refresh_users():
            """Refresh the user list for the selected server."""
            # Clear existing widgets
            for widget in user_list_frame.winfo_children():
                widget.destroy()

            # Get selected server
            selected = selected_server_var.get()
            if not selected:
                return

            # Parse guild_id from selection
            guild_id = selected.split("(")[-1].rstrip(")")

            # Find matching server
            server_folder = None
            db_filename = None
            for srv_guild_id, srv_name in servers:
                if srv_guild_id == guild_id:
                    # Construct database path
                    server_folder = os.path.join("database", srv_name)
                    db_filename = os.path.join(server_folder, f"{srv_guild_id}_data.db")
                    break

            if not db_filename or not os.path.exists(db_filename):
                ctk.CTkLabel(user_list_frame, text="Database file not found for this server.").pack(pady=20)
                return

            # Load users from database
            try:
                db_manager = DBManager(db_path=db_filename)
                users = db_manager.get_all_users_with_metrics()

                if not users:
                    db_manager.close()
                    ctk.CTkLabel(user_list_frame, text="No users found in this server's database.").pack(pady=20)
                    return

                # Display each user
                for user_data in users:
                    user_row = ctk.CTkFrame(user_list_frame, fg_color="transparent")
                    user_row.pack(fill="x", pady=2)

                    user_id = user_data['user_id']

                    # Fetch most recent username from nicknames table
                    cursor = db_manager.conn.cursor()
                    cursor.execute("SELECT nickname FROM nicknames WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
                    username_result = cursor.fetchone()
                    username = username_result[0] if username_result else "Unknown"

                    # Display username and user ID
                    ctk.CTkLabel(user_row, text=username, width=140).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_id), width=130).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['rapport']), width=65).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['anger']), width=65).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['trust']), width=65).pack(side="left", padx=2)
                    ctk.CTkLabel(user_row, text=str(user_data['formality']), width=75).pack(side="left", padx=2)

                    edit_btn = ctk.CTkButton(
                        user_row,
                        text="Edit",
                        command=lambda ud=user_data, dbf=db_filename: self.open_user_edit_dialog(ud, dbf, refresh_users),
                        width=75,
                        height=24,
                        font=("Roboto", 11),
                        fg_color="#17a2b8",
                        hover_color="#138496"
                    )
                    edit_btn.pack(side="left", padx=2)

                db_manager.close()

            except Exception as e:
                ctk.CTkLabel(user_list_frame, text=f"Error loading users: {str(e)}").pack(pady=20)
                print(f"Error loading users: {e}")

        # Refresh button
        refresh_btn = ctk.CTkButton(
            server_selector_frame,
            text="Load Users",
            command=refresh_users,
            width=100,
            fg_color="#28a745",
            hover_color="#218838"
        )
        refresh_btn.pack(side="left", padx=5)

        # Close button
        close_btn = ctk.CTkButton(
            user_window,
            text="Close",
            command=user_window.destroy,
            fg_color="#6c757d",
            hover_color="#5a6268",
            width=120
        )
        close_btn.pack(pady=20)

    def open_user_edit_dialog(self, user_data, db_filename, refresh_callback):
        """Opens a dialog to edit a user's relationship metrics and locks."""
        from database.db_manager import DBManager

        # Fetch username from database
        try:
            db_manager = DBManager(db_path=db_filename)
            cursor = db_manager.conn.cursor()
            cursor.execute("SELECT nickname FROM nicknames WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_data['user_id'],))
            username_result = cursor.fetchone()
            username = username_result[0] if username_result else "Unknown"
            db_manager.close()
        except:
            username = "Unknown"

        # Create edit window
        edit_window = ctk.CTkToplevel(self)
        edit_window.title(f"Edit User - {username}")
        edit_window.geometry("500x800")
        edit_window.resizable(False, False)

        # Bring window to front
        edit_window.lift()
        edit_window.focus_force()
        edit_window.attributes('-topmost', True)
        edit_window.after(100, lambda: edit_window.attributes('-topmost', False))
        # Don't use grab_set() so User Manager stays accessible

        # Title
        ctk.CTkLabel(edit_window, text=f"Edit User Metrics", font=("Roboto", 16, "bold")).pack(pady=(20, 10))
        ctk.CTkLabel(edit_window, text=f"{username} (ID: {user_data['user_id']})", font=("Roboto", 10)).pack(pady=(0, 20))

        # Metrics frame
        metrics_frame = ctk.CTkFrame(edit_window, fg_color="transparent")
        metrics_frame.pack(fill="x", padx=20)

        # Helper function to create metric row
        def create_metric_row(parent, label, value, locked, min_val, max_val):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", pady=10)

            # Label
            ctk.CTkLabel(row, text=f"{label}:", width=80, anchor="w").pack(side="left", padx=5)

            # Value entry
            entry = ctk.CTkEntry(row, width=80)
            entry.insert(0, str(value))
            entry.pack(side="left", padx=5)

            # Range label
            ctk.CTkLabel(row, text=f"({min_val} to {max_val})", width=70, anchor="w").pack(side="left")

            # Lock checkbox
            lock_var = ctk.BooleanVar(value=locked)
            lock_checkbox = ctk.CTkCheckBox(row, text="Lock", variable=lock_var, width=70)
            lock_checkbox.pack(side="left", padx=10)
            ToolTip(lock_checkbox, f"Prevent automatic updates to {label.lower()} from sentiment analysis")

            return entry, lock_var

        # Create metric rows
        rapport_entry, rapport_lock_var = create_metric_row(
            metrics_frame, "Rapport",
            user_data['rapport'],
            user_data.get('rapport_locked', False),
            0, 10
        )

        anger_entry, anger_lock_var = create_metric_row(
            metrics_frame, "Anger",
            user_data['anger'],
            user_data.get('anger_locked', False),
            0, 10
        )

        trust_entry, trust_lock_var = create_metric_row(
            metrics_frame, "Trust",
            user_data['trust'],
            user_data.get('trust_locked', False),
            0, 10
        )

        formality_entry, formality_lock_var = create_metric_row(
            metrics_frame, "Formality",
            user_data['formality'],
            user_data.get('formality_locked', False),
            -5, 5
        )

        # New metrics (2025-10-16)
        fear_entry, fear_lock_var = create_metric_row(
            metrics_frame, "Fear",
            user_data.get('fear', 0),
            user_data.get('fear_locked', False),
            0, 10
        )

        respect_entry, respect_lock_var = create_metric_row(
            metrics_frame, "Respect",
            user_data.get('respect', 0),
            user_data.get('respect_locked', False),
            0, 10
        )

        affection_entry, affection_lock_var = create_metric_row(
            metrics_frame, "Affection",
            user_data.get('affection', 0),
            user_data.get('affection_locked', False),
            0, 10
        )

        familiarity_entry, familiarity_lock_var = create_metric_row(
            metrics_frame, "Familiarity",
            user_data.get('familiarity', 0),
            user_data.get('familiarity_locked', False),
            0, 10
        )

        intimidation_entry, intimidation_lock_var = create_metric_row(
            metrics_frame, "Intimidation",
            user_data.get('intimidation', 0),
            user_data.get('intimidation_locked', False),
            0, 10
        )

        # Info text
        ctk.CTkLabel(
            edit_window,
            text="Locked metrics won't be automatically updated by the bot's sentiment analysis.",
            font=("Roboto", 9),
            text_color="gray"
        ).pack(pady=20)

        # Buttons frame
        button_frame = ctk.CTkFrame(edit_window, fg_color="transparent")
        button_frame.pack(pady=20)

        def save_changes():
            try:
                # Validate and get new values
                new_rapport = int(rapport_entry.get())
                new_anger = int(anger_entry.get())
                new_trust = int(trust_entry.get())
                new_formality = int(formality_entry.get())
                new_fear = int(fear_entry.get())
                new_respect = int(respect_entry.get())
                new_affection = int(affection_entry.get())
                new_familiarity = int(familiarity_entry.get())
                new_intimidation = int(intimidation_entry.get())

                # Validate ranges
                if not (0 <= new_rapport <= 10):
                    self.log_to_console("Error: Rapport must be between 0 and 10")
                    return
                if not (0 <= new_anger <= 10):
                    self.log_to_console("Error: Anger must be between 0 and 10")
                    return
                if not (0 <= new_trust <= 10):
                    self.log_to_console("Error: Trust must be between 0 and 10")
                    return
                if not (-5 <= new_formality <= 5):
                    self.log_to_console("Error: Formality must be between -5 and 5")
                    return
                if not (0 <= new_fear <= 10):
                    self.log_to_console("Error: Fear must be between 0 and 10")
                    return
                if not (0 <= new_respect <= 10):
                    self.log_to_console("Error: Respect must be between 0 and 10")
                    return
                if not (0 <= new_affection <= 10):
                    self.log_to_console("Error: Affection must be between 0 and 10")
                    return
                if not (0 <= new_familiarity <= 10):
                    self.log_to_console("Error: Familiarity must be between 0 and 10")
                    return
                if not (0 <= new_intimidation <= 10):
                    self.log_to_console("Error: Intimidation must be between 0 and 10")
                    return

                # Update database
                db_manager = DBManager(db_path=db_filename)
                db_manager.update_relationship_metrics(
                    user_data['user_id'],
                    respect_locks=False,  # We're manually editing, so ignore current locks
                    rapport=new_rapport,
                    anger=new_anger,
                    trust=new_trust,
                    formality=new_formality,
                    fear=new_fear,
                    respect=new_respect,
                    affection=new_affection,
                    familiarity=new_familiarity,
                    intimidation=new_intimidation,
                    rapport_locked=1 if rapport_lock_var.get() else 0,
                    anger_locked=1 if anger_lock_var.get() else 0,
                    trust_locked=1 if trust_lock_var.get() else 0,
                    formality_locked=1 if formality_lock_var.get() else 0,
                    fear_locked=1 if fear_lock_var.get() else 0,
                    respect_locked=1 if respect_lock_var.get() else 0,
                    affection_locked=1 if affection_lock_var.get() else 0,
                    familiarity_locked=1 if familiarity_lock_var.get() else 0,
                    intimidation_locked=1 if intimidation_lock_var.get() else 0
                )
                db_manager.close()

                self.log_to_console(f"Updated metrics for user {user_data['user_id']}")
                print(f"Updated metrics for user {user_data['user_id']}")

                refresh_callback()
                edit_window.destroy()

            except ValueError:
                self.log_to_console("Error: All metric values must be valid integers")
            except Exception as e:
                self.log_to_console(f"Error saving changes: {str(e)}")
                print(f"Error saving changes: {e}")

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


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = BotGUI()
    app.mainloop()