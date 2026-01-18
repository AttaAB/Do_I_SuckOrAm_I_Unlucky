"""
STEP 04 — Add impact features + isolate my games

Goal:
- Start from data/processed/players.csv (Step 03 output)
- Identify which row belongs to ME (my PUUID)
- Compute team totals per match (team kills, team damage, team gold)
- Create impact metrics (kill participation, damage share, etc.)
- Save:
  1) players_with_features.csv (all players, with extra columns)
  2) my_games.csv (only my rows)

Why:
- "Suck vs unlucky" needs performance features that are comparable across games.
"""

import os                    
from pathlib import Path     
from dotenv import load_dotenv   
import pandas as pd          

load_dotenv()

# ---------------------------
# Input/Output paths
# ---------------------------
IN_FILE = Path("data/processed/players.csv")  
OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_ALL = OUT_DIR / "players_with_features.csv"
OUT_ME = OUT_DIR / "my_games.csv"

# ---------------------------
# Identify "me"
# ---------------------------

MY_PUUID = os.getenv("RIOT_PUUID")


def add_team_totals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add team totals (per match, per team) so we can compute shares.

    Example:
    - team_kills = sum of kills for the 5 players on that team in that match
    - team_damage = sum of damage_to_champions for those 5 players
    """
    group_cols = ["match_id", "team_id"]

    team_totals = (
        df.groupby(group_cols, as_index=False)[
            ["kills", "gold_earned", "damage_to_champions", "vision_score"]
        ]
        .sum()
        .rename(columns={
            "kills": "team_kills",
            "gold_earned": "team_gold",
            "damage_to_champions": "team_damage_to_champions",
            "vision_score": "team_vision_score",
        })
    )

    # Merge team totals back onto the original df
    return df.merge(team_totals, on=group_cols, how="left")


def add_impact_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add common “impact” metrics for each player.

    Metrics:
    - kill_participation = (kills + assists) / team_kills
    - damage_share = player_damage / team_damage
    - gold_share = player_gold / team_gold
    - vision_per_min = vision_score / game_minutes
    """
    # Avoid divide-by-zero by replacing 0 with 1 in denominators
    df["team_kills_safe"] = df["team_kills"].replace({0: 1})
    df["team_damage_safe"] = df["team_damage_to_champions"].replace({0: 1})
    df["team_gold_safe"] = df["team_gold"].replace({0: 1})

    df["kill_participation"] = (df["kills"] + df["assists"]) / df["team_kills_safe"]
    df["damage_share"] = df["damage_to_champions"] / df["team_damage_safe"]
    df["gold_share"] = df["gold_earned"] / df["team_gold_safe"]
    df["vision_per_min"] = df["vision_score"] / df["game_minutes"]

    # Clean up helper columns (optional)
    df.drop(columns=["team_kills_safe", "team_damage_safe", "team_gold_safe"], inplace=True)

    return df


def main():
    """
    Pipeline:
    1) Load players.csv
    2) Add team totals
    3) Add impact features
    4) If RIOT_PUUID exists, flag rows that are me and save my_games.csv
    """
    if not IN_FILE.exists():
        raise FileNotFoundError("players.csv not found. Run Step 03 first.")

    df = pd.read_csv(IN_FILE)

    # Add team totals + impact features
    df = add_team_totals(df)
    df = add_impact_features(df)

    # Save all players with extra features
    df.to_csv(OUT_ALL, index=False)
    print(f"✅ Saved all players w/ features: {OUT_ALL} ({len(df)} rows)")

    # If we know your PUUID, filter to only your rows
    if MY_PUUID:
        df["is_me"] = df["puuid"] == MY_PUUID
        my_df = df[df["is_me"]].copy()

        my_df.to_csv(OUT_ME, index=False)
        print(f"✅ Saved ONLY my games: {OUT_ME} ({len(my_df)} rows)")
        print("Preview of my games:")
        print(my_df[[
            "match_id", "win", "champion_name", "role",
            "kda", "cs_per_min", "kill_participation",
            "damage_share", "vision_per_min"
        ]].head(10))
    else:
        print("⚠️ RIOT_PUUID not set yet, so I can't auto-filter to just you.")
        print("Next: add RIOT_PUUID=... to your .env (I’ll show you how).")


if __name__ == "__main__":
    main()
