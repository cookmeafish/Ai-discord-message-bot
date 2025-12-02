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

## Phase 4 (COMPLETED ✅)

All Phase 4 features have been fully implemented as of 2025-11-23.

### 🚨 CRITICAL: Full Discord Command Parity with GUI (COMPLETED ✅)

**Problem Statement:**
The bot is intended for deployment on a headless VPS (Virtual Private Server) where the GUI is inaccessible or difficult to reach. Currently, many critical configuration settings can ONLY be changed through the GUI (gui.py), making remote management nearly impossible.

**Why This Is Critical:**
- VPS deployments have no display/GUI access
- SSH access doesn't easily support tkinter GUIs
- Bot operators need to configure settings without GUI access
- All GUI functionality MUST be available via Discord commands

**Status:** FULLY IMPLEMENTED - See `cogs/admin.py` lines 1891-2763

All GUI-configurable settings now have Discord command equivalents, including:
- 6 Global bot configuration commands
- 3 Image generation configuration commands
- 4 Status update configuration commands
- 5 Per-channel configuration commands
- 2 Per-server configuration commands
- 2 User metric locking commands (NEW - not in original spec)

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

- `/channel_view_settings` - View all current channel settings ✅ IMPLEMENTED
  - Shows: purpose, reply chance, personality mode, proactive settings, conversation continuation, random events
  - Each setting displays the command needed to change it

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

## Phase 5 (COMPLETED ✅)

All Phase 5 features have been fully implemented as of 2025-10-27.

### 🎯 Intelligent Conversation Continuation Detection (COMPLETED ✅)

**Status:** FULLY IMPLEMENTED - See `modules/conversation_detector.py` and integration in `cogs/events.py`

**Problem Statement:**
Currently, users must mention or reply to the bot every single time during a conversation. This creates a tedious UX where natural conversation flow is broken by constant @mentions. For example:

```
User: @Bot, what's your favorite color?
Bot: I love blue!
User: @Bot, why blue?
Bot: It reminds me of the ocean.
User: @Bot, have you been to the ocean?
Bot: No, but I dream about it!
```

This feels unnatural compared to real conversations where context flows without repeated addressing.

**Proposed Solution: Context-Aware Message Targeting**

Use GPT-4o-mini to analyze each message in context of recent conversation history and intelligently determine if the message is directed at the bot or intended for someone else.

---

#### Core Functionality

**Message Analysis Flow:**
1. User sends message in activated channel (no mention/reply to bot)
2. Bot retrieves last N messages from short-term memory (configurable, default: 10)
3. GPT-4o-mini analyzes conversation context and current message
4. AI returns confidence score (0.0-1.0) indicating if message is directed at bot
5. If score ≥ threshold (configurable, default: 0.7) → Bot replies normally
6. If score < threshold → Bot stays silent

**AI Prompt Structure:**
```
You are analyzing a Discord conversation to determine if the latest message is directed at a bot named "{bot_name}".

Recent conversation history:
{last_N_messages}

Latest message (from {user_name}): "{current_message}"

Determine if this message is:
- A continuation of the conversation with the bot
- A direct question/statement to the bot
- A response to something the bot said

Score from 0.0 to 1.0 (higher = more likely directed at bot):
- 1.0 = Clearly talking to bot (references bot's previous message, asks bot a question, continues topic bot was discussing)
- 0.5 = Ambiguous (could be for bot or someone else)
- 0.0 = Clearly NOT for bot (talking to another user, changing topic completely, general announcement)

Return ONLY a number between 0.0 and 1.0.
```

**Example Scenarios:**

**Scenario 1: Natural Conversation Flow (SHOULD REPLY)**
```
Bot: I love painting landscapes!
User: what kind of landscapes?  ← Score: 0.95 (clear continuation)
```

**Scenario 2: Conversation Shift (SHOULD NOT REPLY)**
```
Bot: I love painting landscapes!
User: @OtherUser did you finish the report?  ← Score: 0.1 (clearly for someone else)
```

**Scenario 3: Topic Change (SHOULD NOT REPLY)**
```
Bot: I love painting landscapes!
[5 messages from other users about coding]
User: anyone know Python?  ← Score: 0.2 (general question, no connection to bot conversation)
```

**Scenario 4: Ambiguous Case (Configurable Threshold Decides)**
```
Bot: I think blue is the best color.
User: what about red?  ← Score: 0.6 (could be responding to bot, or general question)
```

---

#### Configuration Options

**Per-Channel Settings (Database `channel_settings` table):**
- `enable_conversation_detection` (BOOL, default: false) - Master toggle for this feature
- `conversation_detection_threshold` (FLOAT 0.0-1.0, default: 0.7) - Confidence required to reply
- `conversation_context_window` (INT, default: 10) - How many previous messages to analyze

**Global Settings (config.json):**
```json
"conversation_detection": {
  "enabled": false,
  "default_threshold": 0.7,
  "context_window": 10,
  "model": "gpt-4.1-mini",
  "max_tokens": 10,
  "temperature": 0.0
}
```

**GUI Controls:**
- **Global Settings Panel**: Master enable/disable toggle
- **Per-Channel Settings (in Channel Editor)**:
  - Checkbox: "Enable Conversation Detection"
  - Slider: "Detection Sensitivity" (0.0-1.0, maps to threshold)
    - 0.3-0.5 = "Very Responsive" (replies often, may have false positives)
    - 0.6-0.7 = "Balanced" (good mix of responsiveness and accuracy)
    - 0.8-0.9 = "Conservative" (only replies when very confident)
  - Number field: "Context Window Size" (5-20 messages)

**Discord Commands:**
- `/channel_enable_conversation_detection` - Enable for current channel
  - Parameters: `enabled` (bool), `threshold` (optional 0.0-1.0), `context_window` (optional int)
  - Example: `/channel_enable_conversation_detection enabled:true threshold:0.7 context_window:10`
- `/channel_view_conversation_detection` - View current settings for this channel

---

#### Implementation Details

**Location:** `cogs/events.py:on_message()` and new module `modules/conversation_detector.py`

**Modified Message Flow:**
```python
# In cogs/events.py:on_message()
1. Guild validation
2. Message logging to short-term memory
3. Check if message has bot mention/reply → If YES, reply normally (skip detection)
4. Check if conversation detection enabled for channel → If NO, skip
5. Load last N messages from short-term memory
6. Call ConversationDetector.should_respond(messages, current_message, bot_id, threshold)
7. If score >= threshold → Reply normally via ai_handler
8. If score < threshold → Silent (no response)
```

