import aioboto3 
import boto3 
from boto3.dynamodb.conditions import Key
from decimal import Decimal
from enum import Enum, auto
import logging
import os
from typing import Dict, Tuple, List

from TestBot.utils import get_logger
from TestBot.exceptions import BalanceException

ROOT = os.environ["ROOT"]
DEFAULT_BALANCE = 5000
VERSION = os.environ["VERSION"]
log = get_logger(dir=f"{ROOT}/data/logs", filename="Dynamo.log", level=logging.DEBUG)

class Action(Enum):
    INCREMENT = auto()
    DECREMENT = auto()

class DynamoHandler:
    def __init__(self, resource: boto3.resource, client: boto3.client, session: aioboto3.Session):
        self.db = resource
        self.client = client 
        self.session = session
            
    def create_user(self, user_id: int, cmd_id: str) -> bool:
        try:
            self.db.Table(f"{VERSION}_Users").put_item(Item={"UserID": user_id, "Access": 0, "Balance": DEFAULT_BALANCE})
            return True
        except Exception as e:
            log.error(f"An exception occured during `create_user`: {type(e).__name__}", extra={"id":cmd_id})
            return False

    def delete_user(self, user_id: int, cmd_id: str) -> bool:
        try:
            self.db.Table(f"{VERSION}_Users").delete_item(Key={"UserID":user_id})
            return True
        except Exception as e:
            log.error(f"An exception occured during `delete_user`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            return False
        
    def config_user_steamid(self, user_id: int, steam_id: str, cmd_id: str) -> bool:
        try:
            self.db.Table(f"{VERSION}_Users").update_item(
                Key = {
                    "UserID":user_id
                },
                UpdateExpression = "SET #attrName = :attrValue",
                ExpressionAttributeNames = {
                    "#attrName": "SteamID"
                },
                ExpressionAttributeValues = {
                    ":attrValue": steam_id
                }
            )
            return True
        except Exception as e:
            log.error(f"An exception occured during `config_user_steamid`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            return False
  
    def config_user_and_steamid(self, user_id: int, steam_id: str, cmd_id: str) -> bool:
        try:
            self.db.Table(f"{VERSION}_Users").put_item(Item={"UserID":user_id, "SteamID":steam_id, "Access":0, "Balance": DEFAULT_BALANCE})
            return True
        except Exception as e:
            log.error(f"An exception occured during `config_user_and_steamid`: {type(e).__name__}", extra={"id":cmd_id})
            return False

    def check_user_exists(self, user_id: int, cmd_id: str) -> Tuple[bool, bool]:
        try:
            response = self.db.Table(f"{VERSION}_Users").get_item(Key={"UserID":user_id})
            if "Item" in response:
                return True, True
            else:
                return True, False
        except Exception as e:
            log.error(f"An exception occured during `check_user_exists`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            return False, False
    
    def create_guild(self, guild_id: int, cmd_id: str) -> bool:
        try:
            self.db.Table(f"{VERSION}_Guilds").put_item(Item = {"GuildID": guild_id, "Access":0})
            return True
        except Exception as e:
            log.error(f"An exception occured during `create_guild`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            return False

    def delete_guild(self, guild_id: int, cmd_id: str) -> bool:
        try:
            self.db.Table(f"{VERSION}_Guilds").delete_item(Key={"GuildID":guild_id})
            return True
        except Exception as e:
            log.error(f"An exception occured during `delete_guild`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            return False

    def get_balance(self, user_id: int, cmd_id: str, suppress_log: bool = False) -> Tuple[bool, float]:
        try:
            response = self.db.Table(f"{VERSION}_Users").get_item(Key = {"UserID": user_id})
            return True, response["Item"]["Balance"]
        except Exception as e:
            if not suppress_log:
                log.error(f"An exception occured during `get_balance`: {type(e).__name__}",  extra={"id":cmd_id})
            return False, None
        
    def get_user(self, user_id: int, cmd_id: str) -> Tuple[bool, Dict]:
        try:
            response = self.db.Table(f"{VERSION}_Users").get_item(Key = {"UserID": user_id})
            return True, response["Item"]
        except Exception as e:
            log.error(f"An exception occured during `get_user`: {type(e).__name__}", extra={"id":cmd_id})
            return False, None
        
    def get_user_steamid(self, user_id: int, cmd_id: str) -> Tuple[bool, int]:
        try:
            response, user = self.get_user(user_id, cmd_id)
            if not response:
                return False, None
            try:
                return True, user["SteamID"]
            except:
                return True, None
        except Exception as e:
            log.error(f"An exception occured during `get_user_steamid`: {type(e).__name__}", extra={"id":cmd_id})
            return False, None
    
    def set_balance(self, user_id: int, balance: float, cmd_id: str) -> bool:
        try:
            self.db.Table(f"{VERSION}_Users").update_item(
                Key = {"UserID": user_id},
                UpdateExpression = "SET Balance = :val",
                ExpressionAttributeValues = {":val": balance}
            )
            return True
        except Exception as e:
            log.error(f"An exception occured during `set_balance`: {type(e).__name__}", extra={"id":cmd_id})
            return False
        
    def log_completed_bet(self, bet_data, c_id):
        try:
            self.db.Table(f"{VERSION}_BetHistory").put_item(Item = bet_data)
        except:
            log.error(f"An exception occured during `log_bet`", exc_info=True, extra={"id":c_id})
            raise Exception

    def log_in_play_bet(self, bet_data, c_id):
        try:
            self.db.Table(f"{VERSION}_InPlay").put_item(Item = bet_data)
        except Exception:
            log.error(f"An exception occured during `log_bet`", exc_info=True, extra={"id":c_id})
            raise Exception

    def delete_in_play(self, _id):
        try:
            self.db.Table(f"{VERSION}_InPlay").delete_item(Key = {"cmd_id":_id})
        except Exception as e:
            log.error(f"An exception occured during `delete_in_play`", exc_info=True, extra={"id":"NULL"})
            raise Exception

    def update_balance(self, user_id: int, amount_change: Decimal, operation: Action, cmd_id: int, condition_expression: str = None):
        # Base dict
        update_params = {"Key": {"UserID": user_id}, 
                         "ExpressionAttributeValues": {":amount_change": amount_change}}
        # Directional operation         
        if operation == Action.INCREMENT:
            update_params["UpdateExpression"] = "SET Balance = Balance + :amount_change"
        elif operation == Action.DECREMENT:
            update_params["UpdateExpression"] = "SET Balance = Balance - :amount_change"

        # Condition check; used to avoid race conditions
        if condition_expression:
            update_params["ConditionExpression"] = condition_expression

        # Run operation
        try:
            response, current_balance = self.get_balance(user_id, cmd_id)
            if not response:
                raise Exception
            self.db.Table(f"{VERSION}_Users").update_item(**update_params)
        except Exception as e:
            log.error(f"An exception occured during `update_balance`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise BalanceException(current_balance, amount_change)
            else:
                raise Exception

    def load_in_play_bets(self, cmd_id: str = "NULL") -> List[Dict]:
        try:
            response = self.client.scan(TableName=f"{VERSION}_InPlay")
            if "Items" not in response:
                return False
            return response["Items"]
        except Exception as e:
            log.critical(f"An exception occured during `refund_bets`, shutting down: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            raise Exception 

    async def extract_bets(self, user_id: int, cmd_id: str) -> List[Dict]:
        try:
            async with self.session.resource("dynamodb") as resource:
                table = await resource.Table(f"{VERSION}_BetHistory")
                response = await table.query(KeyConditionExpression=Key("UserID").eq(user_id))
            if "Items" not in response:
                return False
            return sorted(response["Items"], key = lambda x: x["Timestamp"])
        except Exception as e:
            log.error(f"An exception occured during `extract_bets`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            raise Exception 

    def create_additional_user(self, data: Dict, cmd_id: str) -> None:
        try:
            self.db.Table(f"{VERSION}_additional_users").put_item(Item = data)
        except Exception:
            log.error(f"An exception occured during `create_additional_user`", exc_info=True, extra={"id":cmd_id})
            raise
        
    def extract_guild_additional_users(self, guildID: int, cmd_id: str):
        try:
            response = self.client.scan(TableName=f"{VERSION}_additional_users")
            if "Items" not in response:
                return False
            vals = [i for i in response["Items"] if int(i["GuildID"]["N"]) == guildID]
            return vals
        except Exception as e:
            log.error(f"An exception occured during `extract_guild_additional_users`: {type(e).__name__}", exc_info=True, extra={"id":cmd_id})
            raise Exception 