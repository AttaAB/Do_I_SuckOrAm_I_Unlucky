"""
Role-aware Impact Score + better "unlucky" flags

Goal:
- Create a single impact_score per game for YOU that combines multiple signals:
  - kill_participation (KP)
  - damage_share
  - cs_per_min
  - vision_per_min
- Make it role-aware by standardizing metrics within each role (TOP/JUNGLE/MIDDLE/BOTTOM/SUPPORT)
- Rank me on my team by impact_score each match
- Identify "unlucky losses": losses where you were top-2 impact on your team
"""

from pathlib import Path
import pandas as pd 

# Paths
DATA_DIR = Path("data/processed")
IN_ALL = DATA_DIR / "players_with_features.csv"
IN_ME = DATA_DIR / "my_games.csv"

OUT_ME = DATA_DIR / "my_games_with_impact.csv"

REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
OUT_REPORT = REPORT_DIR / "S06_impact_summary.txt"

# Helpers
def zscore_within_role(df: pd.DataFrame, col: str, role_col: str = "role") -> pd.Series:
    """
    Compute z-scores within each role group.

    z = (x - mean(role)) / std(role)

    Why:
    - Roles have different baselines (support vision is high, mid CS is high, etc.)
    - This makes metrics comparable across roles.
    """
    def z(g):
        std = g[col].std(ddof=0)
        if std == 0 or pd.isna(std):
            return (g[col] - g[col].mean()) * 0  # all zeros if no variation
        return (g[col] - g[col].mean()) / std # Z score

    return df.groupby(role_col, group_keys=False).apply(z)


def build_impact_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add role-aware z-score columns and my new metric TADA... impact_score.

    Weights (simple, can be tuned):
    - damage_share: 0.35
    - kill_participation: 0.30
    - cs_per_min: 0.25
    - vision_per_min: 0.10
    """

    # Ensure role column exists and remove empty roles if any
    df = df.copy()
    df["role"] = df["role"].fillna("UNKNOWN")

    # z-scores relative to role
    df["z_damage_share"] = zscore_within_role(df, "damage_share")
    df["z_kill_participation"] = zscore_within_role(df, "kill_participation")
    df["z_cs_per_min"] = zscore_within_role(df, "cs_per_min")
    df["z_vision_per_min"] = zscore_within_role(df, "vision_per_min")

    # Impact score
    df["impact_score"] = (
        0.35 * df["z_damage_share"]
        + 0.30 * df["z_kill_participation"]
        + 0.25 * df["z_cs_per_min"]
        + 0.10 * df["z_vision_per_min"]
    )

    return df


def rank_on_team(all_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rank every player by impact_score within their match + team.
    Rank 1 = highest impact on team.
    """
    group_cols = ["match_id", "team_id"]
    all_df = all_df.copy()
    all_df["impact_rank_on_team"] = all_df.groupby(group_cols)["impact_score"].rank(
        ascending=False, method="min"
    )
    return all_df


def main():
    # Load data
    if not IN_ALL.exists() or not IN_ME.exists():
        raise FileNotFoundError("Missing inputs. Run Steps 2–4 first.")

    all_df = pd.read_csv(IN_ALL)
    my_df = pd.read_csv(IN_ME)

    # Get my puuid
    my_puuid = my_df["puuid"].iloc[0]

    # Impact score for all players
    all_df = build_impact_score(all_df)

    # Rank within team
    all_df = rank_on_team(all_df)

    # Filter back down to you (now with impact score + rank)
    me = all_df[all_df["puuid"] == my_puuid].copy()

    # Save your games with impact
    me.to_csv(OUT_ME, index=False)

    # Unlucky losses: lost but top-2 impact on your team
    losses = me[me["win"] == False]
    top2_losses = losses[losses["impact_rank_on_team"] <= 2]

    # Simple summary stats
    summary = {
        "games": int(len(me)),
        "wins": int(me["win"].sum()),
        "losses": int((~me["win"].astype(bool)).sum()),
        "avg_impact_win": float(me[me["win"] == True]["impact_score"].mean()),
        "avg_impact_loss": float(me[me["win"] == False]["impact_score"].mean()),
        "loss_games": int(len(losses)),
        "top2_impact_losses": int(len(top2_losses)),
        "top2_impact_loss_rate": round(len(top2_losses) / len(losses), 3) if len(losses) else None,
    }

    # Most unlucky games: high impact score but loss
    most_unlucky = (
        losses.sort_values("impact_score", ascending=False)
        .loc[:, ["match_id", "champion_name", "role", "kda", "cs_per_min",
                 "kill_participation", "damage_share", "vision_per_min",
                 "impact_score", "impact_rank_on_team"]]
        .head(10)
    )

    # Most "low impact" losses: lowest impact score losses
    lowest_impact_losses = (
        losses.sort_values("impact_score", ascending=True)
        .loc[:, ["match_id", "champion_name", "role", "kda", "cs_per_min",
                 "kill_participation", "damage_share", "vision_per_min",
                 "impact_score", "impact_rank_on_team"]]
        .head(10)
    )

    # Write report
    lines = []
    lines.append("S06 — Role-aware Impact Score Summary\n")
    lines.append(f"Games: {summary['games']} | Wins: {summary['wins']} | Losses: {summary['losses']}\n")
    lines.append(f"Avg impact_score (wins):  {summary['avg_impact_win']:.3f}")
    lines.append(f"Avg impact_score (losses): {summary['avg_impact_loss']:.3f}\n")
    lines.append("Unlucky (stronger definition): Lost but top-2 IMPACT on team")
    lines.append(f"- Loss games: {summary['loss_games']}")
    lines.append(f"- Top-2 impact losses: {summary['top2_impact_losses']}")
    lines.append(f"- Rate: {summary['top2_impact_loss_rate']}\n")

    lines.append("Top 10 most 'unlucky' losses (highest impact_score but lost):")
    lines.append(most_unlucky.to_string(index=False))
    lines.append("\nTop 10 lowest-impact losses (potential 'I played poorly' games):")
    lines.append(lowest_impact_losses.to_string(index=False))

    OUT_REPORT.write_text("\n".join(lines))

    print(f"✅ Saved: {OUT_ME}")
    print(f"✅ Wrote report: {OUT_REPORT}")
    print("Summary:", summary)


if __name__ == "__main__":
    main()
