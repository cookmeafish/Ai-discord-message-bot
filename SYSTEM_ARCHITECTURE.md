
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
    
-   **Context Aggregation for Response Formulation:** To formulate its response, the handler will aggregate context from two sources:
    
    -   **Short-Term Context (24-Hour Sliding Window):** The full transcript of messages in the channel from the preceding 24 hours, retrieved from the Short-Term Message Log. This provides immediate conversational flow, topic awareness, and understanding of recent events.
        
    -   **Long-Term Memory (Database Query):** A query to the database for the user's profile, including summarized memory facts and relationship metrics. This provides deep, historical context.
        
-   **Expressive Emote Integration:** The final output will be processed to include relevant standard and custom server emotes based on the aggregated context and the bot's current persona.
    

### 3.2. Data Persistence & Memory Architecture (Relational Database)

All persistent data is stored in and retrieved from a relational database.

-   **User Schema:** A table for user profiles, tracking `user_id` and all known `nicknames` (historical and current).
    
-   **Bot Self-Identity Schema:** A table dedicated to the bot's persona, storing collections of:
    
    -   `Core Traits`: (e.g., "curious," "cautious," "a fish").
        
    -   `Lore`: (e.g., "Is a fish that can go on land and use Discord.").
        
    -   `Facts & Quirks`: (e.g., "Dreams of being cooked at a 5-star restaurant.").
        
-   **Structured Long-Term Memory Schema:** A table of user-associated memory objects, each containing:
    
    -   `Fact`: The summarized piece of information.
        
    -   `Category`: The general topic of the fact.
        
    -   `FirstMentioned_Timestamp`: The timestamp of the initial recording.
        
    -   `LastMentioned_Timestamp`: The timestamp of the most recent reinforcement.
        
    -   `ReferenceCount`: An integer counter.
        
-   **Per-User Relationship Metrics Schema:** A table linking the bot to each user, containing:
    
    -   `Anger`: Integer (0-10).
        
    -   `Rapport`: Integer (0-10).
        
    -   `Trust`: Integer (0-10).
        
    -   `Formality`: Integer (-5 to +5).
        
-   **Short-Term Message Log:** A table containing the full log of messages from the last 24 hours. This serves as the high-resolution, rolling buffer for the Core Interaction Handler.
    
-   **Message Archive:** A permanent, long-term table for all messages after they have been processed by the memory consolidation system. This serves as the bot's complete historical record.
    

### 3.3. Proactive Engagement Subsystem

This component allows the bot to initiate conversation, governed by strict rules.

-   **Scheduled Event:** A task runs every 30 minutes.
    
-   **Probabilistic Activation:** The task has a 10% chance to activate. If the last message in the channel was from the bot, the activation is automatically skipped.
    
-   **Behavioral Fork (50/50 Chance):**
    
    -   **Contextual Engagement:** The system analyzes the last several messages and generates a relevant, on-topic comment.
        
    -   **Novel Engagement:** The system generates a message on a random topic, influenced by the global "Day Mood."
        

### 3.4. Automated Memory Consolidation Process

A daily, automated background process that converts short-term message data into long-term structured memory.

1.  The process ingests the last 24 hours of messages from the **Short-Term Message Log**.
    
2.  For each user, it generates new summarized facts based on their activity.
    
3.  For each new fact, it queries the database to find if a semantically similar fact already exists for that user.
    
4.  **On Match:** Updates the existing record's `LastMentioned_Timestamp` and increments the `ReferenceCount`.
    
5.  **On No Match:** Creates a new record in the Long-Term Memory table with the new fact and its associated metadata.
    
6.  **Archive & Reset:** After processing, the system moves the 24 hours of messages from the Short-Term Message Log into the permanent **Message Archive** and then clears the Short-Term Message Log. This completes the cycle, leaving the short-term buffer empty and ready for the next 24-hour period.
    

### 3.5. Ancillary Functionality Modules

Standard bot features will be implemented as separate, modular components.

-   **Slash Command Interface:** Full support for modern Discord slash commands.
    
-   **Moderation Module:** Commands for server administration (kick, ban, mute).
    
-   **Utility Module:** Tools such as polls, user info, and server stats.
    

### 3.6. Real-Time Administration Interface

A set of secure, admin-only slash commands for live management of the bot's database.

-   **Functionality:** Provides commands to create, read, update, and delete records for the Bot's Identity, User Memories, and Relationship Metrics.
    
-   **Instantaneous Effect:** Due to the system's Real-Time Data Reliance directive, any changes made via this interface will be reflected in the bot's very next interaction.
    

This document will serve as the guiding document for the bot's development.