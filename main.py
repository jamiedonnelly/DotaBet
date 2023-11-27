import aioboto3
import asyncio
import boto3
from botocore.config import Config
from decimal import Decimal
import disnake
from disnake.ext import commands
import json
import logging
import os 
import matplotlib
import multiprocessing 
from multiprocessing import Queue
matplotlib.use('Agg')

from TestBot.database.dynamo import DynamoHandler, Action
from TestBot.opendota.client import AsyncDotaClient, SyncDotaClient
from TestBot.cogs.users import User
from TestBot.pricing import PricingModel
from TestBot.cogs.guilds import Guild
from TestBot.cogs.balance import Balance
from TestBot.cogs.gambling import Gambling
from TestBot.cogs.utils import Utils
from TestBot.cogs.help import Help
from TestBot.betting import bet_work
from TestBot.utils import get_logger, stream_outputs, stream_bet_logs

ROOT = os.environ["ROOT"]
log = get_logger(dir=f"{ROOT}/data/logs", filename="main.log", level=logging.ERROR)

class MyClient(commands.Bot):
    def __init__(self, output_queue, db, *args, **kwargs):
        super().__init__(*args,**kwargs)
        self.output_queue = output_queue
        self.db = db
        
    async def on_ready(self):
        await self.change_presence(activity=disnake.Game(name='-25 mmr'))
        print('Logged in as')
        print(self.user.name)
        print(self.user.id)
        print('------')
        try:
            await self.update_message()
        except:
            log.error("Update error", exc_info=True, extra={"id":"NULL"})
        # Refund any incomplete bets, if this fails for whatever reason, shut down again
        try:
            await self.loop.run_in_executor(None, self.refund_bets)
        except Exception as e:
            log.critical("`refund_bets` failed. Shutting down the bot.", exc_info=True, extra={"id":"NULL"})
            await self.close()  
            return
        # stream outputs
        self.loop.create_task(stream_outputs(self, self.output_queue))

    async def update_message(self):
        if "update.json" in os.listdir(f"{ROOT}/data/"):
            fp = f"{ROOT}/data/update.json"
            with open(fp,"r") as f:
                json_str = json.load(f)
        else:
            return
        embed = disnake.Embed.from_dict(json_str)
        for guild in self.guilds:
            for channel in guild.channels:
                if isinstance(channel, disnake.TextChannel):
                    try:
                        await channel.send(embed=embed)
                        break
                    except Exception:
                        pass
        # delete update file once it's been sent.
        print("Updates released...")
        os.system(f"rm '{fp}'")

    def refund_bets(self):
        try:
            bets = self.db.load_in_play_bets()
            print(f"Refund bets: {bets}")
            if not bets:
                return
            # refund bet and then delete from the database
            for bet in bets:
                user, value = int(bet["UserID"]["N"]), Decimal(bet["Value"]["N"])
                self.db.update_balance(user, value, Action.INCREMENT, cmd_id="NULL")
                self.db.delete_in_play(bet["cmd_id"]["S"])
        except:
            raise Exception

async def main():
    # load token 
    TOKEN = os.environ["TOKEN"]
    API_KEY = os.environ['OD_API_KEY']
    N_WORKERS = 1

    # Declare intents
    intents = disnake.Intents.default()
    intents.members = True
    intents.message_content = True

    # Instantiate DB handler
    session = aioboto3.Session()
    db_config = Config(
    retries={'max_attempts': 10,'mode': 'standard'},
    connect_timeout = 5,
    read_timeout = 5
    )
    db = DynamoHandler(boto3.resource('dynamodb', config=db_config), boto3.client('dynamodb'), session)

    # Instantiate OpenDota client
    async_dota_client = AsyncDotaClient(API_KEY) 

    # Instantiate worker queues 
    input_queue = Queue()
    output_queue = Queue()
    log_queue = Queue()

    # Initialise logger
    worker = multiprocessing.Process(target = stream_bet_logs, args = (log_queue,), daemon=True)
    worker.start()

    # Initialise workers
    workers = [multiprocessing.Process(target = bet_work, args = (i, input_queue, output_queue, log_queue), daemon=True) for i in range(N_WORKERS)]
    for worker in workers:
        worker.start()
    
    # Instantiate bot
    bot = MyClient(db = db, command_prefix = os.environ["PREFIX"], intents = intents, output_queue = output_queue)

    # Add cogs
    bot.add_cog(User(bot, db_handler=db, dota_client=async_dota_client))
    bot.add_cog(Guild(bot, db_handler=db))
    bot.add_cog(Balance(bot, db_handler=db))
    bot.add_cog(Gambling(bot, db_handler=db, bets_queue=input_queue))
    bot.add_cog(Utils(bot))
    bot.add_cog(Help(bot))

    # Run bot
    await bot.start(TOKEN)

###
if __name__=="__main__":
    asyncio.run(main())