from typing import Dict, List

class GameParser():

    @classmethod
    def process_items(cls, player: Dict) -> List:
        items = [player[f"item_{i}"] for i in range(6)]
        items.append(player["item_neutral"])
        return items 

    @classmethod
    def player_team(cls, player: Dict) -> int:
        if player["player_slot"] <= 127:
            return 1 
        else:
            return -1 
    
    @classmethod    
    def match_start_time(cls, game: Dict) -> int:
        return game['start_time']

    @classmethod
    def process_lane(cls, player: Dict) -> int:
        team = cls.player_team(player)
        if team == 1:
            if player["lane"] == 1:
                return "safe"
            elif player["lane"] == 2:
                return "mid"
            elif player["lane"] == 3:
                return "off"
            else:
                return "jungle"
        else:
            if player["lane"] == 1:
                return "off"
            elif player["lane"] == 2:
                return "mid"
            elif player["lane"] == 3:
                return "safe"
            else:
                return "jungle"

    @classmethod
    def process_player_stats(cls, game: Dict) -> Dict:
        result = {}
        for ix, player in enumerate(game["players"]):
            player_data = {}
            player_data["team"] = cls.player_team(player)
            player_data["hero_id"] = player["hero_id"]
            player_data["lane"] = cls.process_lane(player)
            player_data["lh_t"]  = player["lh_t"]
            player_data["xp_t"]  = player["xp_t"]
            player_data["gold_t"] = player["gold_t"]
            result[f"player_{ix}"] = player_data
        return result
    
    @classmethod
    def process_time(cls, match_data: Dict) -> List:
        time = [i*60 for i in range(len(match_data["players"][0]["xp_t"]))]
        return time

    @classmethod
    def process_objectives(cls, game: Dict, time_series: List) -> Dict: 
        
        # Define a dictionary for objectives
        objectives_data = {
            'goodguys_tower1': [0],
            'goodguys_tower2': [0],
            'goodguys_tower3': [0],
            'goodguys_melee_rax': [0],
            'goodguys_range_rax': [0],
            'goodguys_tower4': [0],
            'badguys_tower1': [0],
            'badguys_tower2': [0],
            'badguys_tower3': [0],
            'badguys_melee_rax': [0],
            'badguys_range_rax': [0],
            'badguys_tower4': [0],
        }
        
        for ix in range(1, len(time_series)):
            objectives = [obj for obj in game["objectives"] if (obj["time"] > time_series[ix-1]) & (obj["time"] <= time_series[ix]) & (obj["type"] == "building_kill")]
            
            if not objectives:
                for key in objectives_data:
                    objectives_data[key].append(objectives_data[key][-1])
            else:
                for o in objectives:
                    for key in objectives_data:
                        if key in o["key"]:
                            objectives_data[key].append(objectives_data[key][-1] + 1)

        return objectives_data

    @classmethod
    def check_early_finish(cls, game: Dict) -> bool:
        times = cls.process_time(game)
        obj = cls.process_objectives(game, times)
        if (obj["goodguys_tower4"][-1]!=2) and (obj["badguys_tower4"][-1]!=2):
            return True
        return False

    @classmethod
    def parse(cls, game: Dict) -> Dict:
        result = {}
        times = cls.process_time(game)
        objectives = cls.process_objectives(game, times)
        result["match_id"] = game["match_id"]
        result["radiant_win"] = game["radiant_win"]
        result["times"] = times 
        result["patch"] = game["patch"]
        result["players"] = cls.process_player_stats(game)
        result["objectives"] = objectives
        return result


if __name__=="__main__":
    game_parser = GameParser()