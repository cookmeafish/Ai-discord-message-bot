# main.py

import discord
from discord.ext import commands
import os
import asyncio

# Import all custom modules
from modules.config_manager import ConfigManager
from modules.emote_orchestrator import EmoteOrchestrator
from modules.personality_manager import PersonalityManager
from modules.ai_handler import AIHandler

async def main():
    # 1. Initialize Config Manager first, as other modules may need it
    config_manager = ConfigManager()

    # 2. Setup Intents
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True
    intents.members = True  # Required for the bot to see all users and emotes across guilds

    # 3. Create Bot instance
    # We remove the default help command to allow for a custom one if desired later
    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    # 4. Initialize and attach all handlers and managers to the bot instance
    # This makes them easily and consistently accessible from any cog.
    print("Initializing modules...")
    bot.config_manager = config_manager
    bot.emote_handler = EmoteOrchestrator(bot)
    bot.personality_manager = PersonalityManager(config_manager.get_config())
    
    openai_api_key = config_manager.get_secret("OPENAI_API_KEY")
    bot.ai_handler = AIHandler(openai_api_key, bot.emote_handler, bot.personality_manager)
    print("✅ All modules initialized.")

    # 5. Load all cogs from the 'cogs' directory
    print("Loading cogs...")
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'✅ Successfully loaded cog: {filename}')
            except Exception as e:
                print(f'🔴 Failed to load cog {filename}: {e}')

    # 6. Define the on_ready event for setup tasks
    @bot.event
    async def on_ready():
        print('------')
        print(f'Bot is logged in as {bot.user}')
        
        # Load custom emotes from all servers the bot is in
        bot.emote_handler.load_emotes()
        
        # Sync slash commands with Discord
        print(f'Syncing slash commands...')
        try:
            # Syncing the command tree copies any new/changed slash commands to Discord.
            synced = await bot.tree.sync()
            print(f"✅ Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"🔴 Failed to sync slash commands: {e}")
        print('------ Bot is Ready ------')

    # 7. Get the bot token and run the bot
    bot_token = config_manager.get_secret("DISCORD_TOKEN")
    if not bot_token:
        print("🔴 FATAL: DISCORD_TOKEN not found in .env file. Please set it via the GUI.")
        return
        
    try:
        # bot.start() is the recommended way to run the bot
        await bot.start(bot_token)
    except discord.errors.LoginFailure:
        print("🔴 FATAL: Login failed. The provided Discord Bot Token is invalid.")
    except Exception as e:
        print(f"🔴 An unexpected error occurred while running the bot: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot shutdown requested by user.")
