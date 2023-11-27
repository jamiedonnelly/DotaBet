from decimal import Decimal
import disnake
import os
from typing import List, Dict

from TestBot.pricing import Odds
from TestBot.exceptions import BetTimeException

PREFIX = os.environ["PREFIX"]
ROOT = os.environ["ROOT"]

async def unsuccessful_cmd(inter, title: str = "Error", message: str = "Something went wrong, please try again later.", fields: List[Dict] = []) -> None:
    embed = disnake.Embed(title=title, description=message, color=0x000000)
    if fields:
        for field in fields:
            embed.add_field(**field, inline=True)
    await inter.followup.send(embed=embed)

async def successful_cmd(inter, title: str = "Success", message: str = None) -> None:
    if message:
        embed = disnake.Embed(title=title, description=message, color=0xFFFFFF)
        await inter.followup.send(embed=embed, ephemeral=True)
    else:
        await inter.followup.send(content="✅", ephemeral=True)

def winning_bet(args: dict, odds: Odds, payout: Decimal, cmd_id: str) -> disnake.Embed:
    outcome = "win" if args["Outcome"] == 1 else "lose"
    if "Username" in args.keys():
        description = f"<@{args['UserID']}> bet on {args['Username']} to {outcome} and won!"
    elif "BeteeID" in args.keys():
        description = f"<@{args['UserID']}> bet on <@{args['BeteeID']}> to {outcome} and won!"
    elif "Team" in args.keys():
        description = f"<@{args['UserID']}> bet on {args['Team']} to {outcome} and won!"
    embed = disnake.Embed(title = "Winning Bet", description=description, color=0xffffff)
    embed.set_thumbnail(url = f"attachment://game{str(cmd_id)}.png")
    embed.set_image(url = f"attachment://game{str(cmd_id)}.png")
    embed.add_field(name="Bet Value", value=str(args["Value"]), inline=True)
    embed.add_field(name="Odds", value=str(odds), inline=True)
    embed.add_field(name="Payout", value=str(payout), inline=True)
    return embed

def losing_bet(args: dict, odds: Odds, payout: Decimal, cmd_id: str) -> disnake.Embed:
    outcome = "win" if args["Outcome"] == 1 else "lose"
    if "Username" in args.keys():
        description = f"<@{args['UserID']}> bet on {args['Username']} to {outcome} and won!"
    elif "BeteeID" in args.keys():
        description = f"<@{args['UserID']}> bet on <@{args['BeteeID']}> to {outcome} and won!"
    elif "Team" in args.keys():
        description = f"<@{args['UserID']}> bet on {args['Team']} to {outcome} and won!"
    embed = disnake.Embed(title = "Losing Bet", description=description, color=0x000000)
    embed.set_thumbnail(url = f"attachment://game{str(cmd_id)}.png")
    embed.set_image(url = f"attachment://game{str(cmd_id)}.png")
    embed.add_field(name="Bet Value", value=str(args["Value"]), inline=True)
    embed.add_field(name="Odds", value=str(odds), inline=True)
    embed.add_field(name="Payout", value=str(payout), inline=True)
    return embed 

async def example_message(inter):
    embed = disnake.Embed(title = "Example Bet", description = """The syntax of a bet command is broken up into 
                          four components: `command`, `user`, `outcome`, `value`.""")
    embed.add_field(name = "Command", value = f"/bet.")
    embed.add_field(name = "User", value = f"Mentioning a configured user (@user) or a profession team by searching their name.")
    embed.add_field(name = "Outcome", value = f"The prediction of the outcome, i.e., is @user going to win/lose. Valid values are variations of win/w/lose/l.")
    embed.add_field(name = "Value", value = f"Any monetary value, i.e., 100.")
    await inter.followup.send(embed = embed)    

async def pnl_embed(inter, cmd_id: str) -> None:
    embed = disnake.Embed(title = "Balance", description=f"<@{inter.user.id}>")
    file = disnake.File(f"{ROOT}/data/plots/pnl{str(cmd_id)}.png", filename=f"pnl{str(cmd_id)}.png")
    embed.set_image(url = f"attachment://pnl{str(cmd_id)}.png")
    await inter.followup.send(embed=embed, file=file)

async def leaderboard_embed(inter, data: dict) -> None:
    embed = disnake.Embed(title = "Leaderboard")
    for ix, val in enumerate(data):
        embed.add_field(name = f"{ix+1}.", value = f"{val['User'].mention}: {val['balance']}")
    await inter.followup.send(embed = embed)

def bet_time_exception_embed(e: BetTimeException):
    embed = disnake.Embed(title = "Bet Time Error", description="Incorrect bet time. Bet refunded.")
    embed.add_field(name = "Bet Time", value=e.bet)
    embed.add_field(name = "Match Start Time", value=e.start)
    embed.add_field(name = "Match End time", value=e.end)
    return embed

