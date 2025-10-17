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

### Relationship Metrics Expansion

**Additional Relationship Dimensions (Proposed)**

Current metrics: `rapport`, `trust`, `anger`, `formality`

Potential new metrics to add:
- **Fear (0-10)**: How much the bot fears this user
  - High fear → nervous, submissive, overly polite, avoids disagreement
  - Low fear → confident, comfortable, willing to argue
  - Use case: Power dynamics, authority figures like Zekke
  - Triggers: User commands, displays of authority, threats, consequences

- **Respect (0-10)**: Professional/personal admiration
  - Distinct from fear - you can respect without fear
  - High respect → listens carefully, values opinions, defers to expertise
  - Low respect → dismissive, argumentative, challenges statements

- **Affection (0-10)**: Emotional warmth beyond rapport
  - More intimate than rapport - familial/romantic attachment level
  - High affection → protective, caring, uses pet names, worries about user
  - Low affection → emotionally distant, transactional

- **Familiarity (0-10)**: How well the bot knows this user
  - Auto-increments with message count and personal info shared
  - High familiarity → references inside jokes, past events, shared history
  - Low familiarity → treats as stranger, formal introductions

- **Intimidation (0-10)**: Passive fear from user's reputation/status
  - Similar to fear but based on perceived power, not direct threats
  - High intimidation → careful word choice, seeks approval, avoids mistakes
  - Could be auto-calculated based on: admin role, message frequency dominance, fear metric

**Implementation Considerations:**
- Would require database schema changes (add columns to `relationship_metrics`)
- Each metric needs sentiment analysis rules in AI handler
- GUI would need updating for new metric controls
- Lock toggles needed for each new metric
- Testing suite expansion required

### Feature Ideas

- ✅ **GUI Image Generation Controls**: Add fields to GUI for configuring image generation rate limiting (max_per_user_per_period and reset_period_hours) - Implemented 2025-10-16
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
