# cogs/moderation.py

import discord
from discord.ext import commands

class ModerationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ban', help='Bans a user from the server. Usage: !ban @user [reason]')
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        try:
            await member.ban(reason=reason)
            await ctx.send(f"✅ {member.mention} has been banned. Reason: {reason}")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to ban this user.")
        except discord.HTTPException as e:
            await ctx.send(f"Failed to ban user. Error: {e}")

async def setup(bot):
    await bot.add_cog(ModerationCog(bot))