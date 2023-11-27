import asyncio
from disnake.ext import commands, tasks
import logging
import math
import os
import threading
from uuid import uuid4

from TestBot.database.dynamo import DynamoHandler
from TestBot.utils import get_logger
from TestBot.embeds import successful_cmd, unsuccessful_cmd, pnl_embed, leaderboard_embed
from TestBot.plotting import plot_pnl
from TestBot.exceptions import NoBetsException

DEFAULT_BALANCE = 5000
PREFIX = os.environ["PREFIX"]
ROOT = os.environ["ROOT"]
logger = get_logger(dir=f"{ROOT}/data/logs", filename="Balance.log", level=logging.INFO)

class Balance(commands.Cog, name = "Balance"):
    """Commands related to user balances."""
    def __init__(self, bot: commands.Bot, db_handler: DynamoHandler):
        self.bot = bot
        self.db = db_handler

    @commands.slash_command(name = "balance", description = "Check your current betting balance.")
    async def balance(self, inter):
        await inter.response.defer()
        # Returns a users balance
        c_id = str(uuid4())
        user_id = inter.user.id
        logger.info(f"`balance` command issued by user {inter.user.name}", extra={"id":c_id})

        # Checks to see if user exists 
        response, val = self.db.get_user(user_id, c_id)
        if not response:
            # If user not found
            logger.warning(f"`balance` command failed.", extra={"id":c_id})
            await unsuccessful_cmd(inter, f"Unsuccessful. Have you run `{PREFIX}config` yet?")
            return
        
        # Try and return balance from data if user found
        try:
            balance = val["Balance"]
            await successful_cmd(inter, title="Balance", message=balance)
            return
        except Exception as e:
            await unsuccessful_cmd(inter)
            logger.warning(f"Exception {type(e).__name__} occurred during `balance` issued by {inter.user.name}", extra={"id":c_id})
            return
    
    @commands.slash_command(name = "refresh", description = f"Reset your balance to {DEFAULT_BALANCE}. Command has a cooldown of 24 hours.")
    @commands.cooldown(1, 60*60*24, commands.BucketType.user)
    async def refresh(self, inter):
        await inter.response.defer()
        # Refreshes a user's balance with a specific cooldown
        c_id = str(uuid4())
        user_id = inter.user.id
        logger.info(f"`refresh` command issued by {inter.user.name}", extra={"id":c_id})

        # If no user exists create user
        response, val = self.db.check_user_exists(user_id, c_id)
        if (not val) or (not response):
            response = self.db.create_user(user_id, c_id)
            if response:
                await successful_cmd(inter)
                return
            else:
                logger.error(f"Failed to create user {inter.user.name}: {inter.user.id}", extra={"id":c_id})
                await unsuccessful_cmd(inter)
                return

        # If user exists reset balance
        response = self.db.set_balance(user_id, DEFAULT_BALANCE, c_id)
        if not response:
            logger.error(f"`refresh` command issued by {inter.user.name} failed", extra={"id":c_id})
            await unsuccessful_cmd(inter)
            return
        
        await successful_cmd(inter)
        return
    
    @refresh.error  # This decorator allows for handling errors local to the 'refresh' command.
    async def refresh_error(self, inter, error):
        if isinstance(error, commands.CommandOnCooldown):
            await unsuccessful_cmd(inter, title="Refresh Error", message=f"Try again in {math.ceil(error.retry_after/60)} minutes.")

    @commands.slash_command(name = "plot", description = "Visualize your Profit & Loss (PnL) over time.")
    async def plot(self, inter):
        await inter.response.defer()
        # Used for plotting a user's balance
        c_id = str(uuid4())
        user_id = inter.user.id
        logger.info(f"`plot` command issued by {inter.user.name}", extra={"id":c_id})
        response, val = self.db.check_user_exists(user_id, c_id)
        if (not response) or (not val):
            logger.warning(f"`plot` command failed due to DB error; user didn't configure.", extra={"id":c_id})
            await unsuccessful_cmd(inter, title = "Error", message=f"Something went wrong. Have you run `config`? Have you placed bets?")
            return
        try:
            data = await self.db.extract_bets(user_id, c_id)
            print(f"data obtained during `plot`: {data}")
            plot_pnl(inter.user.name, data, c_id)
            await pnl_embed(inter, c_id)
        except NoBetsException:
            logger.warning(f"`plot` command failed as there was no data to plot", extra={"id":c_id})
            await unsuccessful_cmd(inter, title = "No Data", message="No betting history data was obtained. Have you placed any bets yet?")
        except Exception:
            logger.warning(f"`plot` command failed during plotting of data. Unclear error", exc_info=True, extra={"id":c_id})
            await unsuccessful_cmd(inter)

    @commands.slash_command(name = "pnl", description = "See your aggregate PnL in figures and percentages.")
    async def pnl(self, inter):
        await inter.response.defer()
        # Used for calculating a user's total PnL
        c_id = str(uuid4())
        user_id = inter.user.id
        logger.info(f"`pnl` command issued by {inter.user.name}", extra={"id":c_id})
        response, val = self.db.check_user_exists(user_id, c_id)
        if (not response) or (not val):
            logger.warning(f"`plot` command failed due to DB error; user didn't configure.", extra={"id":c_id})
            await unsuccessful_cmd(inter, title = "Error", message=f"Something went wrong. Have you run `config`? Have you placed bets?")
            return
        try:
            data = await self.db.extract_bets(user_id, c_id)
            pnl = sum([bet["BalanceDelta"] for bet in data])
            await successful_cmd(inter, title = "PnL", message=f"{inter.user.mention} PnL: {pnl}")
        except:
            logger.warning(f"`pnl` command failed during calculation of pnl value. Unclear error", exc_info=True, extra={"id":c_id})
            await unsuccessful_cmd(inter)
    
    @commands.slash_command(name = "leaderboard", description = "Shows the betting leaderboard for the current server.")
    async def leaderboard(self, inter):
        await inter.response.defer()
        # Returns a leaderboard of top balances in the server
        c_id = str(uuid4())
        # Extract all members in guild
        guild_members = await inter.guild.fetch_members().flatten()
        logger.info(f"`leaderboard` command issued by {inter.user.name}", extra={"id":c_id})
        try:
            # For each member in guild extract their balance
            per_user_data = []
            for member in guild_members:
                response, balance = self.db.get_balance(member.id, c_id, suppress_log = True)
                if (not response) or (not balance):
                    continue
                per_user_data.append({"User": member, "balance": balance})
            
            # If no data obtained
            if not per_user_data:            
                logger.warning(f"`leaderboard` command failed. No data obtained.", extra={"id":c_id})
                await unsuccessful_cmd(inter)
                return
            
            # Sort by balance and print leaderboard embed
            per_user_data = sorted(per_user_data, key = lambda x: x["balance"], reverse=True)[:10]
            await leaderboard_embed(inter, per_user_data)
            
        except:
            logger.warning(f"`leaderboard` command failed during calculation of statisitcs. Unclear error", exc_info=True, extra={"id":c_id})
            await unsuccessful_cmd(inter)
