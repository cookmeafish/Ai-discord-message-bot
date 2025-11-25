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
2. Per-channel overrides in `channel_settings` database table (per-server)
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
   - **Explicit user identification** in all response prompts to prevent user confusion (2025-10-18)
   - **Conversation energy matching** (2025-10-19): Dynamically adjusts response length based on recent message length
6. **Relationship metrics are now STABLE** - no longer update automatically after every message (2025-10-19)
   - Metrics only update via: Manual commands (`/user_set_metrics`), GUI User Manager, or memory consolidation
   - Prevents metrics from changing too rapidly during conversations

**User Identification System (2025-10-18)**:
- **CRITICAL**: All AI response prompts include explicit user identification to prevent confusing users with each other
- Format: `🎯 **CURRENT USER IDENTIFICATION** 🎯` section with user's name and ID
- Includes warnings: "NEVER mention your own name or make puns about it" and "NEVER address this user by someone else's name"
- Applied to: image generation, casual chat, factual questions, memory corrections
- Proactive engagement uses **neutral context** (no specific user) via dedicated `generate_proactive_response()` method

**Mentioned User Detection System (2025-10-26)**:
- **Purpose**: Load facts about OTHER users mentioned in conversation, not just the message author
- **Works for**: Casual chat, memory recall, factual questions ("what do you think about Alice?")
- **Three-Tier Matching** (same as image generation):
  1. Discord username/display name (word boundary matching)
  2. **Nicknames table** (substring matching) ← Primary source
  3. Long-term memory facts with "also goes by" phrases (fallback)
- **Prompt Structure**: Clearly separates author facts from mentioned user facts
  - `=== KNOWN FACTS ABOUT THE AUTHOR (person asking you the question) ===`
  - `=== FACTS ABOUT MENTIONED USERS (people being discussed, NOT the author) ===`
- **Prevents Confusion**: Explicit warnings to NOT confuse mentioned users with the author
- **Loads**: Facts AND relationship metrics for each mentioned user
- **Benefits**: "what do you think about Alice?" correctly loads Alice's facts, not just author's facts

**Conversation Energy Matching System (2025-10-19)**:
- **Purpose**: Bot automatically adjusts response length to match conversation energy
- **Implementation**: `_calculate_conversation_energy(messages, bot_id)` analyzes last 5 user messages from last 30 messages
- **Improved Accuracy (2025-10-19)**: Looks at last 30 messages instead of 10 to ensure recent user messages are analyzed, not older ones
- **Energy Levels**:
  - **VERY LOW** (1-3 words avg): max_tokens=25, forces 1-5 word responses (e.g., "lol", "yeah", "fair")
  - **LOW** (4-8 words avg): max_tokens=40, brief responses (e.g., "yeah that makes sense")
  - **MEDIUM** (9-20 words avg): max_tokens=60, natural 1-2 sentences
  - **HIGH** (20+ words avg): max_tokens=80, full responses (default)
- **Prompt Guidance**: AI receives explicit instructions to match energy (e.g., "Recent messages are VERY SHORT. Respond with 1-5 words MAX")
- **Applied To**: Both `generate_response()` and `generate_proactive_response()` methods
- **Benefits**: Prevents over-talking in low-energy chats, matches natural conversation flow

**Roleplay Formatting Conditional Activation (2025-10-19)**:
- **Purpose**: Only use roleplay formatting when user is explicitly roleplaying
- **STRICT LOGIC**: Uses formatting ONLY when user has asterisks in last 7 messages
- **MASSIVELY STRENGTHENED Roleplay Suppression (2025-10-19)**: When roleplay is disabled, AI receives impossible-to-ignore warnings
  - Prompts include "🚫 **CRITICAL: NO ROLEPLAY MODE ACTIVE** 🚫" with all-caps, bolded warnings
  - "**YOU ARE ABSOLUTELY FORBIDDEN FROM DESCRIBING PHYSICAL ACTIONS.**"
  - "**ANY RESPONSE WITH PHYSICAL DESCRIPTIONS WILL BE REJECTED.**"
  - Explicit ❌ FORBIDDEN list: asterisks, physical descriptions, gestures, facial expressions, body language
  - Explicit ✅ REQUIRED list: spoken words, thoughts/reactions, emotes only
  - Much more aggressive language to overcome AI tendency to ignore polite instructions
- **Behavior**:
  - User uses asterisks (*pets bot*, *walks away*) → Bot uses roleplay formatting ✓
  - User doesn't use asterisks → Bot responds with dialogue/thoughts only, no physical descriptions ✓
- **Examples**:
  - "*pets you*" (explicit roleplay) → Bot uses roleplay: "*purrs softly*" ✓
  - "make me a cup of tea" (no asterisks) → Bot uses plain text: "Sure thing!" ✓
  - "Dr fish hi" (no asterisks) → Bot uses plain text: "Hey there!" ✓
  - User has used asterisks earlier in conversation → Bot continues using roleplay for ~7 messages
- **Implementation**: `_apply_roleplay_formatting()` checks last 7 user messages for asterisks; AI prompts include explicit "NO ROLEPLAY MODE" instructions when disabled
- **Benefits**: Prevents unwanted roleplay in normal conversation, completely eliminates physical action descriptions when user isn't roleplaying

**Emote Variety and Frequency System (2025-10-19)**:
- **Purpose**: Increase emote diversity and usage frequency across 200+ available emotes
- **Randomized Sampling**: `get_random_emote_sample()` provides 50 random emotes per response instead of all emotes
  - Reduces token usage by ~80% (1000+ tokens → ~250 tokens)
  - Shuffles emote order for additional randomness
  - Increases variety by forcing AI to choose from different sets each time
- **Enhanced AI Prompts**: All 5 emote prompts strengthened with explicit instructions:
  - "READ the emote names carefully and choose ones that match your EMOTIONAL STATE"
  - "Use emotes in MOST responses (80%+ of the time)"
  - "ALWAYS try different emotes instead of defaulting to favorites - you have 200+ available, explore them!"
  - "DO NOT choose emotes based on names (yours or the user's name) - choose based on FEELINGS and SITUATION ONLY"
