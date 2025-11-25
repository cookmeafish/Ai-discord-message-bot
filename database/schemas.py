# database/schemas.py
# This file defines the SQL statements for creating the database tables.

# --- User & Bot Identity ---

USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);
"""

NICKNAMES_TABLE = """
CREATE TABLE IF NOT EXISTS nicknames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    nickname TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
"""

BOT_IDENTITY_TABLE = """
CREATE TABLE IF NOT EXISTS bot_identity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    content TEXT NOT NULL
);
"""

# --- Memory & Relationships ---

LONG_TERM_MEMORY_TABLE = """
CREATE TABLE IF NOT EXISTS long_term_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    fact TEXT NOT NULL,
    source_user_id INTEGER,
    source_nickname TEXT,
    category TEXT,
    first_mentioned_timestamp TEXT NOT NULL,
    last_mentioned_timestamp TEXT NOT NULL,
    reference_count INTEGER NOT NULL DEFAULT 1,
    status TEXT DEFAULT 'active',
    superseded_by_id INTEGER,
    last_validated_timestamp TEXT,
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (superseded_by_id) REFERENCES long_term_memory(id)
);
"""

RELATIONSHIP_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS relationship_metrics (
    user_id INTEGER PRIMARY KEY,
    anger INTEGER NOT NULL DEFAULT 0,
    rapport INTEGER NOT NULL DEFAULT 0,
    trust INTEGER NOT NULL DEFAULT 0,
    formality INTEGER NOT NULL DEFAULT 0,
    fear INTEGER NOT NULL DEFAULT 0,
    respect INTEGER NOT NULL DEFAULT 0,
    affection INTEGER NOT NULL DEFAULT 0,
    familiarity INTEGER NOT NULL DEFAULT 0,
    intimidation INTEGER NOT NULL DEFAULT 0,
    rapport_locked INTEGER NOT NULL DEFAULT 0,
    anger_locked INTEGER NOT NULL DEFAULT 0,
    trust_locked INTEGER NOT NULL DEFAULT 0,
    formality_locked INTEGER NOT NULL DEFAULT 0,
    fear_locked INTEGER NOT NULL DEFAULT 0,
    respect_locked INTEGER NOT NULL DEFAULT 0,
    affection_locked INTEGER NOT NULL DEFAULT 0,
    familiarity_locked INTEGER NOT NULL DEFAULT 0,
    intimidation_locked INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
"""

# --- Global State Schema (ADDED) ---

GLOBAL_STATE_TABLE = """
CREATE TABLE IF NOT EXISTS global_state (
    state_key TEXT PRIMARY KEY,
    state_value TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
"""

# --- Logging & Archiving ---

SHORT_TERM_MESSAGE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS short_term_message_log (
    message_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    nickname TEXT,
    channel_id INTEGER NOT NULL,
    content TEXT,
    timestamp TEXT NOT NULL,
    directed_at_bot INTEGER NOT NULL DEFAULT 0
);
"""

MESSAGE_ARCHIVE_TABLE = """
CREATE TABLE IF NOT EXISTS message_archive (
    message_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    content TEXT,
    timestamp TEXT NOT NULL
);
"""

# --- Image Safety & Rate Limiting ---

USER_IMAGE_STATS_TABLE = """
CREATE TABLE IF NOT EXISTS user_image_stats (
    user_id INTEGER PRIMARY KEY,
    last_image_time TEXT,
    hourly_count INTEGER NOT NULL DEFAULT 0,
    daily_count INTEGER NOT NULL DEFAULT 0,
    date TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
"""

# --- Channel Configuration (Per-Server) ---

CHANNEL_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS channel_settings (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT,
    guild_id TEXT NOT NULL,
    purpose TEXT,
    random_reply_chance REAL DEFAULT 0.0,
    immersive_character INTEGER DEFAULT 1,
    allow_technical_language INTEGER DEFAULT 0,
    use_server_info INTEGER DEFAULT 0,
    enable_roleplay_formatting INTEGER DEFAULT 1,
    allow_proactive_engagement INTEGER DEFAULT 1,
    enable_conversation_detection INTEGER DEFAULT 0,
    conversation_detection_threshold REAL DEFAULT 0.7,
    conversation_context_window INTEGER DEFAULT 10,
    formality INTEGER DEFAULT 0,
    formality_locked INTEGER DEFAULT 0,
    activated_at TEXT NOT NULL
);
"""

# A list of all table creation statements for easy initialization
ALL_TABLES = [
    USERS_TABLE,
    NICKNAMES_TABLE,
    BOT_IDENTITY_TABLE,
    LONG_TERM_MEMORY_TABLE,
    RELATIONSHIP_METRICS_TABLE,
    GLOBAL_STATE_TABLE,
    SHORT_TERM_MESSAGE_LOG_TABLE,
    MESSAGE_ARCHIVE_TABLE,
    USER_IMAGE_STATS_TABLE,
    CHANNEL_SETTINGS_TABLE
]




