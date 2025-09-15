# ======================================================================
# !!! DEPRECATION WARNING !!!
# This file is considered legacy and is no longer the main entry point.
# The bot has been refactored to use a more modular 'cogs' structure,
# which is managed by `main.py`.
#
# Running this file will result in an older version of the bot's logic
# and will NOT load any of the commands or events from the 'cogs' folder.
#
# To run the bot correctly, please use the GUI (gui.py) or run:
# python main.py
# ======================================================================

import sys
print("="*60)
print("!!! WARNING: You are attempting to run the legacy `bot.py` file.")
print("This file is deprecated. The correct entry point is `main.py`.")
print("Execution has been stopped to prevent conflicts.")
print("="*60)
sys.exit()


# The original legacy code is preserved below for reference.
# ======================================================================

# # bot.py
# 
# import discord
# from discord.ext import commands
# import json
# import random
# import openai
# import os
# import asyncio
# from emote_orchestrator import EmoteOrchestrator # Import the new class
# 
# def load_config():
#     """Loads settings from the config file."""
#     if not os.path.exists('config.json'):
#         print("ERROR: config.json not found. Please run gui.py first to create and save the configuration.")
#         return None
#     with open('config.json', 'r') as f:
#         return json.load(f)
# 
# # Load configuration at startup
# config = load_config()
# if not config:
#     exit()
# 
# # --- Intents Setup ---
# intents = discord.Intents.default()
# intents.messages = True
# intents.message_content = True
# intents.guilds = True
# intents.members = True
# 
# # --- Bot and Module Initialization ---
# bot = commands.Bot(command_prefix='!', intents=intents)
# emote_handler = EmoteOrchestrator(bot) # Create an instance of the new module
# 
# # --- Helper Functions ---
# def get_channel_personality(channel_id):
#     """Gets the specific personality for a channel, or the default one."""
#     channel_id_str = str(channel_id)
#     if channel_id_str in config['channel_settings']:
#         return config['channel_settings'][channel_id_str]
#     return config['default_personality']
# 
# def generate_ai_response(channel, author, message_history):
#     """Formats the prompt and gets a response from the OpenAI API."""
#     personality_config = get_channel_personality(channel.id)
# 
#     if not config.get('openai_api_key'):
#         print("ERROR: OpenAI API key not found in config.json")
#         return None
#     
#     try:
#         client = openai.OpenAI(api_key=config['openai_api_key'])
#     except Exception as e:
#         print(f"Failed to initialize OpenAI client: {e}")
#         return None
# 
#     # Get available emote names from our new handler
#     available_emotes = emote_handler.get_available_emote_names()
#     emote_instructions = (
#         f"You have access to custom server emotes. You can use them by wrapping their name in colons, for example: :smile:. "
#         f"Here are the emotes available to you: {available_emotes}. Use them to make your responses more expressive."
#     )
# 
#     # Construct the detailed system prompt
#     system_prompt = (
#         f"You are a Discord bot. Your name is {personality_config.get('name', 'AI-Bot')}. "
#         f"Your personality is: {personality_config.get('personality_traits', 'helpful')}. "
#         f"Background lore: {personality_config.get('lore', '')}. "
#         f"Important facts to remember: {personality_config.get('facts', '')}. "
#         f"Your specific purpose in this channel is: {personality_config.get('purpose', 'general chat')}. "
#         "Engage with users naturally. Keep responses concise and suitable for a chat format. Do not use markdown.\n"
#         f"{emote_instructions}"
#     )
# 
#     messages_for_api = [{'role': 'system', 'content': system_prompt}]
#     for msg in message_history:
#         role = 'assistant' if msg.author.id == bot.user.id else 'user'
#         messages_for_api.append({'role': role, 'content': f"{msg.author.display_name}: {msg.content}"})
# 
#     try:
#         response = client.chat.completions.create(
#             model="gpt-4o",
#             messages=messages_for_api,
#             max_tokens=200,
#             temperature=0.7
#         )
#         return response.choices[0].message.content.strip()
#     except openai.APIError as e:
#         print(f"An OpenAI API error occurred: {e}")
#         return "Sorry, I'm having trouble connecting to my AI brain right now."
#     except Exception as e:
#         print(f"An unexpected error occurred during AI response generation: {e}")
#         return None
# 
# # --- Bot Events ---
# @bot.event
# async def on_ready():
#     print(f'Bot is ready! Logged in as {bot.user}')
#     emote_handler.load_emotes() # Load emotes using the new handler
#     print('------')
# 
# @bot.event
# async def on_message(message):
#     if message.author == bot.user:
#         return
# 
#     await bot.process_commands(message)
# 
#     if message.content.startswith(bot.command_prefix):
#         return
# 
#     active_channels_str = config['channel_settings'].keys()
#     active_channels_int = [int(ch_id) for ch_id in active_channels_str]
#     if message.channel.id not in active_channels_int:
#         return
# 
#     should_respond = (bot.user.mentioned_in(message) or 
#                       random.random() < config.get('random_reply_chance', 0.05))
# 
#     if should_respond:
#         async with message.channel.typing():
#             history = [msg async for msg in message.channel.history(limit=10)]
#             history.reverse()
# 
#             ai_response_text = generate_ai_response(message.channel, message.author, history)
#             
#             if ai_response_text:
#                 # Process the response using the new handler
#                 final_response = emote_handler.replace_emote_tags(ai_response_text)
#                 await message.channel.send(final_response)
# 
# # --- Bot Commands (Unchanged) ---
# @bot.command(name='ticket', help='Creates a new private support ticket. Usage: !ticket [reason]')
# @commands.has_permissions(manage_channels=True)
# async def create_ticket(ctx, *, reason: str = "No reason provided"):
#     guild = ctx.guild
#     category_name = "Support Tickets"
#     category = discord.utils.get(guild.categories, name=category_name)
#     if category is None:
#         category = await guild.create_category(category_name)
# 
#     overwrites = {
#         guild.default_role: discord.PermissionOverwrite(read_messages=False),
#         ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
#         guild.me: discord.PermissionOverwrite(read_messages=True)
#     }
#     
#     try:
#         ticket_channel = await guild.create_text_channel(
#             f'ticket-{ctx.author.name}',
#             category=category,
#             overwrites=overwrites,
#             topic=f"Ticket for {ctx.author}. Reason: {reason}"
#         )
#         await ticket_channel.send(
#             f"Hello {ctx.author.mention}, a support ticket has been created.\n"
#             f"**Reason:** {reason}\n"
#             "A staff member will be with you shortly."
#         )
#         await ctx.send(f"✅ Your ticket has been created at {ticket_channel.mention}", delete_after=10)
#     except discord.Forbidden:
#         await ctx.send("❌ I don't have permissions to create channels.")
#     except Exception as e:
#         await ctx.send(f"An error occurred: {e}")
# 
# @bot.command(name='close', help='Closes a ticket channel.')
# @commands.has_permissions(manage_channels=True)
# async def close_ticket(ctx):
#     if "ticket-" in ctx.channel.name:
#         await ctx.send("This channel will be closed in 5 seconds...")
#         await asyncio.sleep(5)
#         await ctx.channel.delete(reason="Ticket closed by user.")
#     else:
#         await ctx.send("This is not a valid ticket channel.")
# 
# @bot.command(name='ban', help='Bans a user from the server. Usage: !ban @user [reason]')
# @commands.has_permissions(ban_members=True)
# async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
#     try:
#         await member.ban(reason=reason)
#         await ctx.send(f"✅ {member.mention} has been banned. Reason: {reason}")
#     except discord.Forbidden:
#         await ctx.send("❌ I don't have permission to ban this user.")
#     except discord.HTTPException as e:
#         await ctx.send(f"Failed to ban user. Error: {e}")
# 
# # --- Run the Bot ---
# if __name__ == '__main__':
#     bot_token = config.get('bot_token')
#     if not bot_token:
#         print("FATAL: Bot token is not configured in config.json. Please set it via the GUI.")
#     else:
#         try:
#             bot.run(bot_token)
#         except discord.errors.LoginFailure:
#             print("FATAL: Login failed. The provided Discord Bot Token is invalid.")
#         except Exception as e:
#             print(f"An error occurred while running the bot: {e}")
