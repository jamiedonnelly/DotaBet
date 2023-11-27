import json
import os

ROOT = os.environ["ROOT"]
JSON_FILE = f"{ROOT}/data/teams.json"

with open(JSON_FILE, "r") as f:
    teams = json.load(f)

team_names = list(teams.keys())

if __name__=="__main__":
    print(f"First 5 team names: {team_names[:5]}\n")
    print(f"Keys in each dict item: {teams[0].keys()}")


