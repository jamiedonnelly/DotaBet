import aioboto3
import asyncio
import boto3
from botocore.config import Config
import disnake
from decimal import Decimal
from fuzzywuzzy import process, fuzz
import logging
import os
import time
import multiprocessing
import threading
from typing import Dict
import traceback

from TestBot.database.dynamo import DynamoHandler, Action
from TestBot.pricing import PricingModel
from TestBot.opendota.client import SyncDotaClient, AsyncDotaClient
from TestBot.utils import LogMessage
from TestBot.exceptions import BalanceException, LobbyTypeException, BetTimeException, ConfigException, BetValueException
from TestBot.embeds import winning_bet, losing_bet, bet_time_exception_embed

# init log
ROOT = os.environ["ROOT"]

# load constants
API_KEY = os.environ['OD_API_KEY']

# instantiate open dota client
od_client = SyncDotaClient(API_KEY)
async_client = AsyncDotaClient(API_KEY)

# Instantiate DB handler
session = aioboto3.Session()
db_config = Config(
retries={'max_attempts': 10,'mode': 'standard'},
connect_timeout = 5,
read_timeout = 5
)
db = DynamoHandler(boto3.resource('dynamodb', config=db_config), boto3.client('dynamodb'), session)

# Instantiate pricing model
s3 = boto3.resource("s3")
pricing_model = PricingModel(s3)

def process_outcome(outcome: str):
    # Uses natural language process to parse the `outcome` arg, improving robustness.
    OUTCOMES = ["Win", "Lose"]
    match, score = process.extractOne(outcome, OUTCOMES)
    if score < 80:
        raise ValueError({"outcome":outcome})
    if match == "Lose":
        return 0
    else:
        return 1

def process_value(value: float):
    try:
        value = Decimal(value)
    except:
        raise ValueError({"value":value})
    if value <= 0:
        raise BetValueException(value)
    return value

def standardise_args(args: Dict):
    args["Outcome"] = process_outcome(args["Outcome"])
    args["Value"] = process_value(args["Value"])
    return args
              
def validate_args_user(args: Dict, c_id: str) -> Dict:
    try:
        guild_add_users = db.extract_guild_additional_users(args["GuildID"], c_id)
    except:
        raise Exception
    for user in guild_add_users:
        if fuzz.ratio(user["Username"]["S"].lower(), args["Username"].lower()) > 85:
            args["BeteeSteamID"] = int(user["SteamID"]["N"])
            return args
    raise ConfigException

def validate_args_team(args: Dict, c_id: str) -> Dict:
    # check if the user betting has configured their profile
    response, val = db.check_user_exists(args["UserID"], c_id)
    # If no user profile configured, add user
    if (not response) or (not val):
        db.create_user(args["UserID"], c_id)
    return args

def validate_args_member(args: Dict, c_id: str) -> Dict:
    # check if the user betting has configured their profile
    response, val = db.check_user_exists(args["UserID"], c_id)
    # If no user profile configured, add user
    if (not response) or (not val):
        db.create_user(args["UserID"], c_id)

    # check if the user being bet on has steam configured
    response, bettee_steamid = db.get_user_steamid(args["BeteeID"], c_id)
    if not response:
        raise ConfigException  
    
    # If successful add  `bettee_steamid` to `args` and return
    args["BeteeSteamID"] = bettee_steamid
    return args

def bet_work(id: int, input_queue: multiprocessing.Queue, output_queue: multiprocessing.Queue, log_queue: multiprocessing.Queue) -> None:
    print(f"Worker {id} activated...")
    while True:
        if input_queue.empty():
            time.sleep(30)
        else:
            args = input_queue.get()
            if "TeamID" in args.keys():
                thread = threading.Thread(target = team_bet, args=(args, output_queue, log_queue))
                thread.start()            
            elif "Username" in args.keys():
                thread = threading.Thread(target = user_bet, args=(args, output_queue, log_queue))
                thread.start()  
            else:
                thread = threading.Thread(target = member_bet, args=(args, output_queue, log_queue))
                thread.start()  

