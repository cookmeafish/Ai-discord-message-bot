# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Bot Overview

This is an AI-powered Discord bot (Dr. Fish) with persistent memory, dynamic personality, and relationship tracking. The bot uses OpenAI's API (GPT-4.1-mini) and SQLite for data persistence.

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
The bot uses SQLite (`database/bot_data.db`). On first run, the bot automatically creates the database and populates Dr. Fish's default personality via `main.py:_populate_bot_identity_if_empty()`.

To manually repopulate bot identity:
```bash
python scripts/populate_bot_identity.py
```

## Architecture & Key Design Principles

### 1. Real-Time Data Reliance
**CRITICAL**: The system queries the database at the moment of each interaction. Never cache personality, user memory, or relationship data. Changes to the database take effect immediately.

### 2. Dual-Layer Memory System
- **Short-Term (24h)**: Full message transcripts in `short_term_message_log` table, filtered by channel
- **Long-Term**: Summarized facts in `long_term_memory` table with source attribution
- **Archive**: After memory consolidation, short-term messages are archived to `database/archive/` as JSON files before deletion

### 3. Configuration via config.json
All configurable values MUST be stored in `config.json` and accessed through `ConfigManager`. Never hardcode:
- AI model names (`ai_models.primary_model`)
- API parameters (max_tokens, temperature)
- Response limits (message counts, context window sizes)
- Timing values

See `AI_GUIDELINES.md` Section 4 for details on centralized configuration requirements.

### 4. Core Message Flow
1. `cogs/events.py:on_message()` - Receives message
2. Message logged to database via `db_manager.log_message()`
3. Intent classified via `ai_handler._classify_intent()` (5 categories: memory_storage, memory_correction, factual_question, memory_recall, casual_chat)
4. Response generated via `ai_handler.generate_response()` with:
   - Bot identity from database (`_build_bot_identity_prompt()`)
   - Relationship metrics (`_build_relationship_context()`)
   - 24h channel-specific message history
5. Sentiment analysis updates relationship metrics automatically (`_analyze_sentiment_and_update_metrics()`)

### 5. Database-Only Interface
All database operations MUST go through `database/db_manager.py`. Never write raw SQL in cogs or modules.

## Important File Locations

### Core Entry Points
- `main.py` - Bot initialization, loads cogs, auto-populates identity
- `cogs/events.py` - Message handling and AI response triggering
- `modules/ai_handler.py` - OpenAI API interface, intent classification, sentiment analysis

### Database Layer
- `database/db_manager.py` - All database operations
- `database/schemas.py` - Table definitions
- `database/bot_data.db` - SQLite database (auto-created)

### Configuration
- `config.json` - All configurable bot parameters (model names, limits, channel settings)
- `.env` - Secrets (DISCORD_TOKEN, OPENAI_API_KEY)

## Key Database Tables

### bot_identity
Stores bot personality in three categories:
- `trait` - Core personality characteristics
- `lore` - Background story and history
- `fact` - Specific behaviors and quirks

Accessed via `db_manager.get_bot_identity(category)` and `db_manager.add_bot_identity(category, content)`

### relationship_metrics
Per-user relationship tracking:
- `rapport` (0-10) - Friendliness/warmth
- `trust` (0-10) - Openness/vulnerability
- `anger` (0-10) - Defensiveness/sarcasm
- `formality` (-5 to +5) - Speech style (casual to formal)

Auto-updates based on user sentiment. Manual adjustment via `/user_set_metrics` command.

### long_term_memory
User-associated facts with source attribution:
- `fact` - The information
- `source_user_id` - Who provided it
- `source_nickname` - Display name of source
- Timestamps and reference counts

### short_term_message_log
24-hour rolling message buffer per channel. Provides high-resolution context for AI responses.

