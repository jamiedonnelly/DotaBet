import asyncio
import disnake
import logging
import os 
import multiprocessing
import  time

ROOT = os.environ["ROOT"]

async def stream_outputs(bot, output_queue: multiprocessing.Queue):
    while True:
        if output_queue.empty():
            await asyncio.sleep(120)
        else:
            args, embed = output_queue.get()
            channel, user = bot.get_channel(args["ChannelID"]), args["UserID"]
            if (embed.title == "Losing Bet") or (embed.title == "Winning Bet"):
                file = disnake.File(f"{ROOT}/data/plots/game{args['cmd_id']}.png", filename=f"game{args['cmd_id']}.png")
                await channel.send(f"<@{user}>", embed=embed, file=file)
            else:
                await channel.send(f"<@{user}>", embed=embed)

def stream_bet_logs(log_queue: multiprocessing.Queue):
    logger = get_logger(dir=f"{ROOT}/data/logs", filename="Betting.log", level=logging.DEBUG)
    while True:
        if log_queue.empty():
            time.sleep(60)
        else:
            log = log_queue.get()
            if log.level == logging.DEBUG:
                logger.debug(log.msg, extra={"id":log.id})
                continue
            if log.level == logging.INFO:
                logger.info(log.msg, extra={"id":log.id})
                continue
            if log.level == logging.WARNING:
                logger.warning(log.msg, extra={"id":log.id})
                continue
            if log.level == logging.ERROR:
                logger.error(log.msg, extra={"id":log.id})
                continue
            if log.level == logging.CRITICAL:
                logger.critical(log.msg, extra={"id":log.id})
                continue

def get_logger(dir: str, filename: str, level=logging.DEBUG) -> logging.Logger:
    # Construct full path
    filepath = os.path.join(dir, filename)

    # Create a logger name based on the filename
    logger_name = filename.split(".")[0]  

    # Configure logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Check if the handler already exists
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == filepath for h in logger.handlers):
        formatter = logging.Formatter('%(asctime)s - [%(id)s] - %(levelname)s - %(message)s')
        
        # Configure file handler for >> `filename`
        file_handler = logging.FileHandler(filepath)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

class LogMessage:
    def __init__(self, level: int, msg: str, id: str):
        self._level = level
        self._msg = msg
        self._id = id 
    
    @property
    def level(self):
        return self._level

    @property
    def msg(self):
        return self._msg
    
    @property
    def id(self):
        return self._id