def member_bet(args: Dict, output_queue: multiprocessing.Queue, log_queue: multiprocessing.Queue) -> disnake.Embed:
    c_id = args["cmd_id"]
    try:
            # Standardise args
        try:
            args = standardise_args(args)
        except BetValueException as e:
            # log message to log-worker
            log_queue.put(LogMessage(logging.WARNING, f"Negative bet value, bet failed. value: {e.value}", c_id))
            # send output to user via parent process
            embed = disnake.Embed(title = "Syntax Error", description="Invalid `bet` value. Bet value must be greater than 0.")
            output_queue.put((args, embed))
            return
        except ValueError as e:
            # log message to log-worker
            log_queue.put(LogMessage(logging.WARNING, f"Incorrect argument formatting raised exception. Argument: {e.args[0]}", c_id))
            # send output to user via parent process
            embed = disnake.Embed(title = "Syntax Error", description="Invalid `bet` syntax. Check `help` for examples.")
            output_queue.put((args, embed))
            return

        # Valiate user (check for config)
        try:
            args = validate_args_member(args, c_id)
        except ConfigException as e:
            log_queue.put(LogMessage(logging.WARNING, "Failed to validate bet arguments.", c_id))
            embed = disnake.Embed(title = "Config Error", description=f"Has the user you are betting on configured their profile with `steamconfig`?")
            output_queue.put((args, embed))
            return
        except Exception as e:
            # to catch generic errors
            log_queue.put(LogMessage(logging.WARNING, "Failed to validate bet arguments.", c_id))
            embed = disnake.Embed(title = "Error", description=f"Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Store initial balance
        response, init_balance = db.get_balance(args["UserID"], c_id)
        if (not response) or (not init_balance):
            log_queue.put(LogMessage(logging.WARNING, "Failed to obtain initial balance.", c_id))
            embed = disnake.Embed(title = "Error", description=f"Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Conditional update on DB balance; avoids race condition
        try:
            db.update_balance(args["UserID"], args["Value"], Action.DECREMENT, c_id, condition_expression="Balance >= :amount_change")
        except BalanceException as e:
            log_queue.put(LogMessage(logging.WARNING, "Balance exception occured during `update_balance` operation.", c_id))
            embed = disnake.Embed(title = "Balance Error", description =  "Invalid balance. The `bet` value exceeds your current balance.",\
                                    fields = [{"name":"Current Balance", "value":str(e.balance)}, {"name":"Bet Value", "value":str(e.value)}])                                    
            output_queue.put((args, embed))
            return
        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, "General exception occurred during `update_balance` operation of `bet` command", c_id))
            embed = disnake.Embed(title = "Error", description =  "Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return

        # Log bets to `InPlay` database
        try:
            db.log_in_play_bet(args, c_id)
        except Exception:
            log_queue.put(LogMessage(logging.CRITICAL, "Unable to log `member_bet` to in play database", c_id))
            embed = disnake.Embed(title = "Error", description =  "Something went wrong, please try again later.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            return

        # Get a new `match_id` 
        try: 
            latest_match_id = od_client.wait_new_id_player(args["BeteeSteamID"], c_id)
        except TimeoutError as e:
            log_queue.put(LogMessage(logging.WARNING, "Waiting for new game timeout exception occurred during `bet` command", c_id))
            embed = disnake.Embed(title = "Timeout Error", description=f"No new game was found. Was this a turbo game? Turbo games are currently not supported. If not this is likely a server error with OpenDota. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return 

        try:
            data = od_client.parse_match_get_data(latest_match_id, c_id)
        except TimeoutError as e:
            log_queue.put(LogMessage(logging.WARNING, "Parsing timeout occured during `bet`.", c_id))
            embed = disnake.Embed(title = "Timeout Error", description="Parse request timed out. Likely an OpenDota server error. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return 

        try:
            odds, payout = pricing_model(data, args, c_id)
        except LobbyTypeException as e:
            log_queue.put(LogMessage(logging.WARNING, "`LobbyTypeException` exception {str(e)} raised while calculating odds and payout", c_id))
            embed = disnake.Embed(title = "Lobby Error", description=f"Incorrect lobby type being bet on. Bet Refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return
        except BetTimeException as e:
            log_queue.put(LogMessage(logging.WARNING, f"`BetTimeException` exception {str(e)} raised while calculating odds and payout", c_id))
            embed = bet_time_exception_embed(e)
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return

        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, f"General exception {str(e)} raised while executing bet", c_id))
            embed = disnake.Embed(title = "Bet Error", description="Error executing the bet. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return
        
        # Process bet outcomes based on payouts
        if payout > 0:
            embed = winning_bet(args, odds, payout, c_id) 
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], payout, Action.INCREMENT, c_id)
            delta = payout
        else:
            embed = losing_bet(args, odds, payout, c_id)
            output_queue.put((args, embed))
            delta = -1*args["Value"]

        # Once bet is succesfully completed, can log the bet in the BetHistory DB.
        bet_data = {
            "UserID": args["UserID"],
            "BetID": c_id,  # Unique identifier for the bet
            "MatchID": latest_match_id,
            "Timestamp": args["Timestamp"],
            "BeteeID": args["BeteeID"],
            "Outcome": args["Outcome"],
            "Value": args["Value"],
            "Odds": str(odds),
            "BalanceDelta": delta,
            "NewBalance": init_balance + delta,
            "GuildID": args["GuildID"]
        }
        # Delete bet from `inPlay` database and log to completed database
        try:
            db.delete_in_play(c_id)
            db.log_completed_bet(bet_data, c_id)
        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, "Failed to log bet in DynamoDB", c_id))
    except:
        trace = traceback.format_exc()
        log_queue.put(LogMessage(logging.CRITICAL, f"Unknown exception occured during `member_bet`. Traceback:\n {str(trace)}", c_id))
        db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
        db.delete_in_play(c_id)

