import disnake
from disnake.ext import commands
import logging
import os

from TestBot.utils import get_logger
from TestBot.embeds import example_message, unsuccessful_cmd

PREFIX = os.environ["PREFIX"]
ROOT = os.environ["ROOT"]
logger = get_logger(dir=f"{ROOT}/data/logs", filename="Help.log", level=logging.INFO)

HELP_ENUM = commands.option_enum({
	"Category Overview": "cogs",
	"Category: Users": "cog:User",
	"Category: Betting": "cog:Gambling",
    "Category: Balance": "cog:Balance",
	"Category: Utils": "cog:Utils",
    "Category: Help": "cog:Help"
})

class Help(commands.Cog, name = "Help"):
    """Commands and functions related to Help functionality and documentation."""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.slash_command(description = "Gives an example of the `bet` command functionality.")
    async def example(self, inter):
        await inter.response.defer()
        try:
            await example_message(inter)
        except:
            await unsuccessful_cmd(inter)

    @commands.slash_command(description="Provides documentation and hints about bot commands.")
    async def help(self, inter, topic: HELP_ENUM):
        await inter.response.defer()

        if topic == "cogs":
            embed = disnake.Embed(title=f"{inter.bot.user.name} Command Categories",
                                description="DotaBet has the following categories for various commands:\n(Please note that DotaBet does not currently support Turbo games)")
            for cog_name, cog_instance in inter.bot.cogs.items():
                if cog_name not in ["Owner", "Guild"]:
                    first_line = cog_instance.__doc__.split('\n')[0] if cog_instance.__doc__ else "No description"
                    embed.add_field(name=f"**{cog_name}**", value=first_line, inline=False)
            await inter.send(embed=embed)
            return

        # Handling specific cog help
        cog_name = topic.replace("cog:", "")
        cog = self.bot.get_cog(cog_name)
        if cog:
            embed = disnake.Embed(title=f"Category: {cog_name}")
            description_lines = [cog.__doc__.split('\n')[0] if cog.__doc__ else "No description", "\n**Commands:**\n"]

            for command in cog.get_slash_commands():
                if command.qualified_name == 'dejelle':
                    continue
                cmd_name = f"/{command.qualified_name}"
                cmd_description = command.description or "No description provided"
                description_lines.append(f"**{cmd_name}**: {cmd_description}")

            embed.description = "\n".join(description_lines)
            await inter.followup.send(embed=embed)
        else:
            await inter.followup.send(f"No category found with the name `{cog_name}`.")