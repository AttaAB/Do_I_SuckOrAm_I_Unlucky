"""
Expected wins model using EARLY-game (timeline) features

Goal:
- Build early-game features at 10 minutes from timeline JSON:
  - gold_diff_10 (my team - enemy)
  - xp_diff_10
  - cs_diff_10
  - kills_diff_10 (from champion kill events up to 10:00)
- Train a simple logistic regression model: P(win | early features)
- Compute:
  - expected_wins = sum(p_win)
  - luck_diff = actual_wins - expected_wins
- Save per-game probabilities + a short report.

Why:
- Early-game features avoid "end-of-game leakage" and make the luck analysis fairer.
"""

import json                        
from pathlib import Path            
import pandas as pd               
from sklearn.linear_model import LogisticRegression   
from sklearn.model_selection import StratifiedKFold, cross_val_predict  # Honest-ish probabilities

# Paths
MATCH_DIR = Path("data/raw")               
TIMELINE_DIR = Path("data/timeline_raw")     
MY_GAMES_FILE = Path("data/processed/my_games.csv")  

OUT_DIR = Path("data/processed")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_FEATURES = OUT_DIR / "early_features_10min.csv"
OUT_PRED = OUT_DIR / "expected_win_probs.csv"

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
OUT_REPORT = REPORT_DIR / "S08_expected_wins_report.txt"

# Target time
TARGET_MINUTE = 10
TARGET_MS = TARGET_MINUTE * 60 * 1000 # bc Riots timestamps are in ms

# Helpers
def load_json(path: Path) -> dict:
    """Read a JSON file from disk into a Python dict."""
    return json.loads(path.read_text())

def get_team_map_from_match(match_json: dict) -> dict:
    """
    Build mapping: participantId (1..10) -> teamId (100 or 200)
    using the match details (data/raw/{match_id}.json).
    """
    participants = match_json.get("info", {}).get("participants", [])
    pid_to_team = {}
    for p in participants:
        pid_to_team[p.get("participantId")] = p.get("teamId")
    return pid_to_team

def get_my_team_id(match_json: dict, my_puuid: str) -> int:
    """
    Find which team (100 or 200) I am on in this match.
    """
    participants = match_json.get("info", {}).get("participants", [])
    for p in participants:
        if p.get("puuid") == my_puuid:
            return p.get("teamId")
    raise ValueError("Could not find my puuid in match participants.")

def frame_at_minute(timeline_json: dict, minute: int) -> dict:
    """
    Timeline has frames by minute index.
    grab frame[minute] if it exists; otherwise take the last available frame (minute).
    """
    frames = timeline_json.get("info", {}).get("frames", [])
    if not frames:
        raise ValueError("Timeline has no frames.")

    if minute < len(frames):
        return frames[minute]
    return frames[-1]

def team_totals_from_frame(frame: dict, pid_to_team: dict) -> dict:
    """
    From a single timeline frame, compute team totals (gold, xp, cs) for team 100 and 200.
    """
    participant_frames = frame.get("participantFrames", {})

    totals = {
        100: {"gold": 0, "xp": 0, "cs": 0},
        200: {"gold": 0, "xp": 0, "cs": 0},
    }

    for pid_str, pf in participant_frames.items():
        pid = int(pid_str)
        team = pid_to_team.get(pid)

        if team not in (100, 200):
            continue

        gold = pf.get("totalGold", 0)
        xp = pf.get("xp", 0)
        cs = pf.get("minionsKilled", 0) + pf.get("jungleMinionsKilled", 0)

        totals[team]["gold"] += gold
        totals[team]["xp"] += xp
        totals[team]["cs"] += cs

    return totals

def kills_diff_up_to_10min(timeline_json: dict, pid_to_team: dict, my_team: int) -> int:
    """
    Count champion kills up to 10 minutes and compute:
    kills_diff = my_team_kills - enemy_kills

    scan events in each frame and count CHAMPION_KILL.
    """
    frames = timeline_json.get("info", {}).get("frames", [])
    my_kills = 0
    enemy_kills = 0
    enemy_team = 200 if my_team == 100 else 100

    # Frames are minute buckets; events have timestamps in ms
    for frame in frames:
        for ev in frame.get("events", []):
            if ev.get("type") != "CHAMPION_KILL":
                continue
            if ev.get("timestamp", 10**12) > TARGET_MS:
                continue

            killer_pid = ev.get("killerId")  # 0 sometimes if tower or minion or something like that killed
            if not killer_pid or killer_pid == 0:
                continue

            killer_team = pid_to_team.get(killer_pid)
            if killer_team == my_team:
                my_kills += 1
            elif killer_team == enemy_team:
                enemy_kills += 1

    return my_kills - enemy_kills

