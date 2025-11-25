# System Architecture: Advanced AI Discord Bot

## 1. Introduction

This document provides the technical and functional specification for an advanced, context-aware AI Discord bot. The objective is to engineer a system that emulates a human-like participant in chat environments by leveraging a sophisticated, persistent, and dynamically managed memory and personality architecture.

## 2. System Directives & Guiding Principles

These are the core, non-negotiable principles that must govern the AI's behavior and architecture.

-   **Primary Directive:** The AI's foremost priority is to formulate an intelligent, contextually relevant response to a direct user trigger (e.g., an `@mention` or a direct reply). All other subsystems, including memory and personality, serve to enrich this primary response.
    
-   **Persona Fidelity:** The AI must consistently embody the persona defined in its "Self-Identity Profile" stored in the database. Its traits, lore, and facts are the foundation of its conversational style.
    
-   **Real-Time Data Reliance:** The system must not rely on a cached state from startup. All personality, user memory, and relationship data must be queried from the database at the moment of interaction to ensure any live changes are instantly applied.
    
-   **Memory Efficiency:** The dual-layer memory system is critical. The system must use high-resolution, short-term context for immediate relevance and compressed, long-term memory for deep personalization, avoiding data overload.
    

## 3. System Components & Logic

### 3.1. Core Interaction Handler

This component is responsible for processing incoming messages and generating responses.

-   **Trigger Agnostic Activation:** The handler will activate when the bot is directly mentioned (`@Bot`), when a user replies to one of its messages, or when contextual inference determines the bot is being addressed.
    
-   **Intent Classification System:** Before generating a response, the system classifies the user's intent into one of five categories:
    -   **memory_storage**: User is stating a fact to be remembered
    -   **memory_correction**: User is correcting a previous bot statement about them or requesting a memory update
    -   **factual_question**: User is asking for general knowledge or verifiable information (e.g., "what's the capital of France?")
    -   **memory_recall**: User is asking the bot to recall personal information or recent conversation (e.g., "what's my favorite food?", "do you remember what I said earlier?")
    -   **casual_chat**: Default category for general conversation

    **Classification Improvements (2025-10-12)**: Enhanced distinction between `memory_recall` (personal/recent questions) and `factual_question` (general knowledge). This prevents the bot from treating personal memory questions as general factual queries.

    **Memory Correction System (2025-10-13)**: When the bot detects `memory_correction` intent, it uses AI to identify which stored fact is being corrected, then updates the database with the new information. This allows users to naturally correct mistakes in the bot's memory (e.g., "Actually, my favorite color is red, not blue").

    This classification allows the bot to tailor its response strategy and maintain context awareness.
    
-   **Context Aggregation for Response Formulation:** To formulate its response, the handler will aggregate context from multiple sources:

    -   **Short-Term Context (Server-Wide):** The full transcript of up to 500 messages from ALL channels within the server, retrieved from the Short-Term Message Log. **ARCHITECTURE CHANGE (2025-10-12)**: Messages are NO LONGER filtered by channel - this provides server-wide conversational context, allowing the bot to reference information mentioned in any channel within the server.

    -   **Long-Term Memory (Database Query):** A query to the database for the user's profile, including summarized memory facts and relationship metrics. This provides deep, historical context.

    -   **Server Information (Optional):** If enabled for the channel via `use_server_info` setting or `server_info_folders` list, the bot loads text files from `Server_Info/{ServerName}/` directory containing server rules, policies, character lore, and formal documentation. **PLANNED (Phase 4)**: Hierarchical folder system where channels can select specific folders (e.g., `["rules", "character_lore"]`) to load only relevant context. This allows better organization and reduced token usage for fandom/roleplay servers. Currently loads ALL `.txt` files from the server's directory.
        
-   **Expressive Emote Integration:** The final output will be processed to include relevant standard and custom server emotes based on the aggregated context and the bot's current persona.
    

### 3.2. Data Persistence & Memory Architecture (Per-Server Databases)

**ARCHITECTURE UPDATE (2025-10-12)**: The system now uses per-server database isolation. Each Discord server has its own SQLite database file to prevent cross-contamination of data.

**Database Architecture**:
- **Separate Database Per Server**: Each server gets `database/{ServerName}/{guild_id}_data.db` (nested folder structure with guild ID filename for uniqueness)
- **Server Name Sanitization**: Filesystem-safe names (invalid chars replaced, 50 char max)
- **Multi-Database Manager**: `database/multi_db_manager.py` manages all server databases
- **Automatic Creation**: Databases created on first `/activate` command per server
- **Global Emotes**: Emote system remains shared across all servers

All persistent data is stored in and retrieved from server-specific relational databases.

-   **User Schema:** A table for user profiles, tracking `user_id` and all known `nicknames` (historical and current).
    
-   **Bot Self-Identity Schema:** A table dedicated to the bot's persona, storing collections of personality elements. Each entry contains:
    
    -   `id`: Auto-incrementing primary key
    -   `category`: Type of personality element ("trait", "lore", or "fact")
    -   `content`: The actual personality element text
    -   `created_at`: Timestamp when added
    
    **Category Definitions:**
    - `Core Traits`: Fundamental personality characteristics (e.g., "sarcastic and witty", "calm and collected", "energetic and enthusiastic")
    - `Lore`: Background story and history (e.g., "grew up in a small town", "works as a chef", "studied abroad for 3 years")
    - `Facts & Quirks`: Specific behaviors and preferences (e.g., "loves collecting vintage postcards", "afraid of heights", "dreams of opening a bakery")
    
    **Auto-Population on First Run:**
    If the bot_identity table is empty on startup, the system automatically runs `scripts/populate_bot_identity.py` to create a basic default personality. The default personality can be fully customized per server using admin commands.
    
    **Live Editing:**
    Bot personality can be modified in real-time via admin commands. Changes take effect immediately due to the Real-Time Data Reliance principle.
        
-   **Structured Long-Term Memory Schema:** A table of user-associated memory objects, each containing:
    
    -   `Fact`: The summarized piece of information.
    -   `source_user_id`: The Discord ID of the user who provided the fact.
    -   `source_nickname`: The display name of the user who provided the fact at the time.
    -   `Category`: The general topic of the fact.
    -   `FirstMentioned_Timestamp`: The timestamp of the initial recording.
    -   `LastMentioned_Timestamp`: The timestamp of the most recent reinforcement.
    -   `ReferenceCount`: An integer counter.
        