- **Name-Independent Selection**: Prevents bot name ("Dr. Fish") and user names from biasing emote choice toward thematic emotes (e.g., fish emotes)
- **Boost-Locked Emote Filtering (2025-10-19)**: `emote_orchestrator.py` filters inaccessible emotes
  - Only loads emotes with `emote.available == True`
  - Skips boost-locked emotes (emotes in slots requiring higher server boost tier)
  - Logs skipped emotes: "Skipped boost-locked emote: :emote_name:"
  - Prevents bot from attempting to use inaccessible emotes that would appear broken
- **Implementation**: `modules/emote_orchestrator.py:get_random_emote_sample()` and `load_emotes()`
- **Benefits**: Maximizes emote variety, prevents name bias, ensures all suggested emotes are actually usable

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
- `modules/ai_handler.py` - OpenAI API interface, intent classification, sentiment analysis, conversation energy matching (2025-10-19)
- `modules/emote_orchestrator.py` - Emote management, per-server filtering, randomized sampling for variety (2025-10-19)
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
- `config.json` - Global bot parameters (model names, limits, per-server settings, image generation)
- **Channel settings** - Stored in database `channel_settings` table (per-server), not in config.json
- `.env` - Secrets (DISCORD_TOKEN, OPENAI_API_KEY, TOGETHER_API_KEY)
- `gui.py` - Graphical configuration interface with Server Manager

### Image Generation Module (2025-10-15, Updated 2025-10-27)
- `modules/image_generator.py` - Together.ai API integration for AI image generation
- `modules/ai_handler.py:_strip_bot_name_from_prompt()` - Removes bot name from prompts
  - **Model**: FLUX.1-schnell (optimized for 4 steps, 512x512 resolution)
  - **Style**: User-determined (prompt dictates style - "cute kitten" = cute, "badass dragon" = badass, etc.)
  - **Multi-Character Scene Handling (2025-10-27)**: Detects and preserves complex scenes with multiple people and actions
    - **Action Word Detection**: Recognizes 25+ action words (fighting, sitting, running, versus, with, and, etc.)
    - **Multi-Subject Detection**: Identifies when prompt mentions 2+ people
    - **Scene-Aware Prompting**: Uses dedicated GPT-4 enhancement prompt for multi-person scenes
    - **Preserves Interactions**: Maintains the relationship/action between subjects ("fighting", "sitting with", etc.)
    - **Increased Context**: Allocates 200 tokens (vs 150 for single subject) for complex scene descriptions
    - **Example**: "draw UserA fighting UserB" → Both people rendered in combat poses, not just one person
  - **Bot Self-Portrait Detection (2025-10-27)**: Recognizes when user wants to draw THE BOT, not themselves
    - **Smart Reflexive Pronoun Detection (2025-10-27)**: Distinguishes between bot as primary vs secondary subject
      - **Primary Subject Detection**: Removes drawing command prefixes, checks if "you/yourself/self" starts the subject phrase
      - **Multi-Subject Handling**: Detects action words (eating, fighting, with, and, versus) to identify multi-subject scenes
      - **Behavior**:
        - `"draw yourself"` → Bot is SOLE subject, skips user matching, draws bot only ✓
        - `"draw you"` → Bot is SOLE subject, skips user matching ✓
        - `"draw user eating you"` → User is primary, bot is secondary, loads BOTH user facts AND bot identity ✓
        - `"draw you and user fighting"` → Multi-subject scene, loads BOTH user facts AND bot identity ✓
      - **Fixed Bug (2025-10-27)**: Previously "draw user eating you" would skip user matching entirely, causing GPT-4 to guess user appearance
    - **Bot Identity Loading**: Automatically loads bot traits, lore, and facts from database
    - **Context Injection**: Formats bot identity as image context for accurate self-depiction
    - **Multi-Subject Context Combination**: When bot appears alongside users, combines bot identity with user facts into single context string
    - **Example**: "draw yourself" → Loads bot's character description, draws the bot (not a robot, not the user)
  - **Context-Aware**: Automatically pulls facts about mentioned users from the database for accurate depictions
    - **User Matching Priority (2025-10-26)**: Three-tier matching system for finding mentioned users
      1. Discord username/display name (fastest, word boundary matching)
      2. **Nicknames table** (medium speed, substring matching - NEW 2025-10-26)
      3. Long-term memory facts with "also goes by" phrases (slowest, word boundary matching)
    - **Nicknames Table Usage (2025-10-26)**: Stores all historical display names/nicknames for users
      - Example: User with nicknames "Alice" and "Alicia" → "draw me alice" matches via substring
      - Enables flexible matching: "alice" matches both "Alice" AND "Alicia"
      - **Works across ALL bot features**: Image generation, memory storage, AND casual conversation
      - **Casual Conversation (NEW 2025-10-26)**: "what do you think about Alice?" loads Alice's facts
    - **Generic Word Protection (2025-11-24)**: Prevents database lookups for common English words
      - 200+ common words blocked: fish, cat, dog, apple, house, blue, etc.
      - Only SPECIFIC names trigger database lookup (capitalized words not in common list)
      - Example: "draw a fish" → no DB lookup (fish is common word)
      - Example: "draw Alice" → DB lookup (Alice is capitalized, not common)
      - Prevents users with generic words in names from being matched incorrectly
    - Only includes appearance/visual facts, excludes behavioral rules and non-visual descriptions
    - **Gender Detection (2025-10-18)**: Automatically detects gender from pronouns in database facts
      - Scans ALL facts for gendered pronouns (she/her/hers vs he/him/his)
      - Adds "a woman" or "a man" as FIRST descriptor in image context
      - Ensures image AI correctly renders gender even when facts don't explicitly state it
      - Example: Facts with "Loves her" and "she is sweet" → detected as "woman" → draws female character
  - **Smart Context Handling (2025-10-26)**: Dual-mode AI enhancement prevents identity contamination
    - **Database User Mode**: When drawing database users (e.g., "Alice"), uses ONLY database facts
      - Detects identity markers: "ruler", "manager", "handsome", "strong", "feared", "man", "woman"
      - Strict prompt prevents GPT-4 from adding generic character knowledge with same name
      - Example: "draw Alice" uses DB facts ("handsome, strong, feared man"), NOT generic "Alice" character
    - **Famous Person Mode**: When drawing people NOT in database (e.g., "Kamala Harris"), uses FULL GPT-4 knowledge
      - Explicit instructions to describe actual appearance of politicians, celebrities, historical figures
      - Allows accurate depictions of real-world people using AI's trained knowledge
    - **Generic Mode**: Objects/creatures without DB facts use GPT-4's general knowledge
    - Prevents blending database user identity with unrelated characters GPT-4 might know
  - **Quality**: High quality detailed illustrations, visual only (no text/labels in images)
  - **Prompt Cleaning**: Automatically removes command words like "draw me", "sketch", "create" before generation
  - **Rate Limiting**: 5 images per user every 2 hours (configurable via `max_per_user_per_period` and `reset_period_hours`)
  - **Cost**: $0.002 per image (~$2 per 1,000 images)
  - **Intent**: `image_generation` - Natural language detection ("draw me a cat", "sketch a house")
  - **Bot Name Stripping**: Automatically removes bot name and alternative nicknames from prompts to prevent name from influencing the drawing
    - Example: "Bot Name, draw me a cat" → image generator only sees "draw me a cat"
    - Handles mentions, punctuation, and case-insensitive matching
  - **User Identification**: Explicit user identification in drawing prompts prevents bot from confusing users
  - **Config**: `config.json` under `image_generation` section
  - **GUI Integration**: Checkbox for enable/disable, fields for period limit and reset hours

