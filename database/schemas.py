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
    category TEXT NOT NULL, -- 'trait', 'lore', 'fact'
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
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
"""

RELATIONSHIP_METRICS_TABLE = """
CREATE TABLE IF NOT EXISTS relationship_metrics (
    user_id INTEGER PRIMARY KEY,
    anger INTEGER NOT NULL DEFAULT 0,
    rapport INTEGER NOT NULL DEFAULT 0,
    trust INTEGER NOT NULL DEFAULT 0,
    formality INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
);
"""

# --- Logging & Archiving ---

SHORT_TERM_MESSAGE_LOG_TABLE = """
CREATE TABLE IF NOT EXISTS short_term_message_log (
    message_id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    content TEXT,
    timestamp TEXT NOT NULL,
    directed_at_bot INTEGER NOT NULL DEFAULT 0 -- --- ADDED: 1 for True, 0 for False ---
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

# A list of all table creation statements for easy initialization
ALL_TABLES = [
    USERS_TABLE,
    NICKNAMES_TABLE,
    BOT_IDENTITY_TABLE,
    LONG_TERM_MEMORY_TABLE,
    RELATIONSHIP_METRICS_TABLE,
    SHORT_TERM_MESSAGE_LOG_TABLE,
    MESSAGE_ARCHIVE_TABLE
]