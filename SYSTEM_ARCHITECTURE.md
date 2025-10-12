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
    -   **memory_correction**: User is correcting a previous bot statement
    -   **factual_question**: User is asking for verifiable information
    -   **memory_recall**: User is asking the bot to recall stored information
    -   **casual_chat**: Default category for general conversation
    
    This classification allows the bot to tailor its response strategy and maintain context awareness.
    
-   **Context Aggregation for Response Formulation:** To formulate its response, the handler will aggregate context from two sources:
    
    -   **Short-Term Context (24-Hour Sliding Window):** The full transcript of messages in the channel from the preceding 24 hours, retrieved from the Short-Term Message Log. This provides immediate conversational flow, topic awareness, and understanding of recent events.
        
    -   **Long-Term Memory (Database Query):** A query to the database for the user's profile, including summarized memory facts and relationship metrics. This provides deep, historical context.
        
-   **Expressive Emote Integration:** The final output will be processed to include relevant standard and custom server emotes based on the aggregated context and the bot's current persona.
    

### 3.2. Data Persistence & Memory Architecture (Relational Database)

All persistent data is stored in and retrieved from a relational database.

-   **User Schema:** A table for user profiles, tracking `user_id` and all known `nicknames` (historical and current).
    
-   **Bot Self-Identity Schema:** A table dedicated to the bot's persona, storing collections of personality elements. Each entry contains:
    
    -   `id`: Auto-incrementing primary key
    -   `category`: Type of personality element ("trait", "lore", or "fact")
    -   `content`: The actual personality element text
    -   `created_at`: Timestamp when added
    
    **Category Definitions:**
    - `Core Traits`: Fundamental personality characteristics (e.g., "sarcastic and witty", "a fish who can walk on land")
    - `Lore`: Background story and history (e.g., "I work as a surgeon despite having fins", "My wife died in a boating accident")
    - `Facts & Quirks`: Specific behaviors and preferences (e.g., "Dreams of being cooked at a 5-star restaurant", "Hates sharks because one ate my cousin Fred")
    
    **Auto-Population on First Run:**
    If the bot_identity table is empty on startup, the system automatically runs `scripts/populate_bot_identity.py` to create Dr. Fish's default personality with 5 traits, 5 lore entries, and 8 facts.
    
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
        
-   **Per-User Relationship Metrics Schema:** A table linking the bot to each user, containing:
    
    -   `user_id`: Discord user ID (primary key)
    -   `Anger`: Integer (0-10) - Bot's defensive/sarcastic level toward user
    -   `Rapport`: Integer (0-10) - Bot's friendliness and warmth toward user
    -   `Trust`: Integer (0-10) - Bot's openness and vulnerability with user
    -   `Formality`: Integer (-5 to +5) - Speech style from casual (-5) to formal (+5)
    -   `last_updated`: Timestamp of most recent metric change
    
    **How Metrics Affect Bot Behavior:**
    - **High Rapport (8-10)**: Casual, friendly, jokes around, uses warm emotes
    - **Low Rapport (0-3)**: Distant, brief responses, neutral/cold emotes
    - **High Trust (7-10)**: Shares personal thoughts, vulnerable, open
    - **Low Trust (0-3)**: Guarded, doesn't share personal information
    - **High Anger (7-10)**: Defensive, sarcastic, slightly rude, annoyed emotes
    - **High Formality (+3 to +5)**: Professional language, no slang
    - **Low Formality (-5 to -3)**: Slang, contractions, very casual
    
    **Automatic Metric Updates:**
    The AI Handler analyzes user sentiment after each interaction and conservatively updates metrics:
    - Compliments/kindness: +1 rapport
    - Personal sharing/vulnerability: +1 trust
    - Insults/rudeness: +1 anger, -1 rapport
    - Professional context: Adjusts formality based on situation
        
-   **Global State Schema:** A simple key-value table to store global bot states, such as the "Daily Mood."
    
    -   `state_key`: (e.g., "daily_mood_anger").
        
    -   `state_value`: The current integer value for that mood.
        
-   **Short-Term Message Log:** A table containing the full log of messages from the last 24 hours. This serves as the high-resolution, rolling buffer for the Core Interaction Handler.
    
-   **Message Archive:** A permanent, long-term table for all messages after they have been processed by the memory consolidation system. This serves as the bot's complete historical record.
    

### 3.3. Proactive Engagement Subsystem

**STATUS: NOT YET IMPLEMENTED - Planned for future development**

This component allows the bot to initiate conversation, governed by strict rules.

-   **Scheduled Event:** A task runs every 30 minutes.
    
-   **Probabilistic Activation:** The task has a 10% chance to activate. If the last message in the channel was from the bot, the activation is automatically skipped.
    
