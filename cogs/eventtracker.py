import discord
from discord.ext import commands
import sqlite3
import re
import asyncio
from typing import Union
from datetime import timedelta


# Init DB
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS events (
        message_id INTEGER PRIMARY KEY,
        role_id INTEGER DEFAULT 0,
        event_id INTEGAR DEFAULT 0,
        channel_id INTEGAR DEFAULT 0,
        limits INTEGAR DEFAULT 0)
''')
conn.commit()

class Buttons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="RSVP", style=discord.ButtonStyle.green, custom_id="rsvp")
    async def rsvp_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        result = get_event_info_from_message_id(interaction.message.id)
        role_id = result[0]
        event_id = result[1]
        limit = result[2]
        event = discord.utils.get(interaction.guild.scheduled_events, id=event_id)
        event_name = re.sub("\[.*?\] ", "", event.name)
        role = discord.utils.get(interaction.guild.roles, id=role_id)
        role_int = len(role.members)
        if role in interaction.user.roles:
            await interaction.response.send_message(content=f"You have already RSVPed for {event_name}.", ephemeral=True)
        else:
            if role_int < limit or limit == 0:
                await interaction.user.add_roles(role)
                role_int += 1
                await interaction.response.send_message(content=f"You have successfully RSVPed for {event_name}.", ephemeral=True)
                if limit != 0:
                    if role_int  >= limit:
                       await event.edit(name = f"[FULL] " + event_name)
                    elif role_int  < limit:
                       await event.edit(name = f"[{role_int}/{limit}] " + event_name)
                    embed = make_embed(event, limit, role_int)
                    await interaction.message.edit(embed=embed)
            else:
                await interaction.response.send_message(content=f"RSVP for {event_name} unsuccessful because the event is full.", ephemeral=True)

    @discord.ui.button(label="UN-RSVP", style=discord.ButtonStyle.red, custom_id="unrsvp")
    async def unrsvp_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        result = get_event_info_from_message_id(interaction.message.id)
        role_id = result[0]
        event_id = result[1]
        limit = result[2]
        event = discord.utils.get(interaction.guild.scheduled_events, id=event_id)
        event_name = re.sub("\[.*?\] ", "", event.name)
        role = discord.utils.get(interaction.guild.roles, id=role_id)
        role_int = len(role.members)
        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            role_int -= 1
            await interaction.response.send_message(content=f"You have successfully un-RSVPed for {event_name}.", ephemeral=True)
            if limit != 0:
                if role_int >= limit:
                    await event.edit(name = f"[FULL] " + event_name)
                elif role_int < limit:
                   await event.edit(name = f"[{role_int}/{limit}] " + event_name)
                embed = make_embed(event, limit, role_int)
                await interaction.message.edit(embed=embed)
        else:
            await interaction.response.send_message(content="No changes have been made because you haven't RSVP'ed.", ephemeral=True)

    @discord.ui.button(label="List Attendees", style=discord.ButtonStyle.grey, custom_id="listattendees")
    async def list_users_button(self, interaction:discord.Interaction, button:discord.ui.Button):
        result = get_event_info_from_message_id(interaction.message.id)
        role_id = result[0]
        event_id = result[1]
        event = discord.utils.get(interaction.guild.scheduled_events, id=event_id)
        event_name = re.sub("\[.*?\] ", "", event.name)
        role = discord.utils.get(interaction.guild.roles, id=role_id)
        member_int = len(role.members)
        if len(role.members) == 0:
            await interaction.response.send_message(content="No attendees yet.", ephemeral=True)
        else:
            member_list = "\n- ".join(str(member.mention) for member in role.members)
            await interaction.response.send_message(content=f"**Members attending {event_name}**\n\n- " + member_list + f"\n\nMember Count: {member_int}", ephemeral=True)


# Discord commands
class EventTracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    async def cog_load(self):
        self.bot.add_view(Buttons())

    @commands.command()
    @commands.has_permissions(manage_events=True)
    @commands.bot_has_permissions(manage_events=True, manage_roles=True)
    async def setupevent(self, ctx, event: Union[discord.ScheduledEvent, discord.Invite]=None, limit: int=None, channel: discord.TextChannel=None):
        if event is None:
            await ctx.send("!setupevent (event) (limit) (#channel)")
            return
        if limit is None or limit < 0:
            await ctx.send("Error: You must put a valid number")
            return
        if channel is None:
            await ctx.send("Error: No channel has been selected")
            return
        if event.guild != ctx.guild:
            return
        if hasattr(event, "scheduled_event"):
            event = event.scheduled_event
        event_id = event.id
        event_name = event.name
        event_check = check_event(event_id)
        if event_check == 0 and limit >= 0:
            if limit != 0:
                event_name = re.sub("\[.*?\] ", "", event.name)
                await event.edit(name = f"[0/{limit}] " + event_name)
            embed = make_embed(event, limit)
            message = await channel.send(embed=embed, view=Buttons())
            guild = ctx.guild
            role_name = f"[EVENT]: {event_name}"
            await guild.create_role(name=role_name)
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            setup_event(message.id, role.id, event_id, channel.id, limit)
            await ctx.send("Event has been setup")
        elif limit >= 0:
            result = get_event_info_from_event_id(event_id)
            message_id = result[0]
            channel_id = result[1]
            role_id = result[2]
            role = discord.utils.get(ctx.guild.roles, id=role_id)
            role_int = len(role.members)
            event_name = re.sub("\[.*?\] ", "", event.name)
            if limit == 0:
                await event.edit(name = event_name)
            elif role_int >= limit:
                await event.edit(name = f"[FULL] " + event_name)
            elif role_int < limit:
                await event.edit(name = f"[{role_int}/{limit}] " + event_name)
            change_limit(message_id, limit)
            channel = self.bot.get_channel(channel_id)
            message = await channel.fetch_message(message_id)
            embed = make_embed(event, limit, role_int)
            await message.edit(embed=embed)
            await ctx.send("Event limit has been changed")
        elif limit < 0:
            await ctx.send("You can't have negatives as your limit")
        elif event_check == 0:
            await ctx.send("This event was already setup")

    @setupevent.error
    async def setupevent_error(self, ctx, error):
        if isinstance(error, discord.ext.commands.BadUnionArgument):
            await ctx.send("Error: You didn't provide a valid event")
        if isinstance(error, discord.ext.commands.errors.ChannelNotFound):
            await ctx.send("Error: You didn't provide a valid channel")
        elif isinstance(error, discord.ext.commands.errors.BadArgument):
            await ctx.send("Error: Invalid number used as the limit")
        else:
            raise error
!
    @commands.command()
    @commands.has_permissions(manage_events=True)
    @commands.bot_has_permissions(manage_events=True, manage_roles=True)
    async def removeevent(self, ctx, event: Union[discord.ScheduledEvent, discord.Invite]):
        if hasattr(event, "scheduled_event"):
            event = event.scheduled_event
        if event.guild != ctx.guild:
            return
        event_id = event.id
        event_check = check_event(event_id)
        if event_check == 0:
            await ctx.send("This event was never setup")
            return
        result = get_event_info_from_event_id(event_id)
        message_id = result[0]
        channel_id = result[1]
        role_id = result[2]
        limit = result[3]
        if limit != 0:
            event_name = re.sub("\[.*?\] ", "", event.name)
            await event.edit(name = event_name)
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.delete()
        role = discord.utils.get(ctx.guild.roles, id=role_id)
        await role.delete()
        remove_event(message_id)
        await ctx.send("Event deleted succesfully")

    @commands.command()
    @commands.is_owner()
    @commands.bot_has_permissions(manage_events=True, manage_roles=True)
    async def forceremoveevent(self, ctx, event):
        result = get_event_info_from_event_id(event)
        message_id = result[0]
        channel_id = result[1]
        role_id = result[2]
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.delete()
        role = discord.utils.get(ctx.guild.roles, id=role_id)
        await role.delete()
        remove_event(message_id)
        await ctx.send("Event deleted succesfully")

    @commands.command()
    @commands.is_owner()
    async def dropevent(self, ctx, event):
        result = get_event_info_from_event_id(event)
        message_id = result[0]
        remove_event(message_id)
        await ctx.send("Dropped")

    @commands.command()
    @commands.has_permissions(manage_events=True)
    @commands.bot_has_permissions(manage_events=True, manage_roles=True)
    async def updateevent(self, ctx, event: Union[discord.ScheduledEvent, discord.Invite]):
        if hasattr(event, "scheduled_event"):
            event = event.scheduled_event
        if event.guild != ctx.guild:
            return
        event_id = event.id
        event_check = check_event(event_id)
        if event.guild != ctx.guild:
            return
        if event_check == 0:
            return
        result = get_event_info_from_event_id(event_id)
        message_id = result[0]
        channel_id = result[1]
        role_id = result[2]
        limit = result[3]
        role = discord.utils.get(ctx.guild.roles, id=role_id)
        role_int = len(role.members)
        event_name = re.sub("\[.*?\] ", "", event.name)
        if limit == 0:
            await event.edit(name = event_name)
        elif role_int >= limit:
            await event.edit(name = f"[FULL] " + event_name)
        elif role_int < limit:
            await event.edit(name = f"[{role_int}/{limit}] " + event_name)
        channel = self.bot.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        embed = make_embed(event, limit, role_int)
        await message.edit(embed=embed)
        await ctx.send("Event has been updated")

    # @commands.Cog.listener()
    # @commands.bot_has_permissions(manage_events=True)
    # async def on_scheduled_event_delete(self, event):
    #     event_id = event.id
    #     event_check = check_event(event_id)
    #     if event_check == 0:
    #         return
    #     result = get_event_info_from_event_id(event_id)
    #     message_id = result[0]
    #     channel_id = result[1]
    #     role_id = result[2]
    #     channel = self.bot.get_channel(channel_id)
    #     message = await channel.fetch_message(message_id)
    #     await message.delete()
    #     role = discord.utils.get(event.guild.roles, id=role_id)
    #     await role.delete()
    #     remove_event(message_id)

    # @commands.Cog.listener()
    # @commands.bot_has_permissions(manage_events=True)
    # async def on_scheduled_event_update(self, before, after):
    #     if after.status != discord.EventStatus.completed and after.status != discord.EventStatus.cancelled:
    #         return
    #     event_id = before.id
    #     event_check = check_event(event_id)
    #     if event_check == 0:
    #         return
    #     result = get_event_info_from_event_id(event_id)
    #     message_id = result[0]
    #     channel_id = result[1]
    #     role_id = result[2]
    #     channel = self.bot.get_channel(channel_id)
    #     message = await channel.fetch_message(message_id)
    #     await message.delete()
    #     role = discord.utils.get(before.guild.roles, id=role_id)
    #     await role.delete()
    #     remove_event(message_id)




def check_event(event_id):
    cursor.execute('SELECT role_id FROM events WHERE event_id = ?', (event_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def get_event_info_from_event_id(event_id):
    cursor.execute('SELECT message_id, channel_id, role_id, limits FROM events WHERE event_id = ?', (event_id,))
    result = cursor.fetchone()
    return result if result else 0

def get_event_info_from_message_id(message_id):
    cursor.execute('SELECT role_id, event_id, limits FROM events WHERE message_id = ?', (message_id,))
    result = cursor.fetchone()
    return result if result else 0

def remove_event(message_id):
    cursor.execute('DELETE FROM events WHERE message_id = ?', (message_id,))
    conn.commit()

def setup_event(message_id, role_id, event_id, channel_id, limit):
    cursor.execute('INSERT OR IGNORE INTO events (message_id, role_id, event_id, channel_id, limits) VALUES (?, ?, ?, ?, ?)', (message_id, role_id, event_id, channel_id, limit))
    conn.commit()

def change_limit(message_id, limit):
    cursor.execute('UPDATE events SET limits=? WHERE message_id=?', (limit, message_id))
    conn.commit()

def make_embed(event, limit, members=0):
    embed = discord.Embed(title=event.name, description=event.description, url=event.url)
    embed.set_author(name=event.creator, icon_url=event.creator.avatar)
    start_time = f"<t:{int(event.start_time.timestamp())}:F>"
    if event.end_time == None:
        embed.add_field(name="Time", value=f"{start_time}")
    elif event.end_time - event.start_time < timedelta(hours=12):
        end_time = f"<t:{int(event.end_time.timestamp())}:t>"
        embed.add_field(name="Time", value=f"{start_time}\nto {end_time}")
    elif event.end_time - event.start_time >= timedelta(hours=12):
        end_time = f"<t:{int(event.end_time.timestamp())}:F>"
        embed.add_field(name="Time", value=f"{start_time}\nto {end_time}")
    if event.location != None:
        event_location = re.sub(r' ', '%20', event.location)
        maps_url = f"https://www.google.com/maps/search/?api=1&query={event_location}"
        embed.add_field(name="Location", value=f"[{event.location}]({maps_url})")
    if limit != 0:
        embed.add_field(name="Max People", value=f"{members}/{limit}")
    return embed

async def setup(bot):
    await bot.add_cog(EventTracking(bot))



print("Initialized event tracking cog")