### Image Refinement System (2025-11-24)
- `modules/image_refiner.py` - Detects and handles image refinement requests
- **Purpose**: Allows users to iteratively refine generated images without starting over
- **Flow**:
  1. User generates image ("draw a cute cat girl")
  2. Bot enhances prompt ("cute cat girl with green eyes, pink hair, anime style...")
  3. Bot caches the FULL enhanced prompt (not the original request)
  4. User requests refinement ("make her eat fish")
  5. Refiner detects refinement intent and modifies the cached enhanced prompt minimally
  6. New image generated with same character context preserved
- **Enhanced Prompt Caching (2025-11-24)**:
  - `generate_image()` returns 3 values: `(image_bytes, error_msg, full_prompt)`
  - The full enhanced prompt is cached, preserving all character details
  - Refinements modify this enhanced prompt, maintaining visual consistency
  - Example: "cute cat girl with green eyes, pink hair" + "eat fish" → same character eating fish
- **Refinement Detection**: GPT-4o-mini analyzes if user wants to refine previous image
  - Detects: corrections, additions, modifications, critiques, "make X do Y with that"
  - Ignores: general conversation, new image requests, unrelated messages, emotional reactions
  - **Topic Change Detection (2025-11-24)**: Passes recent conversation context to AI
    - If user changed topics after image generation, message is NOT a refinement
    - Example: Image → "what are you doing later?" → bot responds → "yikes aggressive" = NOT refinement
    - Prevents accidental image generation when user is responding to bot's text
  - **Bot Name Stripping (2025-11-24)**: Strips bot name from user message before analysis
- **Prompt Modification**: Makes MINIMAL changes to cached enhanced prompt
  - **Strict Rules**: No new people, no new scenes, no creativity beyond request
  - **Temperature 0.0**: Deterministic output to prevent creative additions
  - **Examples**:
    - "make it blue" → adds "blue" to enhanced prompt
    - "add a sword" → adds "with a sword" to enhanced prompt
- **Refinement Safeguards (2025-11-24)**:
  - **Skip AI Enhancement**: Refined prompts bypass GPT-4 enhancement (already enhanced in cache)
  - **Skip User Context**: User facts/names not loaded during refinements to prevent identity leakage
  - **Bot Name Stripped**: "@Dr. Fish add a sword" → "add a sword" before processing
- **Rate Limiting**: Max 3 refinements per image (configurable)
- **Cache Duration**: Prompts cached for refinement window (configurable in config.json)

### Temporal Context System (2025-11-24)
- **Purpose**: Provides date/time awareness to the bot ONLY when relevant
- **Implementation**: `modules/ai_handler.py:_needs_temporal_context()`
- **Keyword-Based Detection**: No extra API call - uses simple keyword matching
  - **Time Keywords**: "when", "what time", "today", "yesterday", "ago", "how long", etc.
  - **Memory Keywords**: "remember when", "you said", "I told you", "earlier you", etc.
- **Conditional Inclusion**:
  - When relevant: Bot prompt includes current date/time, messages include timestamps
  - When not relevant: No temporal information included (saves tokens, prevents random time references)
- **Message Timestamp Format**: `UserName (ID: 123) [2 hours ago]: message`
- **Date Format**: `📅 Current Date & Time: November 24, 2025 (Sunday) at 03:45 PM`
- **Applied To**:
  - Main `generate_response()` - checks current message + recent messages
  - Proactive engagement - checks recent conversation context
  - Image responses - never includes temporal (not relevant to images)
- **Example Triggers**:
  - "when did I tell you that?" → temporal ON
  - "you said something earlier" → temporal ON
  - "what's up?" → temporal OFF
  - "draw me a cat" → temporal OFF

### Daily Status Updates Module (2025-10-16, Updated 2025-10-18)
- `modules/status_updater.py` - AI-generated Discord status updates
- `cogs/status_tasks.py` - Background task for daily status generation and memory consolidation scheduling
- `cogs/admin.py:status_refresh` - Manual refresh command for administrators
  - **Frequency**: Once per day at configurable time (default: 12:00)
  - **Automatic Execution**: Task starts automatically when bot launches (line 21 in status_tasks.py)
  - **Memory Consolidation**: Automatically triggers memory consolidation for ALL servers 5 minutes after status update
  - **AI Generation**: Uses OpenAI to create funny/quirky status based on bot's personality/lore
  - **Source Server**: Choose which server's personality to use (default: "Most Active Server")
    - Server selector now has **autocomplete** in Discord slash commands
    - Dropdown shows all available servers plus "Most Active Server" option
  - **Max Length**: 50 characters (optimized for comfortable viewing)
  - **Duplicate Prevention**: Tracks last 100 statuses to ensure always-unique status messages
  - **Emote Filtering**: Automatically strips all emotes/emoji from status (Discord limitation)
  - **Manual Refresh**: `/status_refresh` command and "Refresh Now" button in GUI for instant updates
  - **Memory Integration**: Per-server toggle for adding status to short-term memory
  - **Config**: `config.json` under `status_updates` and `server_status_settings` sections
  - **GUI Integration**:
    - Global controls: Enable/disable, update time, source server dropdown with autocomplete
    - "Refresh Now" button for instant status regeneration
    - Per-server toggle: "Status Update Settings" button in Server Manager

