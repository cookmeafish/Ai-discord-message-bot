# cogs/tickets.py

import discord
from discord.ext import commands
import asyncio

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ticket', help='Creates a new private support ticket. Usage: !ticket [reason]')
    @commands.has_permissions(manage_channels=True)
    async def create_ticket(self, ctx, *, reason: str = "No reason provided"):
        guild = ctx.guild
        category_name = "Support Tickets"
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            category = await guild.create_category(category_name)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        try:
            ticket_channel = await guild.create_text_channel(
                f'ticket-{ctx.author.name}',
                category=category,
                overwrites=overwrites,
                topic=f"Ticket for {ctx.author}. Reason: {reason}"
            )
            await ticket_channel.send(
                f"Hello {ctx.author.mention}, a support ticket has been created.\n"
                f"**Reason:** {reason}\n"
                "A staff member will be with you shortly."
            )
            await ctx.send(f"✅ Your ticket has been created at {ticket_channel.mention}", delete_after=10)
        except discord.Forbidden:
            await ctx.send("❌ I don't have permissions to create channels.")
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(name='close', help='Closes a ticket channel.')
    @commands.has_permissions(manage_channels=True)
    async def close_ticket(self, ctx):
        if "ticket-" in ctx.channel.name:
            await ctx.send("This channel will be closed in 5 seconds...")
            await asyncio.sleep(5)
            await ctx.channel.delete(reason="Ticket closed by user.")
        else:
            await ctx.send("This is not a valid ticket channel.")

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))