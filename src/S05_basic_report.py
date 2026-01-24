"""
Basic "Do I suck or am I unlucky?" report

Goal:
- Use the processed datasets to generate first results:
  1) Compare my metrics in wins vs losses
  2) Check if I'm often top performer in losses (unlucky signal)
  3) Save a quick report + a few plots

  "Do I perform well and still lose (unlucky)? Or underperform (impact gap)?"
"""

from pathlib import Path            
import pandas as pd                  
import matplotlib.pyplot as plt       

# Paths
DATA_DIR = Path("data/processed")
IN_ALL = DATA_DIR / "players_with_features.csv"
IN_ME = DATA_DIR / "my_games.csv"

REPORT_DIR = Path("reports")
PLOTS_DIR = REPORT_DIR / "plots"
PLOTS_DIR.mkdir(parents=True, exist_ok=True)

OUT_REPORT = REPORT_DIR / "S05_summary.txt"


# Helper functions
def summarize_wins_losses(my_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compares your average performance metrics in wins vs losses.
    Returns a table with mean values for key metrics.
    """
    metrics = ["kda", "cs_per_min", "kill_participation", "damage_share", "vision_per_min"]

    summary = (
        my_df.groupby("win")[metrics]
        .mean()
        .rename(index={True: "WIN", False: "LOSS"})
        .round(3)
    )
    return summary


def add_within_team_ranks(all_df: pd.DataFrame, my_puuid: str) -> pd.DataFrame:
    """
    For each match/team, rank players by key impact metrics.
    Then return only YOUR rows with rank columns added.

    Ranks:
    - damage_share_rank_on_team (1 = best on your team)
    - kp_rank_on_team
    - gold_share_rank_on_team
    """
    # compute ranks within each (match_id, team_id) group
    group_cols = ["match_id", "team_id"]

    # Rank: the higher the better (so ascending=False)
    all_df["damage_share_rank_on_team"] = (
        all_df.groupby(group_cols)["damage_share"].rank(ascending=False, method="min")
    )
    all_df["kp_rank_on_team"] = (
        all_df.groupby(group_cols)["kill_participation"].rank(ascending=False, method="min")
    )
    all_df["gold_share_rank_on_team"] = (
        all_df.groupby(group_cols)["gold_share"].rank(ascending=False, method="min")
    )

    # Filter to only your rows
    my_rows = all_df[all_df["puuid"] == my_puuid].copy()
    return my_rows


def compute_unlucky_index(my_ranked_df: pd.DataFrame) -> dict:
    """
    Define an "unlucky" signal:
    - You're top-2 in damage share on your team AND you lose.

    Returns counts and rates.
    """
    losses = my_ranked_df[my_ranked_df["win"] == False]
    if len(losses) == 0:
        return {"loss_games": 0, "top2_losses": 0, "top2_loss_rate": None}

    top2_losses = losses[losses["damage_share_rank_on_team"] <= 2]
    return {
        "loss_games": int(len(losses)),
        "top2_losses": int(len(top2_losses)),
        "top2_loss_rate": round(len(top2_losses) / len(losses), 3),
    }


def make_plots(my_df: pd.DataFrame):
    # 1) Boxplot: Damage Share in wins vs losses
    plt.figure()
    my_df.boxplot(column="damage_share", by="win")
    plt.title("My Damage Share: Wins vs Losses")
    plt.suptitle("")  # removes default pandas subtitle
    plt.xlabel("Win")
    plt.ylabel("Damage Share")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "damage_share_wins_losses.png")
    plt.close()

    # 2) Boxplot: Kill Participation in wins vs losses
    plt.figure()
    my_df.boxplot(column="kill_participation", by="win")
    plt.title("My Kill Participation: Wins vs Losses")
    plt.suptitle("")
    plt.xlabel("Win")
    plt.ylabel("Kill Participation")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "kill_participation_wins_losses.png")
    plt.close()

    # 3) Scatter: CS/min vs Damage share colored by win (simple with markers)
    plt.figure()
    wins = my_df[my_df["win"] == True]
    losses = my_df[my_df["win"] == False]
    plt.scatter(wins["cs_per_min"], wins["damage_share"], marker="o", label="Win")
    plt.scatter(losses["cs_per_min"], losses["damage_share"], marker="x", label="Loss")
    plt.title("CS/min vs Damage Share")
    plt.xlabel("CS per min")
    plt.ylabel("Damage Share")
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "cs_vs_damage_share.png")
    plt.close()


def main():
    # Load data
    if not IN_ALL.exists() or not IN_ME.exists():
        raise FileNotFoundError("Missing S04 outputs. Ensure players_with_features.csv and my_games.csv exist.")

    all_df = pd.read_csv(IN_ALL)
    my_df = pd.read_csv(IN_ME)

    # Get your PUUID from my_games.csv (reliable)
    my_puuid = my_df["puuid"].iloc[0]

    # 1) Wins vs Losses metric summary
    wl_summary = summarize_wins_losses(my_df)

    # 2) Add ranks within your team per match
    my_ranked = add_within_team_ranks(all_df, my_puuid)

    # 3) Compute "unlucky index"
    unlucky = compute_unlucky_index(my_ranked)

    # 4) Create plots
    make_plots(my_ranked)

    # 5) Write a text report
    lines = []
    lines.append("S05 — Basic Report: Do I suck or am I unlucky?\n")
    lines.append(f"Games analyzed: {len(my_df)}")
    lines.append(f"Wins: {int(my_df['win'].sum())} | Losses: {int((~my_df['win'].astype(bool)).sum())}\n")

    lines.append("Average metrics (WIN vs LOSS):")
    lines.append(wl_summary.to_string())
    lines.append("")

    lines.append("Unlucky Index (simple):")
    lines.append(f"- Loss games: {unlucky['loss_games']}")
    lines.append(f"- Losses where I was top-2 damage share on my team: {unlucky['top2_losses']}")
    lines.append(f"- Rate: {unlucky['top2_loss_rate']}")
    lines.append("")

    lines.append("Saved plots to: reports/plots/")
    lines.append("- damage_share_wins_losses.png")
    lines.append("- kill_participation_wins_losses.png")
    lines.append("- cs_vs_damage_share.png")

    OUT_REPORT.write_text("\n".join(lines))
    print(f"✅ Wrote report: {OUT_REPORT}")
    print(wl_summary)
    print("✅ Unlucky Index:", unlucky)
    print("✅ Plots saved in reports/plots/")


if __name__ == "__main__":
    main()