def build_features_for_match(match_id: str, my_puuid: str) -> dict:
    """
    Build the early-game feature row for ONE match (this will be training data).
    """
    match_path = MATCH_DIR / f"{match_id}.json"
    timeline_path = TIMELINE_DIR / f"{match_id}.json"

    if not match_path.exists() or not timeline_path.exists():
        return None

    match_json = load_json(match_path)
    timeline_json = load_json(timeline_path)

    pid_to_team = get_team_map_from_match(match_json)
    my_team = get_my_team_id(match_json, my_puuid)
    enemy_team = 200 if my_team == 100 else 100

    # conversion from match details: find my participant and get the win/loss result for the match and then make it a boolean (in python from json it might be true/false or it might be "True"/"False" or 1/0, so we convert to bool just in case)
    win = None
    for p in match_json.get("info", {}).get("participants", []):
        if p.get("puuid") == my_puuid:
            win = bool(p.get("win"))
            break
    if win is None:
        return None

    # timeline snapshot at 10 minutes
    frame10 = frame_at_minute(timeline_json, TARGET_MINUTE)
    totals10 = team_totals_from_frame(frame10, pid_to_team)

    gold_diff_10 = totals10[my_team]["gold"] - totals10[enemy_team]["gold"]
    xp_diff_10 = totals10[my_team]["xp"] - totals10[enemy_team]["xp"]
    cs_diff_10 = totals10[my_team]["cs"] - totals10[enemy_team]["cs"]

    kills_diff_10 = kills_diff_up_to_10min(timeline_json, pid_to_team, my_team)

    return {
        "match_id": match_id,
        "win": win,
        "gold_diff_10": gold_diff_10,
        "xp_diff_10": xp_diff_10,
        "cs_diff_10": cs_diff_10,
        "kills_diff_10": kills_diff_10,
    }

# This function loops through matches, builds features, trains a model, and writes the report
def main():
    if not MY_GAMES_FILE.exists():
        raise FileNotFoundError("my_games.csv not found. Run S04 first.")

    my_games = pd.read_csv(MY_GAMES_FILE)
    my_puuid = my_games["puuid"].iloc[0]

    match_ids = my_games["match_id"].tolist()
    rows = []

    for mid in match_ids: # mid = match_ids[0]
        row = build_features_for_match(mid, my_puuid)
        if row is not None:
            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_FEATURES, index=False)

    if len(df) < 30:
        print("⚠️ Very small dataset for modeling. It will run, but results may be noisy.")

    # Expected win probability model
    X = df[["gold_diff_10", "xp_diff_10", "cs_diff_10", "kills_diff_10"]]
    y = df["win"].astype(int)

    # Logistic regression model for our probability estimates. We will use cross-validation to get probabilities that are most "honest".
    model = LogisticRegression(max_iter=2000)

    # Cross-validated predicted probabilities (reduces overfitting vs training+predicting on same data)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    p_win = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]

    df["p_win_10min"] = p_win

    # Luck summary
    actual_wins = int(y.sum())
    expected_wins = float(df["p_win_10min"].sum())
    luck_diff = actual_wins - expected_wins

    df.to_csv(OUT_PRED, index=False)

    # Write report
    lines = []
    lines.append("S08 — Expected wins from EARLY-game (10 min) features\n")
    lines.append(f"Games used: {len(df)}")
    lines.append(f"Actual wins: {actual_wins}")
    lines.append(f"Expected wins (sum p_win): {expected_wins:.2f}")
    lines.append(f"Luck diff (actual - expected): {luck_diff:.2f}")
    lines.append("")
    lines.append("Interpretation:")
    lines.append("- If luck_diff is NEGATIVE, fewer games were won than expected (unlucky).")
    lines.append("- If luck_diff is POSITIVE, more games were won than expected (lucky).")
    lines.append("")
    lines.append("Top 10 most 'unlucky' games (high p_win but loss):")
    unlucky_games = df[df["win"] == False].sort_values("p_win_10min", ascending=False).head(10)
    lines.append(unlucky_games[["match_id", "p_win_10min", "gold_diff_10", "xp_diff_10", "cs_diff_10", "kills_diff_10"]].to_string(index=False))

    lines.append("\nTop 10 most 'lucky' wins (low p_win but win):")
    lucky_games = df[df["win"] == True].sort_values("p_win_10min", ascending=True).head(10)
    lines.append(lucky_games[["match_id", "p_win_10min", "gold_diff_10", "xp_diff_10", "cs_diff_10", "kills_diff_10"]].to_string(index=False))

    OUT_REPORT.write_text("\n".join(lines))

    print(f"✅ Saved features: {OUT_FEATURES}")
    print(f"✅ Saved per-game probs: {OUT_PRED}")
    print(f"✅ Wrote report: {OUT_REPORT}")
    print(f"Actual wins: {actual_wins} | Expected wins: {expected_wins:.2f} | Luck diff: {luck_diff:.2f}")

if __name__ == "__main__":
    main()
