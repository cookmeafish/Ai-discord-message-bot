# main.py

import discord
from discord.ext import commands
import os
import asyncio

from modules.config_manager import ConfigManager

async def main():
    config_manager = ConfigManager()

    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    intents.guilds = True
    intents.members = True

    bot = commands.Bot(command_prefix='!', intents=intents)

    # --- THIS IS THE FIX ---
    # Attach the entire manager object, not just the config dictionary.
    bot.config_manager = config_manager
    # -----------------------
    
    # --- FIX FOR THE __init__.py ERROR ---
    # We will also update the loop to ignore special files.
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'): # <-- Added check
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Successfully loaded cog: {filename}')
            except Exception as e:
                print(f'Failed to load cog {filename}: {e}')

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