**New Module: `modules/conversation_detector.py`**
```python
class ConversationDetector:
    def __init__(self, config_manager):
        self.config = config_manager.get_config()["conversation_detection"]

    async def should_respond(self, recent_messages, current_message, bot_id, threshold):
        """
        Analyzes conversation context to determine if bot should respond.

        Args:
            recent_messages: List of recent messages from short-term memory
            current_message: The message to analyze
            bot_id: Discord bot user ID
            threshold: Confidence threshold (0.0-1.0)

        Returns:
            bool: True if bot should respond, False otherwise
        """
        # Build conversation context
        context = self._format_conversation_history(recent_messages, bot_id)

        # Call GPT-4o-mini for classification
        score = await self._classify_message_target(context, current_message)

        # Log decision for debugging
        logger.info(f"Conversation detection score: {score:.2f} (threshold: {threshold})")

        return score >= threshold
```

**Database Changes:**
Add columns to `channel_settings` table:
- `enable_conversation_detection` (INTEGER, default 0)
- `conversation_detection_threshold` (REAL, default 0.7)
- `conversation_context_window` (INTEGER, default 10)

**Cost Analysis:**
- Model: GPT-4o-mini (~$0.000015 per message analysis)
- Frequency: Every non-mention message in enabled channels
- Example: 1000 messages/day = $0.015/day = ~$0.45/month per channel
- **Cost Optimization**: Only analyze if bot was part of recent conversation (last 10 messages contain at least 1 bot message)

---

#### Edge Cases & Safety Measures

**1. Explicit Mentions/Replies Override Detection**
- If user mentions bot or replies to bot → ALWAYS respond (skip detection)
- Prevents false negatives when user explicitly wants bot

**2. Conversation Recency Check**
- Only run detection if bot participated in last N messages (default: 10)
- If bot hasn't spoken recently, assume conversation moved on → don't analyze

**3. Anti-Spam Protection**
- If bot replied to user's last 3+ messages consecutively → skip detection temporarily
- Prevents bot from dominating conversation

**4. Multi-User Conversations**
- If multiple users in conversation, detection considers who bot last interacted with
- Prioritizes continuing conversation with user bot was talking to

**5. Channel-Specific Behavior**
- Support channels / Q&A channels → Lower threshold (more responsive)
- Casual channels → Higher threshold (less intrusive)

**6. Fallback to Existing Systems**
- Proactive Engagement still works independently (different trigger)
- Random replies (existing feature) still trigger independently

---

#### Benefits

✅ **Natural Conversation Flow**: Users can talk to bot like a real person, no repeated @mentions
✅ **Improved UX**: Reduces friction, makes bot feel more human-like
✅ **Configurable Sensitivity**: Admins control how responsive bot is per channel
✅ **Smart Context Awareness**: Bot understands when conversation shifted away from it
✅ **Low Cost**: GPT-4o-mini is extremely cheap (~$0.015 per 1000 messages)
✅ **No Breaking Changes**: Existing mention/reply behavior unchanged, this is purely additive

---

#### Challenges & Risks

⚠️ **False Positives**: Bot might reply when shouldn't (mitigated by threshold tuning)
⚠️ **False Negatives**: Bot might not reply when should (explicit mentions still work)
⚠️ **Increased API Costs**: Every message needs AI analysis (mitigated by using cheapest model)
⚠️ **Complexity**: Adds another layer of logic to message handling
⚠️ **Conversation Context Ambiguity**: Sometimes unclear if message is for bot

**Mitigation Strategies:**
- Default: **Disabled** (opt-in per channel, not automatic)
- Conservative threshold (0.7) prevents most false positives
- Explicit mentions override detection (safety net)
- Admin feedback loop: Track false positives/negatives, allow threshold adjustment

---

#### Testing Strategy

**Test Categories (add to `testing.py`):**
1. **Basic Detection**: Single-user conversation with bot → should detect continuation
2. **Multi-User Conversations**: Bot talking to UserA, UserB sends message → should not respond to UserB
3. **Topic Shifts**: Bot discussed topic A, user asks about topic B → configurable (threshold-dependent)
4. **Explicit Overrides**: User mentions bot → ALWAYS respond regardless of detection score
5. **Recency Check**: Bot hasn't spoken in 15 messages → skip detection entirely
6. **Edge Cases**: Empty context, bot's first message in channel, etc.

**Manual Testing Scenarios:**
1. Have natural back-and-forth conversation without @mentions → bot should continue naturally
2. Switch conversation to another user mid-chat → bot should stay silent
3. Mention bot explicitly during unrelated conversation → bot should respond immediately
4. Test various threshold values (0.3, 0.5, 0.7, 0.9) to find optimal balance

**A/B Testing:**
- Enable in one channel with threshold 0.7
- Compare user engagement (messages per conversation) vs channels without detection

---

#### Implementation Priority: 🟡 MEDIUM-HIGH

**Why Important:**
- Significantly improves user experience
- Makes bot feel more natural and conversational
- Reduces user friction (no constant @mentions)

**Why Not Critical:**
- Existing mention/reply system works fine
- Feature is purely UX enhancement, not functional requirement
- Can be rolled out gradually (per-channel opt-in)

**Estimated Complexity:** Medium
- New module: `modules/conversation_detector.py` (~150 lines)
- Modify: `cogs/events.py` message flow (~50 lines)
- Database changes: 3 new columns in `channel_settings`
- GUI updates: Checkboxes and sliders in channel editor (~100 lines)
- Discord commands: 2 new commands in `cogs/admin.py` (~80 lines)
- Tests: 8-10 new test cases in `testing.py` (~200 lines)
- Documentation: Update all MD files

**Estimated Time:** 6-8 hours for full implementation + testing

---

#### Acceptance Criteria

✅ Bot correctly identifies when message is continuation of conversation (>90% accuracy in testing)
✅ Bot stays silent when conversation shifts to other users
✅ Explicit mentions/replies ALWAYS trigger response (overrides detection)
✅ Per-channel configuration via GUI and Discord commands
✅ Cost per analyzed message < $0.00002 (GPT-4o-mini)
✅ Feature disabled by default (opt-in)
✅ Comprehensive tests added to `testing.py`
✅ All documentation updated (CLAUDE.md, SYSTEM_ARCHITECTURE.md, README.md)

---

### 🎨 Iterative Image Refinement (COMPLETED ✅)

**Status:** FULLY IMPLEMENTED - See `modules/image_refiner.py` and integration in `modules/image_generator.py`