-   **Behavioral Fork (50/50 Chance):**
    
    -   **Contextual Engagement:** The system analyzes the last several messages and generates a relevant, on-topic comment.
        
    -   **Status-Based Engagement:** The system retrieves its current dynamic status message (e.g., "Pondering the existence of sharks.") and generates a message for the channel that expands on that thought, influenced by the global "Day Mood."
        

### 3.4. Automated Memory Consolidation Process

**STATUS: NOT YET IMPLEMENTED - Planned for future development**

A daily, automated background process that converts short-term message data into long-term structured memory.

1.  The process ingests the last 24 hours of messages from the **Short-Term Message Log**.
    
2.  For each user, it generates new summarized facts based on their activity.
    
3.  For each new fact, it queries the database to find if a semantically similar fact already exists for that user.
    
4.  **On Match:** Updates the existing record's `LastMentioned_Timestamp` and increments the `ReferenceCount`.
    
5.  **On No Match:** Creates a new record in the Long-Term Memory table with the new fact and its associated metadata.
    
6.  **Archive & Reset:** After processing, the system moves the 24 hours of messages from the Short-Term Message Log into the permanent **Message Archive** and then clears the Short-Term Message Log. This completes the cycle, leaving the short-term buffer empty and ready for the next 24-hour period.
    

### 3.5. Dynamic Status Subsystem

**STATUS: NOT YET IMPLEMENTED - Planned for future development**

An automated process that periodically updates the bot's Discord presence to reflect a dynamic, "thoughtful" status.

-   **Scheduled Event:** A task runs at a regular interval (once everyday after converting the short memory to long term.).
    
-   **Status Generation:**
    
    1.  The system queries the database to retrieve the bot's core identity (`lore`, `facts`, `traits`) and the current global mood integers (e.g., `daily_mood_anger`) from the **Global State Schema**.
        
    2.  This context is passed to the AI handler with a specific prompt (e.g., "Generate a short, passive thought or status message for a Discord bot pondering its existence...").
        
    3.  The AI generates a random, flavorful status text that aligns with its personality and current mood.
        
-   **Status Update:** The bot's Discord presence (e.g., "Playing: Pondering the existence of sharks.") will be updated with the newly generated text.
    

### 3.6. Ancillary Functionality Modules

Standard bot features will be implemented as separate, modular components.

-   **Slash Command Interface:** Full support for modern Discord slash commands.
    
-   **Moderation Module:** Commands for server administration (kick, ban, mute).
    
-   **Utility Module:** Tools such as polls, user info, and server stats.
    

### 3.7. Real-Time Administration Interface

**STATUS: COMPLETED ✅**

A set of secure, admin-only slash commands for live management of the bot's database.

-   **Functionality:** Provides commands to create, read, update, and delete records for the Bot's Identity, User Memories, Relationship Metrics, and Global State.
    
-   **Instantaneous Effect:** Due to the system's Real-Time Data Reliance directive, any changes made via this interface will be reflected in the bot's very next interaction.
    

This document will serve as the guiding document for the bot's development.

## 4. Project File Structure & Component Mapping

This section maps the conceptual components defined above to the final, physical file structure of the project. This is the definitive guide for the repository's organization.

**⚠️ IMPORTANT**: When adding new files or directories to the project, this file structure MUST be updated to reflect those changes. The file structure should always represent the current state of the project.

