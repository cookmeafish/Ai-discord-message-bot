# main.py

import discord
from discord.ext import commands
import os
import asyncio

# Import all custom modules
from modules.config_manager import ConfigManager
from modules.emote_orchestrator import EmoteOrchestrator
from modules.ai_handler import AIHandler
from database.db_manager import DBManager # Import the new DBManager

async def main():
    # 1. Initialize Managers first
    config_manager = ConfigManager()
    db_manager = DBManager() # Create an instance of the DBManager

    # 2. Setup Intents
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True
    intents.members = True  # Required for the bot to see all users and emotes across guilds

    # 3. Create Bot instance
    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    # 4. Initialize and attach handlers and managers
    print("Initializing modules...")
    bot.config_manager = config_manager
    bot.db_manager = db_manager # Attach the db_manager to the bot instance
    bot.emote_handler = EmoteOrchestrator(bot)
    
    openai_api_key = config_manager.get_secret("OPENAI_API_KEY")
    bot.ai_handler = AIHandler(openai_api_key, bot.emote_handler)
    print("✅ All modules initialized.")

    # 5. Load all cogs
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
        
        bot.emote_handler.load_emotes()
        
        print(f'Syncing slash commands...')
        try:
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

