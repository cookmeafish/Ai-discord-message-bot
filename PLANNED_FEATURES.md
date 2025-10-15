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
- ✅ **AI Image Generation with Natural Detection** (childlike drawings via Together.ai, $0.002/image, 5/day limit) - Implemented 2025-10-15

## Phase 3 (Planned)

### Proactive Features
- ⏳ **Proactive Engagement Subsystem**: Bot randomly joins conversations based on context (30-minute checks)
- ⏳ **Dynamic Status Updates**: AI-generated Discord status reflecting bot's thoughts and mood

### Architecture Improvements

**Formality Scale Refactor**
- **Current State**: Formality uses -5 to +5 scale (different from other metrics)
- **Proposed Change**: Refactor formality to use 0-10 scale for consistency
- **Requires Changes To**:
  - `database/schemas.py` - Update relationship_metrics table schema
  - `database/db_manager.py` - Update validation logic
  - `modules/ai_handler.py` - Update relationship context prompts (lines 217-244)
  - All existing data migration scripts
- **Benefits**:
  - Consistent metric scaling across all relationship dimensions
  - Simpler mental model for users and developers
  - Easier to understand in GUI
- **Risks**: Breaking change requiring database migration
- **Priority**: Medium (quality of life improvement)

### Feature Ideas

- User-configurable memory consolidation schedules
- Export/import bot personality between servers
- Advanced relationship dynamics (jealousy, loyalty tracking)
- Multi-language support with personality adaptation
- Voice channel interaction support
- Automatic lore generation from conversations
- Relationship visualization in GUI
- Per-user personality overrides (how bot treats specific users)
- Event-triggered personality changes
- Collaborative memory (users can confirm/deny facts about themselves)

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
