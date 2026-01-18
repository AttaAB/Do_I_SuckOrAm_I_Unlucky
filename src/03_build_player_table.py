""""build an analysis-friendly table of player (players.csv) stats from raw match JSON files."""

import json                
from pathlib import Path    
import pandas as pd         

# Paths (where data lives)
RAW_DIR = Path("data/raw")              
OUT_DIR = Path("data/processed")        
OUT_FILE = OUT_DIR / "players.csv"     

# Ensure output directory exists (creates it if missing)
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Convert one match JSON file into a list of rows (one row per player) so 10 rows per match.
def parse_match_file(path: Path) -> list[dict]:

    match_id = path.stem  # filename without .json becomes match_id (e.g., "NA1_12345")

    # Read file text -> convert JSON text into a Python dictionary
    data = json.loads(path.read_text())

    # "info" contains match metadata + the 10 participants
    info = data.get("info", {})
    participants = info.get("participants", [])

    # Match-level metadata (same for all players in the match)
    game_duration = info.get("gameDuration")  # seconds
    queue_id = info.get("queueId")
    game_creation = info.get("gameCreation")  

    rows = []

    for p in participants:
        rows.append({
            # Match info
            "match_id": match_id,
            "queue_id": queue_id,
            "game_duration_sec": game_duration,
            "game_creation": game_creation,

            # Player info
            "summoner_name": p.get("summonerName"),
            "puuid": p.get("puuid"),
            "team_id": p.get("teamId"),
            "win": p.get("win"),

            # In-game context
            "champion_name": p.get("championName"),
            "role": p.get("teamPosition"),   # TOP/JUNGLE/MIDDLE/BOTTOM/SUPPORT
            "lane": p.get("lane"),

            # KDA stats
            "kills": p.get("kills"),
            "deaths": p.get("deaths"),
            "assists": p.get("assists"),

            # Farming + money stats
            "total_minions_killed": p.get("totalMinionsKilled"),
            "neutral_minions_killed": p.get("neutralMinionsKilled"),
            "gold_earned": p.get("goldEarned"),

            # Contribution stats
            "damage_to_champions": p.get("totalDamageDealtToChampions"),
            "vision_score": p.get("visionScore"),
        })

    return rows

#  Add helpful calculated columns for fairer analysis of KDA, CS, CS/min.
def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:

    # KDA = (Kills + Assists) / Deaths
    # If deaths = 0, replace with 1 to avoid division by zero
    df["kda"] = (df["kills"] + df["assists"]) / df["deaths"].replace({0: 1})

    # CS = lane minions + jungle monsters
    df["cs"] = df["total_minions_killed"].fillna(0) + df["neutral_minions_killed"].fillna(0)

    # Convert game duration from seconds to minutes
    df["game_minutes"] = df["game_duration_sec"] / 60

    # CS per minute
    df["cs_per_min"] = df["cs"] / df["game_minutes"]

    return df

"""
    Our main function: 
      1) Loop through all JSON match files in data/raw/
      2) Parse each into rows (10 rows per match)
      3) Build a DataFrame (table)
      4) Add derived columns
      5) Save to CSV
""" 
def main():
    if not RAW_DIR.exists():
        raise FileNotFoundError(
            "data/raw/ not found. Run Step 02 first to download match JSON files."
        )

    all_rows = []

    # Loop over every JSON file in data/raw/
    for path in RAW_DIR.glob("*.json"):
        # Convert one match file -> list of 10-ish rows
        rows = parse_match_file(path)
        all_rows.extend(rows)

    # Convert list-of-dicts -> pandas DataFrame (table)
    df = pd.DataFrame(all_rows)

    # Add our calculated metrics
    df = add_derived_columns(df)

    # Save to CSV 
    df.to_csv(OUT_FILE, index=False)

    print(f"✅ Saved {len(df)} rows to {OUT_FILE}")
    print("Preview (first 3 rows):")
    print(df.head(3))
    
if __name__ == "__main__":
    # This ensures main() runs only when you execute this file directly:
    # python3 src/03_build_player_table.py
    main()

