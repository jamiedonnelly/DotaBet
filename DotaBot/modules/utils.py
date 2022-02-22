import discord 
from discord.ext import commands 


def get_members(bot):
    members = []
    for guild in bot.guilds: 
        for member in guild.members:
            members.append(member)
    return members     