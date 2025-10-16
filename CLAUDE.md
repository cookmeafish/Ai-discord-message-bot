# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Bot Overview

This is an AI-powered Discord bot with persistent memory, dynamic personality, and relationship tracking. The bot uses OpenAI's API (GPT-4.1-mini) and SQLite for data persistence. The bot's personality is fully customizable per server.

## Development Commands

### Running the Bot
```bash
# Standard mode
python main.py

# GUI mode (for configuration)
python gui.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

### Database Management
The bot uses **per-server SQLite databases** with a human-readable folder structure. Each Discord server gets its own folder and database file.

**Database Structure**:
- Folder: `database/{ServerName}/` (human-readable server name)
- File: `{guild_id}_data.db` (Discord guild ID ensures uniqueness)
- Example: `database/Mistel Fiech's Server/1260857723193528360_data.db`

**Database Creation Flow**:
1. User runs `/activate` in a Discord server
2. Bot creates folder `database/{SanitizedServerName}/`
3. Bot creates database file `{guild_id}_data.db` in that folder
4. All tables are initialized via `database/schemas.py`
5. Bot's default personality is auto-populated for that server (can be customized)

**Multi-Database Architecture**:
- `database/multi_db_manager.py` - Central manager for all server databases
- `database/db_manager.py` - Individual database interface (accepts custom `db_path`)
- Access via `bot.get_server_db(guild_id, guild_name)` - Returns server-specific DBManager

To manually repopulate bot identity for a specific server:
```bash
# This will need to be adapted for per-server use
python scripts/populate_bot_identity.py
```

## Architecture & Key Design Principles

### 1. Real-Time Data Reliance
**CRITICAL**: The system queries the database at the moment of each interaction. Never cache personality, user memory, or relationship data. Changes to the database take effect immediately.

### 2. Dual-Layer Memory System (Per-Server)
- **Short-Term (500 messages)**: Full message transcripts in `short_term_message_log` table, **server-wide across all channels** (not filtered by channel)
- **Long-Term**: Summarized facts in `long_term_memory` table with source attribution
- **Archive**: After memory consolidation, short-term messages are archived to `database/{ServerName}/archive/short_term_archive_YYYYMMDD_HHMMSS.json` before deletion
- **Per-Server Independence**: Each server has its own memory systems with no cross-contamination (separate folders, databases, and archives)
- **Cross-Channel Context**: Bot maintains conversation context across all channels within a server, allowing it to reference information mentioned in any channel

### 3. Configuration via config.json
All configurable values MUST be stored in `config.json` and accessed through `ConfigManager`. Never hardcode:
- AI model names (`ai_models.primary_model`)
- API parameters (max_tokens, temperature)
- Response limits (message counts, context window sizes)
- Personality mode settings (`personality_mode.immersive_character`, `personality_mode.allow_technical_language`)
- Timing values

See `AI_GUIDELINES.md` Section 4 for details on centralized configuration requirements.

### 3.5. Personality Mode System
The bot has a configurable personality mode that controls immersion and language:
- **Immersive Character Mode** (`immersive_character`): When enabled (default: true), bot believes it IS the character, not an AI
- **Allow Technical Language** (`allow_technical_language`): When disabled (default: false), bot forbidden from using robotic terms like "cached", "stored", "database"
- **Use Server Information** (`use_server_info`): When enabled (default: false), bot loads text files from `Server_Info/{ServerName}/` directory for rules, policies, and formal documentation (per-server isolation)
- **Roleplay Formatting** (`enable_roleplay_formatting`): When enabled (default: true), bot formats physical actions in italics (e.g., *walks over*, *sighs deeply*). Only works when Immersive Character Mode is enabled.

**Configuration hierarchy:**
1. Global defaults in `config.json` under `personality_mode`
2. Per-channel overrides in `channel_settings`
3. Real-time updates via `/channel_set_personality` or GUI

