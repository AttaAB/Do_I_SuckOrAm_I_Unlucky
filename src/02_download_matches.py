import os            
import time           
import json           
import requests        
from get_matches import riot_get
from pathlib import Path  
from dotenv import load_dotenv 

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")
GAME_NAME = os.getenv("RIOT_GAME_NAME")
TAG_LINE = os.getenv("RIOT_TAG_LINE")
REGION_GROUP = os.getenv("RIOT_REGION_GROUP", "americas")  # NA uses "americas"

if not all([API_KEY, GAME_NAME, TAG_LINE]):
    raise ValueError("Missing env vars. Check .env has RIOT_API_KEY, RIOT_GAME_NAME, RIOT_TAG_LINE.")

HEADERS = {"X-Riot-Token": API_KEY}

DATA_RAW_DIR = Path("data/raw")
DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)

# The following code is almost identical to get_matches.py,
# Simply copied from get_matches.py, changed count to 100 

# 1) Riot ID -> PUUID
account_url = f"https://{REGION_GROUP}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{GAME_NAME}/{TAG_LINE}"
account = riot_get(account_url)
puuid = account["puuid"]

print("Riot ID:", account.get("gameName"), "#", account.get("tagLine"))
print("PUUID:", puuid)

# 2) PUUID -> match IDs (choose how many)
match_ids_url = f"https://{REGION_GROUP}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
match_ids = riot_get(match_ids_url, params={"start": 0, "count": 100}) 

print(f"Found {len(match_ids)} match IDs.")

# 3) For each match ID, download full match JSON and save it
# Endpoint: /lol/match/v5/matches/{matchId}
for i, match_id in enumerate(match_ids, start=1):
    out_path = DATA_RAW_DIR / f"{match_id}.json"

    # Skip if already downloaded
    if out_path.exists():
        print(f"[{i}/{len(match_ids)}] Skipping (already exists): {match_id}")
        continue

    match_url = f"https://{REGION_GROUP}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    match_data = riot_get(match_url)

    out_path.write_text(json.dumps(match_data, indent=2))
    print(f"[{i}/{len(match_ids)}] Saved: {out_path}")

    # Small pause to be nice to the API
    time.sleep(1)

print("Done! Raw match files are in data/raw/")
