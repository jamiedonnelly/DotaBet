import disnake
from disnake.ext import commands
from decimal import Decimal
from fuzzywuzzy import fuzz
import logging
import os
import time
import multiprocessing
from typing import Dict
from uuid import uuid4

from TestBot.database.dynamo import DynamoHandler, Action
from TestBot.teams import team_names, teams
from TestBot.utils import get_logger
from TestBot.embeds import successful_cmd, unsuccessful_cmd 

PREFIX = os.environ["PREFIX"]
ROOT = os.environ["ROOT"]
logger = get_logger(dir=f"{ROOT}/data/logs", filename="Gambling.log", level=logging.INFO)

class Gambling(commands.Cog, name = "Gambling"):
    """Commands related to the gambling functionality."""
    def __init__(self, bot: commands.Bot, db_handler: DynamoHandler, bets_queue: multiprocessing.Queue):
        self.bot = bot
        self.db = db_handler
        self.queue = bets_queue

    def _refund_bet(self, user_id: int, value, cmd_id: str):
        try:
            self.db.update_balance(user_id, Decimal(value), Action.INCREMENT, cmd_id)
            return 
        except:
            logger.error(f"REFUND FAILED. Attempted to refund UserID: {user_id} Amount: {value}")
            return 

    def save_bets(self):
        # This is generally going to be used if the bot shuts down
        raise NotImplementedError
    
    def validate_args(self, args: Dict, c_id: str) -> Dict:
        # check if the user being bet on has steam configured
        response, bettee_steamid = self.db.get_user_steamid(args["BeteeID"], c_id)
        if not response:
            # Generic DB error
            raise Exception        
        # If successful add  `bettee_steamid` to `args` and return
        args["BeteeSteamID"] = bettee_steamid
        return args
    
    @commands.slash_command(description = "Command to bet on a server member's current Dota 2 game. See `/example` if more help is required.")
    async def bet_member(self, inter: disnake.CmdInter, betee: disnake.Member, outcome: str, value: float):
        """Allows a user to bet on a discord member's Dota 2 match in real-time, providing them variable real-time odds based on 
           dynamic ML-based predictions of win probabilities. 

        Args:
            betee: The person being bet on through a discord mention, @#user, command. The user must have correctly configured their profile using `>>steamconfig`.
            outcome: The outcome of the match, e.g., win or lose. 
            value: The value being bet on the match, e,g., 100 or 105000.20
        """
        await inter.response.defer(ephemeral=True)
        c_id = uuid4()
        logger.info(f"`bet_member` command issued by user {inter.user.name} ({inter.user.id})", extra={"id":c_id})
        args = {"UserID": inter.user.id,
                "ChannelID": inter.channel.id,
                "GuildID": inter.guild.id,
                "Timestamp": int(time.time()),
                "BeteeID": betee.id,
                "Outcome": outcome,
                "Value": value,
                "cmd_id": str(c_id)}
        self.queue.put(args, block=False)
        await successful_cmd(inter)

    @commands.slash_command(description = "Command to bet on a pro team's current Dota 2 game. See `/example` if more help is required.")
    async def bet_team(self, inter: disnake.CmdInter, team: str, outcome: str, value: float):
        await inter.response.defer()
        c_id = uuid4()
        logger.info(f"`bet_team` command issued by user {inter.user.id}", extra={"id":c_id})
        args = {"UserID": inter.user.id,
                "ChannelID": inter.channel.id,
                "GuildID": inter.guild.id,
                "Timestamp": int(time.time()),
                "Team": team,
                "TeamID": teams[team]["team_id"],
                "Outcome": outcome,
                "Value": value,
                "cmd_id": str(c_id)}
        self.queue.put(args, block=False)
        await successful_cmd(inter)

    @commands.slash_command(description = "Command to bet on an additional user's configured profile.")
    async def bet_user(self, inter: disnake.CmdInter, username: str, outcome: str, value: float):
        await inter.response.defer()
        c_id = uuid4()
        logger.info(f"`bet_user` command issued by user {inter.user.id}", extra={"id":c_id})
        args = {"UserID": inter.user.id,
                "ChannelID": inter.channel.id,
                "GuildID": inter.guild.id,
                "Timestamp": int(time.time()),
                "Username": username,
                "Outcome": outcome,
                "Value": value,
                "cmd_id": str(c_id)}
        self.queue.put(args, block=False)
        await successful_cmd(inter)

    @bet_team.autocomplete("team")
    async def autocomplete_teams(self, inter: disnake.CmdInter, user_input: str):
        # Pair each language with its match score
        scored_vals = [(val, fuzz.ratio(user_input.lower(), val.lower().replace("TEAM",""))) for val in list(team_names)]
        # Filter and sort the languages by their score in descending order
        # so that the best matches are first
        filtered_sorted_vals = sorted(
            (val for val in scored_vals if val[1] > 60),
            key=lambda val: val[1],
            reverse=True
        )
        return [val[0] for val in filtered_sorted_vals][:5]
        
    @bet_member.error
    async def bet_error(self, inter, error):
        if isinstance(error, commands.BadArgument):
            await unsuccessful_cmd(inter, title="Syntax Error", message=f"Invalid `bet` syntax. Check `{PREFIX}help` for examples.")
            return 



