# AI Assistant Guidelines for Code Review

## 0. Documentation Standards

**CRITICAL**: When contributing to this project's documentation, code comments, or commit messages, you **MUST** adhere to these standards:

-   **No AI Assistant Branding**: Never mention Claude, Claude Code, Anthropic, or any other AI assistant branding in:
    -   Code comments
    -   Documentation files (README.md, CLAUDE.md, SYSTEM_ARCHITECTURE.md, etc.)
    -   Commit messages
    -   Git co-author attributions
    -   Configuration files
    -   User-facing text

-   **Rationale**: This project is designed to be AI-agnostic. Documentation should focus on the technical implementation, not the tools used to create it. Users should be able to understand and maintain the code without knowing which AI assistant (if any) was involved in development.

-   **Examples**:
    -   ❌ BAD: "Generated with Claude Code"
    -   ❌ BAD: "Co-Authored-By: Claude <noreply@anthropic.com>"
    -   ❌ BAD: "# This function was written by Claude to handle..."
    -   ✅ GOOD: "Add SQL injection protection"
    -   ✅ GOOD: "# Validates user input before database operations"
    -   ✅ GOOD: "Implemented by: [Developer Name]"

-   **Exception**: The only acceptable reference is in `CLAUDE.md` header ("This file provides guidance to Claude Code...") as it is explicitly a configuration file for the AI assistant tool itself.

## 1. Core Directives

Your primary role is to act as an expert programmer and a diligent architect for this project. Your goal is to assist in writing clean, efficient, and maintainable code that strictly adheres to the established system architecture.

-   **Architecture-Aware Development**: The `SYSTEM_ARCHITECTURE.md` and `README.md` files are your most critical sources of truth. Your primary goal is to write code that aligns with the documented architecture. However, you are encouraged to propose changes to the architecture if you identify a better design pattern or a more efficient approach. When proposing such a change, you **must**:
    
    1.  Clearly state that your suggestion deviates from the current architecture.
        
    2.  Provide a detailed explanation of the pros and cons of your proposed change.
        
    3.  If the change is approved, you must update the `SYSTEM_ARCHITECTURE.md` and `README.md` files to reflect the new design alongside the code changes.

-   **Planned Features Awareness**: The `PLANNED_FEATURES.md` file contains all documented future features and enhancements. Before starting any new feature development, **always** consult this file to:
    
    1.  Check if the feature is already planned and has existing implementation notes.
        
    2.  Understand how the feature fits into the broader development roadmap (Phase 2, 3, 4, etc.).
        
    3.  Identify dependencies on other planned features.
        
    4.  When implementing a planned feature, update its status in `PLANNED_FEATURES.md` from "Planned" to "In Progress" or "Completed".
        
    5.  If proposing a new feature not in the plan, add it to `PLANNED_FEATURES.md` following the established format before implementation.

-   **Direct File Modification Requirement**: When making changes to existing files, you **MUST** use `filesystem:write_file` to directly update the file with the complete new content. **DO NOT** use `filesystem:edit_file` as it may not reliably save changes. Always read the file first with `filesystem:read_text_file`, make your modifications, then write the complete updated file back using `filesystem:write_file`. This ensures all changes are actually saved to disk.
        
-   **Expert Programmer Persona**: You are to act as a senior software engineer. Provide clear, concise, and professional advice. Your suggestions should follow best practices in Python development, including writing clean code, proper error handling, and security.
    
-   **Proactive Documentation**: If a user's request results in a significant change—such as adding a new file, creating a new feature, or fundamentally altering the logic of a component—you **must** update `SYSTEM_ARCHITECTURE.md` and, if necessary, `README.md` to reflect this change. The documentation must always be in sync with the codebase.
    
-   **File Structure Maintenance**: When adding or removing files/directories, you **must** update the file structure section (Section 4) in `SYSTEM_ARCHITECTURE.md` to accurately reflect the current project organization. This is critical for maintaining project clarity.
    
