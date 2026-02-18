"""
Merge impact_score (S06) with expected win prob (S08)

Goal:
- Join per-match expected probabilities with your per-match impact score
- Create simple labels for game review:
  - "UNLUCKY LOSS" (high p_win but loss)
  - "CLUTCH WIN" (low p_win but win)
  - plus versions conditioned on impact_score
"""

from pathlib import Path
import pandas as pd

# Paths
IN_IMPACT = Path("data/processed/my_games_with_impact.csv")
IN_PROBS  = Path("data/processed/expected_win_probs.csv")

OUT_SCORED = Path("data/processed/my_games_scored.csv")

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
OUT_REPORT = REPORT_DIR / "S09_game_buckets.txt"

# Helpers
def bucket_game(row) -> str:
    """
    Bucket definitions:

    - high_exp: p_win_10min >= 0.65  (expected WIN)
    - low_exp:  p_win_10min <= 0.40  (expected LOSS)
    - high_imp: impact_score >= 0.5
    - low_imp:  impact_score <= -0.5
    """
    p = float(row["p_win_10min"])
    win = bool(row["win"])
    impact = float(row["impact_score"])

    high_exp = p >= 0.65
    low_exp = p <= 0.40
    high_imp = impact >= 0.5
    low_imp = impact <= -0.5

   # Expected WIN but LOSS
    if (not win) and high_exp and low_imp:
        return "THROW"
    if (not win) and high_exp and high_imp:
        return "UNLUCKY LOSS"
    if (not win) and high_exp:
        return "UPSET LOSS"

    # Expected LOSS but WIN
    if win and low_exp and high_imp:
        return "CLUTCH WIN"
    if win and low_exp and low_imp:
        return "LUCKY WIN"
    if win and low_exp:
        return "UPSET WIN"

    # Expected outcomes
    if win and high_exp:
        return "EXPECTED WIN"
    if (not win) and low_exp:
        return "EXPECTED LOSS"

    # Toss-ups
    return "TOSS-UP WIN" if win else "TOSS-UP LOSS"

# Alternative simpler labels (uncomment if you prefer fewer categories):
'''
    if (not win) and high_exp and high_imp:
        return "UNLUCKY LOSS (high exp, high impact)"
    if (not win) and high_exp and low_imp:
        return "THROW? (high exp, low impact)"
    if win and low_exp and high_imp:
        return "CLUTCH WIN (low exp, high impact)"
    if win and low_exp and low_imp:
        return "CARRIED (low exp, low impact)"

    # More general labels
    if (not win) and high_exp:
        return "UNLUCKY LOSS (high exp)"
    if win and low_exp:
        return "CLUTCH WIN (low exp)"

    return "NORMAL"
    '''


def main():
    """
    This function merges impact and expected win probabilities, assigns buckets, and writes a report.
    """
    if not IN_IMPACT.exists():
        raise FileNotFoundError("Missing my_games_with_impact.csv (run S06).")
    if not IN_PROBS.exists():
        raise FileNotFoundError("Missing expected_win_probs.csv (run S08).")

    impact_df = pd.read_csv(IN_IMPACT)
    probs_df = pd.read_csv(IN_PROBS)

    # Merge on match_id
    df = impact_df.merge(
        probs_df[["match_id", "p_win_10min"]],
        on="match_id",
        how="inner"
    )

    # Add label/bucket
    df["bucket"] = df.apply(bucket_game, axis=1)

    # Save merged table
    df.to_csv(OUT_SCORED, index=False)

    # Summary counts
    bucket_counts = df["bucket"].value_counts()

    # Top games to review
    unlucky_losses = df[(df["win"] == False)].sort_values("p_win_10min", ascending=False).head(10)
    clutch_wins = df[(df["win"] == True)].sort_values("p_win_10min", ascending=True).head(10)

    # Write report
    lines = []
    lines.append("S09 — Game Buckets (Impact + Expected Win @10min)\n")
    lines.append(f"Games merged: {len(df)}\n")
    lines.append("Bucket counts:")
    lines.append(bucket_counts.to_string())

    lines.append("\nTop 10 most 'unlucky' losses (highest p_win but lost):")
    cols = [c for c in ["match_id", "champion_name", "role", "impact_score", "impact_rank_on_team", "p_win_10min", "bucket"] if c in df.columns]
    lines.append(unlucky_losses[cols].to_string(index=False))

    lines.append("\nTop 10 most 'clutch' wins (lowest p_win but won):")
    lines.append(clutch_wins[cols].to_string(index=False))

    OUT_REPORT.write_text("\n".join(lines))

    print(f"✅ Saved merged file: {OUT_SCORED}")
    print(f"✅ Wrote report: {OUT_REPORT}")
    print(bucket_counts)



if __name__ == "__main__":
    main()
