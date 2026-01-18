import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RIOT_API_KEY")
GAME_NAME = os.getenv("RIOT_GAME_NAME")
TAG_LINE = os.getenv("RIOT_TAG_LINE")
REGION_GROUP = os.getenv("RIOT_REGION_GROUP", "americas")  # americas / europe / asia

if not all([API_KEY, GAME_NAME, TAG_LINE]):
    raise ValueError("Missing env vars. Check your .env has RIOT_API_KEY, RIOT_GAME_NAME, RIOT_TAG_LINE.")

HEADERS = {"X-Riot-Token": API_KEY}  # recommended auth header

# Wrapper/helper: makes a GET request with my auth header.
# If Riot rate-limits us (429), wait then retry up to `retries (3)` times.
# If any other error (>=400), stop and raise an error.
# If successful, return the response JSON as a Python dict.

def riot_get(url: str, params: dict | None = None, retries: int = 3):
    """Small helper with basic rate-limit handling."""
    for attempt in range(retries):
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if r.status_code == 429:  # rate limited
            wait = int(r.headers.get("Retry-After", "2"))
            print(f"Rate limited (429). Waiting {wait}s...")
            time.sleep(wait)
            continue

        if r.status_code >= 400:
            raise RuntimeError(f"Request failed {r.status_code}: {r.text}")

        return r.json()

    raise RuntimeError("Too many retries due to rate limiting.")

# 1) Riot ID -> PUUID (Account-V1)
# Endpoint: /riot/account/v1/accounts/by-riot-id/{gameName}/{tagLine}
# gameName + tagLine are required.
account_url = f"https://{REGION_GROUP}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{GAME_NAME}/{TAG_LINE}"
account = riot_get(account_url)
puuid = account["puuid"]

print("Riot ID:", account.get("gameName"), "#", account.get("tagLine"))
print("PUUID:", puuid)

# 2) PUUID -> recent match IDs (Match-V5)
# Endpoint: /lol/match/v5/matches/by-puuid/{puuid}/ids
match_ids_url = f"https://{REGION_GROUP}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
match_ids = riot_get(match_ids_url, params={"start": 0, "count": 20})

print(f"Pulled {len(match_ids)} match IDs.")
print("First 5:", match_ids[:5])
