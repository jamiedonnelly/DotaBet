import asyncio
from disnake.ext import commands
import logging
import os
from uuid import uuid4

from TestBot.database.dynamo import DynamoHandler
from TestBot.utils import get_logger

ROOT = os.environ["ROOT"]
logger = get_logger(dir=f"{ROOT}/data/logs", filename="Guild.log", level=logging.INFO)
MAX_RETRIES = 5

class Guild(commands.Cog, name = "Guild"):
    """Commands and functions related to Guilds."""
    def __init__(self, bot: commands.Bot, db_handler: DynamoHandler):
        self.bot = bot
        self.db = db_handler

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        c_id = str(uuid4())
        
        max_retries = 3
        base_delay = 1 # in seconds

        for attempt in range(1, max_retries + 1):
            response = self.db.create_guild(guild.id, c_id)
            if response:
                logger.info(f"Guild {guild.id} added DotaBet.",extra={"id":c_id})
                return  # Exit the loop if successful

            # If here, the operation failed
            # Calculate the next wait time
            wait_time = base_delay * (2 ** attempt)  # Exponential backoff

            # If not the last attempt, sleep for the calculated wait time before retrying
            if attempt != max_retries:
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to create guild entry after {max_retries} attempts. Guild ID: {guild.id}", extra={"id":c_id})
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        c_id = str(uuid4())
        
        max_retries = 3
        base_delay = 1  # in seconds

        for attempt in range(1, max_retries + 1):
            response = self.db.delete_guild(guild.id, c_id)
            if response:
                logger.info(f"Guild {guild.id} removed DotaBet.",extra={"id":c_id})
                return  # Exit the loop if successful

            # If here, the operation failed
            # Calculate the next wait time
            wait_time = base_delay * (2 ** attempt)  # Exponential backoff

            # If not the last attempt, sleep for the calculated wait time before retrying
            if attempt != max_retries:
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed to delete guild entry after {max_retries} attempts. Guild ID: {guild.id}", extra={"id":c_id})
    
    