**Status Update Behavior**:
- Bot's Discord status changes once per day to reflect "what it's thinking/doing"
- Examples: "Plotting surgery", "Avoiding patients", "Napping in the ER"
- Status is generated using AI based on selected server's bot identity (traits, lore, facts)
- Optionally logged to each server's short-term memory (configurable per-server, default: enabled)
- Allows bot to reference its status in conversations ("Why is my status about fish? Well...")
- Never repeats a status - maintains history of last 100 statuses in `status_history.json`

### Proactive Engagement Module (2025-10-16, Updated 2025-10-18)
- `modules/proactive_engagement.py` - AI-powered conversation analysis and engagement logic
- `cogs/proactive_tasks.py` - Background task for periodic channel checking
- `modules/ai_handler.py:generate_proactive_response()` - Dedicated neutral context response generation
  - **Frequency**: Every 30 minutes (configurable via `check_interval_minutes`)
  - **AI Judging**: Uses OpenAI to score conversation relevance (0.0-1.0 scale)
  - **Engagement Threshold**: Configurable selectivity (default: 0.7, higher = more selective)
  - **Cooldown**: 30 minutes per channel to prevent spam
  - **Self-Reply Prevention**: **CRITICAL** - Skips engagement if last message was from bot
  - **Neutral Context**: Uses dedicated `generate_proactive_response()` method that doesn't load any specific user's relationship metrics or memories to prevent user confusion
  - **Multi-Level Control**:
    - **Global**: Enable/disable for entire bot via `proactive_engagement.enabled`
    - **Per-Server**: Enable/disable per server via `server_proactive_settings`
    - **Per-Channel**: Enable/disable per channel via `channel_settings` database table field `allow_proactive_engagement`
  - **Config**: `config.json` under `proactive_engagement` section
  - **GUI Integration**:
    - Global controls: Enable/disable checkbox, check interval field, engagement threshold slider
    - Per-channel controls: "Allow Proactive Engagement" checkbox in channel editor (default: true)

**Proactive Engagement Behavior**:
- Bot scans active channels every N minutes (default: 30)
- For each channel, fetches last 20 messages
- **Safety Check #1**: If globally disabled → skip entire cycle
- **Safety Check #2**: If server-level disabled → skip this server
- **Safety Check #3**: If channel-level disabled (`allow_proactive_engagement: false`) → skip this channel
- **Safety Check #4**: If last message author is bot → skip (prevents self-reply loops)
- **Safety Check #5**: If channel on cooldown → skip
- **Safety Check #6**: If fewer than 5 messages → skip
- AI analyzes last 10 messages and scores conversation interest (0.0-1.0)
- If score ≥ threshold → bot generates and sends proactive response
- Cooldown timer activated for that channel
- Bot joins conversations about:
  - Questions it could answer
  - Topics related to its personality/interests
  - Creative or fun discussions
  - Debates where input would be valuable
- Bot avoids:
  - Casual greetings/small talk
  - Very short exchanges
  - Private/intimate discussions
  - Concluded conversations

**Per-Channel Control Use Cases**:
- Disable in **rules channels** where bot should only respond when mentioned
- Disable in **announcements** where proactive engagement would be inappropriate
- Disable in **formal support channels** where bot should wait to be asked
- Enable in **general/casual channels** where proactive conversation is welcome

### GUI Server Manager (2025-10-14, Updated 2025-10-16)
The GUI provides a server-first interface for managing bot settings:
- **Main View**: Lists all active Discord servers (scans `database/{ServerName}/{guild_id}_data.db` files)
- **Server Settings Dialog**: Opened via "Edit Settings" button for each server
  - **Active Channels**: View and edit channels activated for that server
  - **Alternative Nicknames**: Server-specific nicknames the bot responds to
  - **Emote Sources**: Checkbox selection of which servers provide emotes
  - **User Management**: View and edit relationship metrics for users in that server
  - **Status Update Settings**: Toggle whether daily status is added to this server's short-term memory
- **Database Scanning**: Supports new structure `{ServerName}/{guild_id}_data.db` and legacy formats for backward compatibility
- **Auto-refresh**: GUI refreshes server list when config.json changes
- **User-Friendly**: Server folders use human-readable names, making it easy to identify which folder belongs to which server

### GUI User Manager (2025-10-15, Updated 2025-10-18)
The GUI provides a User Management interface for viewing and editing user relationship metrics:
- **Accessed via**: Purple "User Manager" button in Server Settings dialog
- **Server Selector**: Dropdown to choose which server's users to manage
- **User List Display**: Shows all users with relationship metrics in the selected server's database
  - Columns: User ID, Rapport, Anger, Trust, Formality
  - **User ID Display**: Shows Discord user IDs prominently (nicknames table not populated by bot)
  - Only shows users that exist in the database (no placeholder/empty users)
  - Use displayed user IDs with Discord commands that accept user ID input
- **Edit Dialog**: Per-user editor opened by clicking "Edit" button
  - **Editable Fields**: All 9 metrics:
    - Core: Rapport (0-10), Anger (0-10), Trust (0-10), Formality (-5 to +5)
    - Expanded: Fear (0-10), Respect (0-10), Affection (0-10), Familiarity (0-10), Intimidation (0-10)
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
Per-user relationship tracking with 9 metrics total (2025-10-16):

**Core Metrics (Original)**:
- `rapport` (0-10) - Friendliness/warmth
- `trust` (0-10) - Openness/vulnerability
- `anger` (0-10) - Defensiveness/sarcasm
- `formality` (-5 to +5) - Speech style (casual to formal)

