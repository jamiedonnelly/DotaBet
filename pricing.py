import asyncio
import boto3
from datetime import datetime
from decimal import Decimal
import logging
import numpy as np 
import math
import os
import time
from typing import Dict, Tuple
from xgboost import XGBClassifier

from TestBot.opendota.client import SyncDotaClient, AsyncDotaClient
from TestBot.opendota.parsing import GameParser
from TestBot.exceptions import LobbyTypeException, BetTimeException
from TestBot.utils import get_logger
from TestBot.plotting import plot_game

PREFIX = os.environ["PREFIX"]
ROOT = os.environ["ROOT"]
MODEL_PATH = f"{ROOT}/model/"
WEIGHTS1, WEIGHTS2 = "draft.json", "stats.json"
WEIGHTS = "weights.json"
logger = get_logger(dir=f"{ROOT}/data/logs", filename="Pricing.log", level=logging.INFO)

class Odds:
    def __init__(self, prob: float):
        self._prob = prob
        self._numerator, self._denominator = self._transform()

    def _transform(self) -> Tuple[Decimal, Decimal]:
        odds = (1 / self._prob) - 1
        # To convert odds to a fraction
        denominator = 10
        numerator = round(odds * denominator)
        # Simplify the fraction
        common_divisor = math.gcd(numerator, denominator)
        return Decimal(numerator // common_divisor), Decimal(denominator // common_divisor)

    @property
    def numerator(self):
        return self._numerator

    @property
    def denominator(self):
        return self._denominator

    def payout(self, stake: Decimal) -> Decimal:
        profit = stake * (self.numerator / self.denominator)
        return stake + profit

    def __repr__(self):
        return f"{self.numerator}/{self.denominator}"
    
    def __str__(self):
        return f"{self.numerator}/{self.denominator}"
    
    def __lt__(self, other):
        if not isinstance(other, Odds):
            return NotImplemented
        return self._prob < other._prob

    def __le__(self, other):
        if not isinstance(other, Odds):
            return NotImplemented
        return self._prob <= other._prob

    def __gt__(self, other):
        if not isinstance(other, Odds):
            return NotImplemented
        return self._prob > other._prob

    def __ge__(self, other):
        if not isinstance(other, Odds):
            return NotImplemented
        return self._prob >= other._prob
   
class PricingModel:

    def __init__(self, aws: boto3.resource): 
        self.s3 = aws.meta.client
        try:
            self.draft, self.stats = self._load_models()
        except:
            logger.error(f"Failed to retrieve model from AWS. Shutting down.")
            raise Exception

    def _download_weights(self) -> None:
        MAX_RETRIES, RETRY_DELAY = 3, 5
        retry_count = 0
        status = False
        while retry_count < MAX_RETRIES and not status:
            try:
                self.s3.download_file("dotabet", "draft.json", os.path.join(MODEL_PATH, WEIGHTS1))
                self.s3.download_file("dotabet", "stats.json", os.path.join(MODEL_PATH, WEIGHTS1))
            except:
                retry_count += 1 
                if retry_count == MAX_RETRIES:
                    raise 
                else:
                    time.sleep(RETRY_DELAY)

    def _load_models(self) -> Tuple[XGBClassifier, XGBClassifier]:
        if (WEIGHTS1 not in os.listdir(MODEL_PATH)) or (WEIGHTS2 not in os.listdir(MODEL_PATH)):
            self._download_weights()
        draft, stats = XGBClassifier(n_jobs=1), XGBClassifier(n_jobs=1)
        draft.load_model(os.path.join(MODEL_PATH, WEIGHTS1))
        stats.load_model(os.path.join(MODEL_PATH, WEIGHTS2))
        return draft, stats

    def _bet_time(self, raw_game: Dict, bet_time: int) -> int:
        # Calculates the minute of the game; used to then index the stats
        bet_minute = math.ceil((bet_time - raw_game["start_time"]) / 60)
        return bet_minute
        
    def _bet_outcome(self, raw_game: dict, direction: int, team: int) -> int:
        # This determines whether a bet won based on the match outcome and arguments
        if (raw_game["radiant_win"]) and (direction == 1) and (team == 1):
            return 1
        if (not raw_game["radiant_win"]) and (direction == 1) and (team == 0):
            return 1 
        if (not raw_game["radiant_win"]) and (direction == 0) and (team == 1):
            return 1 
        if (raw_game["radiant_win"]) and (direction == 0) and (team == 0):
            return 1 
        else:
            return 0

    def _json_to_array(self, parsed_game: Dict, time_index: int) -> np.array:
        # Convert processed/parsed game data to numpy array 
        player_stats = self._process_player_stats(parsed_game["players"], time_index)
        time_val = parsed_game["times"][time_index]
        X = np.concatenate([np.array([parsed_game["patch"]]), np.array([time_val]), player_stats])
        return X.reshape(1, -1)
    
    def _team_prediction(self, raw_game: dict, args: dict) -> int:
        # Extracts the team of the player being bet on
        if "BeteeSteamID" in args.keys():
            _id = args["BeteeSteamID"]
            for player in raw_game["players"]:
                if player["account_id"] == _id:
                    return int(player["isRadiant"])
        elif "TeamID" in args.keys():
            _id = args["TeamID"]
            if raw_game["radiant_team"]["team_id"] == _id:
                return 1
            return 0

    def _process_player_stats(self, players: dict, time_index: int) -> np.array:
        # Processing each players stats for the ML model 
        radiant = sorted([players[key] for key in players.keys() if players[key]["team"]==1],key = lambda x: x["lane"])
        dire = sorted([players[key] for key in players.keys() if players[key]["team"]==-1],key = lambda x: x["lane"])
        radiant_heroes, dire_heroes = [i["hero_id"] for i in radiant], [i["hero_id"] for i in dire]
        radiant_xp, dire_xp = [i["xp_t"][time_index] for i in radiant], [i["xp_t"][time_index] for i in dire]
        radiant_lh, dire_lh = [i["lh_t"][time_index] for i in radiant], [i["lh_t"][time_index] for i in dire]
        radiant_g, dire_g = [i["gold_t"][time_index] for i in radiant], [i["gold_t"][time_index] for i in dire]
        return np.concatenate([radiant_heroes, radiant_xp, radiant_lh, radiant_g, dire_heroes, dire_xp, dire_lh, dire_g])

    def _check_bet_time(self, raw_game: Dict, bet_time: int) -> int:
        # Check if the bet_time is in a valid range
        if bet_time >= (raw_game["start_time"] - 60*5) and bet_time < (raw_game["start_time"] + raw_game["duration"]):
            return max(bet_time, raw_game["start_time"])
        else:
            raise BetTimeException(datetime.fromtimestamp(raw_game['start_time']).strftime('%H:%M:%S'), \
                                datetime.fromtimestamp(raw_game['start_time'] + raw_game['duration']).strftime('%H:%M:%S'), \
                                datetime.fromtimestamp(bet_time).strftime('%H:%M:%S'))

    def _check_lobby_type(self, raw_game: Dict) -> None:
        # Check for valid lobby type
        if raw_game["lobby_type"] not in [0,1,2,5,6,7]:
            raise LobbyTypeException

    def _process_game(self, raw_game: Dict, args: Dict, cmd_id: str) -> Tuple[int, Dict, np.array]:
        # Validity Checks
        self._check_lobby_type(raw_game)
        args["Timestamp"] = self._check_bet_time(raw_game, args["Timestamp"])
        
        # Process data
        processed_game = GameParser.parse(raw_game)
        time_index = self._bet_time(raw_game, args["Timestamp"])

        # Convert to array 
        return time_index, processed_game, self._json_to_array(processed_game, time_index)
    
    def _probability_transform(self, Rwin_prob: float, direction: int, team: int) -> float:
        # Converts the raw P(Radiant Win) from the model into the relevant prob based on the bet
        if (team == 1) and (direction == 1):
            return Rwin_prob
        if (team == 1) and (direction == 0):
            return 1 - Rwin_prob
        if (team == 0) and (direction == 1):
            return 1 - Rwin_prob
        if (team == 0) and (direction == 0):
            return Rwin_prob
        
    def _process_plot_stats(self, processed_game: Dict) -> Tuple[np.array, np.array, str]:
        players = processed_game["players"]
        radiant = [players[key] for key in players.keys() if players[key]["team"]==1]
        dire = [players[key] for key in players.keys() if players[key]["team"]==-1]
        rad_gold = np.sum(np.concatenate([np.array(player["gold_t"]).reshape(1,-1) for player in radiant],axis=0),axis=0)
        rad_xp = np.sum(np.concatenate([np.array(player["xp_t"]).reshape(1,-1) for player in radiant],axis=0),axis=0)

        dire_gold = np.sum(np.concatenate([np.array(player["gold_t"]).reshape(1,-1) for player in dire],axis=0),axis=0)
        dire_xp = np.sum(np.concatenate([np.array(player["xp_t"]).reshape(1,-1) for player in dire],axis=0),axis=0)

        radiant_xp_adv = (rad_xp - dire_xp)
        radiant_gold_adv = (rad_gold - dire_gold)
        return radiant_xp_adv, radiant_gold_adv, "Radiant" if processed_game["radiant_win"] else "Dire"

    def _draft_arr(self, X: np.array) -> np.array:
        time, rad_h, dire_h = X[:,1], X[:,2:7], X[:, 22:27]
        X_draft = np.concatenate([time.reshape(-1,1), rad_h, dire_h],axis=1)
        return X_draft

    def _stats_arr(self, X: np.array) -> np.array:
        time, rad_stats, dire_stats = X[:,1].reshape(-1,1), X[:, 7:22], X[:, 27:]
        X_stats = np.concatenate([time.reshape(-1,1), rad_stats, dire_stats],axis=1)
        return X_stats

    def _get_game_info(self, raw_game: Dict, args: Dict, cmd_id: str) -> Tuple[np.array, str, Dict, int]:
        time, processed, X = self._process_game(raw_game, args, cmd_id)
        team = self._team_prediction(raw_game, args)
        return X, team, processed, time

    def _calculate_payout(self, raw_game: Dict, outcome: int, team: int, odds: Odds, bet_value: Decimal) -> Decimal:
        if not self._bet_outcome(raw_game, outcome, team):
            return 0
        return odds.payout(bet_value)
    
    def calculate_odds(self, X: np.array, direction: int, team: int) -> Odds:
        # Format arrays into model-specific arrays
        Xd, Xs = self._draft_arr(X), self._stats_arr(X)
        # Calculate probs from each model 
        prob_d, prob_s = self.draft.predict_proba(Xd).flatten(), self.stats.predict_proba(Xs).flatten()
        # Linear combination of model probabilities for prediction 
        raw_prob = prob_d * (0.6/(0.71 + 0.6)) + prob_s * (0.71/(0.71 + 0.6))
        # Transform probabilities 
        prob = self._probability_transform(raw_prob[1], direction, team)
        # Produce odds
        odds = Odds(prob)
        return odds
    
    def __call__(self, raw_game: Dict, args: Dict, cmd_id: str) -> Tuple[Odds, Decimal]:
        try:
            X, team, processed, minute = self._get_game_info(raw_game, args, cmd_id)
            gold, xp, winner = self._process_plot_stats(processed)
            plot_game(winner, xp, gold, minute, cmd_id)
            odds = self.calculate_odds(X, args["Outcome"], team)
            payout = self._calculate_payout(raw_game, args["Outcome"], team, odds, args["Value"])
        except (LobbyTypeException, BetTimeException, Exception) as e:
            logger.error(f"Error {str(e)} occurred", exc_info=True, extra={"id": cmd_id})
            raise
        return odds, payout

if __name__=="__main__":
    match_id = object()
    args = {...}
    aws = boto3.resource("s3")
    client = SyncDotaClient(os.environ["OD_API_KEY"])
    raw_game = client.parse_match_get_data(match_id, 0)
    pricing = PricingModel(aws)
    odds, payout = pricing(raw_game, args, 1)
    print(f"Bet on {args['BeteeSteamID']} to {args['Outcome']} for odds: {odds} and won: {payout}")
    
