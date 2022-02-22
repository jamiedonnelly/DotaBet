from __main__ import invite_link
from discord.ext import commands 
import discord



class General(commands.Cog):
    
    def __init__(self,):
        
        
        
        
    @commands.command()
    async def invite(self,ctx):
        embed = discord.Embed(name="Invite Link",description=invite_link)
        await ctx.channel.send(embed=embed)
        

    @commands.command()
    