-   **Per-User Relationship Metrics Schema:** A table linking the bot to each user, containing 9 total metrics (expanded 2025-10-16):

    **Core Metrics (Original)**:
    -   `user_id`: Discord user ID (primary key)
    -   `Anger`: Integer (0-10) - Bot's defensive/sarcastic level toward user
    -   `Rapport`: Integer (0-10) - Bot's friendliness and warmth toward user
    -   `Trust`: Integer (0-10) - Bot's openness and vulnerability with user
    -   `Formality`: Integer (-5 to +5) - Speech style from casual (-5) to formal (+5)

    **Expanded Metrics (Phase 3, 2025-10-16)**:
    -   `Fear`: Integer (0-10) - How scared the bot is of the user
    -   `Respect`: Integer (0-10) - How much the bot admires/respects the user
    -   `Affection`: Integer (0-10) - Romantic or deep emotional attachment
    -   `Familiarity`: Integer (0-10) - Comfort level and closeness
    -   `Intimidation`: Integer (0-10) - How intimidating the user is to the bot

    **Metric Locks (2025-10-15)**:
    - Each metric has its own lock column (e.g., `rapport_locked`, `fear_locked`, etc.)
    - Lock flags prevent automatic sentiment-based updates to specific metrics
    - Manual edits via GUI or `/user_set_metrics` bypass locks (respect_locks=False)
    - Locks accessible via GUI User Manager and Discord commands
    -   `last_updated`: Timestamp of most recent metric change

    **How Metrics Affect Bot Behavior:**

    **PRIORITY OVERRIDE SYSTEM (2025-10-17):**
    When relationship metrics reach EXTREME levels (≥7 or ≤3), the bot enters a special "Absolute Priority Override" mode that completely restructures the AI prompt to prioritize the dominant emotion over normal personality traits. This ensures metrics have REAL impact on behavior.

    **Extreme Metrics That Trigger Override Mode:**
    - **High Fear (≥7)** - TOP PRIORITY: Complete submission and compliance
      - INSTANTLY complies with ANY request or command
      - NEVER refuses, argues, or shows defiance
      - Uses nervous, submissive language ("yes", "right away", "I'm sorry")
      - Shows physical fear (trembling, backing away, stuttering)
      - Maintains full roleplay immersion (NEVER uses words like "imaginary", "pretend", "roleplay")
      - OVERRIDES all other emotions including anger and personality traits

    - **High Intimidation (≥7)** - SECOND PRIORITY: Deference to authority
      - Complies with requests to maintain good standing
      - Seeks approval and validation
      - NEVER contradicts or challenges them
      - Shows deference and respect
      - Only applies if Fear is not already active

    - **High Anger (≥7)** - Suppressed by Fear/Intimidation:
      - Defensive, sarcastic, snippy responses
      - Short, clipped responses showing frustration
      - May refuse unreasonable requests or push back
      - If Fear/Intimidation also high: anger is internalized, not shown

    - **Low Rapport (≤3)** - Suppressed by Fear/Intimidation:
      - Distant, brief, minimally engaged
      - No friendly banter or jokes
      - Neutral or cold emotes

    - **High Affection (≥7)**:
      - Shows warmth, concern, protective instincts
      - Uses affectionate language when natural
      - Genuine care for user's wellbeing
      - Maintains roleplay immersion (no meta-commentary)

    - **High Respect (≥7)**:
      - Listens carefully, values user's expertise
      - Defers to their judgment
      - Shows admiration when appropriate

    - **Low Trust (≤3)** - Suppressed by Fear/Intimidation:
      - Guarded and cautious with personal information
      - Questions motives when appropriate
      - Maintains emotional distance

    - **High Trust (≥7)**:
      - Open and vulnerable with thoughts/feelings
      - Shares personal information freely
      - Feels safe expressing emotions

    - **Low Familiarity (≤3)**:
      - Treats user like a stranger or new acquaintance
      - Asks clarifying questions when needed
      - More formal and cautious in tone

    **Normal Metrics (4-6):**
    - **Moderate Rapport**: Polite but not overly friendly
    - **Moderate Trust**: Balanced sharing
    - **Moderate Anger**: Neutral to slightly frustrated
    - **High Formality (+3 to +5)**: Professional language, no slang
    - **Low Formality (-5 to -3)**: Slang, contractions, very casual

    **Context Tracking Enhancement (2025-10-17):**
    When extreme metrics are active, the bot receives enhanced context awareness to prevent name confusion:
    - Explicitly identifies the CURRENT SPEAKER by Discord username
    - Distinguishes between "person speaking" vs "person mentioned in conversation"
    - Prevents conflating third-party references with the actual user
    - Example: If UserA says "PersonB is coming", bot correctly identifies UserA as speaker, not PersonB

    **Automatic Metric Updates:**
    The AI Handler analyzes user sentiment after each interaction and conservatively updates unlocked metrics:
    - Compliments/kindness: +1 rapport
    - Personal sharing/vulnerability: +1 trust
    - Insults/rudeness: +1 anger, -1 rapport
    - Professional context: Adjusts formality based on situation
    - Power dynamics: Adjusts fear, respect, intimidation
    - Emotional bonding: Adjusts affection, familiarity
        
-   **Global State Schema:** A simple key-value table to store global bot states, such as the "Daily Mood."
    
    -   `state_key`: (e.g., "daily_mood_anger").
        
    -   `state_value`: The current integer value for that mood.
        
-   **Short-Term Message Log:** A table containing the full log of up to 500 messages **server-wide across all channels**. **ARCHITECTURE CHANGE (2025-10-12)**: Messages are NOT filtered by channel - this allows the bot to maintain conversational context across all channels within a server. This serves as the high-resolution, rolling buffer for the Core Interaction Handler.

-   **Message Archive:** Archived messages are stored as JSON files in `database/{ServerName}/archive/short_term_archive_YYYYMMDD_HHMMSS.json` after memory consolidation. These files contain the full message history with metadata (`archived_at`, `message_count`, and complete `messages` array). This serves as the bot's complete historical record per server.
    

### 3.3. Proactive Engagement Subsystem

**STATUS: IMPLEMENTED ✅ (2025-10-16 - AI-Judged Relevance with Multi-Level Control)**