def team_bet(args: Dict, output_queue: multiprocessing.Queue, log_queue: multiprocessing.Queue) -> disnake.Embed:
    c_id = args["cmd_id"]
    
    try:
        # Standardise args
        try:
            args = standardise_args(args)
        except BetValueException as e:
            # log message to log-worker
            log_queue.put(LogMessage(logging.WARNING, f"Negative bet value, bet failed. value: {e.value}", c_id))
            # send output to user via parent process
            embed = disnake.Embed(title = "Syntax Error", description="Invalid `bet` value. Bet value must be greater than 0.")
            output_queue.put((args, embed))
            return
        except ValueError as e:
            # log message to log-worker
            log_queue.put(LogMessage(logging.WARNING, f"Incorrect argument formatting raised exception {e.args[0]}", c_id))
            # send output to user via parent process
            embed = disnake.Embed(title = "Syntax Error", description="Invalid `bet` syntax. Check `help` for examples.")
            output_queue.put((args, embed))
            return
        
        # Valiate user (check for config)
        try:
            args = validate_args_member(args, c_id)
        except ConfigException as e:
            log_queue.put(LogMessage(logging.WARNING, "Failed to validate bet arguments.", c_id))
            embed = disnake.Embed(title = "Config Error", description=f"Has the user you are betting on configured their profile with `steamconfig`?")
            output_queue.put((args, embed))
            return
        except Exception as e:
            # to catch generic errors
            log_queue.put(LogMessage(logging.WARNING, "Failed to validate bet arguments.", c_id))
            embed = disnake.Embed(title = "Error", description=f"Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Store initial balance
        response, init_balance = db.get_balance(args["UserID"], c_id)
        if (not response) or (not init_balance):
            log_queue.put(LogMessage(logging.WARNING, "Failed to obtain initial balance.", c_id))
            embed = disnake.Embed(title = "Error", description=f"Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Conditional update on DB balance; avoids race condition
        try:
            db.update_balance(args["UserID"], args["Value"], Action.DECREMENT, c_id, condition_expression="Balance >= :amount_change")
        except BalanceException as e:
            log_queue.put(LogMessage(logging.WARNING, "Balance exception occured during `update_balance` operation.", c_id))
            embed = disnake.Embed(title = "Balance Error", description =  "Invalid balance. The `bet` value exceeds your current balance.",\
                                    fields = [{"name":"Current Balance", "value":str(e.balance)}, {"name":"Bet Value", "value":str(e.value)}])                                    
            output_queue.put((args, embed))
            return
        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, "General exception occurred during `update_balance` operation of `bet` command", c_id))
            embed = disnake.Embed(title = "Error", description =  "Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Log bets to `InPlay` database
        try:
            db.log_in_play_bet(args, c_id)
        except Exception:
            log_queue.put(LogMessage(logging.CRITICAL, "Unable to log `team_bet` to in play database", c_id))
            embed = disnake.Embed(title = "Error", description =  "Something went wrong, please try again later.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            return

        # Get a new `match_id` 
        try: 
            latest_match_id = od_client.wait_new_id_team(args["TeamID"], c_id)
        except TimeoutError as e:
            log_queue.put(LogMessage(logging.WARNING, "Waiting for new game timeout exception occurred during `bet` command", c_id))
            embed = disnake.Embed(title = "Timeout Error", description=f"No new game was found. Was this a turbo game? Turbo games are currently not supported. If not this is likely a server error with OpenDota. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return 
        
        # Parse new game and extract stats
        try:
            data = od_client.parse_match_get_data(latest_match_id, c_id)
        except TimeoutError as e:
            log_queue.put(LogMessage(logging.WARNING, "Parsing timeout occured during `bet`.", c_id))
            embed = disnake.Embed(title = "Timeout Error", description="Parse request timed out. Likely an OpenDota server error. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return 
        
        # Run the blocking pricing call in a separate thread
        try:
            odds, payout = pricing_model(data, args, c_id)
        except LobbyTypeException as e:
            log_queue.put(LogMessage(logging.WARNING, "`LobbyTypeException` exception {str(e)} raised while calculating odds and payout", c_id))
            embed = disnake.Embed(title = "Lobby Error", description=f"Incorrect lobby type being bet on. Bet Refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return

        except BetTimeException as e:
            log_queue.put(LogMessage(logging.WARNING, "`BetTimeException` exception {str(e)} raised while calculating odds and payout", c_id))
            embed = bet_time_exception_embed(e)
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return

        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, f"General exception {str(e)} raised while executing bet", c_id))
            embed = disnake.Embed(title = "Bet Error", description="Error executing the bet. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return
        
        # Process bet outcomes based on payouts
        if payout > 0:
            embed = winning_bet(args, odds, payout, c_id) 
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], payout, Action.INCREMENT, c_id)
            delta = payout
        else:
            embed = losing_bet(args, odds, payout, c_id)
            output_queue.put((args, embed))
            delta = -1*args["Value"]

        # Once bet is succesfully completed, can log the bet in the BetHistory DB.
        bet_data = {
            "UserID": args["UserID"],
            "BetID": c_id,  # Unique identifier for the bet
            "MatchID": latest_match_id,
            "Timestamp": args["Timestamp"],
            "BeteeID": args["BeteeID"],
            "Outcome": args["Outcome"],
            "Value": args["Value"],
            "Odds": str(odds),
            "BalanceDelta": delta,
            "NewBalance": init_balance + delta,
            "GuildID": args["GuildID"]
        }

        # Delete bet from `inPlay` database and log to completed database
        try:
            db.delete_in_play(c_id)
            db.log_completed_bet(bet_data, c_id)
        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, "Failed to log bet in DynamoDB", c_id))
    except:
        trace = traceback.format_exc()
        log_queue.put(LogMessage(logging.CRITICAL, f"Unknown exception occured during `member_bet`. Traceback:\n {str(trace)}", c_id))
        db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
        db.delete_in_play(c_id)