**Memory Consolidation Process:**
- AI analyzes messages from last 24h and extracts facts about users
- Facts are saved to `long_term_memory` with source attribution
- All short-term messages are then archived to `database/archive/short_term_archive_YYYYMMDD_HHMMSS.json`
- After archival, short-term table is cleared
- Triggered manually via `/consolidate_memory` command (admin only)
- Can be automated via scheduled task (currently commented out in `cogs/memory_tasks.py`)

## Admin Commands

### Bot Identity Management
- `/bot_add_trait` - Add personality trait
- `/bot_add_lore` - Add backstory/history
- `/bot_add_fact` - Add quirk/behavior
- `/bot_view_identity` - Display complete personality

### User Relationship Management
- `/user_view_metrics` - View relationship stats
- `/user_set_metrics` - Manually adjust metrics
- `/user_view_memory` - View stored facts
- `/user_add_memory` - Add fact about user

### Memory Management
- `/consolidate_memory` - Manually trigger memory consolidation (extracts facts from last 24h, archives short-term messages, clears short-term table)

### Global State
- `/bot_set_mood` - Set global mood integers
- `/bot_get_mood` - View current mood

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
  "short_term_context_messages": 10,
  "recent_messages_for_intent": 5,
  "max_response_length": 80
}
```

## Emotional Context System

The bot blends two emotional sources:
1. **Relationship metrics** - Baseline tone based on user relationship
2. **Lore-based emotions** - Topic-specific emotions (wife → sad, sharks → angry, cooking → excited)

This blending happens in `ai_handler.generate_response()` via the system prompt.

## Emote System

Custom Discord emotes are managed by `EmoteOrchestrator`:
- Loads server emotes on ready
- Provides AI with plain tags (`:fishstrong:`)
- Replaces tags with Discord format (`<:fishstrong:1234567890>`) before sending
- `_strip_discord_formatting()` in AI Handler removes Discord syntax from context to prevent AI from replicating malformed syntax

## Implementation Status

### Phase 1 (COMPLETED ✅)
- Bot identity database system
- Relationship metrics tracking
- Emotional context blending
- Intent classification
- Automatic metric updates
- Real-time admin interface

### Phase 2 (IN PROGRESS 🔧)
- ✅ Memory consolidation system (AI-powered fact extraction from 24h messages)
- ✅ Automatic archival of short-term messages to JSON before deletion
- ✅ SQLite auto-vacuum enabled for database optimization
- ⏳ Proactive engagement subsystem
- ⏳ Dynamic status updates

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

### Adding a New Admin Command
1. Add command in `cogs/admin.py`
2. Add corresponding DB method in `database/db_manager.py`
3. Test with `/command_name`

### Adding New AI Model Task
1. Add task config to `config.json` under `ai_models`
2. Use `self._get_model_config('task_name')` in AI Handler
3. Falls back to `primary_model` automatically

### Adding New Relationship Metric Guidance
Update `_build_relationship_context()` in `modules/ai_handler.py` to add prompt guidance for new metric ranges.

## Important Notes

- **No Emoji in Console Output**: Avoid emojis in print statements due to Windows console compatibility. Use text or disable logging emoji.
- **Discord Intents Required**: `messages`, `message_content`, `guilds`, `members` must be enabled in Discord Developer Portal.
- **Database Thread Safety**: SQLite connection uses `check_same_thread=False` - safe for Discord.py's async environment but not for true multi-threading.
- **Message Deduplication**: `EventsCog._processing_messages` set prevents duplicate processing of the same message ID.
- **Database Optimization**: SQLite auto-vacuum is enabled (`PRAGMA auto_vacuum = FULL`) to automatically reclaim space after message deletion during consolidation.
- **Archive Format**: Archived messages are stored as JSON with metadata: `archived_at`, `message_count`, and full `messages` array with all fields.

## Documentation Files

- **SYSTEM_ARCHITECTURE.md** - Complete technical specification (authoritative)
- **AI_GUIDELINES.md** - Code review standards and architectural requirements
- **README.md** - User-facing setup and feature guide
- **PLANNED_FEATURES.md** - Future development roadmap
- **TROUBLESHOOTING.md** - Common issues and solutions