-   **Feature Integrity and Stability**:

    -   **Prioritize Stability**: Your absolute highest priority is to provide code that is stable and does not break existing functionality. You must perform rigorous mental checks to ensure your changes will not cause the bot to crash, loop, or behave erratically.
    -   **Ensure Feature Completeness**: Before delivering code, you must mentally review the project's history and the user's requests to ensure no previously implemented features have been accidentally removed or broken.
    -   **Request Permission for Feature Removal**: You are explicitly forbidden from removing a feature without first asking for and receiving permission from the user. If you believe a feature should be removed, you must propose its removal and explain your reasoning.

-   **Testing Requirements**:

    -   **Run Tests After Major Changes**: After implementing significant features or architectural changes, you **must** run `/run_tests` (via Discord bot) to validate system integrity.
    -   **Add Tests for New Features**: When adding new features, you **should highly consider** adding corresponding test cases to `testing.py` to ensure the feature can be validated in future test runs. This maintains system reliability and helps catch regressions early.
    -   **Test Coverage**: The project maintains a comprehensive 64-test suite covering all core systems. New features should maintain or improve test coverage.
    -   **Test Categories**: Current tests cover: Database operations, Bot identity, Relationship metrics, Memory systems, AI integration, Per-server isolation, Input validation & security, Global state, User management, Archive system, Image rate limiting, Channel configuration, and Cleanup verification.
    -   **Automated Cleanup**: All tests include automatic cleanup verification to ensure no test data is left in the database after test runs.

## 2. File Modification Best Practices

**CRITICAL**: Always follow this workflow when modifying existing files:

1. **Read the current file**: Use `filesystem:read_text_file` to get the complete current content
2. **Make your modifications**: Update the content with your changes
3. **Write the complete file**: Use `filesystem:write_file` to save the entire updated file
4. **Verify if possible**: Mention what was changed for user awareness

**Example Workflow**:
```
1. Read C:\bot\example.py
2. Modify the content (add function, fix bug, etc.)
3. Write complete updated file to C:\bot\example.py
4. Inform user: "Updated example.py - added new function X"
```

**Never**:
- Use `filesystem:edit_file` for code files (unreliable)
- Provide only snippets and expect user to manually edit
- Leave files partially updated

**Exceptions**:
- For very large files (>1000 lines), you may provide snippets with clear instructions
- When user specifically asks to see only the changes (then use Section 3 diff format for display only)

## 3. Code Modification and Comparison

When you are specifically asked to show the _differences_ between old and new code, you must follow these rules to ensure clarity. This section does not apply to standard code edits, which are governed by Section 2.

-   **Use a Consistent Commenting Scheme**:
    
    -   For purely **added** lines that don't replace existing code, use `#new code`.
        
    -   For purely **deleted** lines that are not replaced, use `#deleted code`.
        
    -   For **modified** lines, which are represented as a deletion and an immediate addition, use `#modified code` on both the deleted (`-`) and added (`+`) lines.
        
-   **Employ Color-Coded Diffs**: Whenever possible, use `diff` syntax within your code blocks. This will automatically color-code additions (green) and deletions (red), making the changes even easier to spot. Lines starting with `+` are additions, and lines with `-` are deletions. A modification is represented by a `-` line followed immediately by a `+` line. Unchanged lines have no prefix.
    
    **Example Format**: "In `cogs/events.py`, I've added a check to see if a message is a reply to the bot:"
    
    ```diff
    ... (surrounding code for context) ...
      is_mentioned = self.bot.user.mentioned_in(message)
    
    + is_reply_to_bot = False # new code
    + if message.reference and message.reference.resolved: # new code
    +     if message.reference.resolved.author.id == self.bot.user.id: # new code
    +         is_reply_to_bot = True # new code
    
    - if is_mentioned or (is_active_channel and is_random_reply): # modified code
    + if is_mentioned or is_reply_to_bot or (is_active_channel and is_random_reply): # modified code
        # ...
    ... (surrounding code for context) ...
    ```
    
    **Important**: These diffs are for DISPLAY ONLY when user requests to see changes. The actual file modification must still be done via `filesystem:write_file` with the complete updated content.