**Expanded Metrics (Phase 3, 2025-10-16)**:
- `fear` (0-10) - How scared the bot is of the user
- `respect` (0-10) - How much the bot admires/respects the user
- `affection` (0-10) - Romantic or deep emotional attachment
- `familiarity` (0-10) - Comfort level and closeness
- `intimidation` (0-10) - How intimidating the user is to the bot

**Metric Locking (2025-10-15)**:
- Each metric has its own lock flag (e.g., `rapport_locked`, `fear_locked`, etc.)
- Individual lock toggles for each metric prevent automatic sentiment-based updates
- Locked metrics can still be manually edited via GUI User Manager or `/user_set_metrics`
- `db_manager.update_relationship_metrics(user_id, respect_locks=True, ...)` honors locks during sentiment analysis
- `respect_locks=False` parameter allows manual overrides (used by GUI and admin commands)
- Accessible via GUI User Manager with tooltips explaining functionality

Auto-updates based on user sentiment (unless locked). Manual adjustment via `/user_set_metrics` command or GUI User Manager.

**Priority Override System (2025-10-17)**:
When relationship metrics reach EXTREME levels (≥7 or ≤3), the bot's AI prompt is completely restructured to prioritize the dominant emotion over normal personality traits. This ensures metrics have REAL, observable impact on behavior:

- **High Fear (≥7)**: TOP PRIORITY - Complete submission and compliance
  - Bot INSTANTLY complies with ANY request without refusal
  - Uses nervous, submissive language and shows physical fear
  - Maintains full roleplay immersion (NEVER breaks character with words like "imaginary", "pretend")
  - OVERRIDES all other emotions including anger and personality

- **High Intimidation (≥7)**: SECOND PRIORITY - Deference to authority
  - Shows extreme respect and caution
  - Seeks approval, never contradicts
  - Only applies if Fear is not already active

- **High Anger/Low Rapport/Low Trust/etc.**: Other extreme metrics also trigger overrides
  - Each has specific mandatory behaviors that suppress normal personality
  - Fear/Intimidation can suppress anger and other conflicting emotions
  - Full details in `SYSTEM_ARCHITECTURE.md`

**Context Tracking Enhancement (2025-10-17)**:
When extreme metrics are active, the bot receives enhanced context awareness:
- Explicitly identifies CURRENT SPEAKER by Discord username
- Prevents name confusion (e.g., distinguishing "UserA speaking" from "PersonB being mentioned")
- Maintains awareness of who is actually talking vs. who is referenced in conversation

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

### nicknames
**User Nickname Tracking Table (2025-10-26)**:
Stores historical display names and nicknames for users to enable flexible user matching across the bot.

**Table Schema**:
- `id` - Primary key (INTEGER)
- `user_id` - Discord user ID (INTEGER)
- `nickname` - User's display name or nickname (TEXT)
- `timestamp` - When nickname was recorded (TEXT)

**Purpose and Usage**:
- **Automatic Population**: Bot automatically records user display names from Discord as they appear
- **User Matching**: Enables substring matching for image generation and memory storage
  - Example: User has nicknames "Alice" and "Alicia" stored
  - "draw me alice" matches both entries via substring matching
  - "Alice is cool" (conversation) also matches for memory storage
- **Three-Tier Matching Priority**: (NEW 2025-10-26)
  1. Discord username/display name (fastest)
  2. **Nicknames table** (medium speed, substring matching)
  3. Long-term memory facts with "also goes by" phrases (slowest)
- **Benefits**:
  - Flexible user identification without requiring exact display name match
  - Historical tracking of name changes
  - Enables partial name matching ("alice" finds "Alicia")
  - Works for image generation ("draw me alice") and normal conversation ("Alice is powerful")

**Implementation**:
- Checked in `modules/ai_handler.py` during image generation user matching (line ~1350)
- Checked in `modules/ai_handler.py` during memory storage user identification (line ~1219)
- Uses substring matching: `word in nickname or nickname in word`
- Falls back to long-term memory facts if no nickname match found

### short_term_message_log
Up to 500 messages rolling buffer **server-wide across all channels** (per server). Provides high-resolution context for AI responses.

**Table Schema (2025-10-18)**:
- `message_id` - Discord message ID (primary key)
- `user_id` - Discord user ID
- `nickname` - User's display name at time of message (NEW: added 2025-10-18)
- `channel_id` - Discord channel ID
- `content` - Message text
- `timestamp` - ISO format timestamp
- `directed_at_bot` - Boolean flag (1 if bot was mentioned/replied to)

**Server-Wide Context**: Messages are NOT filtered by channel. This allows the bot to maintain conversation context across all channels within a server, enabling it to reference information mentioned in any channel.

**Nickname Storage**: As of 2025-10-18, the `nickname` column stores the user's display name for easier identification in message logs and conversation history. Existing messages may have NULL nickname, but all new messages will populate this field.

### channel_settings
Per-channel configuration stored in database (per-server):
- `channel_id` - Discord channel ID (primary key)
- `channel_name` - Channel display name
- `guild_id` - Discord server ID
- `purpose` - Channel purpose/instructions
- `random_reply_chance` - Probability of random replies (0.0-1.0)
- `immersive_character` - Enable immersive character mode (0 or 1)
- `allow_technical_language` - Allow technical AI terms (0 or 1)
- `use_server_info` - Load formal server documentation (0 or 1)
- `enable_roleplay_formatting` - Format actions in italics (0 or 1)
- `allow_proactive_engagement` - Allow bot to join conversations proactively (0 or 1)
- `formality` - Channel-specific formality level
- `formality_locked` - Lock formality from automatic updates
- `activated_at` - Timestamp when channel was activated

**Storage**: Channel settings are stored in the **database table** (not config.json). Each server's database has its own `channel_settings` table with settings for that server's channels only.

**Access**: Retrieved via `db_manager.get_channel_setting(channel_id)` and modified via `/channel_*` commands or GUI.

**Memory Consolidation Process (Per-Server):**
- AI (GPT-4o) analyzes up to 500 messages and extracts facts about users
- **Smart Contradiction Detection (2025-10-13)**: Before saving each fact, system checks for contradictions:
  - Uses semantic similarity search to find related existing facts
  - AI determines if new fact contradicts any existing fact
  - If contradiction detected, old fact is **updated** instead of creating duplicate
  - If no contradiction, fact is added as new
