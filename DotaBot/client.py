import discord 
import asyncio
from modules.dota_client import DotaClient
from cogs.gambling import Gambling
from modules.utils import *
import logging 

#####


logging.basicConfig(filename="client.log",level=logging.CRITICAL)
logger = logging.getLogger(__name__)

invite_link = "https://discord.com/api/oauth2/authorize?client_id=939836345839403018&permissions=534723950656&scope=bot"

class MyClient(discord.ext.commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args,**kwargs)
        
    async def on_ready(self):
        await bot.change_presence(activity=discord.Game(name='-25'))
        print('Logged in as')
        print(bot.user.name)
        print(bot.user.id)
        print('------')
               
###
if __name__=="__main__":
    
    
    ### Load MySQL Params to access databases ####
    host = ''
    user = ''
    database = ''
    password=''

    ### Set intents ###
    intents = discord.Intents.default()
    intents.members = True

    bot = MyClient(command_prefix="$",intents=intents)

    bot.add_cog(Gambling(bot,host,user,database,password))

    bot.run({token})