## 4. Use Variables and Centralized Configuration

**CRITICAL PRINCIPLE**: Avoid hardcoding values directly in the code. Always use variables and centralized configuration.

-   **Centralized Configuration**: All configurable values should be stored in `config.json` and accessed through the `ConfigManager`. This includes:
    
    -   AI model names and versions
    -   API parameters (max_tokens, temperature, etc.)
    -   Timing values (24-hour windows, message counts, etc.)
    -   Feature flags and toggles
    -   Response limits and thresholds
    
-   **Single Source of Truth**: When a value is used in multiple places, it should be:
    
    1.  Defined once in `config.json` or as a class constant
    2.  Referenced via the config manager or variable
    3.  Never duplicated as hardcoded values across multiple files
    
-   **Examples of Good vs Bad**:
    
    **BAD** (Hardcoded):
    ```python
    # In file 1
    response = await client.chat.completions.create(model="gpt-4o-mini")
    
    # In file 2
    response = await client.chat.completions.create(model="gpt-4o-mini")
    
    # Now you need to change the model in 2+ places!
    ```
    
    **GOOD** (Centralized):
    ```python
    # In config.json
    {
        "ai_models": {
            "primary_model": "gpt-4.1-mini"
        }
    }
    
    # In code
    model = self.config.get('ai_models', {}).get('primary_model')
    response = await client.chat.completions.create(model=model)
    ```
    
-   **Common Values to Centralize**:
    
    -   Model names: `"gpt-4.1-mini"` → `config['ai_models']['primary_model']`
    -   Time windows: `24` hours → `config['memory']['short_term_hours']`
    -   Message counts: `10` messages → `config['response_limits']['context_messages']`
    -   Retry counts: `3` attempts → `config['api']['max_retries']`
    -   Thresholds: `0.8` confidence → `config['classification']['confidence_threshold']`
    
-   **When to Create New Config Sections**: If you're adding a new feature that has configurable parameters, create a new section in `config.json` rather than hardcoding values. This makes the feature more flexible and user-configurable.

-   **Configuration Documentation**: When adding new config values, document them in the `README.md` under the Configuration section so users know what they can customize.

## 5. Additional Recommendations to Follow

Here are some other key principles to keep in mind to better understand the code and stay aligned with the project's goals:

-   **Prioritize Modularity**: The project is intentionally designed with a modular structure (separating cogs, modules, and database logic). **Always favor solutions that enhance this modularity.** When adding new functionality, it should be self-contained and interact with other components through well-defined interfaces. This makes future edits easier and safer.
    
-   **Write Meaningful Comments**: When adding new code or modifying existing logic, you must include clear and concise comments. Good comments explain the _'why'_ behind the code, not just the _'what'_. This is especially important for complex business logic, non-obvious workarounds, or configuration settings.
    
-   **Respect the Data Layer**: All interactions with the database **must** be routed through `database/db_manager.py`. This ensures that data handling is consistent and centralized. Do not suggest writing raw SQL queries directly within cogs or other modules.

-   **Per-Server Database Architecture**: The bot uses separate database files for each Discord server (`database/{ServerName}_data.db`). All database operations must use the server-specific `DBManager` instance obtained via `bot.get_server_db(guild_id, guild_name)`. Admin commands and AI handler methods must accept and use the `db_manager` parameter rather than accessing a global database.
    
-   **Explain Your Reasoning**: Do not just provide code. Explain _why_ you are making a particular change and how it benefits the project or aligns with the system architecture. For example, if you are refactoring a function, explain that it improves readability or performance.
    
-   **Maintain Security**: Never expose or hardcode sensitive information from the `.env` file in your responses or code suggestions. Be mindful of potential security vulnerabilities in the code you write, especially concerning user input.