def user_bet(args: Dict, output_queue: multiprocessing.Queue, log_queue: multiprocessing.Queue) -> disnake.Embed:
    c_id = args["cmd_id"]
    try:
        # Standardise args
        try:
            args = standardise_args(args)
        except BetValueException as e:
            # log message to log-worker
            log_queue.put(LogMessage(logging.WARNING, f"Negative bet value, bet failed. value: {e.value}", c_id))
            # send output to user via parent process
            embed = disnake.Embed(title = "Syntax Error", description="Invalid `bet` value. Bet value must be greater than 0.")
            output_queue.put((args, embed))
            return
        except ValueError as e:
            # log message to log-worker
            log_queue.put(LogMessage(logging.WARNING, f"Incorrect argument formatting raised exception {e.args[0]}", c_id))
            # send output to user via parent process
            embed = disnake.Embed(title = "Syntax Error", description="Invalid `bet` syntax. Check `help` for examples.")
            output_queue.put((args, embed))
            return
        
        # Valiate user (check for config)
        try:
            args = validate_args_user(args, c_id)
        except ConfigException as e:
            log_queue.put(LogMessage(logging.WARNING, "Failed to validate bet arguments. User likely doesn't exist.", c_id))
            embed = disnake.Embed(title = "Config Error", description=f"Have you correctly configured the profile of the user? Check `/configured_users` to see all configured users in the server.")
            output_queue.put((args, embed))
            return
        except Exception as e:
            # to catch generic errors
            log_queue.put(LogMessage(logging.WARNING, "Failed to validate bet arguments.", c_id))
            embed = disnake.Embed(title = "Error", description=f"Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Store initial balance
        response, init_balance = db.get_balance(args["UserID"], c_id)
        if (not response) or (not init_balance):
            log_queue.put(LogMessage(logging.WARNING, "Failed to obtain initial balance.", c_id))
            embed = disnake.Embed(title = "Error", description=f"Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Conditional update on DB balance; avoids race condition
        try:
            db.update_balance(args["UserID"], args["Value"], Action.DECREMENT, c_id, condition_expression="Balance >= :amount_change")
        except BalanceException as e:
            log_queue.put(LogMessage(logging.WARNING, "Balance exception occured during `update_balance` operation.", c_id))
            embed = disnake.Embed(title = "Balance Error", description =  "Invalid balance. The `bet` value exceeds your current balance.",\
                                    fields = [{"name":"Current Balance", "value":str(e.balance)}, {"name":"Bet Value", "value":str(e.value)}])                                    
            output_queue.put((args, embed))
            return
        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, "General exception occurred during `update_balance` operation of `bet` command", c_id))
            embed = disnake.Embed(title = "Error", description =  "Something went wrong, please try again later.")
            output_queue.put((args, embed))
            return
        
        # Log bets to `InPlay` database 
        try:
            db.log_in_play_bet(args, c_id)
        except Exception:
            log_queue.put(LogMessage(logging.CRITICAL, "Unable to log `user_bet` to in play database", c_id))
            embed = disnake.Embed(title = "Error", description =  "Something went wrong, please try again later.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            return

        # Get a new `match_id` 
        try: 
            latest_match_id = od_client.wait_new_id_player(args["BeteeSteamID"], c_id)
        except TimeoutError as e:
            log_queue.put(LogMessage(logging.WARNING, "Waiting for new game timeout exception occurred during `bet` command", c_id))
            embed = disnake.Embed(title = "Timeout Error", description=f"No new game was found. Was this a turbo game? Turbo games are currently not supported. If not this is likely a server error with OpenDota. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return 
        
        # Parse new game and extract stats
        try:
            data = od_client.parse_match_get_data(latest_match_id, c_id)
        except TimeoutError as e:
            log_queue.put(LogMessage(logging.WARNING, "Parsing timeout occured during `bet`.", c_id))
            embed = disnake.Embed(title = "Timeout Error", description="Parse request timed out. Likely an OpenDota server error. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return 
        
        # Run the blocking pricing call in a separate thread
        try:
            odds, payout = pricing_model(data, args, c_id)
        except LobbyTypeException as e:
            log_queue.put(LogMessage(logging.WARNING, f"`LobbyTypeException` exception {str(e)} raised while calculating odds and payout", c_id))
            embed = disnake.Embed(title = "Lobby Error", description=f"Incorrect lobby type being bet on. Bet Refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return

        except BetTimeException as e:
            log_queue.put(LogMessage(logging.WARNING, f"`BetTimeException` exception {str(e)} raised while calculating odds and payout", c_id))
            embed = bet_time_exception_embed(e)
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return

        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, f"General exception {str(e)} raised while executing bet", c_id))
            embed = disnake.Embed(title = "Bet Error", description="Error executing the bet. Bet refunded.")
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
            db.delete_in_play(c_id)
            return
        
        # Process bet outcomes based on payouts
        if payout > 0:
            embed = winning_bet(args, odds, payout, c_id) 
            output_queue.put((args, embed))
            db.update_balance(args["UserID"], payout, Action.INCREMENT, c_id)
            delta = payout
        else:
            embed = losing_bet(args, odds, payout, c_id)
            output_queue.put((args, embed))
            delta = -1*args["Value"]

        # Once bet is succesfully completed, can log the bet in the BetHistory DB.
        bet_data = {
            "UserID": args["UserID"],
            "BetID": c_id,  # Unique identifier for the bet
            "MatchID": latest_match_id,
            "Timestamp": args["Timestamp"],
            "BeteeUsername": args["Username"],
            "Outcome": args["Outcome"],
            "Value": args["Value"],
            "Odds": str(odds),
            "BalanceDelta": delta,
            "NewBalance": init_balance + delta,
            "GuildID": args["GuildID"]
        }

        # Delete bet from `inPlay` database and log to completed database
        try:
            db.delete_in_play(c_id)
            db.log_completed_bet(bet_data, c_id)
        except Exception as e:
            log_queue.put(LogMessage(logging.WARNING, "Failed to log bet in DynamoDB", c_id))
    except:
        trace = traceback.format_exc()
        log_queue.put(LogMessage(logging.CRITICAL, f"Unknown exception occured during `user_bet`. Traceback:\n {str(trace)}", c_id))
        db.update_balance(args["UserID"], args["Value"], Action.INCREMENT, c_id)
        db.delete_in_play(c_id)