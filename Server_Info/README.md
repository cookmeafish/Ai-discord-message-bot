# Server Information Directory

This directory is used to store formal server information that the bot can reference when responding in specific channels.

## Purpose

Use this for:
- Server rules and policies
- Moderation guidelines
- FAQ information
- Channel-specific instructions
- Any formal documentation the bot should know

## How to Use

1. Create `.txt` files in this directory with your server information
2. Name them descriptively (e.g., `server_rules.txt`, `moderation_policy.txt`, `faq.txt`)
3. In the GUI channel editor, enable "Use Server Information" checkbox for channels that should access these files
4. The bot will load ALL `.txt` files from this directory when responding in those channels

## Example

**File: `server_rules.txt`**
```
1. Be respectful to all members
2. No spam or advertising
3. Keep discussions on-topic
4. Follow Discord's Terms of Service
```

When "Use Server Information" is enabled for a channel, the bot will have access to this information and can reference it when answering questions about rules.

## Configuration

Enable this feature per-channel via:
- **GUI**: Edit Channel → Check "Use Server Information"
- **Discord**: `/channel_set_personality use_server_info:true`
- **config.json**: Add `"use_server_info": true` to channel settings

## Notes

- Files are loaded in alphabetical order
- Only `.txt` files are loaded (UTF-8 encoding)
- These files are excluded from git by default to protect sensitive information
- Best used with formal channels (rules, support, moderation, etc.)
- Works great with "Allow Technical Language" enabled for formal tone
