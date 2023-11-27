import asyncio
import logging
import os
import requests
from typing import Dict, List
import httpx 
import time

from TestBot.opendota.utils import check_response
from TestBot.utils import get_logger

ROOT = os.environ["ROOT"]
logger = get_logger(dir=f"{ROOT}/data/logs", filename="Dota.log", level=logging.DEBUG)

class AsyncDotaClient():

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.opendota.com/api/"

    def format_api_url(self, query: str, api_key: str = None) -> str:
        if api_key:
            return f"{self.base_url}{query}?api_key={api_key}"
        else:
            return f"{self.base_url}{query}"
    
    async def get_json_data(self, query: str, params: Dict = None):
        url = self.format_api_url(query)
        
        if not params:
            params = {}
        params["api_key"] = self.api_key 
        
        RETRIES = 3
        for _ in range(RETRIES):
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10, read=30.0)) as client:
                    response = check_response(await client.get(url, params=params))
                return response.json()
            except (httpx.RequestError, Exception) as e:
                await asyncio.sleep(5) 
        logger.error(f"Error {str(e)} in `get_json_data`.", exc_info=True, extra={"id":0})

    async def health(self):
        try:
            return await self.get_json_data("health")
        except Exception as e:
            logger.error(f"Error {str(e)} in `health`.", exc_info=True, extra={"id":0})
    
    async def is_parsed(self, match_id: int) -> bool:
        data = await self.get_match(match_id)
        # check if the xp/gold data is valid
        if (data['radiant_xp_adv'] is None) & (data['radiant_gold_adv'] is None):
            return False
        return True

    async def wait_new_id(self, player_id: int) -> int:
        # Extract current `match_id`
        latest_id = await self.latest_match_id(player_id)
        status = False
        # Wait for new `match_id`
        while not status:
            _id = await self.latest_match_id(player_id)
            if _id != latest_id:
                return _id
            # sleep for 120; a long sleep improves rest of the code but increases latency
            await asyncio.sleep(120)
        logger.error(f"No new _id found in `wait_new_id`. Raising exception.", exc_info=True, extra={"id":0})
        raise

    async def parse_game(self, match_id: int) -> None:
        try:
            # post request
            query = f"request/{match_id}"
            url = self.format_api_url(query, self.api_key)
            check_response(requests.post(url))
            
            # async check to see if parse has completed
            status = True
            while status:
                if await self.is_parsed(match_id):
                    status = False
                else:
                    await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Error {str(e)} in `parse_game`.", exc_info=True, extra={"id":0})

    async def parse_match_get_data(self, match_id: int) -> Dict:
        MAX_RETRIES, RETRY_DELAY = 5, 5
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Check if the game is already parsed
                if await self.is_parsed(match_id):
                    logger.info(f"Match {match_id} is already parsed. Retrieving data...", extra={"id":0})
                    match_data = await asyncio.wait_for(self.get_match(match_id), timeout=60)
                    return match_data

                # If not parsed, try parsing it
                logger.info(f"Match {match_id} is not parsed. Attempting parse (Attempt {attempt}/{MAX_RETRIES})...", extra={"id":0})
                await asyncio.wait_for(self.parse_game(match_id), timeout=220)

                # After parsing, retrieve the game data
                # Add sleep to allow the OpenDota server time to adjust 
                await asyncio.sleep(20)
                match_data = await asyncio.wait_for(self.get_match(match_id), timeout=30)
                
                if not match_data["radiant_xp_adv"]:
                    logger.warning(f"Match data for {match_id} is empty or invalid. Retrying...", extra={"id":0})
                    continue

                return match_data

            except asyncio.TimeoutError:
                logger.warning(f"Timeout error on attempt {attempt} for match_id {match_id}.", extra={"id":0})
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to retrieve match data for match_id {match_id} after {MAX_RETRIES} attempts due to timeouts.", extra={"id":0})
                    raise 

            except Exception as e:
                logger.warning(f"Error while trying to retrieve match data for match_id {match_id} on attempt {attempt}: {str(e)}", extra={"id":0})
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to retrieve match data for match_id {match_id} after {MAX_RETRIES} attempts.", extra={"id":0})
                    raise

        logger.error(f"Failed to retrieve match data for match_id {match_id} after {MAX_RETRIES} attempts.", extra={"id":0})
        raise ValueError(f"Failed to retrieve match data for match_id {match_id}.")

    async def get_match(self, match_id: int) -> Dict:
        query = f"matches/{match_id}"
        data = await self.get_json_data(query)
        return data
    
    async def get_recent_id(self) -> str:
        data = await self.get_json_data("live")
        return data[0]["match_id"]

    async def get_current_patch(self) -> int:
        query = "constants/patch"
        data = await self.get_json_data(query)
        sorted_ids = [d["id"] for d in sorted(data, key=lambda x: x["date"])]
        return sorted_ids[-1]
    
    async def get_matches_by_player(self, player_id: int, limit: int=None) -> List[Dict]:
        query = f"players/{player_id}/matches"
        data = await self.get_json_data(query)
        if limit:
            return data[:limit]
        else:
            return data
    
    async def latest_match_id(self, player_id: int) -> Dict:
        matches = await self.get_matches_by_player(player_id)
        return matches[0]['match_id']
    

class SyncDotaClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.opendota.com/api/"

    def format_api_url(self, query: str, api_key: str = None) -> str:
        if api_key:
            return f"{self.base_url}{query}?api_key={api_key}"
        else:
            return f"{self.base_url}{query}"

    def get_json_data(self, query: str, params: Dict = None):
        url = self.format_api_url(query)
        
        if not params:
            params = {}
        params["api_key"] = self.api_key 
        
        RETRIES = 3
        for _ in range(RETRIES):
            try:
                response = check_response(requests.get(url, params = params))
                return response.json()
            except Exception as e:
                time.sleep(5)
                #logger.error(f"Error {str(e)} in `get_json_data`.", exc_info=True, extra={"id":cmd_id})
    
    def is_parsed(self, match_id: int) -> bool:
        data = self.get_match(match_id)
        # check if the xp/gold data is valid
        if (data['radiant_xp_adv'] is None) & (data['radiant_gold_adv'] is None):
            return False
        return True

    def wait_new_id_player(self, player_id: int, cmd_id: str, timeout: int = 80 * 60) -> int:
        # init timer
        start_time = time.time()
        # Extract current `match_id`
        latest_id = self.latest_match_id_player(player_id)
        status = False
        # Wait for new `match_id`
        while not status:
            if (time.time() - start_time) > timeout:
                raise TimeoutError
            _id = self.latest_match_id_player(player_id)
            if _id != latest_id:
                logger.debug(f"New id found: {_id}", extra={"id":cmd_id})
                return _id
            # sleep for 120; a long sleep improves rest of the code but increases latency
            time.sleep(120)
        logger.error(f"No new _id found in `wait_new_id_player`. Raising exception.", exc_info=True, extra={"id":cmd_id})
        raise Exception

    def wait_new_id_team(self, team_id: int, cmd_id: str, timeout: int = 80 * 60) -> int:
        # init timer
        start_time = time.time()
        # Extract current `match_id`
        latest_id = self.latest_match_id_team(team_id)
        status = False
        # Wait for new `match_id`
        while not status:
            if (time.time() - start_time) > timeout:
                raise TimeoutError
            _id = self.latest_match_id_team(team_id)
            if _id != latest_id:
                logger.debug(f"New id found: {_id}", extra={"id":cmd_id})
                return _id
            # sleep for 120; a long sleep improves rest of the code but increases latency
            time.sleep(30)
        logger.error(f"No new _id found in `wait_new_id_team`. Raising exception.", exc_info=True, extra={"id":cmd_id})
        raise Exception

    def parse_game(self, match_id: int, timeout: int = 180) -> None:
        # post request
        query = f"request/{match_id}"
        url = self.format_api_url(query, self.api_key)
        check_response(requests.post(url))
        
        # async check to see if parse has completed
        status = True
        # init timer
        start_time = time.time()
        while status:
            if (time.time() - start_time) > timeout:
                raise TimeoutError
            if self.is_parsed(match_id):
                status = False
            else:
                time.sleep(20)

    def parse_match_get_data(self, match_id: int, cmd_id: str) -> Dict:
        MAX_RETRIES, RETRY_DELAY = 8, 5

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                # Check if the game is already parsed
                if self.is_parsed(match_id):
                    logger.info(f"Match {match_id} is already parsed. Retrieving data...", extra={"id":cmd_id})
                    match_data = self.get_match(match_id)
                    return match_data

                # If not parsed, try parsing it
                logger.info(f"Match {match_id} is not parsed. Attempting parse (Attempt {attempt}/{MAX_RETRIES})...", extra={"id":cmd_id})
                self.parse_game(match_id)

                # After parsing, retrieve the game data
                # Add sleep to allow the OpenDota server time to adjust 
                time.sleep(20)
                match_data = self.get_match(match_id)
                
                if not match_data["radiant_xp_adv"]:
                    logger.warning(f"Match data for {match_id} is empty or invalid. Retrying...", extra={"id":cmd_id})
                    continue

                return match_data

            except TimeoutError as e:
                logger.warning(f"Error while trying to retrieve match data for match_id {match_id} on attempt {attempt}: {str(e)}", extra={"id":cmd_id})
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to retrieve match data for match_id {match_id} after {MAX_RETRIES} attempts.", extra={"id":cmd_id})
                    raise
            
            except Exception as e:
                logger.warning(f"Error while trying to retrieve match data for match_id {match_id} on attempt {attempt}: {str(e)}", extra={"id":cmd_id})
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Failed to retrieve match data for match_id {match_id} after {MAX_RETRIES} attempts.", extra={"id":cmd_id})
                    raise

        logger.error(f"Failed to retrieve match data for match_id {match_id} after {MAX_RETRIES} attempts.", extra={"id":cmd_id})
        raise ValueError(f"Failed to retrieve match data for match_id {match_id}.")

    def get_match(self, match_id: int) -> Dict:
        query = f"matches/{match_id}"
        data = self.get_json_data(query)
        return data

    def get_recent_id(self) -> str:
        data = self.get_json_data("live")
        return data[0]["match_id"]

    def get_matches_by_player(self, player_id: int, limit: int=None) -> List[Dict]:
        query = f"players/{player_id}/matches"
        data = self.get_json_data(query)
        if limit:
            return data[:limit]
        else:
            return data
        
    def get_matches_by_team(self, team_id: int, limit: int=None) -> List[Dict]:
        query = f"teams/{team_id}/matches"
        data = self.get_json_data(query)
        if limit:
            return data[:limit]
        else:
            return data

    def latest_match_id_player(self, player_id: int) -> Dict:
        matches = self.get_matches_by_player(player_id)
        return matches[0]['match_id']

    def latest_match_id_team(self, team_id: int) -> Dict:
        matches = self.get_matches_by_team(team_id)
        return matches[0]['match_id']
    
    def health(self):
        try:
            return self.get_json_data("health")
        except Exception as e:
            logger.error(f"Error {str(e)} in `health`.")
    
if __name__=="__main__":
    api_key = os.environ["OD_API_KEY"]
    sda = SyncDotaClient(api_key=api_key)
    ada = AsyncDotaClient(api_key=api_key)