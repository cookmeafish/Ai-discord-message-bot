# main.py

import discord
from discord.ext import commands
import os
import asyncio

# Import your new config manager
from modules.config_manager import ConfigManager

async def main():
    # Initialize the config manager
    config_manager = ConfigManager()

    # --- Intents Setup ---
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True
    intents.members = True

    # --- Bot Initialization ---
    bot = commands.Bot(command_prefix='!', intents=intents)

    # Attach the config manager to the bot so it's accessible in cogs
    bot.config = config_manager.get_config()
    
    # Load all cogs from the 'cogs' directory
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Successfully loaded cog: {filename}')
            except Exception as e:
                print(f'Failed to load cog {filename}: {e}')

    # --- Run the Bot ---
    bot_token = config_manager.get_secret("DISCORD_TOKEN")
    if not bot_token:
        print("FATAL: DISCORD_TOKEN not found in .env file.")
        return

    try:
        await bot.start(bot_token)
    except discord.errors.LoginFailure:
        print("FATAL: Login failed. The provided Discord Bot Token is invalid.")
    except Exception as e:
        print(f"An error occurred while running the bot: {e}")

if __name__ == '__main__':
    asyncio.run(main())