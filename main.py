# main.py

import discord
from discord.ext import commands
import os
import asyncio

from modules.config_manager import ConfigManager

async def main():
    config_manager = ConfigManager()

    intents = discord.Intents.default()
    # ... (rest of intents)

    bot = commands.Bot(command_prefix='!', intents=intents)

    bot.config_manager = config_manager
    
    # Load all cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Successfully loaded cog: {filename}')
            except Exception as e:
                print(f'Failed to load cog {filename}: {e}')

    # --- ADD THIS SECTION TO SYNC SLASH COMMANDS ---
    @bot.event
    async def on_ready():
        print(f'Syncing slash commands...')
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync slash commands: {e}")
    # -----------------------------------------------

    bot_token = config_manager.get_secret("DISCORD_TOKEN")
    # ... (rest of main.py)

if __name__ == '__main__':
    asyncio.run(main())