# cogs/events.py

import discord
from discord.ext import commands
import random

from modules.emote_orchestrator import EmoteOrchestrator
from modules.ai_handler import AIHandler
from modules.personality_manager import PersonalityManager

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config_manager.get_config()
        print("✅ EventsCog: Initialized.")

        self.emote_handler = EmoteOrchestrator(bot)
        self.personality_manager = PersonalityManager(self.config)
        
        openai_api_key = bot.config_manager.get_secret("OPENAI_API_KEY")
        self.ai_handler = AIHandler(openai_api_key, self.emote_handler, self.personality_manager)
        print("✅ EventsCog: All modules loaded.")

    @commands.Cog.listener()
    async def on_ready(self):
        # This listener is in main.py now, but we'll leave this here in case.
        # The main on_ready in main.py handles command syncing.
        pass

    @commands.Cog.listener()
    async def on_message(self, message):
        # --- START DEBUGGING ---
        print("\n--- New Message Detected ---")
        print(f"1. Message from: {message.author} in channel {message.channel.id}")
        
        if message.author == self.bot.user:
            print("2. 🔴 Bot message. Ignoring.")
            return

        print("2. ✅ Not a bot message.")
        
        if message.content.startswith(self.bot.command_prefix):
            print("3. 🔴 Message is a command. Ignoring for chat response.")
            await self.bot.process_commands(message)
            return

        print("3. ✅ Message is not a command.")

        # Reload the config to ensure we have the latest channel settings
        self.config = self.bot.config_manager.get_config()
        active_channels_str = self.config.get('channel_settings', {}).keys()
        active_channels_int = [int(ch_id) for ch_id in active_channels_str]
        print(f"4. Checking channel... Current Channel ID: {message.channel.id}")
        print(f"   Active Channel IDs from config: {active_channels_int}")
        
        if message.channel.id not in active_channels_int:
            print("5. 🔴 Channel is NOT active. Stopping.")
            return

        print("5. ✅ Channel is active.")

        is_mentioned = self.bot.user.mentioned_in(message)
        rand_chance = self.config.get('random_reply_chance', 0.05)
        should_respond = is_mentioned or (random.random() < rand_chance)
        
        print(f"6. Checking response conditions...")
        print(f"   Mentioned: {is_mentioned}")
        print(f"   Random chance threshold: {rand_chance}")

        if not should_respond:
            print("7. 🔴 Response conditions not met. Stopping.")
            return
        
        print("7. ✅ Response conditions met! Preparing to reply.")
        
        async with message.channel.typing():
            print("8. Fetching message history...")
            history = [msg async for msg in message.channel.history(limit=10)]
            history.reverse()

            print("9. Calling AI Handler to generate response...")
            ai_response_text = await self.ai_handler.generate_response(message.channel, message.author, history)

            if ai_response_text:
                print(f"10. ✅ AI Handler returned a response: '{ai_response_text[:50]}...'")
                final_response = self.emote_handler.replace_emote_tags(ai_response_text)
                print("11. Sending final message to Discord.")
                await message.channel.send(final_response)
            else:
                print("10. 🔴 AI Handler returned nothing. Stopping.")

async def setup(bot):
    await bot.add_cog(EventsCog(bot))