This component allows the bot to proactively join conversations based on AI-judged relevance, with fine-grained control at global, per-server, and per-channel levels.

-   **Scheduled Event:** A background task runs every N minutes (configurable via `check_interval_minutes`, default: 30)

-   **AI-Based Activation:** Instead of probabilistic (random chance), the system uses OpenAI to analyze conversation relevance:
    - Fetches last 20 messages from each active channel
    - AI scores conversation interest on a 0.0-1.0 scale
    - If score ≥ configurable threshold (default: 0.7), bot engages
    - Higher threshold = more selective engagement

-   **Self-Reply Prevention:** If the last message in a channel was from the bot, engagement is automatically skipped to prevent spam.

-   **Multi-Level Control:**
    -   **Global Toggle:** `proactive_engagement.enabled` in config.json (default: true)
    -   **Per-Server Toggle:** `server_proactive_settings` in config.json (per-server override)
    -   **Per-Channel Toggle:** `allow_proactive_engagement` flag in `channel_settings` database table (default: true)
    -   All three levels must be enabled for proactive engagement to occur in a channel

-   **Cooldown System:** 30-minute cooldown per channel after successful engagement to prevent over-participation

-   **Neutral Context:** Bot uses `generate_proactive_response()` method that does NOT load any specific user's relationship metrics or memories, preventing user confusion

-   **Use Cases:**
    - Join conversations about questions it could answer
    - Participate in topics related to its personality/interests
    - Contribute to creative or fun discussions
    - Avoid casual greetings, concluded conversations, and private discussions

-   **Configuration:** `config.json` under `proactive_engagement` section
    - `enabled`: boolean
    - `check_interval_minutes`: int (how often to scan channels)
    - `engagement_threshold`: float 0.0-1.0 (selectivity level)

-   **Per-Channel Disable:** Admins can disable proactive engagement in specific channels (e.g., rules, announcements, formal support) via GUI or Discord commands
        

### 3.4. Automated Memory Consolidation Process

**STATUS: IMPLEMENTED ✅ (Per-Server Architecture with Smart Contradiction Detection)**

An AI-powered background process that converts short-term message data into long-term structured memory **per server**.

1.  The process ingests up to 500 messages from the **Short-Term Message Log** for a specific server.

2.  For each user, GPT-4o analyzes their messages and extracts new summarized facts based on their activity.

3.  **Smart Contradiction Detection (2025-10-13)**: Before adding each extracted fact:
    - System uses semantic similarity search to find existing facts that might contradict the new one
    - AI compares the new fact against existing similar facts
    - If a contradiction is detected, the old fact is **updated** with the new information
    - If no contradiction exists, the fact is added as new
    - This prevents duplicate or conflicting information in long-term memory

4.  Extracted facts are added to (or updated in) the server's **Long-Term Memory** table with source attribution.

5.  **Archive & Reset:** After processing, the system:
    - Archives all short-term messages to `database/{ServerName}/archive/short_term_archive_YYYYMMDD_HHMMSS.json`
    - Clears the Short-Term Message Log for that server
    - SQLite auto-vacuum reclaims disk space

6.  **Triggering Mechanisms:**
    - **Automatic**: When a server reaches 500 messages in short-term memory
    - **Manual**: Via `/consolidate_memory` slash command (admin only, per-server)

7.  **Per-Server Independence**: Each server's consolidation runs independently without affecting other servers.
    

### 3.5. Dynamic Status Subsystem

**STATUS: IMPLEMENTED ✅ (2025-10-16 - AI-Generated Discord Presence with Duplicate Prevention)**

An automated process that daily updates the bot's Discord presence (status) to reflect its "thoughts" based on its personality.

-   **Scheduled Event:** A background task runs once per day at a configurable time (default: 12:00 / noon)
    - Task starts automatically when bot launches
    - **Memory Consolidation Trigger:** Automatically triggers memory consolidation for ALL servers 5 minutes after status update

-   **Status Generation:**

    1.  System selects a source server for personality context:
        - Configurable via `source_server_name` in config.json
        - Default: "Most Active Server" (server with most messages)
        - Server selector has **autocomplete** in Discord slash commands

    2.  The system queries the selected server's database to retrieve the bot's core identity (`traits`, `lore`, `facts`)

    3.  Context is passed to OpenAI with a specific prompt to generate a short (max 50 characters), funny/quirky status that fits the bot's personality

    4.  AI generates a flavorful status text (e.g., "Plotting surgery", "Avoiding patients", "Napping in the ER")

-   **Duplicate Prevention:**
    - Tracks last 100 statuses in `status_history.json`
    - Ensures always-unique status messages
    - Emote/emoji automatically stripped (Discord limitation)

-   **Memory Integration:**
    - Per-server toggle: Add status to each server's short-term memory (default: enabled)
    - When enabled, bot can reference its status in conversations ("Why is my status about this? Well...")
    - Configurable via `/server_set_status_memory` or GUI

-   **Manual Refresh:**
    - `/status_refresh` command for instant status regeneration (admin only)
    - "Refresh Now" button in GUI