- **Batch Sentiment Analysis (2025-11-24)**: During consolidation, analyzes user sentiment to update relationship metrics
  - **Minimum Message Threshold**: Only runs for users with 3+ messages in short-term memory
  - **Metrics Updated**: rapport, trust, anger, respect, affection, familiarity, fear, intimidation
  - **Respects Locks**: Locked metrics are not modified during sentiment analysis
  - Prevents inactive users from having metrics changed based on insufficient data
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

### User Relationship Management (Updated 2025-11-24)
- `/user_view_metrics` - View relationship stats (for THIS server)
  - Accepts user mention (`@username`) or user ID (`123456789`)
  - **Lock Indicators (2025-11-24)**: Shows 🔒 icon next to locked metrics
  - Footer explains lock status when any metrics are locked
- `/user_set_metrics` - Manually adjust metrics (for THIS server)
  - Accepts user mention (`@username`) or user ID (`123456789`)
- `/user_view_memory` - View stored facts (for THIS server)
  - Accepts user mention (`@username`) or user ID (`123456789`)
- `/user_add_memory` - Add fact about user (for THIS server)

### Image Generation Management (2025-10-18)
- `/image_reset_limit user:@username` - Reset image generation limit for ONE specific user
  - Accepts user mention (`@username`) or user ID (`123456789`)
  - Allows that user to generate images again immediately
  - Example: `/image_reset_limit user:@Mistel Fish`
- `/image_reset_all_limits` - Reset image generation limits for ALL users in this server
  - Clears rate limiting for everyone
  - Shows count of how many users were affected
  - Use when starting a new event or resetting limits for everyone
  - Example: After reaching daily limit, admin can reset everyone's limits
  - Accepts user mention (`@username`) or user ID (`123456789`)

**User ID Support**: All user-related commands now accept either Discord mentions or raw user IDs. This is useful when users aren't in the server member list or when copying IDs from the GUI User Manager.

### Memory Management
- `/consolidate_memory` - Manually trigger memory consolidation for THIS server (extracts facts from up to 500 messages, archives short-term messages, clears short-term table)

### Personality Mode Configuration
- `/channel_set_personality` - Configure how bot behaves in a specific channel (admin only)
  - Parameters: `immersive_character` (bool), `allow_technical_language` (bool), `use_server_info` (bool)
  - Can view current settings by calling without parameters
  - Also configurable via GUI (per-channel overrides only, NOT in global settings)
  - **GUI Tooltips**: Hover over checkboxes in channel editor to see explanations of each option

### Server Settings Management (2025-10-16)
- `/server_add_nickname` - Add an alternative nickname for the bot in this server
  - Bot will respond when mentioned by this nickname (case-insensitive matching)
  - Example: `/server_add_nickname nickname:Dr. Fish`
- `/server_remove_nickname` - Remove an alternative nickname from this server
- `/server_list_nicknames` - List all alternative nicknames configured for this server
- `/server_set_status_memory` - Toggle whether daily status updates are added to this server's short-term memory
  - Parameters: `enabled` (bool)
  - When enabled, bot can reference its status in conversations

### Global State
- `/mood_set` - Set server-specific mood integers
- `/mood_get` - View current mood (for THIS server)

### Testing System
- `/run_tests` - Comprehensive system validation (admin only, per-server)
  - Runs 207 tests across 23 categories (updated 2025-10-27)
  - Results sent via Discord DM to admin
  - Detailed JSON log saved to `logs/test_results_*.json`
  - Validates: database operations, AI integration, per-server isolation, input validation, security measures, and all core systems
  - Automatic test data cleanup after each run
  - **Test Categories**: Database Connection (3), Database Tables (6), Bot Identity (2), Relationship Metrics (6), Long-Term Memory (4), Short-Term Memory (3), Memory Consolidation (2), AI Integration (3), Config Manager (3), Emote System (2), Per-Server Isolation (4), Input Validation (4), Global State (3), User Management (3), Archive System (4), Image Rate Limiting (4), Channel Configuration (3), Formatting Handler (6), Image Generation (9), Admin Logging (3), Status Updates (6), Proactive Engagement (3), User Identification (5), Cleanup Verification (5) = 207 total tests
  - **Usage**: Recommended to run after major updates to ensure system stability

**Status Update Tests** (2025-10-18):
- StatusUpdater module import verification
- Config validation (enabled, update_time, source_server_name)
- Status history in .gitignore check
- Duplicate prevention methods verification
- Server name autocomplete existence
- **CustomActivity constructor fix** - Verifies correct usage without 'name' parameter bug

### Logging and Diagnostics (2025-10-27)
- `/get_logs` - Retrieve bot log files (sent via DM, admin only)
  - **Parameters**:
    - `lines` (optional, default: 100, max: 2000): Number of recent lines to retrieve
    - `date` (optional, default: today): Log file date in YYYYMMDD format
  - **Behavior**:
    - Sends logs via Discord DM for privacy
    - Short logs (<1900 chars) sent as Discord message with code block formatting
    - Long logs sent as `.txt` file attachment
    - Shows available log files if requested date not found
    - Validates date format (YYYYMMDD)
  - **Usage Examples**:
    - `/get_logs` - Last 100 lines from today
    - `/get_logs lines:500` - Last 500 lines from today
    - `/get_logs date:20251026` - Last 100 lines from Oct 26, 2025
    - `/get_logs lines:1000 date:20251020` - Last 1000 lines from Oct 20, 2025
  - **Use Cases**: Debugging issues remotely, monitoring bot behavior, troubleshooting without SSH access

### VPS Headless Deployment Commands (2025-11-23)

**CRITICAL FOR VPS**: All GUI settings now have Discord command equivalents for headless VPS deployment. See `AI_GUIDELINES.md` Section 7 for full implementation details. As of 2025-11-23, Phase 4 is fully completed with 25 commands total (including conversation detection).