```
/
├── 📂 cogs/
│   ├── 📄 __init__.py
│   ├── 📄 admin.py
│   ├── 📄 events.py
│   ├── 📄 memory_tasks.py
│   ├── 📄 moderation.py
│   ├── 📄 settings.py
│   └── 📄 utility.py
|
├── 📂 database/
│   ├── 📄 __init__.py
│   ├── 📄 bot_data.db
│   ├── 📄 db_manager.py
│   └── 📄 schemas.py
|
├── 📂 logs/
│   └── 📄 bot_YYYYMMDD.log (daily rotating log files)
|
├── 📂 modules/
│   ├── 📄 __init__.py
│   ├── 📄 ai_handler.py
│   ├── 📄 config_manager.py
│   ├── 📄 emote_orchestrator.py
│   └── 📄 logging_manager.py
|
├── 📂 Notes/
│   └── 📄 New ideas.txt
|
├── 📂 scripts/
│   └── 📄 populate_bot_identity.py
|
├── 📂 tests/
│   ├── 📄 __init__.py
│   └── 📄 (Unit tests for modules and cogs)
|
├── 📜 .env
├── 📜 .gitignore
├── 📜 AI_GUIDELINES.md
├── 📜 config.json
├── 📜 debug.log
├── 📜 gui.py
├── 📜 main.py
├── 📜 PLANNED_FEATURES.md
├── 📜 README.md
├── 📜 requirements.txt
├── 📜 SYSTEM_ARCHITECTURE.md
├── 📜 TROUBLESHOOTING.md
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

The central component for all data persistence logic.

-   `__init__.py`: Marks the directory as a Python package, enabling imports of the manager and schemas.
    
-   `bot_data.db`: The SQLite database file containing all persistent bot data (automatically created on first run).
    
-   `db_manager.py`: The sole interface for the database. Contains all functions for data manipulation (e.g., `get_long_term_memory`, `add_long_term_memory`, `get_global_state`, `set_global_state`, `get_bot_identity`, `get_relationship_metrics`, `update_relationship_metrics`). All other parts of the bot interact with the database through this manager.
    
-   `schemas.py`: Defines the database table structures (e.g., via ORM classes or SQL statements) as described in section 3.2.

### 4.2.1. `logs/` Directory

Contains daily rotating log files for debugging and monitoring.

-   `bot_YYYYMMDD.log`: Daily log files with timestamps, log levels, and detailed information about bot operations.

### 4.2.2. `scripts/` Directory

Contains utility scripts for database management and initialization.

-   `populate_bot_identity.py`: Script that automatically populates the bot's initial personality (traits, lore, facts) on first run. Can also be run manually to reset the bot's identity.
    

### 4.3. `modules/` Directory

Contains core helper classes not directly tied to Discord's API.

-   `__init__.py`: Marks the directory as a Python package so these helper modules can be imported.
    
-   `ai_handler.py`: Interfaces with the OpenAI API, taking context from other components and returning raw text. Implements the Intent Classification System.
    
-   `config_manager.py`: Manages the loading of `config.json` and `.env` files.
    
-   `emote_orchestrator.py`: Manages the loading and replacement of custom server emotes.
    
-   `logging_manager.py`: A dedicated module to handle structured logging for debugging and monitoring.
    

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
    
-   `gui.py`: The optional graphical user interface for configuration and startup.
    
-   `main.py`: The primary entry point for the application, responsible for initializing managers and loading cogs.
    
-   `PLANNED_FEATURES.md`: Comprehensive roadmap of all planned features organized by development phase (Phase 2, 3, 4, etc.). Contains implementation details, technical requirements, and status tracking. **AI assistants must consult this file before implementing new features.**
    
-   `README.md`: The user-facing guide for quick start, setup, features overview, and basic usage.
    
-   `requirements.txt`: Lists all Python package dependencies.
    
-   `SYSTEM_ARCHITECTURE.md`: This document - the technical specification and architectural blueprint for the entire system.
    
-   `TROUBLESHOOTING.md`: Comprehensive troubleshooting guide with solutions to common issues, database problems, performance optimization, and debugging steps.
    
-   `test_file.txt`: Temporary test file (can be safely deleted).

## 5. Implementation Status

### Phase 1: COMPLETED ✅
**Bot Identity & Relationship Metrics System**

Phase 1 has been fully implemented and is production-ready.

#### Implemented Features:
- ✅ **Bot Identity Database System**: Bot's personality (traits, lore, facts) stored in and retrieved from database
- ✅ **Automatic Identity Population**: First-run script auto-populates Dr. Fish's default personality
- ✅ **Relationship Metrics**: Per-user tracking of rapport, trust, anger, and formality (0-10 scale)
- ✅ **Emotional Context Blending**: Bot adjusts responses based on both emotional topics and user relationships
- ✅ **Channel Formality System**: Channel-level formality settings with optional user-level overrides
- ✅ **Automatic Metric Updates**: AI analyzes sentiment and updates relationship metrics after interactions
- ✅ **Real-Time Administration Interface**: Full CRUD commands for bot identity, user metrics, and memories
- ✅ **Global Mood System**: Database storage for bot's daily mood states

#### Admin Commands Available:
- Bot Identity: `/bot_add_trait`, `/bot_add_lore`, `/bot_add_fact`, `/bot_view_identity`
- User Relationships: `/user_view_metrics`, `/user_set_metrics`, `/user_view_memory`, `/user_add_memory`
- Global Mood: `/bot_set_mood`, `/bot_get_mood`

### Core System Components: COMPLETED ✅
- ✅ Core Interaction Handler with Intent Classification
- ✅ Database Schema (all tables defined and in use)
- ✅ Short-Term Message Logging (24-hour rolling window)
- ✅ Long-Term Memory Storage & Retrieval
- ✅ Global State Management
- ✅ Emote Integration System
- ✅ Channel-Specific Configuration
- ✅ Structured Logging System with Daily Rotation

### Phase 2: PLANNED ⏳
**Memory Consolidation & Proactive Engagement**
- ⏳ Proactive Engagement Subsystem (30-minute scheduled checks)
- ⏳ Automated Memory Consolidation Process (daily AI-powered summarization)
- ⏳ Dynamic Status Subsystem (AI-generated status updates)
- ⏳ Semantic Similarity Checking for Memory Deduplication
