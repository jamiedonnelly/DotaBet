import disnake
from disnake.ext import commands
import logging
import os

from TestBot.utils import get_logger
from TestBot.embeds import unsuccessful_cmd

ROOT = os.environ["ROOT"]
logger = get_logger(dir=f"{ROOT}/data/logs", filename="Util.log", level=logging.INFO)

class Utils(commands.Cog, name = "Utils"):
    """Commands related to simple utilities."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(description = "Returns any string printed to the chat.")
    async def echo(self, inter, *, content: str):
        await inter.response.defer()
        try:
            await inter.followup.send(content)
        except:
            await unsuccessful_cmd(inter)
            return

    @commands.slash_command(description = "Used to test the connection.")
    async def ping(self, inter):
        await inter.response.defer()
        try:
            await inter.followup.send("pong")
        except:
            await unsuccessful_cmd(inter)
            return