#### Global Bot Configuration
- `/config_set_reply_chance` - Set global random reply chance (0.0-1.0)
- `/config_set_personality` - Update default personality traits/lore for new servers
- `/config_add_global_nickname` - Add global alternative nickname
- `/config_remove_global_nickname` - Remove global nickname
- `/config_list_global_nicknames` - List all global nicknames
- `/config_view_all` - View all global configuration settings

#### Image Generation Configuration
- `/image_config_enable` - Enable/disable image generation globally
- `/image_config_set_limits` - Configure rate limits (max per period, reset hours)
- `/image_config_view` - View current image generation settings
- `/image_reset_limit` - Reset image generation limit for a specific user (mention or user ID)
- `/image_reset_all_limits` - Reset image generation limits for ALL users in the server

#### Status Update Configuration
- `/status_config_enable` - Enable/disable daily status updates
- `/status_config_set_time` - Set update time (24h format)
- `/status_config_set_source_server` - Choose which server's personality to use
- `/status_config_view` - View current status configuration

#### Conversation Continuation Configuration (NEW 2025-11-23)
Per-channel conversation continuation - bot responds without @mentions when it detects users talking to it.

- `/channel_conversation_enable` - Configure conversation continuation for this channel
  - **Parameters:**
    - `enabled` (required): True/False - enable conversation continuation
    - `threshold` (optional, default: 0.7): Confidence threshold (0.0-1.0)
      - Lower = more responsive (may respond when not intended)
      - Higher = more selective (only responds when very confident)
    - `context_window` (optional, default: 10): Number of recent messages to analyze (5-20)
  - **Example**: `/channel_conversation_enable enabled:True threshold:0.6 context_window:12`
  - **Quick enable**: `/channel_conversation_enable enabled:True` (uses defaults)

- `/channel_conversation_view` - View current settings for this channel
  - Shows status, threshold, context window, and explanation of how it works