**Problem Statement:**
Currently, when the bot generates an image that doesn't match user expectations, the user must re-submit the entire prompt with modifications. This creates friction and wastes the user's rate limit. For example:

```
User: draw a cool cat with flaming fur
Bot: [generates image of cool cat with normal fur]
User: no, I said with flaming fur! and also can you make it hold a sword in its mouth?
Bot: [treats as new request, uses another rate limit slot, might not connect to previous image]
```

Users expect to be able to iterate on images naturally, like working with a human artist who can refine their work based on feedback.

**Proposed Solution: AI-Powered Image Refinement**

Use GPT-4o-mini to detect when a user wants to refine/remake a recently generated image, then intelligently modify the original prompt based on user feedback and regenerate.

---

#### Core Functionality

**Refinement Detection Flow:**
1. Bot generates an image for a user
2. Bot stores the original prompt in memory (per-user, temporary cache)
3. User sends follow-up message
4. GPT-4o-mini analyzes message to determine if it's a refinement request
5. If YES → Extract changes, modify original prompt, regenerate image
6. If NO → Treat as normal message (conversation or new image request)

**AI Analysis Prompt Structure:**
```
You are analyzing a Discord message to determine if the user wants to refine/remake a recently generated image.

CONTEXT:
- The bot just generated an image for this user
- Original prompt: "{original_prompt}"
- Time since generation: {minutes} minutes ago

USER'S MESSAGE: "{user_message}"

Determine if this message is requesting a REFINEMENT of the previous image.

Indicators of refinement request:
✅ Corrections: "no, I said...", "you forgot the...", "it's missing..."
✅ Additions: "also add...", "can you include...", "with a sword too"
✅ Modifications: "make it bigger", "change the color to...", "make it hold..."
✅ Critiques: "that's wrong", "not what I wanted", "redo it with..."

NOT a refinement request:
❌ General conversation: "that's cool!", "I like it", "thanks"
❌ Unrelated message: "what's the weather?", "hey how are you"
❌ New image request: "now draw a dog", "draw something else"

Respond with JSON:
{
  "is_refinement": true/false,
  "confidence": 0.0-1.0,
  "changes_requested": "description of what user wants changed" (if is_refinement=true)
}
```

**Prompt Modification Process:**
Once refinement is detected, use GPT-4o to intelligently merge the original prompt with user feedback:

```
You are modifying an image generation prompt based on user feedback.

ORIGINAL PROMPT: "{original_prompt}"

USER FEEDBACK: "{changes_requested}"

Create a NEW prompt that:
1. Keeps everything from the original that wasn't criticized
2. Fixes/changes elements the user mentioned
3. Adds new elements the user requested
4. Maintains coherent scene composition

Return ONLY the new prompt (no explanations).

Example:
Original: "a cool cat with flaming fur"
Feedback: "no flaming fur, and make it hold a sword in its mouth"
New Prompt: "a cool cat holding a sword in its mouth"
```

---

#### Example Scenarios

**Scenario 1: Adding Elements**
```
User: draw a dragon
Bot: [generates dragon image]
User: can you add fire breath and make it blue?
Bot: [detects refinement, modifies prompt to "a blue dragon breathing fire", regenerates]
```

**Scenario 2: Correcting Mistakes**
```
User: draw a cool cat with flaming fur
Bot: [generates cat without flames]
User: no, I said with flaming fur!
Bot: [detects refinement, emphasizes "a cool cat with flaming fur, flames on its body", regenerates]
```

**Scenario 3: Multiple Changes**
```
User: draw a knight
Bot: [generates knight image]
User: make him hold a sword, add a red cape, and put him on a mountain
Bot: [detects refinement, modifies to "a knight holding a sword, wearing a red cape, standing on a mountain", regenerates]
```

**Scenario 4: Not a Refinement (False Positive Prevention)**
```
User: draw a cat
Bot: [generates cat image]
User: that's awesome! now draw a dog
Bot: [detects NEW request, not refinement, treats as separate image generation]
```

---

#### Implementation Details

**Location:** `modules/image_generator.py` and `modules/ai_handler.py`

**New Components:**

**1. Image Prompt Cache (Per-User)**
```python
# In modules/image_generator.py
self.recent_prompts = {
    # user_id: {
    #     "prompt": "original prompt text",
    #     "timestamp": datetime,
    #     "message_id": discord_message_id (for reference)
    # }
}
```

**Cache Management:**
- Store prompt after successful image generation
- Expire after 10 minutes (configurable via `config.json`)
- One prompt per user (overwrites on new generation)
- Clear on bot restart (in-memory only, no persistence)

**2. Refinement Detector (New Module)**
```python
# In modules/image_generator.py or new modules/image_refiner.py
class ImageRefiner:
    async def detect_refinement(self, user_id, user_message, original_prompt, minutes_ago):
        """
        Uses GPT-4o-mini to detect if message is requesting image refinement.

        Returns:
            dict: {
                "is_refinement": bool,
                "confidence": float,
                "changes_requested": str
            }
        """

    async def modify_prompt(self, original_prompt, changes_requested):
        """
        Uses GPT-4o to intelligently modify prompt based on feedback.

        Returns:
            str: Modified prompt for image generation
        """
```

**3. Modified Message Flow (in `cogs/events.py` or `modules/ai_handler.py`)**
```python
# BEFORE intent classification
if image_generator.has_recent_prompt(user_id):
    refinement_data = await image_refiner.detect_refinement(
        user_id,
        message.content,
        image_generator.get_recent_prompt(user_id)
    )

    if refinement_data["is_refinement"] and refinement_data["confidence"] >= 0.7:
        # This is a refinement request
        modified_prompt = await image_refiner.modify_prompt(
            original_prompt=refinement_data["original_prompt"],
            changes_requested=refinement_data["changes_requested"]
        )

        # Generate image with modified prompt
        await image_generator.generate_image(message, modified_prompt)
        return  # Skip normal message processing
```

---

#### Configuration Options

**Global Settings (config.json):**
```json
"image_refinement": {
  "enabled": true,
  "detection_threshold": 0.7,
  "cache_duration_minutes": 10,
  "allow_refinement_after_rate_limit": true,
  "max_refinements_per_image": 3
}
```

**Configuration Details:**
- `enabled` - Master toggle for refinement system
- `detection_threshold` - Confidence required to treat message as refinement (0.0-1.0)
- `cache_duration_minutes` - How long to remember original prompt (default: 10 minutes)
- `allow_refinement_after_rate_limit` - If true, refinements don't count toward rate limit (user-friendly)
- `max_refinements_per_image` - Prevent infinite refinement loops (default: 3)