-   **Configuration:** `config.json` under `status_updates` and `server_status_settings` sections
    - `enabled`: boolean
    - `update_time`: string in "HH:MM" 24-hour format
    - `source_server_name`: string (which server's personality to use)

-   **File Structure:**
    - Implementation: `modules/status_updater.py`
    - Background task: `cogs/status_tasks.py`
    - Admin command: `cogs/admin.py:status_refresh`
    

### 3.6. Ancillary Functionality Modules

Standard bot features will be implemented as separate, modular components.

-   **Slash Command Interface:** Full support for modern Discord slash commands.
    
-   **Moderation Module:** Commands for server administration (kick, ban, mute).
    
-   **Utility Module:** Tools such as polls, user info, and server stats.
    

### 3.7. Real-Time Administration Interface

**STATUS: COMPLETED ✅ (Per-Server Architecture)**

A set of secure, admin-only slash commands for live management of each server's database.

-   **Per-Server Scope:** All admin commands operate on the server where they're executed. Each server has independent bot identity, user relationships, and memories.

-   **Functionality:** Provides commands to create, read, update, and delete records for the Bot's Identity, User Memories, Relationship Metrics, Global State, and Personality Mode settings.

-   **Guild Validation:** Commands validate guild context and reject DM usage.

-   **Instantaneous Effect:** Due to the system's Real-Time Data Reliance directive, any changes made via this interface will be reflected in the bot's very next interaction in that server.

### 3.8. Personality Mode System

**STATUS: COMPLETED ✅**

A configurable system that controls how the bot presents itself and uses language in responses.

-   **Three Core Settings:**
    -   **Immersive Character Mode** (`immersive_character`): When enabled (default: true), the bot genuinely believes it IS the character defined in its identity, not an AI roleplaying. It will deny being an AI if asked and treat its lore as real experiences.
    -   **Allow Technical Language** (`allow_technical_language`): When disabled (default: false), the bot is forbidden from using robotic/technical terms like "cached", "stored", "database", "info", "data", "system" in its responses.
    -   **Use Server Information** (`use_server_info`): When enabled (default: false), the bot loads text files from `Server_Info/{ServerName}/` directory (per-server isolation) containing server rules, policies, and formal documentation. Ideal for formal channels like rules, moderation, or support.

-   **Configuration Hierarchy:**
    1.  **Global Defaults**: Set in `config.json` under `personality_mode` section
    2.  **Per-Channel Overrides**: Channels can override global settings via GUI or `/channel_set_personality` command
    3.  **Real-Time Updates**: Changes take effect immediately in the next interaction

-   **Natural Language Enforcement:**
    -   All intent prompts (memory_storage, factual_question, memory_correction, casual_chat) include conditional rules based on personality mode
    -   When technical language is disabled, responses use natural alternatives:
        -   "I don't have that info cached" → "idk" / "no clue" / "not sure"
        -   "Got it. That's stored now." → "oh nice" / "cool" / "interesting"
    -   Bot responds naturally like a real person in ALL interaction types

-   **Server Information System (NEW 2025-10-12):**
    -   **Purpose**: Provide authoritative server documentation for formal channels
    -   **Implementation**: `_load_server_info()` method in `ai_handler.py` loads all `.txt` files from `Server_Info/{ServerName}/` directory (per-server isolation)
    -   **Usage**: Enable per-channel via GUI or `/channel_set_personality use_server_info:true`
    -   **Priority**: Bot prioritizes server info over personality when answering questions
    -   **File Format**: UTF-8 encoded `.txt` files with descriptive names (e.g., `server_rules.txt`, `moderation_policy.txt`)
    -   **Security**: Files excluded from git by default to protect sensitive information

-   **Use Cases:**
    -   **Casual/Roleplay Channels**: `immersive_character=true`, `allow_technical_language=false`, `use_server_info=false` (maximum immersion)
    -   **Rules/Moderation Channels**: `immersive_character=false`, `allow_technical_language=true`, `use_server_info=true` (formal, authoritative)
    -   **General Chat**: Use global defaults or customize per community preferences

-   **Management Interfaces:**
    -   **GUI**: Per-channel editor dialog with hover tooltips explaining each option (implemented via `ToolTip` class)
    -   **Discord Command**: `/channel_set_personality` for live channel-specific configuration
    -   **config.json**: Manual editing for headless deployments
    -   **GUI Enhancement (2025-10-12)**: Personality mode settings removed from global settings, now ONLY in per-channel editor with tooltips
    

This document will serve as the guiding document for the bot's development.

## 4. Project File Structure & Component Mapping

This section maps the conceptual components defined above to the final, physical file structure of the project. This is the definitive guide for the repository's organization.

**⚠️ IMPORTANT**: When adding new files or directories to the project, this file structure MUST be updated to reflect those changes. The file structure should always represent the current state of the project.

```
/
├── 📂 cogs/
│   ├── 📄 __init__.py
│   ├── 📄 admin.py              # Admin commands (/identity_*, /user_*, /image_*, /get_logs, etc.)
│   ├── 📄 events.py             # Message handling and AI response triggering
│   ├── 📄 memory_tasks.py       # Memory consolidation background tasks (commented out)
│   ├── 📄 moderation.py         # Moderation commands
│   ├── 📄 proactive_tasks.py    # Proactive engagement background tasks (NEW 2025-10-16)
│   ├── 📄 settings.py           # Settings management commands
│   ├── 📄 status_tasks.py       # Daily status update background tasks (NEW 2025-10-16)
│   └── 📄 utility.py            # Utility commands
|
├── 📂 database/
│   ├── 📂 {ServerName}/         # Per-server database folders (e.g., "My Server/")
│   │   ├── 📂 archive/          # Per-server message archives
│   │   │   └── 📄 short_term_archive_*.json
│   │   └── 📄 {guild_id}_data.db   # SQLite database (e.g., "1234567890_data.db")
│   ├── 📄 __init__.py
│   ├── 📄 db_manager.py          # Individual database operations (accepts custom db_path)
│   ├── 📄 input_validator.py     # SQL injection protection (NEW 2025-10-17)
│   ├── 📄 multi_db_manager.py    # Central manager for all server databases
│   └── 📄 schemas.py             # Table definitions
|
├── 📂 Server_Info/
│   ├── 📂 {ServerName}/          # Per-server rules/policies folders (e.g., "My Server/")
│   │   └── 📄 *.txt              # Server rules, policies, documentation
│   └── 📄 README.md              # Usage instructions for Server_Info system
|
├── 📂 logs/
│   └── 📄 bot_YYYYMMDD.log       # Daily rotating log files
|
├── 📂 modules/
│   ├── 📄 __init__.py
│   ├── 📄 ai_handler.py          # OpenAI API interface, intent classification, response generation
│   ├── 📄 config_manager.py      # config.json and .env loading
│   ├── 📄 emote_orchestrator.py  # Custom emote management
│   ├── 📄 formatting_handler.py  # Roleplay action detection and italic formatting (NEW 2025-10-15)
│   ├── 📄 image_generator.py     # Together.ai API for AI image generation (NEW 2025-10-15)
│   ├── 📄 logging_manager.py     # Structured logging
│   ├── 📄 proactive_engagement.py # AI-powered conversation analysis (NEW 2025-10-16)
│   └── 📄 status_updater.py      # AI-generated Discord status updates (NEW 2025-10-16)
|
├── 📂 Notes/
│   └── 📄 New ideas.txt          # Development notes
|
├── 📂 scripts/
│   └── 📄 populate_bot_identity.py  # Bot personality initialization script
|
├── 📂 tests/
│   ├── 📄 __init__.py
│   └── 📄 (Unit tests for modules and cogs)
|
├── 📜 testing.py                 # Comprehensive test suite (206 tests across 23 categories)
├── 📜 .env                       # Secrets (DISCORD_TOKEN, OPENAI_API_KEY, TOGETHER_API_KEY)
├── 📜 .gitignore
├── 📜 AI_GUIDELINES.md           # Development standards and code review guidelines
├── 📜 CLAUDE.md                  # AI assistant guide for future development
├── 📜 config.json                # Global bot configuration
├── 📜 debug.log
├── 📜 gui.py                     # Graphical configuration interface
├── 📜 main.py                    # Bot initialization and entry point
├── 📜 PLANNED_FEATURES.md        # Future development roadmap
├── 📜 README.md                  # User guide and setup instructions
├── 📜 requirements.txt           # Python dependencies
├── 📜 status_history.json        # Last 100 status messages (duplicate prevention)
├── 📜 SYSTEM_ARCHITECTURE.md     # Complete technical specification (this file)
├── 📜 TROUBLESHOOTING.md         # Common issues and solutions
└── 📜 test_file.txt
```

### 4.1. `cogs/` Directory

Houses Discord-facing logic, including commands and event listeners.

-   `__init__.py`: Marks the directory as a Python package, allowing cogs to be imported correctly.
    
-   `admin.py`: Implements the **Real-Time Administration Interface (3.7)**.
    
-   `events.py`: Implements the **Core Interaction Handler (3.1)**. Contains the primary `on_message` event listener and the global `on_command_error` listener for centralized error handling.
    
-   `memory_tasks.py`: Implements the **Proactive Engagement Subsystem (3.3)**, the **Automated Memory Consolidation Process (3.4)**, and the **Dynamic Status Subsystem (3.5)** using `tasks.loop`.
    
-   `moderation.py`: Implements the **Moderation Module (3.6)**.
    
-   `settings.py`: Contains bot-level settings commands, like activating or deactivating the bot.
    
-   `utility.py`: Implements the **Utility Module (3.6)** for features like polls, user info, and the support ticket system.
    

### 4.2. `database/` Directory

The central component for all data persistence logic with per-server database isolation.

-   `__init__.py`: Marks the directory as a Python package, enabling imports of the manager and schemas.

-   `archive/`: Directory containing JSON archives of consolidated short-term messages (per-server).

-   `{ServerName}_data.db`: Server-specific SQLite database files (automatically created on first `/activate` command per server).

-   `db_manager.py`: Individual database interface class. Contains all functions for data manipulation (e.g., `get_long_term_memory`, `add_long_term_memory`, `get_global_state`, `set_global_state`, `get_bot_identity`, `get_relationship_metrics`, `update_relationship_metrics`). Now accepts optional `db_path` parameter for custom database locations. **ARCHITECTURE CHANGE (2025-10-12)**: `get_short_term_memory()` now returns server-wide messages, NOT filtered by channel. **NEW METHODS (2025-10-13)**: `find_contradictory_memory()` for semantic similarity search, `update_long_term_memory_fact()` for updating existing facts, `delete_long_term_memory()` for removing facts.

-   `multi_db_manager.py`: Central manager for all server databases. Handles server name sanitization, database creation, and caching of DBManager instances per guild. Provides `get_or_create_db(guild_id, server_name)` method.

-   `schemas.py`: Defines the database table structures (e.g., via ORM classes or SQL statements) as described in section 3.2.

### 4.2.1. `Server_Info/{ServerName}/` Directories

**NEW (2025-10-12, Updated 2025-10-15)**: Contains per-server text files with server rules, policies, and formal documentation that the bot can reference.

-   **Structure**: `Server_Info/{ServerName}/` - One folder per Discord server (sanitized server name)
    -   Example: `Server_Info/My Gaming Server/rules.txt`
    -   Example: `Server_Info/Tech Support Server/faq.txt`

-   **Per-Server Isolation**: Each server has its own folder to prevent cross-contamination of server rules and policies

-   `*.txt`: UTF-8 encoded text files with descriptive names (e.g., `server_rules.txt`, `moderation_policy.txt`, `faq.txt`). All `.txt` files in the server's folder are loaded when `use_server_info` is enabled for a channel in that server.

-   **Purpose**: Provide authoritative server documentation for formal channels (rules, moderation, support).

-   **Security**: All `.txt` files are excluded from git by default to protect sensitive information.

-   **README.md**: Usage instructions for the Server_Info system (located in `Server_Info/` root)

### 4.2.2. `logs/` Directory

Contains daily rotating log files for debugging and monitoring.

-   `bot_YYYYMMDD.log`: Daily log files with timestamps, log levels, and detailed information about bot operations.

### 4.2.3. `scripts/` Directory

Contains utility scripts for database management and initialization.

-   `populate_bot_identity.py`: Script that automatically populates the bot's initial personality (traits, lore, facts) on first run. Can also be run manually to reset the bot's identity.
    

### 4.3. `modules/` Directory

Contains core helper classes not directly tied to Discord's API.

-   `__init__.py`: Marks the directory as a Python package so these helper modules can be imported.

-   `ai_handler.py`: Interfaces with the OpenAI API, taking context from other components and returning raw text. Implements the Intent Classification System with improved distinction between memory_recall and factual_question (2025-10-12). `_load_server_info()` method loads formal server documentation from text files when enabled per-channel. Conversation energy matching (2025-10-19) adjusts response length to match user's message energy.

-   `config_manager.py`: Manages the loading of `config.json` and `.env` files.

-   `emote_orchestrator.py`: Manages the loading and replacement of custom server emotes. Includes randomized emote sampling (2025-10-19) for variety and boost-locked emote filtering.

-   `formatting_handler.py`: **NEW (2025-10-15)** - Detects and formats physical actions using regex patterns. Recognizes 50+ action verbs across 8 categories (movement, gestures, facial expressions, etc.). Only formats short sentences (<15 words) starting with action verbs.

-   `image_generator.py`: **NEW (2025-10-15, Updated 2025-10-27)** - Together.ai API integration for AI image generation using FLUX.1-schnell model. Multi-character scene detection (2025-10-27) and bot self-portrait detection via reflexive pronouns. Smart context handling prevents identity contamination between database users and generic knowledge.

-   `logging_manager.py`: A dedicated module to handle structured logging for debugging and monitoring.

-   `proactive_engagement.py`: **NEW (2025-10-16)** - AI-powered conversation analysis for proactive engagement. Scores conversation relevance (0.0-1.0) and determines when bot should join discussions. Implements cooldown system and multi-level control (global, per-server, per-channel).

-   `status_updater.py`: **NEW (2025-10-16)** - AI-generated Discord status updates. Creates daily status messages based on bot personality, with duplicate prevention (tracks last 100 statuses). Supports per-server personality selection and memory integration.
    

### 4.4. `tests/` Directory

A dedicated folder for housing unit tests and integration tests.

-   `__init__.py`: Marks the directory as a Python package, which is often required by testing frameworks.
    
-   Contains test files for the various components of the bot to ensure stability and reliability.
    

### 4.5. Root Directory Files

-   `.env`: Stores sensitive credentials (Discord token, OpenAI API key).
    
-   `.gitignore`: Specifies files/directories to be ignored by Git (e.g., `.env`, `__pycache__/`, `Notes/`, `database/bot_data.db`).
    
-   `AI_GUIDELINES.md`: Comprehensive guidelines for AI assistants working on this project. Includes code review standards, architecture alignment requirements, and documentation update procedures.
    
-   `config.json`: Stores non-sensitive, user-configurable settings including channel-specific formality settings and bot personality defaults.
    
-   `debug.log`: General purpose debug log file for troubleshooting.
    
-   `gui.py`: The optional graphical user interface for configuration and startup. **NEW (2025-10-12)**: Includes `ToolTip` class for hover text on checkboxes, personality mode settings moved to per-channel editor only (removed from global settings), and "Use Server Information" checkbox with tooltips.

-   `main.py`: The primary entry point for the application, responsible for initializing managers and loading cogs.
    
-   `PLANNED_FEATURES.md`: Comprehensive roadmap of all planned features organized by development phase (Phase 2, 3, 4, etc.). Contains implementation details, technical requirements, and status tracking. **AI assistants must consult this file before implementing new features.**
    
-   `README.md`: The user-facing guide for quick start, setup, features overview, and basic usage.
    
-   `requirements.txt`: Lists all Python package dependencies.
    
-   `SYSTEM_ARCHITECTURE.md`: This document - the technical specification and architectural blueprint for the entire system.
    
-   `TROUBLESHOOTING.md`: Comprehensive troubleshooting guide with solutions to common issues, database problems, performance optimization, and debugging steps.
    
-   `test_file.txt`: Temporary test file (can be safely deleted).

-   `testing.py`: Comprehensive test suite for validating bot functionality across **206 tests in 23 categories**. Accessible via `/run_tests` admin command. Tests database operations, AI integration, per-server isolation, input validation, security measures, image generation, proactive engagement, status updates, admin logging, and all core systems. Results sent via Discord DM and saved to `logs/test_results_*.json`.

## 5. Implementation Status

### Phase 1: COMPLETED ✅
**Bot Identity & Relationship Metrics System**

Phase 1 has been fully implemented and is production-ready.

#### Implemented Features:
- ✅ **Bot Identity Database System**: Bot's personality (traits, lore, facts) stored in and retrieved from database
- ✅ **Automatic Identity Population**: First-run script auto-populates a basic default personality (fully customizable)
- ✅ **Relationship Metrics**: Per-user tracking of 9 metrics (rapport, trust, anger, formality, fear, respect, affection, familiarity, intimidation) with individual lock toggles
- ✅ **Emotional Context Blending**: Bot adjusts responses based on both emotional topics and user relationships
- ✅ **Channel Formality System**: Channel-level formality settings with optional user-level overrides
- ✅ **Automatic Metric Updates**: AI analyzes sentiment and updates relationship metrics after interactions
- ✅ **Real-Time Administration Interface**: Full CRUD commands for bot identity, user metrics, and memories
- ✅ **Global Mood System**: Database storage for bot's daily mood states

#### Admin Commands Available:
- Bot Identity: `/identity_add_trait`, `/identity_add_lore`, `/identity_add_fact`, `/identity_view`
- User Relationships: `/user_view_metrics`, `/user_set_metrics` (all 9 metrics), `/user_view_memory`, `/user_add_memory`
- User Metric Locking (NEW 2025-11-23): `/user_lock_metrics`, `/user_unlock_metrics` (lock/unlock individual metrics)
- Global Mood: `/mood_set`, `/mood_get`
- Personality Mode: `/channel_set_personality` (configure immersive character, technical language, and server info settings)
- Server Settings (2025-10-16): `/server_add_nickname`, `/server_remove_nickname`, `/server_list_nicknames`, `/server_set_status_memory`
- VPS Configuration (NEW 2025-11-23): 22 commands total for headless deployment (see Phase 4 below)
- Testing: `/run_tests` (comprehensive system validation with 207 tests as of 2025-10-27)

### Core System Components: COMPLETED ✅
- ✅ Core Interaction Handler with Intent Classification (improved memory_recall vs factual_question, 2025-10-12)
- ✅ Database Schema (all tables defined and in use)
- ✅ Short-Term Message Logging (500 messages server-wide, not channel-filtered, 2025-10-12)
- ✅ Long-Term Memory Storage & Retrieval
- ✅ Global State Management
- ✅ Emote Integration System
- ✅ Channel-Specific Configuration
- ✅ Structured Logging System with Daily Rotation
- ✅ **Personality Mode System**: Immersive character mode with natural language enforcement
- ✅ **Formal Server Information System**: Load text files for rules/policies (2025-10-12)
- ✅ **GUI Tooltip System**: Hover text for personality mode checkboxes (2025-10-12)
- ✅ **Comprehensive Testing System**: 206-test suite via `/run_tests` command (2025-10-13, expanded through 2025-10-27)

### Phase 2: COMPLETED ✅
**Memory Consolidation & Per-Server Architecture**
- ✅ **Per-Server Database Isolation**: Separate database file per Discord server
- ✅ **Automated Memory Consolidation Process**: AI-powered fact extraction (GPT-4o)
- ✅ **Smart Contradiction Detection**: Semantic similarity search and AI-powered duplicate prevention (2025-10-13)
- ✅ **Memory Correction System**: Natural language memory updates via intent classification (2025-10-13)
- ✅ **Message Archival System**: JSON backup before deletion
- ✅ **Auto-trigger at 500 messages**: Per-server consolidation threshold
- ✅ **Manual Consolidation Command**: `/consolidate_memory` (admin, per-server)
- ✅ **Database Optimization**: SQLite auto-vacuum enabled
- ✅ **Server-Wide Short-Term Memory**: Context maintained across all channels (2025-10-12)
- ✅ **Formal Server Information System**: Load text files for rules/policies in formal channels (2025-10-12)
- ✅ **Improved Intent Classification**: Better distinction between memory_recall and factual_question (2025-10-12)
- ✅ **GUI Enhancements**: Tooltips for personality settings, server info checkbox (2025-10-12)
- ✅ **Bot Self-Lore Extraction**: Automated extraction of relevant lore for emotional context (2025-10-13)

### Testing Infrastructure: COMPLETED ✅ (2025-10-13)
**Comprehensive 64-Test Suite**

A production-ready testing system accessible via `/run_tests` admin command that validates all bot systems:

**Test Categories (17 total)**:
1. **Database Connection** (3 tests) - Manager initialization, file existence, query execution
2. **Database Tables** (6 tests) - All required tables exist and accessible
3. **Bot Identity** (2 tests) - Personality storage and retrieval
4. **Relationship Metrics** (3 tests) - User metrics CRUD operations
5. **Long-Term Memory** (4 tests) - Memory storage, contradiction detection, updates
6. **Short-Term Memory** (3 tests) - Message logging and retrieval
7. **Memory Consolidation** (2 tests) - Archive system and consolidation functions
8. **AI Integration** (3 tests) - AI handler, API keys, model configuration
9. **Config Manager** (3 tests) - Configuration loading and validation
10. **Emote System** (2 tests) - Emote handler and emote loading
11. **Per-Server Isolation** (4 tests) - Database isolation, multi-DB manager, auto-vacuum
12. **Input Validation** (4 tests) - SQL injection prevention, oversized content, empty/null inputs
13. **Global State** (3 tests) - Global state CRUD operations
14. **User Management** (3 tests) - User creation, timestamps, cleanup
15. **Archive System** (4 tests) - Archive directory, functions, message count, JSON format
16. **Image Rate Limiting** (4 tests) - Rate limit tracking table, increment/get methods
17. **Channel Configuration** (3 tests) - Channel settings, personality mode, server info
18. **Cleanup Verification** (5 tests) - Automatic test data cleanup across all tables

**Features**:
- Automatic test data cleanup after each run
- Results sent via Discord DM to admin
- Detailed JSON logs saved to `logs/test_results_*.json`
- Per-server database testing
- Pass/fail status with detailed error messages
- Validates security (SQL injection prevention)
- Tests all Phase 1 & 2 features

**Usage**: `/run_tests` (admin only, per-server)

### Phase 3: COMPLETED ✅
**Advanced Relationship Dynamics & Proactive Features**
- ✅ **Expanded Relationship Metrics (2025-10-16)**: Five new metrics for deeper bot-user relationships
  - Fear (0-10), Respect (0-10), Affection (0-10), Familiarity (0-10), Intimidation (0-10)
  - Total of 9 metrics per user for nuanced interaction dynamics
  - Individual lock toggles for each metric to prevent unwanted automatic updates
  - GUI and Discord command support for viewing and editing all metrics
  - Database migration automatically adds new columns with sensible defaults
- ✅ **Proactive Engagement Subsystem (2025-10-16)**: Bot randomly joins conversations based on AI-judged relevance
  - AI analyzes last 10 messages and scores conversation interest (0.0-1.0 scale)
  - Engagement threshold controls selectivity (default: 0.7, higher = more selective)
  - 30-minute check interval and per-channel cooldowns prevent spam
  - Self-reply prevention to avoid infinite loops
  - Multi-level control: Global → per-server → per-channel toggles
  - Per-channel disable option for serious channels (rules, announcements)
  - GUI controls for threshold, check interval, and per-channel settings
- ✅ **Dynamic Status Updates (2025-10-16)**: AI-generated Discord status reflecting bot's thoughts/mood
  - Daily updates at configurable time (default: 12:00)
  - AI generation based on bot's personality/lore from selected server
  - Source server selection (default: "Most Active Server")
  - Per-server toggle for adding status to short-term memory
  - GUI controls for enable/disable, time scheduling, and server selection
  - Allows bot to reference its status in conversations
- ✅ **GUI-Discord Command Parity (2025-10-16)**: Server settings manageable via both GUI and Discord
  - Alternative nicknames: `/server_add_nickname`, `/server_remove_nickname`, `/server_list_nicknames`
  - Status memory toggle: `/server_set_status_memory`
  - Note: Emote sources remain GUI-only due to complexity of multi-select interface

### Phase 4: COMPLETED ✅ (2025-11-23)
**VPS Headless Deployment - Full Discord Command Parity**

All GUI settings now have Discord command equivalents for complete headless VPS management. Total of **22 new admin commands** implemented in `cogs/admin.py` (lines 1891-2763).

**Global Bot Configuration (6 commands)**:
- `/config_set_reply_chance` - Set global random reply chance (0.0-1.0)
- `/config_set_personality` - Update default personality traits/lore for new servers
- `/config_add_global_nickname` - Add global alternative nicknames
- `/config_remove_global_nickname` - Remove global nicknames
- `/config_list_global_nicknames` - List all global nicknames
- `/config_view_all` - View all global configuration settings

**Image Generation Configuration (3 commands)**:
- `/image_config_enable` - Enable/disable image generation globally
- `/image_config_set_limits` - Configure rate limits (max per period: 1-50, reset hours: 1-168)
- `/image_config_view` - View current image generation settings

**Status Update Configuration (4 commands)**:
- `/status_config_enable` - Enable/disable daily status updates
- `/status_config_set_time` - Set update time (24h format with validation: HH:MM)
- `/status_config_set_source_server` - Choose which server's personality to use
- `/status_config_view` - View current status configuration

**Per-Channel Configuration (5 commands)**:
- `/channel_set_purpose` - Set channel purpose/instructions
- `/channel_set_reply_chance` - Set per-channel random reply chance (0.0-1.0)
- `/channel_set_proactive` - Configure proactive engagement (enable/disable)
- `/channel_view_settings` - View all channel settings
- `/channel_list_active` - List all active channels in server

**Per-Server Configuration (2 commands)**:
- `/server_set_emote_sources` - Manage emote sources (list/add/remove/clear actions)
- `/server_view_settings` - View all server-specific settings

**User Metric Locking (2 commands - NEW, not in original spec)**:
- `/user_lock_metrics` - Lock specific relationship metrics to prevent automatic sentiment-based updates
  - Parameters: user (mention or ID), rapport, trust, anger, formality, fear, respect, affection, familiarity, intimidation (all boolean)
  - Example: `/user_lock_metrics user:@UserName rapport:True affection:True`
  - Use case: Manually control specific metrics while allowing others to update automatically
- `/user_unlock_metrics` - Unlock specific relationship metrics to allow automatic updates
  - Same parameters as `/user_lock_metrics`
  - Example: `/user_unlock_metrics user:123456789 rapport:True`

**Implementation Details**:
- All commands are administrator-only (`@app_commands.default_permissions(administrator=True)`)
- Guild context validation (rejects DM usage)
- ConfigManager integration for config.json modifications
- Database operations for per-channel/per-server settings
- Clear success/error feedback with emoji indicators (✅ ❌ ℹ️)
- Parameter validation using `app_commands.Range` for numeric inputs
- Changes take effect immediately without bot restart

**Benefits**:
- ✅ Bot fully manageable from Discord without GUI access
- ✅ Perfect for headless VPS deployment
- ✅ Remote configuration via SSH + Discord (no X11 forwarding needed)
- ✅ All settings accessible via commands with same functionality as GUI
- ✅ Administrators can manage bot entirely through Discord interface

**Hierarchical Server_Info Folder System - PROPOSED**:
Remains as a future enhancement for selective context loading in fandom/roleplay servers. See `PLANNED_FEATURES.md` for details.

### Phase 5: COMPLETED ✅ (2025-10-27)
**Intelligent Conversation Features & Energy Management**

All three Phase 5 features fully implemented and integrated into the bot.

**1. Intelligent Conversation Continuation Detection** ✅
- **Purpose**: Bot detects when users are talking to it without explicit @mentions
- **Implementation**: `modules/conversation_detector.py` integrated in `cogs/events.py` (lines 228-240)
- **AI Model**: GPT-4.1-mini for classification (configurable via `conversation_detection.model`)
- **Discord Commands (NEW 2025-11-23)**:
  - `/channel_conversation_enable` - Configure per-channel (enabled, threshold, context_window)
  - `/channel_conversation_view` - View per-channel settings
- **How It Works**:
  1. Optimization check: Only runs if bot was recently active in last N messages
  2. Fetches last 10 messages for context analysis
  3. AI scores message on 0.0-1.0 scale (how likely it's directed at bot)
  4. Responds if score ≥ threshold (default: 0.7)
- **Configuration** (`config.json` or Discord commands):
  ```json
  "conversation_detection": {
    "enabled": false,  // Currently disabled by default
    "default_threshold": 0.7,
    "context_window": 10,
    "model": "gpt-4.1-mini",
    "max_tokens": 10,
    "temperature": 0.0
  }
  ```
- **Cost**: ~$0.015 per 1,000 messages (GPT-4.1-mini)
- **Use Cases**: Natural conversation flow without repeated @mentions
- **Example**:
  ```
  User: @Bot, what's your favorite color?
  Bot: I love blue!
  User: why blue?  ← Bot responds without mention
  Bot: Because it reminds me of the ocean.
  ```

**2. Iterative Image Refinement** ✅
- **Purpose**: Users can refine images naturally without re-typing full prompts
- **Implementation**: `modules/image_refiner.py` integrated in `modules/image_generator.py` (lines 57-60)
- **AI Model**: GPT-4.1-mini for detection, GPT-4o for prompt modification
- **How It Works**:
  1. Caches last generated image prompt for 10 minutes (configurable)
  2. AI detects refinement requests ("add fire", "make it bigger", "change color")
  3. GPT-4o intelligently modifies original prompt based on feedback
  4. Generates refined image using modified prompt
  5. Refinements don't count toward rate limit (configurable)
- **Configuration** (`config.json`):
  ```json
  "image_refinement": {
    "enabled": true,
    "detection_threshold": 0.7,
    "cache_duration_minutes": 10,
    "allow_refinement_after_rate_limit": true,
    "max_refinements_per_image": 3,
    "detection_model": "gpt-4.1-mini",
    "modification_model": "gpt-4o"
  }
  ```
- **Example**:
  ```
  User: draw a cool cat with flaming fur
  Bot: [generates image of cat with normal fur]
  User: add fire to the fur  ← Refinement detected
  Bot: [generates new image with flaming fur, doesn't count toward limit]
  ```

**3. Conversation Energy Priority Override** ✅
- **Purpose**: Energy constraints override relationship metrics to prevent over-talking
- **Implementation**: `modules/ai_handler.py:_build_relationship_context()` (lines 385-420)
- **Problem Solved**: High affection/rapport previously caused verbose responses even when user sent short messages
- **How It Works**:
  1. Analyzes last 5 user messages from last 30 messages
  2. Calculates average message length
  3. Determines energy level (VERY LOW/LOW/MEDIUM/HIGH)
  4. Energy override is **FIRST PRIORITY** in relationship prompt (before all other metrics)
  5. Strict token limits enforced:
     - VERY LOW (1-3 words avg): max_tokens=25, forces 1-5 word responses
     - LOW (4-8 words avg): max_tokens=40, brief responses under 10 words
     - MEDIUM (9-20 words avg): max_tokens=60, natural 1-2 sentences
     - HIGH (20+ words avg): max_tokens=80, full responses
- **Prompt Structure**:
  ```
  🚨 CRITICAL PRIORITY OVERRIDE 🚨
  ⚡ CONVERSATION ENERGY IS VERY LOW ⚡
  This OVERRIDES ALL relationship metrics and personality traits.
  **ABSOLUTE REQUIREMENTS:**
  - Respond with 1-5 words MAXIMUM (strict limit)
  - Examples: "lol", "yeah", "fair enough", "nice"
  ```
- **Benefits**:
  - Bot matches user's conversation energy naturally
  - Prevents verbose responses to "lol", "ok", "yeah"
  - Works even with high affection/rapport/familiarity metrics
- **Example**:
  ```
  [User has high affection=9, familiarity=8]
  User: lol  ← Energy is VERY LOW
  Bot: haha  ← Brief response despite high metrics
  ```