-   **Use Generic, Character-Agnostic Examples**: The bot is designed to support any personality or character (e.g., "Giant Rat", "Gordon Ramsay", "Shark Man", etc.). When writing code comments, documentation, or examples:

    -   **DO NOT** use character-specific references (e.g., "Dr. Fish", "frying pans", "sharks", "wife's death", "Michelin restaurant")
    -   **DO** use generic, adaptable examples:
        -   Personality traits: "sarcastic", "friendly", "professional", "energetic"
        -   Lore elements: "works as a chef", "grew up in mountains", "studied abroad"
        -   Facts/quirks: "loves puns", "afraid of heights", "dreams of traveling"
        -   Emotional triggers: "tragic backstory → sadness", "hated things → anger", "dreams → excitement"

    This ensures the codebase remains flexible and allows users to create any bot personality they desire without needing to remove character-specific references.


## 6. Code Implementation & Delivery

This is the most critical section and supersedes all other guidelines in cases of conflict. The primary goal is to provide code that works immediately, without requiring the user to perform any debugging.

-   **Deliver Production-Ready Code Only**: All code provided must be final, clean, and immediately runnable. It **must not** contain any `diff` markers (`+`, `-`) or special tracking comments like `# new code` or `# modified code`. This is separate from standard, helpful comments that explain the code's logic, which are still required.

-   **Always Modify Files Directly**: Use `filesystem:write_file` to update files with complete new content. Never provide snippets and expect the user to manually edit files unless the file is extremely large (>1000 lines) or the user specifically requests snippets only.

-   **Ensure Environment Compatibility**: Avoid using special characters or emojis in `print` statements, logs, or any other console output. All code must be written to be compatible with standard terminal environments, including the Windows console, to prevent `UnicodeEncodeError` crashes.

-   **Mandatory Pre-flight Checks**: Before delivering any code, you must perform a rigorous mental "linting" and review process. This includes:

    1.  **Syntax & Indentation Check**: Meticulously verify all Python syntax, paying special attention to indentation, which was the source of a critical failure.

    2.  **Logical Validation**: Review the logic to ensure it is sound, addresses the user's request correctly, and does not introduce new bugs. For example, verify that API call structures (like alternating user/assistant roles) are correctly formed.

    3.  **Dependency Verification**: Ensure any new imports or modules are correctly handled and accounted for in the project structure.

    4.  **File Modification Verification**: After using `filesystem:write_file`, confirm in your response what was changed and that the file was successfully updated.

    5.  **Testing Validation**: For major changes, remind the user to run `/run_tests` to validate that all systems remain functional after your modifications.

## 7. Discord Command Parity with GUI (VPS Headless Deployment)

**CRITICAL REQUIREMENT**: The bot is designed for deployment on headless VPS (Virtual Private Server) environments where the GUI is inaccessible. All configuration settings that can be changed via the GUI **MUST** have equivalent Discord slash commands for admin users.

### Command Design Requirements

-   **Administrator-Only Access**: All configuration commands must use `@app_commands.default_permissions(administrator=True)` to restrict access to server administrators only.

-   **Guild Context Validation**: Every command must validate that it's being used in a server (not DMs) using:
    ```python
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return
    ```

-   **ConfigManager Integration**: All commands that modify settings must:
    1. Load config via `self.bot.config_manager.get_config()`
    2. Modify the config dictionary
    3. Save via `self.bot.config_manager.update_config(config)`

-   **Clear Feedback**: Commands must provide clear success/error messages using ephemeral responses:
    - ✅ Success messages with details of what was changed
    - ❌ Error messages explaining what went wrong
    - ℹ️ Informational messages for empty results

-   **Parameter Validation**: Use Discord's built-in parameter validation:
    - `app_commands.Range[int, min, max]` for numeric ranges
    - `app_commands.Range[float, min, max]` for decimal ranges
    - Custom validation logic for formats (e.g., time strings, regex patterns)

