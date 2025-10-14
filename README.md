# AI Discord Message Bot

This is an advanced, context-aware AI Discord bot designed for natural and engaging conversations. It features a persistent memory, a dynamic personality system, relationship tracking with users, and the ability to learn and adapt over time.

## Key Features

- **Per-Server Database Isolation**: Each Discord server gets its own database file (`database/{ServerName}_data.db`) preventing cross-contamination of data between servers. Bot personality, user relationships, and memories are completely isolated per server.

- **Advanced Conversational AI**: Responds intelligently to mentions and replies using the context of recent conversation and long-term memory.

- **Dynamic Personality System**: The bot's personality, lore, and quirks are stored in each server's database and can be edited live, allowing its character to evolve without restarts.
  - **Per-Server Personalities**: Each server can have completely different bot personalities
  - **Auto-Populated Identity**: On first `/activate`, a default bot personality is automatically set up for that server (fully customizable)
  - **Real-Time Editing**: Modify traits, lore, and facts through admin commands (per-server)

- **Relationship Metrics**: The bot tracks its relationship with each user through four metrics:
  - **Rapport** (0-10): How friendly and warm the bot is
  - **Trust** (0-10): How open and vulnerable the bot acts
  - **Anger** (0-10): How defensive or sarcastic the bot becomes
  - **Formality** (-5 to +5): Speech style from very casual to very professional
  - Metrics automatically update based on interactions and can be manually adjusted

- **Emotional Context Blending**: The bot's responses adapt based on both its relationship with users AND emotional topics in its lore (e.g., tragic backstory elements trigger sadness, hated things trigger anger).

- **Long-Term Memory**: Remembers key facts and information about users over time, leading to highly personalized interactions.

- **Expressive Emote Usage**: Intelligently uses custom server emotes to add personality and context to its messages.

- **Channel-Specific Personalities**: Each channel can have unique purpose/instructions and random reply chance settings via the GUI.

- **Immersive Character Mode**: Configurable personality system where the bot can genuinely believe it's the character (not an AI roleplaying), with natural language enforcement to eliminate robotic terms like "cached" or "database". Fully configurable per-channel for formal/technical channels.

- **Memory Consolidation (Per-Server)**: Automated system that extracts facts from conversations using GPT-4o, archives message history to JSON, and clears short-term memory. Each server's consolidation runs independently at 500 messages or via `/consolidate_memory` command.

- **Smart Memory Correction**: Bot automatically detects when you correct its memory ("Actually, my favorite color is red") and updates stored facts. Uses AI-powered contradiction detection during consolidation to prevent duplicate or conflicting information.

- **Headless & GUI Operation**: Can be configured and run via a simple graphical user interface with channel management (add/edit/remove) or managed manually for server-based operation.

- **Global Emotes**: While data is isolated per-server, the emote system remains global - the bot can use emotes from any server it's in, regardless of which server the conversation is happening in.

For a complete technical breakdown of the bot's architecture, memory systems, and long-term vision, please see the `SYSTEM_ARCHITECTURE.md` file.

For detailed Phase 1 setup instructions and feature documentation, see `PHASE1_SETUP.md`.

## Quick Start

### First-Time Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Credentials**: Create a `.env` file in the project root:
   ```
   DISCORD_TOKEN="your_discord_token_here"
   OPENAI_API_KEY="your_openai_api_key_here"
   ```

3. **Run the Bot**:
   ```bash
   python main.py
   ```
   
   Or use the GUI:
   ```bash
   python gui.py
   ```

On first startup, the bot will launch and be ready to create server-specific databases.

### Activating the Bot in Your Server

After the bot is running, go to any Discord server where the bot is installed and run:

```
/activate
```

This will:
- Create a server-specific database (`database/{ServerName}_data.db`)
- Populate the bot's default personality for THIS server only
- Initialize all necessary tables for this server