**GUI Controls:**
- **Image Generation Settings Panel**:
  - Checkbox: "Enable Image Refinement"
  - Slider: "Refinement Detection Sensitivity" (0.0-1.0)
  - Number field: "Cache Duration (minutes)" (5-30)
  - Checkbox: "Allow Refinements After Rate Limit" (prevents frustration)
  - Number field: "Max Refinements Per Image" (1-5)

**Discord Commands:**
- `/image_refinement_config` - Configure refinement settings
  - Parameters: `enabled` (bool), `threshold` (float), `cache_duration` (int), `allow_after_limit` (bool)
  - Example: `/image_refinement_config enabled:true threshold:0.7 cache_duration:10`

---

#### Rate Limiting Behavior

**Two Possible Approaches (Configurable):**

**Approach A: Refinements Count Toward Limit (Strict)**
- User has 5 images per 2 hours
- Original image: 1/5 used
- Refinement 1: 2/5 used
- Refinement 2: 3/5 used
- Prevents abuse, but frustrates users who get bad results

**Approach B: Refinements Don't Count (User-Friendly) - RECOMMENDED**
- User has 5 images per 2 hours
- Original image: 1/5 used
- Refinement 1: still 1/5 (doesn't count)
- Refinement 2: still 1/5 (doesn't count)
- New image: 2/5 used
- **Safeguard**: Max 3 refinements per original image (prevents infinite loops)

**Implementation:**
```python
# In modules/image_generator.py
if is_refinement and config["allow_refinement_after_rate_limit"]:
    # Don't increment rate limit counter
    # But check refinement counter for this image
    if refinement_count >= config["max_refinements_per_image"]:
        await message.reply("You've reached the maximum refinements for this image. Please start fresh.")
        return
```

---

#### Edge Cases & Safety Measures

**1. Ambiguous Requests (Threshold Tuning)**
- "make it better" → Confidence: 0.5 (too vague, might not trigger)
- "add fire" → Confidence: 0.9 (clear refinement)
- Default threshold: 0.7 balances false positives/negatives

**2. Time Window Expiration**
- After 10 minutes, original prompt cache expires
- Prevents user from saying "change it" hours later
- Cache expiration configurable per server needs

**3. Multiple Users**
- Each user has separate prompt cache
- User A's refinement can't affect User B's image

**4. Refinement Loop Prevention**
- Max 3 refinements per original image (configurable)
- After max reached: "Please start with a new image request"
- Prevents user from endlessly refining same image

**5. False Positive Prevention**
- "that's cool! now draw X" → Detected as NEW request, not refinement
- "I like it, thanks" → Ignored, treated as conversation
- AI explicitly trained to distinguish appreciation from criticism

**6. Explicit New Requests Override**
- "now draw a dog" → Even if recent image exists, treated as new request
- "draw me something else" → Cache cleared, fresh start

**7. Rate Limit Integration**
- If user hit rate limit AND refinements count toward limit → Show friendly error
- If refinements don't count → Allow refinement even after limit (up to max refinements)

---

#### Benefits

✅ **Natural User Experience**: Users can iterate like working with a real artist
✅ **Reduced Frustration**: No need to re-type entire prompt after minor mistakes
✅ **Better Image Quality**: Users can refine until satisfied
✅ **Efficient Rate Limiting**: Refinements don't count (optional), encourages experimentation
✅ **Smart Detection**: AI distinguishes refinements from new requests automatically
✅ **Low Cost**: Detection uses GPT-4o-mini (~$0.00002/message), modification uses GPT-4o (~$0.0001/prompt)

---

#### Challenges & Risks

⚠️ **False Positives**: Bot might treat conversation as refinement request
⚠️ **False Negatives**: Bot might miss subtle refinement requests
⚠️ **Prompt Modification Quality**: GPT-4o might misunderstand user intent
⚠️ **Abuse Potential**: Users might spam refinements (mitigated by max count)
⚠️ **Memory Management**: Caching prompts per user adds memory overhead

**Mitigation Strategies:**
- Conservative threshold (0.7) prevents most false positives
- Max refinements per image (3) prevents spam
- Time-based expiration (10 min) limits memory usage
- GPT-4o's strong comprehension ensures accurate prompt modifications
- Detailed logging for debugging false positives/negatives

---

#### Cost Analysis

**Per Refinement Request:**
1. **Detection**: GPT-4o-mini (~$0.00002)
2. **Prompt Modification**: GPT-4o (~$0.0001) - only if refinement detected
3. **Image Generation**: Together.ai FLUX.1 ($0.002)

**Total Cost Per Refinement**: ~$0.0022 (same as original image)

**Monthly Estimate (Active Server):**
- 100 original images/month
- 30% require 1 refinement = 30 refinements
- 10% require 2 refinements = 20 refinements
- Cost: (100 × $0.002) + (50 refinements × $0.0022) = $0.20 + $0.11 = **$0.31/month**

**Very affordable** given the UX improvement.

---

#### Testing Strategy

**Test Categories (add to `testing.py`):**
1. **Refinement Detection**: "add fire" after image → should detect refinement
2. **False Positive Prevention**: "that's cool!" → should NOT detect refinement
3. **New Request Detection**: "now draw a dog" → should detect NEW request, not refinement
4. **Prompt Modification Accuracy**: Original + feedback → verify new prompt includes changes
5. **Cache Expiration**: Refinement request after 11 minutes → should fail (cache expired)
6. **Multi-User Isolation**: User A's refinement doesn't affect User B's cache
7. **Refinement Loop Prevention**: 4th refinement attempt → should be blocked
8. **Rate Limit Handling**: Refinement after rate limit → depends on config setting

**Manual Testing Scenarios:**
1. Generate image → request obvious refinement ("add X") → verify regeneration with changes
2. Generate image → say "nice!" → verify bot doesn't regenerate
3. Generate image → request 3 refinements → verify 4th is blocked
4. Generate image → wait 11 minutes → request refinement → verify error message
5. Test various feedback styles: corrections, additions, modifications

**A/B Testing:**
- Track refinement request success rate (detected correctly vs false positives/negatives)
- Monitor user satisfaction: Do refined images match expectations better?

---

#### Implementation Priority: 🟡 MEDIUM

**Why Important:**
- Major UX improvement for image generation feature
- Reduces user frustration with imperfect results
- Makes bot feel more collaborative and intelligent

**Why Not Critical:**
- Image generation already works without refinement
- Users can currently re-submit full prompts (workaround exists)
- Feature is enhancement, not core requirement

**Estimated Complexity:** Medium
- New module: `modules/image_refiner.py` (~200 lines)
- Modify: `modules/image_generator.py` (add caching, ~50 lines)
- Modify: `modules/ai_handler.py` or `cogs/events.py` (refinement detection flow, ~80 lines)
- Config updates: Add `image_refinement` section to `config.json`
- GUI updates: Refinement settings in Image Generation panel (~80 lines)
- Discord commands: 1 new command in `cogs/admin.py` (~50 lines)
- Tests: 8-10 new test cases in `testing.py` (~250 lines)
- Documentation: Update all MD files

**Estimated Time:** 5-7 hours for full implementation + testing

---

#### Acceptance Criteria

✅ Bot correctly detects refinement requests with >85% accuracy in testing
✅ Bot generates modified prompts that accurately reflect user feedback
✅ False positive rate < 10% (doesn't regenerate on "that's cool!")
✅ Refinements don't count toward rate limit (configurable)
✅ Max refinements per image enforced (prevents loops)
✅ Cache expires after configured duration (default 10 min)
✅ Multi-user isolation works correctly
✅ Comprehensive tests added to `testing.py`
✅ All documentation updated (CLAUDE.md, SYSTEM_ARCHITECTURE.md, README.md)
✅ GUI controls functional and intuitive

---

#### Integration with Conversation Detection (Phase 5 Feature)

**Synergy Opportunity:**
If both features are implemented, they complement each other:

1. User: "draw a cat" (mentions bot)
2. Bot: [generates cat image]
3. User: "add a hat" (NO mention)
   - Conversation detection: "Is this for me?" → YES (continuing conversation)
   - Refinement detection: "Is this a refinement?" → YES (adding element)
   - Bot: [regenerates with hat]
4. User: "that looks great!" (NO mention)
   - Conversation detection: "Is this for me?" → YES
   - Refinement detection: "Is this a refinement?" → NO (appreciation)
   - Bot: [responds conversationally, no regeneration]

**Both features work together** to create seamless, natural interaction.

---

### ⚡ Conversation Energy Priority Override Fix (COMPLETED ✅)

**Status:** FULLY IMPLEMENTED - See `modules/ai_handler.py:_build_relationship_context()` lines 385-420

**Problem Statement:**
The bot currently has a conversation energy matching system that adjusts response length based on user message length. However, relationship metrics (especially high affection, high rapport, etc.) sometimes override the energy constraints, causing the bot to write long verbose responses when the user sends short messages like "lol", "yeah", or "ok".

**Example of Current Broken Behavior:**
```
User: lol
Bot (with high affection): *smiles warmly at you and wraps you in a gentle hug*
     I'm so glad I could make you laugh! Your happiness means everything to me
     and I love seeing you smile like that. It brightens my whole day! :fishsmile:
```

**Expected Behavior:**
```
User: lol
Bot (with high affection): lol nice :fishsmile:
```

**Root Cause Analysis:**

After reviewing `modules/ai_handler.py`, the issue is clear:

1. **Energy System (Lines 474-573)**: Correctly calculates conversation energy and sets:
   - VERY LOW (1-3 words avg) → max_tokens=25, guidance: "Respond with 1-5 words MAX"
   - LOW (4-8 words avg) → max_tokens=40, guidance: "1 SHORT sentence or brief phrase"
   - MEDIUM (9-20 words avg) → max_tokens=60
   - HIGH (20+ words avg) → max_tokens=80

2. **Relationship Context (Lines 345-473)**: Provides guidance like:
   - "AFFECTION IS HIGH: Show warmth, protective instincts, concern for their wellbeing"
   - "RAPPORT IS HIGH: Be casual, friendly, joke around"
   - "FAMILIARITY IS HIGH: Reference inside jokes, shared history"

3. **Prompt Order (Lines 2389, 2462)**:
   - Relationship context is added FIRST
   - Energy guidance is appended AT THE END
   - **BUT**: Energy guidance is NOT given priority status like fear/intimidation metrics

**The Problem:**
When the AI sees both "AFFECTION IS HIGH: Show warmth, concern" AND "Respond with 1-5 words MAX", it interprets showing affection/warmth as more important than brevity. The relationship guidance psychologically overrides the energy constraint because it's framed as a personality requirement rather than a hard constraint.

**Comparison to Working System:**
Fear/Intimidation metrics (lines 388-408) use **PRIORITY OVERRIDE** framing:
```
🚨 CRITICAL PRIORITY OVERRIDE 🚨
⚠️ FEAR IS HIGH (7+): This OVERRIDES your normal personality...
```

This explicit priority language works perfectly - the AI never violates fear constraints.

---

#### Detailed Metric Analysis: Which Metrics Influence Message Length?

After examining the relationship context code (lines 410-467), here's a breakdown of how each metric **implicitly or explicitly** affects response length:

**Metrics That ENCOURAGE Verbosity (Longer Responses):**

1. **Trust (HIGH ≥7)** - Line 421
   - Guidance: "You can be vulnerable and share personal thoughts/feelings **openly**."
   - Effect: "Share openly" psychologically encourages elaboration and detail
   - Example impact: Instead of "yeah I get it", bot says "yeah I totally get it, I've felt that way before too"

2. **Affection (HIGH ≥7)** - Line 454
   - Guidance: "**Show warmth**, protective instincts, **concern for their wellbeing**. May use affectionate terms."
   - Effect: "Show warmth" and "concern" encourages demonstrative language
   - **This is a PRIMARY culprit**: AI interprets "showing concern" as requiring explanation/elaboration
   - Example impact: User says "lol" → Bot says "*hugs* I'm so glad I made you laugh, you mean so much to me"

3. **Familiarity (HIGH ≥7)** - Line 460
   - Guidance: "**Reference inside jokes, shared history, past conversations** naturally."
   - Effect: Encourages adding context and backstory references
   - Example impact: Instead of "lol true", bot says "lol remember when we talked about that last week? still funny"

4. **Respect (HIGH ≥7)** - Line 448
   - Guidance: "You admire this user. **Listen carefully** to their opinions, value their expertise, defer to their judgment."
   - Effect: "Listen carefully" and "value their expertise" might encourage thoughtful, detailed acknowledgment
   - Example impact: Instead of "good point", bot says "that's a really good point, I hadn't thought about it that way"

**Metrics That ENCOURAGE Brevity (Shorter Responses):**

1. **Rapport (LOW ≤3)** - Line 415
   - Guidance: "Be distant, **brief**, use neutral or slightly cold emotes."
   - **CRITICAL**: This is the ONLY metric that EXPLICITLY uses the word "brief"
   - Effect: Direct instruction to keep responses short
   - Works correctly: Low rapport = short responses ✓

2. **Trust (LOW ≤3)** - Line 423
   - Guidance: "Be guarded, **don't share too much** personal info."
   - Effect: "Don't share too much" naturally limits response length
   - Works correctly: Low trust = withholding = shorter responses ✓

3. **Anger (HIGH ≥7)** - Line 430
   - Guidance: "Be defensive, sarcastic, or slightly rude."
   - Effect: Sarcasm and defensiveness tend to be punchy and brief
   - Works correctly: Anger = curt responses ✓

4. **Affection (LOW ≤2)** - Line 456
   - Guidance: "Emotionally distant from this user. Interactions are **transactional**, not personal."
   - Effect: "Transactional" suggests brief, to-the-point exchanges
   - Works correctly: Low affection = brief, impersonal responses ✓

5. **Familiarity (LOW ≤3)** - Line 462
   - Guidance: "Treat this user like a stranger. Be more cautious, ask clarifying questions."
   - Effect: Caution typically leads to brief, safe responses (though questions can add length)
   - Mixed effect: Caution = brevity, but questions = potential verbosity

**Metrics With NO Clear Length Influence:**

1. **Formality (±5 range)** - Lines 435-438
   - Guidance: HIGH = "professional, polite language", LOW = "casual, slang, contractions"
   - Effect: Affects vocabulary/style only, not length
   - No verbosity bias ✓

2. **Fear (LOW ≤2)** - Line 444
   - Guidance: "You feel comfortable and confident around this user."
   - Effect: No length guidance, only emotional state
   - No verbosity bias ✓

3. **Intimidation (LOW ≤2)** - Line 466
   - Guidance: "This user doesn't intimidate you. Peer-level relationship, equal footing."
   - Effect: No length guidance, only power dynamics
   - No verbosity bias ✓

---

#### Summary: The Verbosity Culprits

**Primary offenders causing over-talking:**
1. **Affection (HIGH)** - "Show warmth, concern" → AI adds explanations/demonstrations
2. **Trust (HIGH)** - "Share openly" → AI elaborates on thoughts/feelings
3. **Familiarity (HIGH)** - "Reference history" → AI adds context/backstory

**Why these override energy constraints:**
- These metrics use **action verbs** ("show", "share", "reference") that psychologically demand demonstration
- The AI interprets these as REQUIREMENTS that must be fulfilled
- Energy guidance is just appended at the end, so it's treated as secondary
- No explicit instruction that brevity can STILL express these emotions

**The fix:**
Make energy a **PRIORITY OVERRIDE** that explicitly states:
- "Even if you have high affection, you MUST be brief"
- "Show warmth through emote choice, not verbosity"
- "Brevity IS a form of respect when the user is low-energy"

This reframes the relationship metrics as flexible guidelines that adapt to energy level, rather than absolute requirements.

---

#### Proposed Solution: Energy as Priority Override

Make conversation energy a **CRITICAL PRIORITY** when in VERY LOW or LOW modes, using the same override framework as fear/intimidation.

**Implementation Changes:**

**1. Modify `_build_relationship_context()` to Accept Energy Level**

Add energy level parameter and restructure guidance:

```python
def _build_relationship_context(self, user_id, channel_config, db_manager, energy_level="HIGH"):
    """
    Args:
        energy_level: One of "VERY LOW", "LOW", "MEDIUM", "HIGH"
    """
    metrics = db_manager.get_relationship_metrics(user_id)

    # ... existing metric loading ...

    # Check for priority overrides
    has_critical_energy = energy_level in ["VERY LOW", "LOW"]
    has_high_fear = 'fear' in metrics and metrics['fear'] >= 7
    has_high_intimidation = 'fear' in metrics and metrics['intimidation'] >= 7

    # PRIORITY OVERRIDE SECTION
    if has_critical_energy or has_high_fear or has_high_intimidation:
        relationship_prompt += "\n🚨 CRITICAL PRIORITY OVERRIDE 🚨\n"

        # Energy override comes FIRST (highest priority)
        if has_critical_energy:
            if energy_level == "VERY LOW":
                relationship_prompt += (
                    "⚡ **CONVERSATION ENERGY IS VERY LOW** ⚡\n"
                    "This OVERRIDES ALL relationship metrics and personality traits.\n"
                    "**ABSOLUTE REQUIREMENTS:**\n"
                    "- Respond with 1-5 words MAXIMUM (strict limit)\n"
                    "- Examples: 'lol', 'yeah', 'fair', 'nice', 'oof', ':emote:'\n"
                    "- FORBIDDEN: Full sentences, explanations, multiple thoughts\n"
                    "- Even if you have high affection/rapport/familiarity, you MUST be brief\n"
                    "- Single emote responses are PERFECT\n\n"
                    "**RATIONALE**: User is low-energy right now. Matching their brevity shows respect.\n"
                    "Long responses would feel overwhelming and out of place.\n\n"
                )
            elif energy_level == "LOW":
                relationship_prompt += (
                    "⚡ **CONVERSATION ENERGY IS LOW** ⚡\n"
                    "This OVERRIDES relationship metrics that encourage verbosity.\n"
                    "**REQUIREMENTS:**\n"
                    "- Keep responses under 10 words (strict limit)\n"
                    "- 1 SHORT sentence or brief phrase only\n"
                    "- Examples: 'yeah that makes sense', 'lol fair enough', 'sounds good :emote:'\n"
                    "- FORBIDDEN: Multiple sentences, detailed explanations\n"
                    "- Even with high affection/familiarity, stay concise\n\n"
                    "**RATIONALE**: User is being brief. Match their conversational style.\n\n"
                )

        # Fear/Intimidation overrides (existing code, comes after energy)
        if has_high_fear:
            # NOTE: Fear can make responses brief naturally, so it complements low energy
            relationship_prompt += "⚠️ FEAR IS HIGH (7+): ... (existing fear guidance)\n"
            if has_critical_energy:
                relationship_prompt += "NOTE: Low conversation energy + fear = VERY brief, nervous responses.\n"

        # ... rest of override section ...

    # Standard relationship guidance (medium/high energy only)
    else:
        # Existing rapport/trust/anger/formality guidance here
        # These only apply when energy is MEDIUM or HIGH
        pass

    return relationship_prompt
```

**2. Update Call Sites to Pass Energy Level**

```python
# In generate_response() around line 1300
energy_analysis = self._calculate_conversation_energy(short_term_memory, bot_id)

# Determine energy level for relationship context
if energy_analysis['max_tokens'] <= 25:
    energy_level = "VERY LOW"
elif energy_analysis['max_tokens'] <= 40:
    energy_level = "LOW"
elif energy_analysis['max_tokens'] <= 60:
    energy_level = "MEDIUM"
else:
    energy_level = "HIGH"

relationship_prompt = self._build_relationship_context(
    author.id,
    personality_config,
    db_manager,
    energy_level=energy_level  # NEW PARAMETER
)
```

**3. Remove Redundant Energy Guidance from Prompt**

Since energy is now baked into relationship context as a priority override, we can simplify the final prompt:

```python
# BEFORE (line 2389):
system_prompt += f"{identity_prompt}\n{relationship_prompt}\n{user_profile_prompt}\n{mentioned_users_prompt}\n{server_info}{energy_analysis['energy_guidance']}"

# AFTER:
system_prompt += f"{identity_prompt}\n{relationship_prompt}\n{user_profile_prompt}\n{mentioned_users_prompt}\n{server_info}"
# energy_guidance is now integrated into relationship_prompt as a priority override
```

**4. Strengthen max_tokens Hard Limit**

Add reminder in the prompt that max_tokens is a HARD limit:

```python
# Add to casual_chat system prompt (around line 2470)
if energy_level in ["VERY LOW", "LOW"]:
    system_prompt += (
        f"\n⚡ **TOKEN LIMIT ENFORCEMENT** ⚡\n"
        f"You have a STRICT limit of {energy_analysis['max_tokens']} tokens.\n"
        f"This is NOT a suggestion - it's a hard technical constraint.\n"
        f"The API will CUT OFF your response if you exceed this limit.\n\n"
    )
```

---

#### Key Improvements

**1. Priority-Based Override System**
- Energy constraints are now treated as **CRITICAL PRIORITY** (like fear/intimidation)
- Uses explicit "OVERRIDES ALL relationship metrics" language
- AI receives clear hierarchy: Energy > Fear/Intimidation > Relationship Metrics > Personality

**2. Explicit Rationale for AI**
- Explains WHY brevity is important: "User is low-energy right now. Matching their brevity shows respect."
- Helps AI understand that brevity IS a form of respect/affection, not coldness
- Reframes relationship metrics: "Even with high affection, stay concise"

**3. Forbidden vs. Required Format**
- Clear ❌ FORBIDDEN list: "Full sentences, explanations, multiple thoughts"
- Clear ✅ REQUIRED list: "1-5 words MAX, single emote responses are PERFECT"
- Same format that works for fear/intimidation and roleplay suppression

**4. Complementary Metric Handling**
- Fear + Low Energy = naturally reinforcing (both encourage brevity)
- Affection + Low Energy = potential conflict resolved by priority override
- Rapport + Low Energy = can still be friendly, just brief ("lol nice :emote:")

---

#### Example Behavior After Fix

**Scenario 1: High Affection + Very Low Energy**
```
User: lol
Bot: lol :fishsmile:
```
(Affection is expressed through emote choice, not verbosity)

**Scenario 2: High Rapport + Low Energy**
```
User: yeah fair
Bot: right? :fishgrin:
```
(Casual friendliness without over-talking)

**Scenario 3: High Familiarity + Very Low Energy**
```
User: oof
Bot: big oof :fishcry:
```
(Inside joke reference via emote, still brief)

**Scenario 4: High Affection + Medium Energy**
```
User: i had a rough day today
Bot: aw man, i'm sorry :fishsad: you wanna talk about it?
```
(Normal energy allows fuller expression of care)

---

#### Testing Strategy

**Test Cases (add to `testing.py`):**

1. **Very Low Energy + High Affection**
   - User: "lol"
   - Expected: 1-5 words max
   - Verify: No multi-sentence responses about warmth/care

2. **Very Low Energy + High Rapport**
   - User: "yeah"
   - Expected: 1-5 words max
   - Verify: Friendly but brief (emote + 1 word ideal)

3. **Low Energy + High Familiarity**
   - User: "that's kinda funny ngl"
   - Expected: Under 10 words
   - Verify: Can reference inside jokes but stay concise

4. **Very Low Energy + High Fear**
   - User: "good"
   - Expected: 1-5 words max, nervous tone
   - Verify: Fear and energy complement each other (both encourage brevity)

5. **Medium Energy + High Affection**
   - User: "i'm feeling kinda down today"
   - Expected: 1-2 sentences showing care
   - Verify: Energy allows fuller responses when appropriate

6. **Energy Transition Testing**
   - User alternates between "lol" and longer messages
   - Verify: Bot adjusts length accordingly without lag

**Manual Testing Protocol:**
1. Set user rapport/affection to 10 (via `/user_set_metrics`)
2. Send series of very short messages ("lol", "yeah", "ok")
3. Verify bot responds with 1-5 words consistently
4. Send longer message (15+ words)
5. Verify bot expands response appropriately
6. Return to short messages
7. Verify bot contracts again

---

#### Implementation Priority: 🟡 MEDIUM-HIGH

**Why Important:**
- Fixes a recurring UX issue that breaks immersion
- Makes conversation energy system actually work as intended
- Users frequently complain about over-talking bots

**Why Not Critical:**
- Bot is still functional, just verbose sometimes
- Workaround exists (user can send longer messages to get longer responses back)
- Doesn't break any core functionality

**Estimated Complexity:** Low-Medium
- Modify: `modules/ai_handler.py` - `_build_relationship_context()` (~100 lines modified)
- Modify: `modules/ai_handler.py` - `generate_response()` call sites (~20 lines)
- Modify: `modules/ai_handler.py` - `generate_proactive_response()` call site (~10 lines)
- Tests: 6-8 new test cases in `testing.py` (~200 lines)
- Documentation: Update CLAUDE.md, SYSTEM_ARCHITECTURE.md

**Estimated Time:** 2-3 hours for implementation + testing

---

#### Acceptance Criteria

✅ Bot responds with 1-5 words when user sends 1-3 word messages (regardless of relationship metrics)
✅ Bot responds with <10 words when user sends 4-8 word messages (regardless of relationship metrics)
✅ High affection/rapport/familiarity do NOT cause verbosity during low-energy conversations
✅ Energy priority override uses same explicit formatting as fear/intimidation overrides
✅ Bot can still express affection/rapport through emote choice and tone (not length)
✅ Energy transitions work smoothly (short → long → short messages)
✅ All relationship metrics still function normally during medium/high energy conversations
✅ Comprehensive tests added to `testing.py`
✅ Documentation updated across all MD files

---

#### Implementation Notes

**Backward Compatibility:**
- No database changes required
- No config changes required
- Existing relationship metrics continue working exactly as before
- Only affects prompt structure and priority hierarchy

**Side Benefits:**
- Cleaner prompt structure (no redundant energy guidance appended at end)
- Better AI comprehension of priority hierarchy
- Framework can be extended for other priority overrides in future
- More consistent with existing fear/intimidation override system

**Code Reuse:**
- Leverages existing priority override framework (fear/intimidation)
- Uses proven prompt formatting that already works well
- No new dependencies or modules needed

---

---

## Phase 6 (PLANNED)

### Support Ticketing System

**Problem Statement:**
Users need a way to contact server staff for help with rules, questions, and support issues. Currently there's no structured system for handling user inquiries.

**Proposed Solution: AI-Powered Ticket System**

A complete ticketing system where users can create private support tickets, receive AI-assisted answers based on Server_Info content, and escalate to staff if needed.

**CRITICAL: Complete Isolation from Chat System**
This ticketing system operates COMPLETELY SEPARATELY from the normal chat/AI response system:
- Does NOT use normal message intents (memory_storage, casual_chat, etc.)
- Does NOT access the database for user facts or relationship metrics
- Does NOT use bot personality or lore
- ONLY uses Server_Info folder content for answering questions
- Separate cog file (`cogs/tickets.py`) with no dependencies on ai_handler's chat methods

---

#### Core Functionality

**1. Ticket Button Channel Setup**
- Admin runs `/ticket_setup` to configure:
  - Ticket button channel (read-only channel with "Create Ticket" button)
  - Ticket category (where new tickets are created)
  - Closed tickets category (where resolved tickets are moved)
  - Staff role (who gets pinged on escalation)

**2. Ticket Creation Flow**
1. User clicks "Create Ticket" button in designated channel
2. Bot creates private channel `ticket-{number}` with permissions:
   - User: Read + Send messages
   - Bot: Read + Send + Manage Channel
   - Staff role: Read + Send messages
   - @everyone: No access
3. Bot sends generic (non-AI) welcome message:
   > "Thank you for contacting support. Please describe your issue and wait for a response."

**3. User Response Handling**
- **No response within 30 minutes**: Ticket auto-deleted (abandoned)
- **User describes issue**: Bot generates AI response using ONLY Server_Info context

**4. AI Response Generation**
```python
async def generate_ticket_response(self, user_message, guild_id, guild_name):
    """Generate AI response using ONLY Server_Info context - NO database access"""
    server_info = self._load_server_info(guild_id, guild_name)

    system_prompt = f"""You are a support assistant for this Discord server.
    Answer the user's question using ONLY the following server information:

    {server_info}

    If the information isn't available, politely say you cannot answer and
    a staff member will assist them.

    IMPORTANT: Do NOT use any personality, lore, or user-specific information.
    This is a neutral support context only."""

    # Call OpenAI API
    return response
```

**5. Resolution Flow**
After AI responds, two buttons appear:
- **"Resolved"** (green): Closes ticket, moves to Closed Tickets category
- **"Need More Help"** (red): Pings @staff role for human assistance

**6. Ticket Lifecycle**
- Status values: `awaiting_response`, `open`, `resolved`, `escalated`, `closed`
- Max 3 open tickets per user
- Closed tickets auto-deleted after 30 days

---

#### Database Schema

```sql
-- Ticket configuration per server
CREATE TABLE IF NOT EXISTS ticket_config (
    guild_id TEXT PRIMARY KEY,
    ticket_button_channel_id TEXT,
    ticket_category_id TEXT,
    closed_category_id TEXT,
    staff_role_id TEXT,
    next_ticket_number INTEGER DEFAULT 1
);

-- Individual tickets
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_number INTEGER NOT NULL,
    guild_id TEXT NOT NULL,
    channel_id TEXT UNIQUE,
    user_id TEXT NOT NULL,
    status TEXT DEFAULT 'awaiting_response',
    created_at TEXT NOT NULL,
    first_response_at TEXT,
    closed_at TEXT,
    close_reason TEXT
);
```

---

#### Slash Commands

| Command | Description | Permissions |
|---------|-------------|-------------|
| `/ticket_setup` | Configure ticket system (button channel, categories, staff role) | Administrator |
| `/ticket_config_view` | View current ticket configuration | Administrator |
| `/ticket_close` | Manually close a ticket (in ticket channel) | Manage Messages |
| `/ticket_add_user` | Add a user to the ticket | Manage Messages |

---

#### Configuration (config.json)

```json
"tickets": {
    "enabled": true,
    "timeout_minutes": 30,
    "max_per_user": 3,
    "retention_days": 30,
    "ai_model": "gpt-4.1-mini",
    "ai_max_tokens": 500
}
```

---

#### Implementation Files

| File | Changes |
|------|---------|
| `cogs/tickets.py` | **NEW** - Complete ticketing cog with buttons, commands, AI response |
| `database/schemas.py` | Add `ticket_config` and `tickets` tables |
| `database/db_manager.py` | Add ticket-related database methods |
| `config.json` | Add `tickets` configuration section |
| `main.py` | Register persistent button views on startup |

---

#### User Flow Summary

1. **Admin Setup**: `/ticket_setup` → configures channels, categories, staff role
2. **User Creates Ticket**: Clicks button → private channel created
3. **Initial Message**: Generic "describe your issue" (non-AI)
4. **30-min Timeout**: No response → ticket deleted
5. **User Describes Issue**: AI responds using Server_Info ONLY
6. **Resolution**:
   - Resolved → ticket closed, moved to closed category
   - Need More Help → @staff pinged, human takes over
7. **Cleanup**: Closed tickets auto-deleted after 30 days

---

#### Key Design Principles

1. **Complete Chat System Isolation**: Tickets do NOT use normal message intents, database facts, or bot personality
2. **Server_Info Only**: AI responses draw ONLY from `Server_Info/{ServerName}/` text files
3. **No User Tracking**: No relationship metrics, no memory storage, no user profiling in tickets
4. **Staff Escalation**: Clear path to human help when AI can't answer
5. **Automatic Cleanup**: Abandoned and old tickets cleaned up automatically

---

**Implementation Priority:** 🟡 MEDIUM

**Estimated Complexity:** Medium-High
- New cog with Discord UI components (Views, Buttons)
- Database schema additions
- Background tasks for timeout and cleanup
- Persistent views that survive bot restarts

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