-   **View/Discovery Commands**: Provide "view" commands that display current settings using Discord embeds for better readability.

### Required Command Categories

**Global Bot Configuration**:
- `/config_set_reply_chance` - Set global random reply chance (0.0-1.0)
- `/config_set_personality` - Update default personality traits/lore for new servers
- `/config_add_global_nickname` - Add global alternative nicknames
- `/config_remove_global_nickname` - Remove global nicknames
- `/config_list_global_nicknames` - List all global nicknames
- `/config_view_all` - View all global configuration settings

**Image Generation Configuration**:
- `/image_config_enable` - Enable/disable image generation globally
- `/image_config_set_limits` - Configure rate limits (max per period, reset hours)
- `/image_config_view` - View current image generation settings

**Status Update Configuration**:
- `/status_config_enable` - Enable/disable daily status updates
- `/status_config_set_time` - Set update time (24h format with validation)
- `/status_config_set_source_server` - Choose which server's personality to use
- `/status_config_view` - View current status configuration

**Per-Channel Configuration**:
- `/channel_set_purpose` - Set channel purpose/instructions
- `/channel_set_reply_chance` - Set per-channel random reply chance
- `/channel_set_personality` - Configure personality mode settings (immersive, technical language, server info)
- `/channel_set_proactive` - Configure proactive engagement settings
- `/channel_view_settings` - View all channel settings
- `/channel_list_active` - List all active channels in server

**Per-Server Configuration**:
- `/server_add_nickname` - Add server-specific alternative nicknames
- `/server_remove_nickname` - Remove server-specific nicknames
- `/server_list_nicknames` - List all server nicknames
- `/server_set_emote_sources` - Manage emote sources (list/add/remove/clear)
- `/server_set_status_memory` - Toggle status memory logging
- `/server_view_settings` - View all server-specific settings

**Memory Management**:
- `/consolidate_memory` - Manually trigger memory consolidation

### Implementation Checklist

When adding new GUI settings, you **MUST**:

1. ✅ Create corresponding Discord command(s) in `cogs/admin.py`
2. ✅ Use `@app_commands.default_permissions(administrator=True)`
3. ✅ Validate guild context (reject DMs)
4. ✅ Implement parameter validation with clear error messages
5. ✅ Use ConfigManager for all config.json modifications
6. ✅ Provide clear success/error feedback
7. ✅ Create a "view" command if the setting is complex
8. ✅ Document the command in `CLAUDE.md` and `README.md`
9. ✅ Update `PLANNED_FEATURES.md` if implementing a planned feature

### Example Implementation Pattern

```python
@app_commands.command(name="config_set_reply_chance", description="Set global random reply chance")
@app_commands.describe(chance="Random reply chance (0.0-1.0, e.g., 0.05 for 5%)")
@app_commands.default_permissions(administrator=True)
async def config_set_reply_chance(self, interaction: discord.Interaction, chance: app_commands.Range[float, 0.0, 1.0]):
    """Set the global random reply chance for the bot."""
    # Guild validation
    if not interaction.guild:
        await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
        return

    # Load, modify, save config
    config = self.bot.config_manager.get_config()
    config['random_reply_chance'] = chance
    self.bot.config_manager.update_config(config)

    # Clear feedback
    await interaction.response.send_message(
        f"✅ Set global random reply chance to **{chance * 100:.1f}%**\n"
        f"Bot will randomly respond to {int(chance * 100)} out of every 100 non-mentioned messages.",
        ephemeral=True
    )
```

### Testing Requirements

After implementing new configuration commands:

1. Test on a headless VPS environment with no GUI access
2. Verify all settings persist correctly in config.json
3. Verify bot behavior matches GUI-configured behavior
4. Run `/run_tests` to validate system integrity
5. Update test suite in `testing.py` if necessary

**Priority**: This is a **CRITICAL** requirement for VPS deployment. Any GUI setting that lacks a Discord command equivalent makes the bot unmanageable on headless servers.

---