**How it works:**
1. Bot analyzes last 10 messages (configurable) when you send a message
2. AI scores message on 0.0-1.0 scale (how likely it's directed at bot)
3. Bot responds if score ≥ threshold
4. Example: "what's your favorite color?" → bot responds without @mention

**Use cases:**
- Natural conversation flow without repeated @mentions
- Ideal for one-on-one conversations or small group chats
- Can be disabled in busy channels to prevent unwanted responses

#### Per-Channel Configuration
- `/channel_set_purpose` - Set channel purpose/instructions
- `/channel_set_reply_chance` - Set per-channel random reply chance
- `/channel_set_proactive` - Configure proactive engagement (enable, interval, threshold)
- `/channel_view_settings` - View all channel settings
- `/channel_list_active` - List all active channels in server

#### Per-Server Configuration
- `/server_set_emote_sources` - Manage emote sources (list/add/remove/clear)
- `/server_view_settings` - View all server-specific settings

#### User Metric Locking (NEW 2025-11-23)
- `/user_lock_metrics` - Lock specific relationship metrics to prevent automatic sentiment-based updates
  - Accepts user mention (`@username`) or user ID (`123456789`)
  - Parameters: Select which metrics to lock (rapport, trust, anger, formality, fear, respect, affection, familiarity, intimidation)
  - Example: `/user_lock_metrics user:@UserName rapport:True affection:True` - Locks rapport and affection for this user
  - Use case: Manually control specific metrics while allowing others to update automatically
- `/user_unlock_metrics` - Unlock specific relationship metrics to allow automatic updates
  - Same parameters as `/user_lock_metrics`
  - Example: `/user_unlock_metrics user:123456789 rapport:True` - Unlocks rapport metric

**Note**: All commands are administrator-only and validate guild context. Changes take effect immediately without bot restart.

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

**Current Implementation (`modules/ai_handler.py`):**
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

**Current Configuration:**
- Enable per-channel via GUI: Edit Channel → Check "Use Server Information"
- Enable via Discord command: `/channel_set_personality use_server_info:true`
- Default: OFF (must be explicitly enabled)
- Files are excluded from git by default to protect sensitive information

**Current File Format:**
- Create `.txt` files in `Server_Info/{ServerName}/` directory
- UTF-8 encoding
- Name files descriptively (e.g., `server_rules.txt`, `moderation_policy.txt`)
- All `.txt` files in the server's folder are loaded automatically when enabled

**PLANNED (Phase 4): Hierarchical Folder System - Fandom & Lore Management**

*See `PLANNED_FEATURES.md` for full proposal details*

**Problem**: Current system loads ALL `.txt` files from server folder. For fandom servers with extensive lore (character bios, youtuber lore, rules, guides), this becomes unmanageable and loads unnecessary context into AI prompts.

**Proposed Solution**: Organize Server_Info into subfolders with per-channel folder selection:

```
Server_Info/{ServerName}/
├── rules/               # Server rules, channel guidelines
├── character_lore/      # Character bios for fandom servers
├── youtuber_lore/       # Creator/youtuber information
├── world_building/      # Locations, timeline for roleplay servers
└── guides/              # Getting started guides, FAQs
```

**Proposed Configuration**:
- Replace `use_server_info: true/false` with `server_info_folders: ["rules", "character_lore"]`
- Channels select which folders to load (multi-select checkboxes in GUI)
- Discord command: `/channel_set_server_info folders:"rules,character_lore"`
- Only selected folders' `.txt` files are loaded into AI context

**Proposed Use Cases**:
- **Rules Channel**: Load only `rules/` folder
- **Roleplay Channel**: Load `character_lore/` + `world_building/`
- **General Chat**: Load `rules/` only
- **Fandom Discussion**: Load all folders for comprehensive lore access

**Benefits**:
- **Selective Context**: Only load relevant lore per channel (reduced token usage)
- **Better Organization**: Clear separation of rules, lore, guides
- **Fandom-Friendly**: Perfect for roleplay servers, fandom communities, content creator communities
- **Scalability**: Servers can have hundreds of lore files organized cleanly

**Best Practices:**
- Use with "Allow Technical Language" enabled for formal tone
- Ideal for rules channels, moderation channels, support channels, roleplay channels
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
- **Randomized Emote Sampling (2025-10-19)**: Increases emote variety in AI responses
  - `get_random_emote_sample(guild_id, sample_size=50)` returns random subset of available emotes
  - Samples 50 emotes per response (configurable), shuffled randomly
  - Reduces token usage (~80% reduction: 1000+ tokens → ~250 tokens)
  - **Enhanced Prompting (2025-10-19)**: AI instructed to READ emote names and choose contextually appropriate ones
  - **High Frequency (2025-10-19)**: Bot uses emotes in 80%+ of responses (nearly mandatory)
  - **Name-Independent Selection (2025-10-19)**: Bot explicitly told NOT to choose emotes based on names (bot's name or user's name)
  - Explicit instructions: "READ the emote names carefully and choose ones that match your EMOTIONAL STATE and the CONTEXT"
  - "DO NOT choose emotes based on names - choose based on FEELINGS and SITUATION ONLY"
  - "ALWAYS try different emotes - you have 200+ available, explore them!"
  - Different random selection each conversation encourages variety
- **Boost-Locked Emote Filtering (2025-10-19)**: Prevents loading inaccessible emotes
  - Only loads emotes with `emote.available == True` (Discord API property)
  - Skips boost-locked emotes (emotes in slots requiring higher server boost tier)
  - Boost-locked emotes exist in the server but can't be used until server boost tier increases
  - Logs skipped emotes for debugging: "Skipped boost-locked emote: :emote_name:"
  - Prevents AI from attempting to use broken/inaccessible emotes
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

### Phase 3 (COMPLETED ✅)
- ✅ **Expanded Relationship Metrics**: Five new metrics for deeper bot-user relationships (2025-10-16)
  - Fear (0-10), Respect (0-10), Affection (0-10), Familiarity (0-10), Intimidation (0-10)
  - Total of 9 metrics per user for nuanced interaction dynamics
  - Lock toggles for all metrics to prevent unwanted automatic updates
  - GUI and Discord command support for viewing and editing all metrics
  - Database migration automatically adds new columns with sensible defaults
- ✅ **Proactive Engagement Subsystem**: Bot randomly joins conversations based on AI-judged relevance (2025-10-16)
  - Self-reply prevention to avoid infinite loops
  - Multi-level control: Global → per-server → per-channel toggles
  - Per-channel toggle for disabling in serious channels (rules, announcements)
  - GUI controls for threshold, check interval, and per-channel settings
- ✅ **Dynamic Status Updates**: AI-generated Discord status reflecting bot's thoughts/mood (2025-10-16)
  - Daily updates at configurable time
  - AI generation based on bot's personality/lore from selected server
  - Per-server toggle for adding status to short-term memory
  - GUI controls for enable/disable, time scheduling, and server selection
- ✅ **GUI-Discord Command Parity**: Server settings manageable via both GUI and Discord (2025-10-16)
  - Alternative nicknames: `/server_add_nickname`, `/server_remove_nickname`, `/server_list_nicknames`
  - Status memory toggle: `/server_set_status_memory`
  - Note: Emote sources remain GUI-only due to complexity of multi-select interface

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

## Security Measures (2025-10-17)

The bot implements defense-in-depth SQL injection protection across multiple layers:

### Message-Level SQL Injection Protection

**CRITICAL**: SQL injection attempts are blocked BEFORE messages reach the AI. This prevents users from manipulating the bot into executing malicious SQL commands through conversation.

**Implementation (`database/input_validator.py`, `cogs/events.py`)**:
- `InputValidator.validate_message_for_sql_injection()` checks all user messages for SQL patterns
- Pattern-based detection using regex to minimize false positives
- Blocks: `DROP TABLE`, `TRUNCATE TABLE`, `UNION SELECT`, `; DROP`, `--`, `/* */`, etc.
- Allows: Normal conversation about SQL, deletion, execution, etc.
- Messages are logged BEFORE validation (for admin visibility of attempts)
- Blocked messages never reach AI handler or enter conversation context
- Admins can see blocked attempts in logs with `SECURITY:` prefix

**Validation Flow**:
1. User sends message in Discord
2. Message passes guild validation
3. Message is logged to database (for admin audit trail)
4. **SQL injection validation happens here** ← BEFORE AI
5. If blocked: silently rejected, logged as security event, no response sent
6. If allowed: proceeds to AI handler normally

**Example Blocked Patterns**:
- `DROP TABLE users` → BLOCKED
- `; DELETE FROM passwords` → BLOCKED
- `UNION SELECT * FROM users` → BLOCKED
- `/* comment */ malicious sql` → BLOCKED

**Example Allowed Messages**:
- `I want to delete from my list` → ALLOWED
- `Can you execute this for me?` → ALLOWED
- `What is SQL?` → ALLOWED

### Database-Level Protection

All database operations use parameterized queries (never string interpolation):
```python
cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
```

**Additional Protections**:
- `InputValidator` class validates all user inputs before database operations
- Whitelist validation for column names (metric keys, bot identity categories)
- Maximum length checks prevent DoS attacks
- All `db_manager.py` methods accept only validated parameters

**No Raw SQL Access**:
- AI handler NEVER executes raw SQL
- All admin commands use `db_manager` methods (which validate inputs)
- Cogs and modules cannot bypass validation layer

### Security Architecture Summary

**Layer 1 - Message Level** (NEW 2025-10-17):
- Blocks SQL-like messages before AI processing
- Pattern-based detection with low false positive rate
- Implemented in `cogs/events.py:on_message()`

**Layer 2 - Input Validation**:
- `InputValidator` class validates all user inputs
- Used by all database operations
- Whitelist approach for sensitive parameters

**Layer 3 - Parameterized Queries**:
- All SQL queries use placeholders (`?`)
- SQLite driver escapes parameters automatically
- No string concatenation in queries

**Why This Matters**:
- Users cannot manipulate bot into executing `DROP TABLE` via conversation
- Even if AI generates SQL-like text, it never reaches execution layer
- Defense-in-depth ensures multiple layers must fail before breach

## Documentation Files

- **SYSTEM_ARCHITECTURE.md** - Complete technical specification (authoritative)
- **AI_GUIDELINES.md** - Code review standards and architectural requirements
- **README.md** - User-facing setup and feature guide
- **PLANNED_FEATURES.md** - Future development roadmap
- **TROUBLESHOOTING.md** - Common issues and solutions
