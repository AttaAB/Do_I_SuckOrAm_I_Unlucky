"""
Download match timeline JSON (early-game data)

Goal:
- For each match already downloaded (data/raw/*.json),
  download its timeline data using Riot’s timeline endpoint.
- Save each timeline to data/timeline_raw/{match_id}.json

Why:
  - This lets us build EARLY-game features (e.g., gold diff @10),
  which are fair inputs for an expected-win model.
"""

import os                      
import time                     
import json                   
from pathlib import Path      
import requests                
from dotenv import load_dotenv  

load_dotenv()

# Load Riot API key and region group from .env
API_KEY = os.getenv("RIOT_API_KEY")
REGION_GROUP = os.getenv("RIOT_REGION_GROUP", "americas") 

# Basic validation
if not API_KEY:
    raise ValueError("Missing RIOT_API_KEY in .env")

HEADERS = {"X-Riot-Token": API_KEY}

# Paths
RAW_MATCH_DIR = Path("data/raw")                
TIMELINE_DIR = Path("data/timeline_raw")         
TIMELINE_DIR.mkdir(parents=True, exist_ok=True)

# Helpers
def riot_get(url: str, params=None, retries: int = 3):
    """
    Make a GET request to Riot API with basic rate-limit handling.
    - If 429 (rate limit), wait and retry.
    - If >=400 other error, raise.
    """
    for _ in range(retries):
        r = requests.get(url, headers=HEADERS, params=params, timeout=25)

        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", "2"))
            print(f"Rate limited (429). Waiting {wait}s...")
            time.sleep(wait)
            continue

        if r.status_code >= 400:
            raise RuntimeError(f"Request failed {r.status_code}: {r.text}")

        return r.json()

    raise RuntimeError("Too many retries due to rate limiting.")

#  Download the timeline data for each match in the raw data directory and save it to the timeline_raw directory
def main():
    if not RAW_MATCH_DIR.exists():
        raise FileNotFoundError("data/raw not found. Run S02 first.")

    match_files = sorted(RAW_MATCH_DIR.glob("*.json"))
    print(f"Found {len(match_files)} match files in {RAW_MATCH_DIR}")

    for i, match_path in enumerate(match_files, start=1):
        match_id = match_path.stem
        out_path = TIMELINE_DIR / f"{match_id}.json"

        # Skip if already downloaded
        if out_path.exists():
            print(f"[{i}/{len(match_files)}] Skipping (exists): {match_id}")
            continue

        timeline_url = f"https://{REGION_GROUP}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        timeline = riot_get(timeline_url)

        out_path.write_text(json.dumps(timeline, indent=2))
        print(f"[{i}/{len(match_files)}] Saved timeline: {out_path}")

        # Gentle pause to reduce rate-limit chances
        time.sleep(1)

    print("Done! Timelines saved in data/timeline_raw/")

# allows the script to be run directly without importing
if __name__ == "__main__":
    main()