**AI Handler Integration:**
- `_get_personality_mode(channel_config)` retrieves settings with fallback to global
- `_build_bot_identity_prompt(db_manager, channel_config)` includes conditional immersion instructions
- All intent prompts (memory_storage, factual_question, memory_correction, casual_chat) enforce natural language based on settings
- `_load_server_info(channel_config)` loads formal server documentation when `use_server_info` is enabled
- `_apply_roleplay_formatting(text, channel_config)` applies action formatting via `FormattingHandler` module

**Roleplay Formatting Implementation (2025-10-15)**:
- `modules/formatting_handler.py` - Detects and formats physical actions using regex patterns
- 50+ action verbs across 8 categories (movement, gestures, facial expressions, sounds, looking, physical contact, etc.)
- Only formats short sentences (<15 words) that start with action verbs
- Preserves existing formatting (doesn't re-format already italicized text)
- Conservative approach: won't format sentences starting with "I" or containing dialogue
- Applied to all AI responses (memory_storage, memory_correction, casual_chat, image responses)
- Configurable per-channel via GUI checkbox or config.json setting

### 4. Core Message Flow (Per-Server)
1. `cogs/events.py:on_message()` - Receives message
2. Guild validation and server-specific database retrieval via `bot.get_server_db(guild.id, guild.name)`
3. Message logged to server database via `db_manager.log_message()`
4. Intent classified via `ai_handler._classify_intent()` (6 categories: image_generation, memory_storage, memory_correction, factual_question, memory_recall, casual_chat)
   - **image_generation**: User requesting bot to draw/sketch/create an image ("draw me a cat", "can you sketch a house")
   - **memory_recall**: Personal questions about user or recent conversation ("what's my favorite food?", "do you remember what I said?")
   - **factual_question**: General knowledge questions ("what's the capital of France?")
   - Improved classification distinguishes between image generation, personal memory recall, and general factual queries
5. Response generated via `ai_handler.generate_response(message, short_term_memory, db_manager)` with:
   - Bot identity from server database (`_build_bot_identity_prompt(db_manager)`)
   - Relationship metrics (`_build_relationship_context(user_id, channel_config, db_manager)`)
   - Server information from text files (`_load_server_info(channel_config)`) if enabled
   - Up to 500 messages server-wide history (not filtered by channel)
6. Sentiment analysis updates relationship metrics automatically (`_analyze_sentiment_and_update_metrics(message, ai_response, user_id, db_manager)`)

**Alternative Nicknames (Per-Server, 2025-10-14)**:
- Bot responds to mentions, replies, Discord username, server nickname, AND alternative nicknames
- **Server-specific nicknames**: Each server can configure custom nicknames via GUI Server Manager
- Configured in `server_alternative_nicknames: {guild_id: [nickname1, nickname2]}`
- Falls back to global `alternative_nicknames` for backward compatibility
- Flexible matching: Ignores spaces, periods, special characters (e.g., "Dr. Fish" matches "drfish")
- Implemented in `_check_bot_name_mentioned()` with `_normalize_text()` helper

### 5. Database-Only Interface (Per-Server Architecture)
All database operations MUST go through `database/db_manager.py`. Never write raw SQL in cogs or modules.

**CRITICAL**: All cogs and modules that interact with the database must:
1. Accept `db_manager` as a parameter (don't access `bot.db_manager` globally)
2. Validate guild context before database operations
3. Use `bot.get_server_db(guild_id, guild_name)` to get the correct database instance

## Important File Locations

### Core Entry Points
- `main.py` - Bot initialization, loads cogs, auto-populates identity
- `cogs/events.py` - Message handling and AI response triggering
- `modules/ai_handler.py` - OpenAI API interface, intent classification, sentiment analysis
- `modules/formatting_handler.py` - Roleplay action detection and italic formatting (2025-10-15)

### Database Layer
- `database/multi_db_manager.py` - Central manager for all server databases
- `database/db_manager.py` - Individual database operations (accepts custom db_path)
- `database/schemas.py` - Table definitions
- `database/{ServerName}/{guild_id}_data.db` - Per-server SQLite databases (auto-created on /activate)
  - Example: `database/Mistel Fiech's Server/1260857723193528360_data.db`
- `database/{ServerName}/archive/` - JSON archives of consolidated messages (per-server isolation)
- `Server_Info/{ServerName}/` - Text files with server rules, policies, and formal documentation (per-server isolation)

### Configuration
- `config.json` - All configurable bot parameters (model names, limits, channel settings, per-server settings, image generation)
- `.env` - Secrets (DISCORD_TOKEN, OPENAI_API_KEY, TOGETHER_API_KEY)
- `gui.py` - Graphical configuration interface with Server Manager

### Image Generation Module (2025-10-15)
- `modules/image_generator.py` - Together.ai API integration for AI image generation
  - **Model**: FLUX.1-schnell (optimized for 4 steps, 512x512 resolution)
  - **Style**: Childlike crayon drawings ("kindergarten art style")
  - **Rate Limiting**: 5 images per user every 2 hours (configurable via `max_per_user_per_period` and `reset_period_hours`)
  - **Cost**: $0.002 per image (~$2 per 1,000 images)
  - **Intent**: `image_generation` - Natural language detection ("draw me a cat", "sketch a house")
  - **Config**: `config.json` under `image_generation` section
  - **GUI Integration**: Checkbox for enable/disable, field for period limit and reset hours

### GUI Server Manager (2025-10-14, Updated 2025-10-15)
The GUI provides a server-first interface for managing bot settings:
- **Main View**: Lists all active Discord servers (scans `database/{ServerName}/{guild_id}_data.db` files)
- **Server Settings Dialog**: Opened via "Edit Settings" button for each server
  - **Active Channels**: View and edit channels activated for that server
  - **Alternative Nicknames**: Server-specific nicknames the bot responds to
  - **Emote Sources**: Checkbox selection of which servers provide emotes
- **Database Scanning**: Supports new structure `{ServerName}/{guild_id}_data.db` and legacy formats for backward compatibility
- **Auto-refresh**: GUI refreshes server list when config.json changes
- **User-Friendly**: Server folders use human-readable names, making it easy to identify which folder belongs to which server

### GUI User Manager (2025-10-15)
The GUI provides a User Management interface for viewing and editing user relationship metrics:
- **Accessed via**: Purple "User Manager" button in main GUI window
- **Server Selector**: Dropdown to choose which server's users to manage
- **User List Display**: Shows all users with relationship metrics in the selected server's database
  - Columns: User ID, Rapport, Anger, Trust, Formality
  - Only shows users that exist in the database (no placeholder/empty users)
- **Edit Dialog**: Per-user editor opened by clicking "Edit" button
  - **Editable Fields**: All 4 metrics (Rapport 0-10, Anger 0-10, Trust 0-10, Formality -5 to +5)
  - **Individual Metric Locks**: Each metric has its own lock toggle checkbox
    - Locked metrics won't be automatically updated by sentiment analysis
    - Tooltips explain lock functionality on hover
  - **Range Validation**: Ensures values stay within valid bounds
  - **Manual Override**: GUI editing bypasses locks (respect_locks=False)
- **Per-Server Isolation**: Each server's users are completely separate
- **Real-Time Updates**: Changes take effect immediately in bot behavior

## Key Database Tables (Per-Server)

Each server has its own complete set of these tables in its dedicated database file.

### bot_identity
Stores bot personality in three categories (unique per server):
- `trait` - Core personality characteristics
- `lore` - Background story and history
- `fact` - Specific behaviors and quirks

Accessed via `db_manager.get_bot_identity(category)` and `db_manager.add_bot_identity(category, content)`

**Per-Server**: Each server can have a completely different bot personality

### relationship_metrics
Per-user relationship tracking:
- `rapport` (0-10) - Friendliness/warmth
- `trust` (0-10) - Openness/vulnerability
- `anger` (0-10) - Defensiveness/sarcasm
- `formality` (-5 to +5) - Speech style (casual to formal)
- `rapport_locked`, `anger_locked`, `trust_locked`, `formality_locked` (0/1) - Lock flags to prevent automatic updates (2025-10-15)

**Metric Locking (2025-10-15)**:
- Individual lock toggles for each metric prevent automatic sentiment-based updates
- Locked metrics can still be manually edited via GUI User Manager or `/user_set_metrics`
- `db_manager.update_relationship_metrics(user_id, respect_locks=True, ...)` honors locks during sentiment analysis
- `respect_locks=False` parameter allows manual overrides (used by GUI and admin commands)
- Accessible via GUI User Manager with tooltips explaining functionality

Auto-updates based on user sentiment (unless locked). Manual adjustment via `/user_set_metrics` command or GUI User Manager.

### long_term_memory
User-associated facts with source attribution:
- `fact` - The information
- `source_user_id` - Who provided it
- `source_nickname` - Display name of source
- Timestamps and reference counts

**Memory Correction (2025-10-13)**:
- Natural language corrections via `memory_correction` intent
- AI identifies which fact to update based on user's correction
- Example: "Actually, my favorite color is red, not blue" automatically updates the stored fact
- Semantic similarity search prevents duplicate/contradictory facts
- Accessed via `db_manager.find_contradictory_memory()`, `db_manager.update_long_term_memory_fact()`, and `db_manager.delete_long_term_memory()`

### short_term_message_log
Up to 500 messages rolling buffer **server-wide across all channels** (per server). Provides high-resolution context for AI responses.

**Server-Wide Context**: Messages are NOT filtered by channel. This allows the bot to maintain conversation context across all channels within a server, enabling it to reference information mentioned in any channel.

**Memory Consolidation Process (Per-Server):**
- AI (GPT-4o) analyzes up to 500 messages and extracts facts about users
- **Smart Contradiction Detection (2025-10-13)**: Before saving each fact, system checks for contradictions:
  - Uses semantic similarity search to find related existing facts
  - AI determines if new fact contradicts any existing fact
  - If contradiction detected, old fact is **updated** instead of creating duplicate
  - If no contradiction, fact is added as new
- Facts are saved to (or updated in) that server's `long_term_memory` with source attribution
- All short-term messages are then archived to `database/{ServerName}/archive/short_term_archive_YYYYMMDD_HHMMSS.json`
- After archival, short-term table is cleared for that server
- Triggered automatically when server reaches 500 messages
- Triggered manually via `/consolidate_memory` command (admin only, per-server)
- Can be automated on schedule via task (currently commented out in `cogs/memory_tasks.py`)

## Admin Commands (Per-Server)

**IMPORTANT**: All admin commands operate on the server where they're executed. Each server has independent data.

### Bot Identity Management
- `/identity_add_trait` - Add personality trait (for THIS server)
- `/identity_add_lore` - Add backstory/history (for THIS server)
- `/identity_add_fact` - Add quirk/behavior (for THIS server)
- `/identity_view` - Display complete personality (for THIS server)

### User Relationship Management
- `/user_view_metrics` - View relationship stats (for THIS server)
- `/user_set_metrics` - Manually adjust metrics (for THIS server)
- `/user_view_memory` - View stored facts (for THIS server)
- `/user_add_memory` - Add fact about user (for THIS server)

### Memory Management
- `/consolidate_memory` - Manually trigger memory consolidation for THIS server (extracts facts from up to 500 messages, archives short-term messages, clears short-term table)

### Personality Mode Configuration
- `/channel_set_personality` - Configure how bot behaves in a specific channel (admin only)
  - Parameters: `immersive_character` (bool), `allow_technical_language` (bool), `use_server_info` (bool)
  - Can view current settings by calling without parameters
  - Also configurable via GUI (per-channel overrides only, NOT in global settings)
  - **GUI Tooltips**: Hover over checkboxes in channel editor to see explanations of each option

### Global State
- `/mood_set` - Set server-specific mood integers
- `/mood_get` - View current mood (for THIS server)

### Testing System
- `/run_tests` - Comprehensive system validation (admin only, per-server)
  - Runs 79 tests across 19 categories
  - Results sent via Discord DM to admin
  - Detailed JSON log saved to `logs/test_results_*.json`
  - Validates: database operations, AI integration, per-server isolation, input validation, security measures, and all core systems
  - Automatic test data cleanup after each run
  - **Test Categories**: Database Connection (3), Database Tables (6), Bot Identity (2), Relationship Metrics (6), Long-Term Memory (4), Short-Term Memory (3), Memory Consolidation (2), AI Integration (3), Config Manager (3), Emote System (2), Per-Server Isolation (4), Input Validation (4), Global State (3), User Management (3), Archive System (4), Image Rate Limiting (4), Channel Configuration (3), Formatting Handler (6), Image Generation (6), Cleanup Verification (5)
  - **Usage**: Recommended to run after major updates to ensure system stability

## AI Model Configuration

The bot uses task-specific model configurations in `config.json`:

```json
"ai_models": {
  "primary_model": "gpt-4.1-mini",
  "intent_classification": {
    "model": "gpt-4.1-mini",
    "max_tokens": 15,
    "temperature": 0.0
  },
  "sentiment_analysis": {
    "model": "gpt-4.1-mini",
    "max_tokens": 100,
    "temperature": 0.0
  },
  "main_response": {
    "model": "gpt-4.1-mini",
    "max_tokens": 80,
    "temperature": 0.8
  }
}
```

Access via `AIHandler._get_model_config(task_type)` which falls back to `primary_model` if task-specific config is missing.

## Response Limits Configuration

Configurable context window sizes in `config.json`:

```json
"response_limits": {
  "short_term_context_messages": 500,
  "recent_messages_for_intent": 5,
  "max_response_length": 80,
  "short_term_message_limit": 500
}
```

**Note**: `short_term_message_limit` triggers automatic memory consolidation when reached (per server).

## Emotional Context System

The bot blends two emotional sources:
1. **Relationship metrics** - Baseline tone based on user relationship
2. **Lore-based emotions** - Topic-specific emotions based on bot's lore (e.g., tragic backstory → sad, hated things → angry, dreams → excited)

This blending happens in `ai_handler.generate_response()` via the system prompt.

## Formal Server Information System (Updated 2025-10-15)

For formal channels (rules, moderation, support, etc.), the bot can load text files instead of relying on personality database:

**Purpose**: Provide authoritative server documentation that the bot references when answering questions
**Use Cases**: Server rules, moderation policies, FAQs, channel instructions

**Implementation (`modules/ai_handler.py`):**
- `_load_server_info(channel_config, guild_id, server_name)` checks if `use_server_info` is enabled
- Loads ALL `.txt` files from `Server_Info/{ServerName}/` directory (per-server isolation)
- Returns formatted string with file contents
- Injected into system prompt for `factual_question` and `casual_chat` intents
- Bot prioritizes server info over personality when answering questions

**Per-Server Isolation:**
- Each server has its own `Server_Info/{ServerName}/` folder
- Example: `Server_Info/Mistel Fiech's Server/rules.txt`
- Prevents cross-contamination of server rules and policies
- Server name is sanitized for filesystem safety

**Configuration:**
- Enable per-channel via GUI: Edit Channel → Check "Use Server Information"
- Enable via Discord command: `/channel_set_personality use_server_info:true`
- Default: OFF (must be explicitly enabled)
- Files are excluded from git by default to protect sensitive information

**File Format:**
- Create `.txt` files in `Server_Info/{ServerName}/` directory
- UTF-8 encoding
- Name files descriptively (e.g., `server_rules.txt`, `moderation_policy.txt`)
- All `.txt` files in the server's folder are loaded automatically when enabled

**Best Practices:**
- Use with "Allow Technical Language" enabled for formal tone
- Ideal for rules channels, moderation channels, support channels
- Bot will reference these files authoritatively when answering questions
- Does NOT replace personality - personality still affects tone and style

## Emote System (Per-Server Filtering)

Custom Discord emotes are managed by `EmoteOrchestrator`:
- Loads emotes from ALL servers the bot is in
- **Per-Server Filtering (2025-10-14)**: Servers can restrict which servers' emotes are available
  - Configured via GUI Server Manager → Edit Settings → Emote Sources
  - Config format: `server_emote_sources: {guild_id: [allowed_guild_id1, allowed_guild_id2]}`
  - Default behavior: If server not configured, all emotes available (backward compatible)
  - Use case: Professional servers can restrict to professional emotes only
- Provides AI with plain tags (`:fishstrong:`)
- Replaces tags with Discord format (`<:fishstrong:1234567890>`) before sending
- `_strip_discord_formatting()` in AI Handler removes Discord syntax from context to prevent AI from replicating malformed syntax
- Filtering implemented in `get_emotes_for_guild(guild_id)` and `replace_emote_tags(text, guild_id)`

## Implementation Status

### Phase 1 (COMPLETED ✅)
- Bot identity database system
- Relationship metrics tracking
- Emotional context blending
- Intent classification
- Automatic metric updates
- Real-time admin interface

### Phase 2 (COMPLETED ✅)
- ✅ **Per-Server Database Isolation**: Separate database file per Discord server
- ✅ **User-Friendly Database Structure**: `database/{ServerName}/{guild_id}_data.db` for easy server identification (2025-10-15)
- ✅ **Per-Server Server_Info Folders**: `Server_Info/{ServerName}/` prevents cross-contamination of server rules (2025-10-15)
- ✅ **Memory consolidation system**: AI-powered fact extraction using GPT-4o
- ✅ **Smart Contradiction Detection**: Semantic similarity search and AI-powered duplicate prevention (2025-10-13)
- ✅ **Memory Correction System**: Natural language memory updates via intent classification (2025-10-13)
- ✅ **Automatic archival**: Short-term messages to JSON before deletion (per-server in `database/{ServerName}/archive/`)
- ✅ **Auto-trigger at 500 messages**: Per-server consolidation threshold
- ✅ **SQLite auto-vacuum**: Database optimization enabled
- ✅ **Personality Mode System**: Immersive character mode with natural language enforcement
- ✅ **GUI Personality Controls**: Per-channel personality settings with hover tooltips
- ✅ **Server-Wide Short-Term Memory**: Context maintained across all channels within a server
- ✅ **Formal Server Information System**: Load text files for rules/policies in formal channels (per-server)
- ✅ **Improved Intent Classification**: Better distinction between memory_recall and factual_question
- ✅ **Bot Self-Lore Extraction**: Automated extraction of relevant lore for emotional context (2025-10-13)
- ✅ **Roleplay Action Formatting**: Automatic italic formatting of physical actions for immersive roleplay (2025-10-15)
- ✅ **AI Image Generation**: Natural language-triggered childlike drawings via Together.ai FLUX.1-schnell (2025-10-15)
- ✅ **Relationship Metric Locks**: Individual lock toggles for each metric to prevent automatic sentiment analysis updates (2025-10-15)
- ✅ **GUI User Manager**: Visual interface for viewing and editing user relationship metrics with lock controls (2025-10-15)

### Phase 3 (PLANNED)
- ⏳ **Proactive engagement subsystem**: Planned
- ⏳ **Dynamic status updates**: Planned

See `PLANNED_FEATURES.md` for detailed roadmap.

## Code Modification Requirements

From `AI_GUIDELINES.md`:

1. **Read Before Write**: Always use Read tool before modifying files
2. **Write Complete Files**: Use Write tool to save entire updated files (not Edit tool)
3. **Update Documentation**: Changes to architecture require updates to `SYSTEM_ARCHITECTURE.md`
4. **Consult PLANNED_FEATURES.md**: Before implementing new features, check if already documented
5. **No Hardcoding**: Use config.json for all tunable parameters
6. **Maintain Modularity**: Keep cogs, modules, and database logic separated

## Common Development Patterns

### Adding a New Admin Command (Per-Server)
1. Add command in `cogs/admin.py`
2. Use `_get_db(interaction)` helper to get server-specific database
3. Validate guild context (reject if not in a server)
4. Add corresponding DB method in `database/db_manager.py` if needed
5. Test with `/command_name` in a Discord server

### Adding New AI Model Task
1. Add task config to `config.json` under `ai_models`
2. Use `self._get_model_config('task_name')` in AI Handler
3. Falls back to `primary_model` automatically

### Adding New Relationship Metric Guidance
Update `_build_relationship_context()` in `modules/ai_handler.py` to add prompt guidance for new metric ranges.

## Important Notes

- **Per-Server Architecture**: Each Discord server has its own database folder and file. Always use `bot.get_server_db(guild_id, guild_name)` to get the correct database instance.
- **Database Structure (2025-10-15)**: `database/{ServerName}/{guild_id}_data.db` - Human-readable folder name, guild_id in filename for uniqueness
- **Database Isolation**: Bot personality, user relationships, and memories are completely separate per server. No data sharing between servers.
- **Archive Isolation (2025-10-15)**: Each server's archives stored in `database/{ServerName}/archive/` - no cross-contamination
- **Server Info Isolation (2025-10-15)**: Each server's rules/policies stored in `Server_Info/{ServerName}/` - prevents cross-contamination
- **Server-Wide Memory**: Short-term memory is NOT filtered by channel. Bot maintains context across all channels within a server.
- **Per-Server Emote Filtering (2025-10-14)**: Servers can restrict which servers' emotes are available via `server_emote_sources` config. Managed through GUI Server Manager.
- **Per-Server Alternative Nicknames (2025-10-14)**: Each server can configure custom nicknames via `server_alternative_nicknames` config. Falls back to global `alternative_nicknames` for backward compatibility.
- **GUI Server Manager**: Server-first interface for managing channels, nicknames, and emote sources per server. Scans database folder to display all active servers with human-readable names.
- **GUI Tooltips**: Hover over personality mode checkboxes in channel editor to see explanations. Implemented using `ToolTip` class in `gui.py`.
- **Migration Script**: `scripts/migrate_to_final_structure.py` converts legacy database formats to new structure
- **No Emoji in Console Output**: Avoid emojis in print statements due to Windows console compatibility. Use text or disable logging emoji.
- **Discord Intents Required**: `messages`, `message_content`, `guilds`, `members` must be enabled in Discord Developer Portal.
- **Database Thread Safety**: SQLite connection uses `check_same_thread=False` - safe for Discord.py's async environment but not for true multi-threading.
- **Message Deduplication**: `EventsCog._processing_messages` set prevents duplicate processing of the same message ID.
- **Database Optimization**: SQLite auto-vacuum is enabled (`PRAGMA auto_vacuum = FULL`) to automatically reclaim space after message deletion during consolidation.
- **Archive Format**: Archived messages are stored as JSON with metadata: `archived_at`, `message_count`, and full `messages` array with all fields (per-server in respective server's archive folder).

## Documentation Files

- **SYSTEM_ARCHITECTURE.md** - Complete technical specification (authoritative)
- **AI_GUIDELINES.md** - Code review standards and architectural requirements
- **README.md** - User-facing setup and feature guide
- **PLANNED_FEATURES.md** - Future development roadmap
- **TROUBLESHOOTING.md** - Common issues and solutions
