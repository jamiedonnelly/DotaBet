import disnake
from disnake.ext import commands, tasks
import logging
from uuid import uuid4
import os

from TestBot.database.dynamo import DynamoHandler
from TestBot.opendota.client import AsyncDotaClient
from TestBot.utils import get_logger
from TestBot.embeds import successful_cmd, unsuccessful_cmd

PREFIX = os.environ["PREFIX"]
ROOT = os.environ["ROOT"]
logger = get_logger(dir=f"{ROOT}/data/logs", filename="User.log", level=logging.INFO)

class User(commands.Cog, name = "User"):
    """Commands and functionality related to user profiles and configuration."""
    def __init__(self, bot: commands.Bot, db_handler: DynamoHandler, dota_client: AsyncDotaClient):
        self.bot = bot
        self.db = db_handler
        self.dota = dota_client
        
    async def _check_user_id(self, user_id: str, cmd_id: str):
        # Checks to see if the user_id value provided is valid in OpenDota
        query = f"players/{user_id}"
        try:
            data = await self.dota.get_json_data(query)
            # Iterates through returned data
            for key in data.keys():
                # If any valid data is found, return the id
                if data[key]:
                    return user_id
            # if no valid data is found it will return false
            logger.error(f"Was not able to find the user: {user_id}", extra={"id":cmd_id})
            return False
        except Exception as e:
            logger.error(f"Exception: {e} in `_check_user_id`", exc_info=True)
            return False
            
    @commands.slash_command(description = "Set up your own account to start making bets.")
    async def config(self, inter):
        """
            This configures a user's discord profile, providing them with a betting account and initial balance. 
        """
        await inter.response.defer()
        # This configures a user for betting.
        c_id = str(uuid4())
        user_id = inter.user.id
        logger.info(f"`config` command issued by {inter.user.name}, user_id: {user_id}", extra={"id":c_id})
        # Check to see if the user exists
        response, val = self.db.check_user_exists(user_id, c_id)

        # If the operation failed at the DB level
        if not response:
            logger.error(f"`config` command issued by {inter.user.name}, user_id: {user_id} failed", extra={"id":c_id})
            await unsuccessful_cmd(inter)
            return

        # If no user found
        if not val:
            # If user does not exist
            logger.debug(f"User {inter.user.name} ({user_id}) was not configured; creating user.", extra={"id":c_id})
            response = self.db.create_user(user_id, c_id)
            if response:
                await successful_cmd(inter)
                return
            else:
                logger.error(f"Failed to create user {inter.user.name}: {inter.user.id}", extra={"id":c_id})
                await unsuccessful_cmd(inter)
                return

        # If user already exists successful 
        if val:
            await successful_cmd(inter)
            return

    @commands.slash_command(description = "Configure your Steam profile to be bet on with your SteamID3.")
    async def steamconfig(self, inter, id):
        """This configures a user's profile, allowing other users in the server to bet on them. This is done using a SteamID3 which can be found by searching for your profile on OpenDota and extracting the number at the end of the url,
                    `opendota.com/players/SteamID3`. A user must be exposing their match data which is done through settings on the Dota 2 client.
        Args:
            ID : Steam ID3. Can be found by searching for your profile on OpenDota and extracting the number at the end of the url,
                    `opendota.com/players/SteamID3`
        """
        await inter.response.defer()
        # This configures a user's steam profile for them to be bet on        
        c_id = str(uuid4())
        
        # Tests for a valid ID - if it can be cast to `int`
        try:
            steam_id = int(id.strip())
        except ValueError:
            await unsuccessful_cmd(inter, "Not a valid Steam ID.")
            return 
        
        user_id = inter.user.id
        logger.info(f"`steamconfig` command issued by {inter.user.name}, steam_id: {steam_id}", extra={"id":c_id})

        # Checks OpenDota to test for a valid ID
        try:
            _id = await self._check_user_id(steam_id, c_id)
        # Catches generic errors as well as timeouts
        except Exception as e:
            logger.error(f"Exception {type(e).__name__} occurred during `steamconfig` issued by {inter.user.name}", extra={"id":c_id})
            await unsuccessful_cmd(inter)
            return
        
        # If `self._check_user_id` gives invalid _id
        if not _id:
            logger.error(f"Invalid steam_id provided during `steamconfig` issued by {inter.user.name}", extra={"id":c_id})
            await unsuccessful_cmd(inter, title="No user found.", message=f"No valid steam user was found with id: {steam_id}")
            return
        
        # Finally, if a valid ID is found, set up the profile
        # First check to see if the person has run a `config` command:
        response, val = self.db.check_user_exists(user_id, c_id)

        if not response:
            logger.error(f"DB error occurred during while checking if the user exists.", extra={"id":c_id})
            await unsuccessful_cmd(inter)
            return
        
        # If no user profile found, configure user profile first
        if not val:
            response = self.db.config_user_and_steamid(user_id, steam_id, c_id)
            if not response:
                logger.error(f"DB error occurred during configuration of user profile.", extra={"id":c_id})
                await unsuccessful_cmd(inter)
                return
            await successful_cmd(inter)
            return      
            
        # If user profile found, set up `steam_id` for user profile
        response = self.db.config_user_steamid(user_id, steam_id, c_id)
        if response:
            await successful_cmd(inter)
            return 
        else:
            logger.error(f"DB error occurred during configuration of user profile.", extra={"id":c_id})
            await unsuccessful_cmd(inter)
            return
        
    @commands.slash_command(description = "Returns a configured user's Steam ID.")
    async def steamid(self, inter):
        # Replies a user's steam ID if it is configured
        await inter.response.defer()
        c_id = str(uuid4())        
        user_id = inter.user.id
        logger.info(f"`steamid` command issued by {inter.user.name}", extra={"id":c_id})
        
        # Get user steam id from DB
        response, _id = self.db.get_user_steamid(user_id, c_id)
        
        # DB failure
        if not response:
            logger.error(f"`steamid` command issued by {inter.user.name} failed, likely a DB-side failure.", extra={"id":c_id})
            await unsuccessful_cmd(inter)
            return

        # If value obtained
        if _id:
            await successful_cmd(inter, title="Steam ID", message=f"{_id}")
            return
        # If no value obtained
        else:
            await unsuccessful_cmd(inter, message=f"Unsuccessful. Have you run `{PREFIX}config` yet?")
            return

    @commands.slash_command(description = "Add a new user to be bet on by providing a name and steamdID.")
    async def add_user(self, inter, username: str, steam_id: int):
        await inter.response.defer()
        c_id = str(uuid4())
        guildID = inter.guild.id 
        
        # Checks OpenDota to test for a valid ID
        try:
            _id = await self._check_user_id(steam_id, c_id)
        # Catches generic errors as well as timeouts
        except Exception as e:
            logger.error(f"Exception {type(e).__name__} occurred during `steamconfig` issued by {inter.user.name}", extra={"id":c_id})
            await unsuccessful_cmd(inter, title="Error", message=f"No valid steam user found with id: {steam_id}")
            return

        # Format data to be added into database
        user = {"Username": username, "SteamID": _id, "GuildID": guildID}

        # Add user into database
        try:
            self.db.create_additional_user(user, c_id)
        except Exception as e:
            logger.error(f"Exception {type(e).__name__} occurred while creating additional user", extra={"id":c_id})
            await unsuccessful_cmd(inter)
            return

        # Return successful
        await successful_cmd(inter)

    @commands.slash_command(description= "See all the users configured in this guild.")
    async def configured_users(self, inter):
        await inter.response.defer()
        c_id = str(uuid4())
        guild_id = inter.guild.id
        additional_users = self.db.extract_guild_additional_users(guild_id, c_id)
        raise NotImplementedError