Each server gets its own isolated database with its own bot personality, user relationships, and memories!

## Configuration

### Using the GUI (Recommended for First-Time Setup)

1. Run `python gui.py`
2. Enter your Discord Bot Token and OpenAI API Key
3. Adjust global settings:
   - Random reply chance
   - **Personality Mode** checkboxes:
     - Immersive Character Mode (Bot believes it's the character)
     - Allow Technical Language (e.g., 'cached', 'database')
   - Default personality traits and lore
4. Configure channel-specific settings:
   - Add channels with custom purpose/instructions
   - Edit existing channels with the "Edit" button to configure per-channel personality mode
   - Remove channels with the "Remove" button
5. Click "Save Config" to create `.env` and `config.json`
6. Click "Start Bot" to run
7. Use "Test Memory Consolidation" button to test the memory system

### Manual Configuration (Headless/Server Mode)

1. **Create `.env`** with your credentials (see Quick Start above)

2. **Edit `config.json`** to customize bot behavior:
   ```json
   {
     "random_reply_chance": 0.05,
     "personality_mode": {
       "immersive_character": true,
       "allow_technical_language": false
     },
     "ai_models": {
       "primary_model": "gpt-4.1-mini"
     },
     "channel_settings": {
       "123456789": {
         "purpose": "General chat channel",
         "random_reply_chance": 0.05,
         "immersive_character": true,
         "allow_technical_language": false
       }
     }
   }
   ```

3. **Run**: `python main.py`

## Phase 1 Features (Implemented)

### Bot Identity Management

The bot's personality is now stored in the database and can be modified in real-time:

- `/identity_add_trait` - Add a personality trait
- `/identity_add_lore` - Add backstory/lore
- `/identity_add_fact` - Add a fact or quirk
- `/identity_view` - View complete personality

**Example**:
```
/identity_add_trait trait:loves puns and wordplay
/identity_add_lore lore:I once performed emergency surgery on a dolphin
/identity_add_fact fact:I'm allergic to tartar sauce
```

### User Relationship Management

Track and manage the bot's relationships with users:

- `/user_view_metrics` - View relationship metrics for a user
- `/user_set_metrics` - Manually adjust metrics
- `/user_view_memory` - See stored facts about a user
- `/user_add_memory` - Add a memory about a user

### Memory Management

- `/consolidate_memory` - Manually trigger memory consolidation for THIS server (admin only)
  - Extracts facts from up to 500 messages using GPT-4o
  - Archives all short-term messages to JSON files
  - Clears short-term message log (auto-vacuum reclaims space)
  - Operates only on the server where the command is run
  - Also triggers automatically when server reaches 500 messages

### Personality Mode Configuration

- `/channel_set_personality` - Configure how the bot behaves in a specific channel (admin only)
  - `immersive_character`: Bot believes it's the character (true/false)
  - `allow_technical_language`: Allow technical terms like "cached", "database" (true/false)
  - Can also be configured globally via GUI or per-channel in the GUI channel editor

**Example**:
```
/user_view_metrics user:@Username
/user_set_metrics user:@Username rapport:10 trust:8 formality:-3
```

### How Relationship Metrics Work

**Rapport** affects friendliness:
- High (8-10): Casual, jokes around, warm emotes
- Low (0-3): Distant, brief, neutral emotes

**Trust** affects openness:
- High (7-10): Shares personal thoughts, vulnerable
- Low (0-3): Guarded, doesn't share much

**Anger** affects tone:
- High (7-10): Defensive, sarcastic, annoyed
- Low (0-2): Calm and patient

**Formality** affects speech style:
- High (+3 to +5): Professional, no slang
- Low (-5 to -3): Very casual, uses contractions

Metrics automatically update based on user interactions (compliments increase rapport, insults increase anger, etc.).

## Default Bot Personality

The bot comes with a basic default personality that can be fully customized per server using admin commands.

**How to Customize:**
1. Use `/identity_add_trait [trait]` to add personality characteristics
2. Use `/identity_add_lore [lore]` to add background story elements
3. Use `/identity_add_fact [fact]` to add specific behaviors and quirks
4. Use `/identity_view` to see the current personality

**Personality Structure:**
- **Traits**: Core personality characteristics (e.g., "sarcastic", "friendly", "professional")
- **Lore**: Background story and history (e.g., "works as a chef", "grew up in the mountains")
- **Facts**: Specific behaviors and quirks (e.g., "loves puns", "afraid of heights", "dreams of traveling")

**Example Commands:**
```
/identity_add_trait trait:loves puns and wordplay
/identity_add_lore lore:grew up in a small coastal town
/identity_add_fact fact:secretly collects vintage postcards
```

Each server can have a completely different bot personality, allowing for unique experiences per community!

## Testing the System

### Comprehensive Test Suite

The bot includes a comprehensive 64-test suite that validates all core systems:

**Run All Tests**:
```
/run_tests
```

This command (admin only) runs 64 tests across 17 categories and provides:
- Results sent via Discord DM to the admin who ran the command
- Detailed JSON log saved to `logs/test_results_*.json`
- Pass/fail status with error details for debugging

**What Gets Tested**:
- Database Connection & Tables (9 tests)
- Bot Identity System (2 tests)
- Relationship Metrics (3 tests)
- Long-Term & Short-Term Memory (7 tests)
- Memory Consolidation (2 tests)
- AI Integration (3 tests)
- Config Manager (3 tests)
- Emote System (2 tests)
- Per-Server Isolation (4 tests)
- Input Validation & Security (4 tests)
- Global State Management (3 tests)
- User Management (3 tests)
- Archive System (4 tests)
- Image Rate Limiting (4 tests)
- Channel Configuration (3 tests)
- Cleanup Verification (5 tests)

**When to Run Tests**:
- After major updates or configuration changes
- Before deploying to production
- When troubleshooting unexpected behavior
- To verify per-server database integrity

All test data is automatically cleaned up after each run.

### Manual Testing Examples

### Test Basic Personality
```
@Bot tell me about yourself
```
Bot should reference its database personality.

### Test Emotional Topics
```
@Bot tell me about [topic from bot's lore]
@Bot what do you think about [thing mentioned in bot's facts]?
```
Bot should respond with appropriate emotions based on its configured personality and lore.

### Test Relationship Metrics
```
/user_set_metrics user:@YourUsername rapport:10 trust:10
```
Talk to the bot - it should be very friendly and open.

```
/user_set_metrics user:@YourUsername rapport:0 anger:10
```
Talk to the bot - it should be cold and defensive.

### Test Auto-Updates
```
/user_set_metrics user:@YourUsername rapport:5
@Bot you're the best bot ever!
/user_view_metrics user:@YourUsername
```
Rapport should have increased to 6.

## Project Structure

```
/
├── cogs/               # Discord command handlers and event listeners
├── database/           # Database manager and schemas
├── logs/              # Daily rotating log files
├── modules/           # Core helper classes (AI, config, emotes, logging)
├── scripts/           # Utility scripts (e.g., populate_bot_identity.py)
├── tests/             # Unit tests
├── testing.py         # Comprehensive 64-test suite (accessible via /run_tests)
├── config.json        # Bot configuration
├── .env              # Credentials (not in git)
├── main.py           # Entry point
└── gui.py            # Optional GUI
```

See `SYSTEM_ARCHITECTURE.md` for detailed component descriptions.

## Database

The bot uses **per-server SQLite databases** (`database/{ServerName}_data.db`) with the following tables in each:

- `bot_identity` - Bot's personality (traits, lore, facts) - unique per server
- `relationship_metrics` - Per-user relationship tracking (auto-created on first interaction)
- `long_term_memory` - Facts about users with source attribution
- `global_state` - Server-specific bot states (moods, etc.)
- `short_term_message_log` - Up to 500 messages rolling buffer (server-wide, not per-channel)
- `database/archive/` - JSON archives of consolidated messages (per-server)
- `Server_Info/` - Text files with server rules, policies, and formal information (in root directory)

**Per-Server Isolation**: Each server has completely separate data. Bot personality, user memories, and relationship metrics do not cross between servers.

**Server-Wide Context**: Short-term memory includes messages from ALL channels in the server, allowing the bot to maintain context across channels.

**Server Information**: Store server rules, policies, and formal documentation as `.txt` files in `Server_Info/` directory (located in project root). Enable per-channel via GUI to make the bot reference these files when responding (ideal for rules/moderation channels).

**SQLite Optimization**: Auto-vacuum is enabled to automatically reclaim space after message deletion.

**Database Management**: `database/multi_db_manager.py` handles creation and access to all server databases. Use `bot.get_server_db(guild_id, server_name)` to access a specific server's database.

You can edit individual server databases directly using any SQLite browser (e.g., DB Browser for SQLite).

## Troubleshooting

For common issues and solutions, see the dedicated **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** guide.

Quick fixes:
- **Bot not starting?** Check `.env` file has correct tokens
- **Personality not working?** Use `/identity_view` to verify database
- **Metrics not updating?** Check console logs for "Updated metrics" messages
- **Commands not showing?** Wait up to 1 hour for Discord to sync slash commands
- **Bot behaving unexpectedly?** Run `/run_tests` to validate system integrity

For detailed solutions, log file locations, and advanced troubleshooting, see TROUBLESHOOTING.md.

## Phase 2 Status (COMPLETED ✅)

All Phase 2 features have been implemented:
- ✅ **Per-Server Database Isolation**: Separate database file per Discord server
- ✅ **Memory Consolidation System**: AI-powered fact extraction using GPT-4o
- ✅ **Smart Contradiction Detection**: Prevents duplicate/conflicting facts during consolidation (2025-10-13)
- ✅ **Natural Memory Correction**: Bot updates facts when users make corrections (2025-10-13)
- ✅ **Message Archival**: Automatic JSON backup before deletion (per-server)
- ✅ **Auto-trigger Consolidation**: Runs when server reaches 500 messages
- ✅ **Database Optimization**: SQLite auto-vacuum enabled
- ✅ **GUI Channel Management**: Add, edit, and remove channels
- ✅ **Immersive Character Mode**: Bot believes it's the character, not an AI
- ✅ **Natural Language Enforcement**: Eliminates robotic terms in all intents
- ✅ **Per-Channel Personality Mode**: Configure immersion/technical language per channel
- ✅ **GUI Personality Controls**: Checkboxes for global and per-channel personality settings
- ✅ **Bot Self-Lore Extraction**: Automated extraction of relevant lore for emotional context (2025-10-13)
- ✅ **Comprehensive Testing Suite**: 64-test suite validating all systems via `/run_tests` (2025-10-13)

## Phase 3 (Planned)

Upcoming features:
- ⏳ **Automated Daily Consolidation**: Optional scheduled consolidation per server
- ⏳ **Dynamic Status Updates**: Bot updates its Discord status with AI-generated thoughts
- ⏳ **Proactive Engagement**: Bot randomly joins conversations based on context
- ⏳ **Database Migration Tool**: Import old single-database data to per-server format

## Documentation

- **README.md** (this file) - Quick start, setup, and feature overview
- **TROUBLESHOOTING.md** - Common issues and detailed solutions
- **PLANNED_FEATURES.md** - Development roadmap and future features
- **SYSTEM_ARCHITECTURE.md** - Technical specification and architecture (for developers)
- **AI_GUIDELINES.md** - Guidelines for AI assistants working on this project

## Support

For issues or questions, check the documentation files or review the console logs in the `logs/` directory.
