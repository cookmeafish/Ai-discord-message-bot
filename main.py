# main.py

import discord
from discord.ext import commands
import os
import asyncio

# Import all custom modules
from modules.config_manager import ConfigManager
from modules.emote_orchestrator import EmoteOrchestrator
from modules.ai_handler import AIHandler
from modules.conversation_detector import ConversationDetector
from modules.logging_manager import get_logger
from database.multi_db_manager import MultiDBManager


def _populate_bot_identity_if_empty(db_manager, logger):
    """
    Checks if the bot_identity table is empty and populates it with a basic default personality.
    This runs automatically on first startup, so users don't need to run a separate script.
    Users can fully customize the personality using /bot_add_trait, /bot_add_lore, and /bot_add_fact commands.
    """
    # Check if bot already has identity
    existing_traits = db_manager.get_bot_identity("trait")

    if existing_traits:
        logger.info("Bot identity already exists in database. Skipping population.")
        return

    logger.info("Bot identity is empty. Populating basic default personality for first-time setup...")

    # Core Traits - Generic friendly bot
    traits = [
        "Helpful and friendly",
        "Conversational and engaging",
        "Enjoys chatting with users",
        "Has a good sense of humor",
        "Curious about the world"
    ]

    for trait in traits:
        db_manager.add_bot_identity("trait", trait)

    # Lore - Simple background
    lore_entries = [
        "I'm an AI assistant living in this Discord server",
        "I learn about users over time through our conversations",
        "I adapt my personality based on my relationship with each user",
        "I'm here to chat and help out when needed"
    ]

    for lore in lore_entries:
        db_manager.add_bot_identity("lore", lore)

    # Facts & Quirks - Basic behaviors
    facts = [
        "I use emotes to express myself",
        "I remember facts about users for personalized conversations",
        "I enjoy both serious and lighthearted discussions",
        "I can adapt my formality level based on the situation"
    ]

    for fact in facts:
        db_manager.add_bot_identity("fact", fact)

    logger.info(f"✅ Successfully populated bot identity with {len(traits)} traits, {len(lore_entries)} lore entries, and {len(facts)} facts!")
    logger.info("Bot is ready to chat! Use /bot_add_trait, /bot_add_lore, and /bot_add_fact to customize the personality.")


async def main():
    # 1. Initialize logging first
    logger = get_logger()
    logger.info("Starting bot initialization...")

    # 2. Initialize Managers
    config_manager = ConfigManager()
    multi_db_manager = MultiDBManager()  # Changed to MultiDBManager

    # 3. Setup Intents
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True
    intents.members = True
    intents.emojis_and_stickers = True  # Required to access custom emojis

    # 4. Create Bot instance
    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

    # 5. Initialize and attach handlers and managers
    logger.info("Initializing modules...")
    bot.config_manager = config_manager
    bot.multi_db_manager = multi_db_manager  # Attach MultiDBManager
    bot.emote_handler = EmoteOrchestrator(bot)

    # Add helper method to bot to get server-specific database
    def get_server_db(guild_id, guild_name=None):
        """Helper to get or create server-specific database."""
        if guild_name:
            return bot.multi_db_manager.get_or_create_db(guild_id, guild_name)
        else:
            # Try to find guild name from bot's guilds
            guild = bot.get_guild(int(guild_id))
            if guild:
                return bot.multi_db_manager.get_or_create_db(guild_id, guild.name)
            else:
                return bot.multi_db_manager.get_or_create_db(guild_id, f"Server_{guild_id}")

    bot.get_server_db = get_server_db

    openai_api_key = config_manager.get_secret("OPENAI_API_KEY")
    bot.ai_handler = AIHandler(openai_api_key, bot.emote_handler)

    # Initialize conversation detector
    bot.conversation_detector = ConversationDetector(config_manager)
    # Set the OpenAI client from AI handler
    bot.conversation_detector.set_openai_client(bot.ai_handler.client)
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
