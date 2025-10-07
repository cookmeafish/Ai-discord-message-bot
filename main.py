# main.py

import discord
from discord.ext import commands
import os
import asyncio

# Import all custom modules
from modules.config_manager import ConfigManager
from modules.emote_orchestrator import EmoteOrchestrator
from modules.ai_handler import AIHandler
from modules.logging_manager import get_logger
from database.db_manager import DBManager

async def main():
    # 1. Initialize logging first
    logger = get_logger()
    logger.info("Starting bot initialization...")
    
    # 2. Initialize Managers
    config_manager = ConfigManager()
    db_manager = DBManager()

    # 3. Setup Intents
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True
    intents.members = True

    # 4. Create Bot instance
    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    # 5. Initialize and attach handlers and managers
    logger.info("Initializing modules...")
    bot.config_manager = config_manager
    bot.db_manager = db_manager
    bot.emote_handler = EmoteOrchestrator(bot)
    
    openai_api_key = config_manager.get_secret("OPENAI_API_KEY")
    bot.ai_handler = AIHandler(openai_api_key, bot.emote_handler)
    logger.info("All modules initialized.")

    # 6. Load all cogs
    logger.info("Loading cogs...")
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f'Successfully loaded cog: {filename}')
            except Exception as e:
                logger.error(f'Failed to load cog {filename}: {e}')

    # 7. Define the on_ready event for setup tasks
    @bot.event
    async def on_ready():
        logger.info('------')
        logger.info(f'Bot is logged in as {bot.user}')
        
        bot.emote_handler.load_emotes()
        
        logger.info(f'Syncing slash commands...')
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
        logger.info('------ Bot is Ready ------')

    # 8. Get the bot token and run the bot
    bot_token = config_manager.get_secret("DISCORD_TOKEN")
    if not bot_token:
        logger.critical("DISCORD_TOKEN not found in .env file. Please set it via the GUI.")
        return
        
    try:
        await bot.start(bot_token)
    except discord.errors.LoginFailure:
        logger.critical("Login failed. The provided Discord Bot Token is invalid.")
    except Exception as e:
        logger.critical(f"An unexpected error occurred while running the bot: {e}", exc_info=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot shutdown requested by user.")


