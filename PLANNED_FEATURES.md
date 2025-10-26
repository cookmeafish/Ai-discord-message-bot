# Planned Features

This document tracks future development features for the Discord bot.

## Phase 2 (COMPLETED ✅)

All Phase 2 features have been fully implemented as of 2025-10-14.

### Additional Updates - 2025-10-14:

- ✅ **Multi-Server Database Fix** (guild_id prefix prevents filename collisions)
- ✅ **Archive Filename Fix** (guild_id in archive names for per-server identification)
- ✅ **Flexible Nickname Detection** (bot responds to name variations: "Dr. Fish", "drfish", "dr fish")
- ✅ **Alternative Nicknames System** (configurable via GUI, supports any custom variations)
- ✅ **Concurrent Response Limit** (max 3 simultaneous responses to prevent bot overload)
- ✅ **Discord Reply Feature** (bot uses Discord's native reply UI for all responses)
- ✅ **Per-Server Emote Filtering** (restrict which servers' emotes are available per server)
- ✅ **Per-Server Alternative Nicknames** (server-specific nicknames with flexible matching, falls back to global)
- ✅ **GUI Server Manager Redesign** (server-first interface with channels, nicknames, and emote sources per server)

###  Phase 2 Core Features:

- ✅ Per-Server Database Isolation
- ✅ Memory consolidation system (AI-powered fact extraction using GPT-4o)
- ✅ **Smart Contradiction Detection** (semantic similarity search + AI-powered duplicate prevention) - Implemented in consolidation 2025-10-14
- ✅ **Natural Memory Correction System** (users can correct bot's memory naturally) - Fully wired up 2025-10-14
- ✅ **Bot Self-Lore Extraction** (automated extraction of bot's self-generated lore) - Implemented 2025-10-14
- ✅ **Memory Schema Migration** (added status, superseded_by_id, last_validated_timestamp columns) - Migrated 2025-10-14
- ✅ **Input Validation & SQL Injection Protection** (defense-in-depth security) - Implemented 2025-10-13
- ✅ Automatic archival (JSON before deletion)
- ✅ Auto-trigger at 500 messages per server
- ✅ SQLite auto-vacuum
- ✅ Personality Mode System (immersive character mode)
- ✅ GUI Personality Controls (per-channel settings with tooltips)
- ✅ Server-Wide Short-Term Memory (cross-channel context)
- ✅ Formal Server Information System (text file loading)
- ✅ Improved Intent Classification (memory_recall vs factual_question)
- ✅ **Comprehensive Testing Suite** (76 tests across 19 categories, accessible via `/run_tests`)
- ✅ **Roleplay Actions with Italic Formatting** (automatic detection and formatting of physical actions, configurable per-channel) - Implemented 2025-10-15
- ✅ **AI Image Generation with Natural Detection** (childlike drawings via Together.ai, $0.002/image, 5 per 2-hour period) - Implemented 2025-10-15

## Phase 3 (COMPLETED ✅)

### Proactive Features
- ✅ **Proactive Engagement Subsystem**: Bot randomly joins conversations based on context (Implemented 2025-10-16)
  - AI judges conversation relevance using configurable threshold
  - Periodic checks every 30 minutes (configurable)
  - Anti-spam: Cooldown timer prevents repeated engagement
  - **Self-reply prevention**: Skips if last message was from bot
  - **Multi-level control**: Global → per-server → per-channel toggles
  - Per-channel toggle: Disable for serious channels (rules, announcements)
  - GUI controls for threshold, check interval, and per-channel settings
- ✅ **Dynamic Status Updates**: AI-generated Discord status reflecting bot's thoughts and mood (Implemented 2025-10-16)
  - Generates funny/quirky status once per day at configurable time
  - Uses AI based on bot's personality/lore from selected server
  - Per-server toggle for adding status to short-term memory
  - GUI controls for enable/disable, time scheduling, and server selection

### Relationship Metrics Expansion (COMPLETED ✅ 2025-10-16)

**Five New Relationship Dimensions - IMPLEMENTED**

Original 4 metrics: `rapport`, `trust`, `anger`, `formality`
**New 5 metrics added**: `fear`, `respect`, `affection`, `familiarity`, `intimidation`

Total: **9 relationship metrics per user**

All five proposed metrics have been fully implemented:

- ✅ **Fear (0-10)**: How much the bot fears this user
  - High fear → nervous, submissive, overly polite, avoids disagreement
  - Low fear → confident, comfortable, willing to argue
  - Use case: Power dynamics, authority figures
  - Database column added with migration script

- ✅ **Respect (0-10)**: Professional/personal admiration
  - Distinct from fear - you can respect without fear
  - High respect → listens carefully, values opinions, defers to expertise
  - Low respect → dismissive, argumentative, challenges statements

- ✅ **Affection (0-10)**: Emotional warmth beyond rapport
  - More intimate than rapport - familial/romantic attachment level
  - High affection → protective, caring, uses pet names, worries about user
  - Low affection → emotionally distant, transactional

- ✅ **Familiarity (0-10)**: How well the bot knows this user
  - High familiarity → references inside jokes, past events, shared history
  - Low familiarity → treats as stranger, formal introductions

- ✅ **Intimidation (0-10)**: Passive fear from user's reputation/status
  - Similar to fear but based on perceived power, not direct threats
  - High intimidation → careful word choice, seeks approval, avoids mistakes

**Implementation Completed:**
- ✅ Database schema changes (5 new columns + 5 lock columns added to `relationship_metrics`)
- ✅ Automatic database migration with sensible defaults
- ✅ GUI User Manager updated for all 9 metrics with lock controls
- ✅ Discord commands `/user_view_metrics` and `/user_set_metrics` support all 9 metrics
- ✅ Individual lock toggles for each metric (prevents automatic updates)
- ✅ Testing suite expanded (Tests 6a & 6b added for new metrics)
- ✅ AI Handler integration for sentiment-based updates
- ✅ Documentation updated across all MD files

### Feature Ideas

- ✅ **GUI Image Generation Controls**: Add fields to GUI for configuring image generation rate limiting (max_per_user_per_period and reset_period_hours) - Implemented 2025-10-16

## Phase 4 (HIGH PRIORITY - VPS HEADLESS DEPLOYMENT)

### 🚨 CRITICAL: Full Discord Command Parity with GUI

**Problem Statement:**
The bot is intended for deployment on a headless VPS (Virtual Private Server) where the GUI is inaccessible or difficult to reach. Currently, many critical configuration settings can ONLY be changed through the GUI (gui.py), making remote management nearly impossible.

**Why This Is Critical:**
- VPS deployments have no display/GUI access
- SSH access doesn't easily support tkinter GUIs
- Bot operators need to configure settings without GUI access
- All GUI functionality MUST be available via Discord commands

**Current Status:**
Some Discord commands exist, but many GUI settings have NO Discord equivalent. This makes VPS deployment impractical for many use cases.

**Required Implementation: Complete Command Coverage**

All GUI-configurable settings MUST have Discord command equivalents. Below is the comprehensive list of missing commands:

---

#### 1. Global Bot Configuration Commands

**Missing Commands:**
- `/config_set_reply_chance` - Set global random reply chance (0.0-1.0)
  - Example: `/config_set_reply_chance chance:0.05`
  - Current: GUI-only (gui.py:93)

- `/config_set_personality` - Update default personality traits and lore for new servers
  - Parameters: `traits` (optional), `lore` (optional)
  - Example: `/config_set_personality traits:"helpful, friendly, curious" lore:"I am a helpful AI..."`
  - Current: GUI-only (gui.py:156-161)

- `/config_add_global_nickname` - Add global alternative nickname
  - Example: `/config_add_global_nickname nickname:"drfish"`
  - Current: GUI-only (gui.py:163-169)
  - Note: Server-specific nicknames already have `/server_add_nickname` ✅

- `/config_remove_global_nickname` - Remove global alternative nickname
- `/config_list_global_nicknames` - List all global alternative nicknames

---

#### 2. Image Generation Configuration Commands

**Missing Commands:**
- `/image_config_enable` - Enable/disable image generation globally
  - Example: `/image_config_enable enabled:true`
  - Current: GUI-only (gui.py:97-104)

- `/image_config_set_limits` - Configure rate limiting for image generation
  - Parameters: `max_per_period` (int), `reset_period_hours` (int)
  - Example: `/image_config_set_limits max_per_period:5 reset_period_hours:2`
  - Current: GUI-only (gui.py:106-114)

- `/image_config_view` - View current image generation settings
  - Shows: enabled status, max per period, reset period hours, model, style

---

#### 3. Status Update Configuration Commands

**Missing Commands:**
- `/status_config_enable` - Enable/disable daily status updates
  - Example: `/status_config_enable enabled:true`
  - Current: GUI-only (gui.py:120-127)

- `/status_config_set_time` - Set daily update time (24h format)
  - Example: `/status_config_set_time time:"14:30"`
  - Current: GUI-only (gui.py:129-132)

- `/status_config_set_source_server` - Choose which server's personality generates status
  - Parameters: `server_name` (string, or "Most Active Server")
  - Example: `/status_config_set_source_server server_name:"Mistel Fiech's Server"`
  - Current: GUI-only (gui.py:134-146)

- `/status_config_view` - View current status update configuration
  - Shows: enabled, update time, source server name

**Note:** `/server_set_status_memory` already exists for per-server memory toggle ✅

---

#### 4. Per-Channel Configuration Commands

**Missing Commands:**
- `/channel_set_purpose` - Set channel purpose/instructions
  - Example: `/channel_set_purpose purpose:"Strictly answer user questions based on server rules."`
  - Current: GUI-only (gui.py:481-485)

- `/channel_set_reply_chance` - Set per-channel random reply chance
  - Example: `/channel_set_reply_chance chance:0.08`
  - Current: GUI-only (gui.py:488-492)

- `/channel_set_proactive_interval` - Set proactive engagement check interval (minutes)
  - Example: `/channel_set_proactive_interval interval:45`
  - Current: GUI-only (gui.py:554-558)

- `/channel_set_proactive_threshold` - Set engagement threshold (0.0-1.0, higher = more selective)
  - Example: `/channel_set_proactive_threshold threshold:0.8`
  - Current: GUI-only (gui.py:560-564)

- `/channel_view_settings` - View all current channel settings
  - Shows: purpose, reply chance, personality mode, proactive settings, all toggles

**Note:** `/channel_set_personality` already exists for personality mode toggles ✅

---

#### 5. Per-Server Emote Management Commands

**Missing Commands:**
- `/server_set_emote_sources` - Configure which servers' emotes are available in this server
  - Parameters: `action` (list/add/remove/clear), `guild_id` (optional)
  - Examples:
    - `/server_set_emote_sources action:list` - Show available servers and current sources
    - `/server_set_emote_sources action:add guild_id:1260857723193528360` - Allow emotes from specific server
    - `/server_set_emote_sources action:remove guild_id:1260857723193528360` - Remove emote source
    - `/server_set_emote_sources action:clear` - Remove all restrictions (allow all emotes)
  - Current: GUI-only (gui.py:1035-1118)

---

#### 6. View/List Commands for Discovery

**Missing Commands:**
- `/config_view_all` - View all global configuration settings
  - Shows: reply chance, personality defaults, global nicknames, image gen, status updates

- `/server_view_settings` - View all server-specific settings
  - Shows: alternative nicknames, emote sources, status memory toggle

- `/channel_list_active` - List all active channels in this server
  - Shows: channel ID, channel name, purpose (first 50 chars)

---

### Implementation Priority: 🔴 CRITICAL - HIGHEST PRIORITY

This MUST be completed before any other Phase 4 features. VPS deployment is a core requirement, and without full command parity, the bot cannot be effectively managed remotely.

**Estimated Complexity:** Medium-High
- Create 20+ new admin commands in `cogs/admin.py`
- Each command must validate permissions (admin only)
- Each command must update `config.json` via `ConfigManager`
- Commands must provide clear feedback (success/error messages)
- Add comprehensive parameter validation
- Update all documentation (CLAUDE.md, README.md, SYSTEM_ARCHITECTURE.md)
- Add tests to `testing.py` for new commands

**Acceptance Criteria:**
- ✅ Every GUI setting has a Discord command equivalent
- ✅ All commands work correctly on VPS without GUI
- ✅ Commands provide clear, helpful feedback
- ✅ Documentation updated with all new commands
- ✅ Tests added for all new commands
- ✅ Bot can be fully configured via Discord alone

**Testing Strategy:**
1. Deploy bot to headless VPS with no GUI access
2. Configure all settings using ONLY Discord commands
3. Verify all settings persist correctly in config.json
4. Verify bot behavior matches GUI-configured behavior
5. Run `/run_tests` to validate system integrity

---

### Server_Info Folder System - Fandom & Lore Management

**Problem Statement:**
Current `Server_Info` loads ALL `.txt` files from a single folder. For fandom servers with extensive lore (character bios, youtuber lore, rules, guides), this becomes unmanageable and loads unnecessary context into AI prompts.

**Proposed Solution: Hierarchical Server_Info Menu System**

**Directory Structure:**
```
Server_Info/
└── {ServerName}/
    ├── rules/
    │   ├── server_rules.txt
    │   └── channel_guidelines.txt
    ├── character_lore/
    │   ├── main_character.txt
    │   ├── side_character1.txt
    │   └── side_character2.txt
    ├── youtuber_lore/
    │   ├── creator1_bio.txt
    │   └── creator2_bio.txt
    ├── world_building/
    │   ├── locations.txt
    │   └── timeline.txt
    └── guides/
        └── getting_started.txt
```

**Per-Channel Folder Selection:**
- Instead of `use_server_info: true/false`, channels get `server_info_folders: ["rules", "character_lore"]`
- AI loads ONLY text files from selected folders
- GUI provides checkboxes for each available folder
- Discord command: `/channel_set_server_info folders:"rules,character_lore"`

**Use Cases:**
- **Rules Channel**: Load only `rules/` folder
- **Roleplay Channel**: Load `character_lore/` + `world_building/`
- **General Chat**: Load `rules/` only
- **Fandom Discussion Channel**: Load all folders for comprehensive lore access

**GUI Implementation:**
- **Server Manager → Active Channels → Edit Channel Dialog**:
  - "Server Information Folders" section
  - Scans `Server_Info/{ServerName}/` for subdirectories
  - Displays checkbox for each folder found
  - Multi-select support (user can enable multiple folders)

**Discord Command Implementation:**
- `/channel_set_server_info` - Configure which folders are loaded for current channel
  - Parameters:
    - `folders` (optional): Comma-separated list of folder names (e.g., "rules,character_lore")
    - `action` (optional): "list" shows available folders, "clear" disables all folders
  - Examples:
    - `/channel_set_server_info folders:rules,character_lore` - Enable specific folders
    - `/channel_set_server_info action:list` - Show all available folders
    - `/channel_set_server_info action:clear` - Disable server info for this channel

**File Management:**
- **GUI Button**: "Manage Server Info Folders" in Server Settings Dialog
  - Lists all folders in `Server_Info/{ServerName}/`
  - Allows creating new folders (name input)
  - Allows deleting empty folders
  - Shows file count per folder
  - Opens folder in file explorer for manual editing

**Benefits:**
- **Selective Context**: Only load relevant lore per channel
- **Reduced Token Usage**: Smaller AI prompts = faster/cheaper responses
- **Better Organization**: Clear separation of rules, lore, guides
- **Fandom-Friendly**: Perfect for roleplay servers, fandom communities, content creator communities
- **Scalability**: Servers can have hundreds of lore files organized cleanly

**Backward Compatibility:**
- Channels with `use_server_info: true` default to loading ALL folders (current behavior)
- Empty `server_info_folders` list = load nothing
- Missing `server_info_folders` field = fall back to old behavior (load everything)

**Implementation Priority:** Medium (very useful for fandom/roleplay servers, but not critical)

**Estimated Complexity:** Medium
- Modify `_load_server_info()` in `modules/ai_handler.py` to accept folder list
- Update GUI channel editor to scan and display folders as checkboxes
- Create Discord command `/channel_set_server_info`
- Create GUI dialog for managing folders (create, delete, view)
- Update documentation across all MD files
- Add tests for folder-based loading

---

### Other Feature Ideas

- User-configurable memory consolidation schedules
- Export/import bot personality between servers
- Multi-language support with personality adaptation
- Voice channel interaction support
- Automatic lore generation from conversations
- Relationship visualization in GUI (graph/chart showing metric evolution over time)
- Per-user personality overrides (how bot treats specific users differently)
- Event-triggered personality changes (seasonal events, milestones)
- Collaborative memory (users can confirm/deny facts about themselves)
- Relationship decay over time (metrics slowly drift toward neutral if no interaction)
- Metric thresholds triggering special behaviors (e.g., max affection unlocks special responses)

## Testing Requirements

When implementing features:
1. Update this document with progress
2. Follow guidelines in `AI_GUIDELINES.md`
3. Update `SYSTEM_ARCHITECTURE.md` for architectural changes
4. **Run `/run_tests` to validate all systems after major changes**
5. Add new tests to `testing.py` for new features
6. Test thoroughly with multiple servers
7. Consider backwards compatibility

### Testing Infrastructure (COMPLETED ✅)

**76-Test Comprehensive Suite** covering:
- Database operations (connection, tables, schemas)
- Bot identity system (traits, lore, facts)
- Relationship metrics (rapport, trust, anger, formality)
- Memory systems (short-term, long-term, consolidation, archival)
- AI integration (response generation, intent classification, sentiment analysis)
- Per-server isolation (database files, multi-DB manager)
- Input validation & security (SQL injection prevention, oversized content)
- Global state management (key-value storage)
- User management (creation, timestamps, cleanup)
- Image rate limiting (hourly/daily tracking)
- Channel configuration (personality mode settings)
- Formatting handler (roleplay action detection and formatting)
- Image generation system (module import, config, integration, methods)
- Emote system (global emote availability)
- Config manager (settings validation)
- Automatic cleanup verification (no test data left behind)

**Accessible via**: `/run_tests` (admin only, per-server)
**Results**: Discord DM + JSON log in `logs/test_results_*.json`

## Contributing

When implementing features, follow the testing requirements above to ensure system stability.
