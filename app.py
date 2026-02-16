"""
Streamlit dashboard for: "Do I suck or am I unlucky?"
"""

from pathlib import Path
from io import BytesIO
import pandas as pd
import streamlit as st

# Paths

# S06 output: games + impact_score (+ other metrics)
IMPACT = Path("data/processed/my_games_with_impact.csv")

# S08 output: expected win probability at 10 minutes (timeline-only, no objectives)
PROBS = Path("data/processed/expected_win_probs.csv")

# S09 output (optional): impact + expected probs merged + bucket labels
SCORED = Path("data/processed/my_games_scored.csv")

# Helpers
@st.cache_data
def load_df(path: Path) -> pd.DataFrame:
    """Load a CSV from disk into a pandas DataFrame (cached for speed)."""
    return pd.read_csv(path)


@st.cache_data
def load_df_bytes(b: bytes) -> pd.DataFrame:
    """Load a CSV from uploaded bytes into a pandas DataFrame (cached)."""
    return pd.read_csv(BytesIO(b))


def load_required_csv(path: Path, label: str) -> pd.DataFrame:
    """
    Minimal deploy-safe loader:
    - If file exists in the repo/runtime, load from disk.
    - Else (common in Streamlit deploy), ask user to upload it.
    """
    if path.exists():
        return load_df(path)

    st.warning(f"Missing file in deployment: {path}. Please upload **{label}** to continue.")
    up = st.file_uploader(f"Upload {label}", type=["csv"], key=f"upload_{path}")
    if up is None:
        st.stop()
    return load_df_bytes(up.getvalue())


def build_scored_from_parts() -> pd.DataFrame:
    """
    Build the "scored" dataset inside the app (merge impact + expected win probs).
    This uses ONLY S08 probabilities: expected_win_probs.csv (p_win_10min).
    """
    impact_df = load_required_csv(IMPACT, "my_games_with_impact.csv (S06)")
    probs_df = load_required_csv(PROBS, "expected_win_probs.csv (S08)")[["match_id", "p_win_10min"]].copy()
    df = impact_df.merge(probs_df, on="match_id", how="inner")
    return df


def bucket_rule(p_win: float, win: bool, impact: float) -> str:
    """
    Assign a simple label ("bucket") based on:
    - p_win: expected probability of winning at 10 minutes
    - win: actual outcome
    - impact: impact_score
    """
    HIGH_EXP = 0.65
    LOW_EXP = 0.35
    HIGH_IMP = 0.5
    LOW_IMP = -0.5

    high_exp = p_win >= HIGH_EXP
    low_exp = p_win <= LOW_EXP
    high_imp = impact >= HIGH_IMP
    low_imp = impact <= LOW_IMP

    if (not win) and high_exp and high_imp:
        return "UNLUCKY LOSS (high exp, high impact)"
    if (not win) and high_exp and low_imp:
        return "THROW? (high exp, low impact)"
    if win and low_exp and high_imp:
        return "CLUTCH WIN (low exp, high impact)"

    if (not win) and high_exp:
        return "UNLUCKY LOSS (high exp)"
    if win and low_exp:
        return "CLUTCH WIN (low exp)"

    return "NORMAL"


def luck_metrics(d: pd.DataFrame) -> dict:
    """Compute luck metrics for a dataframe."""
    if len(d) == 0:
        return {"games": 0, "actual_wins": 0, "expected_wins": 0.0, "luck_diff": 0.0}

    actual_wins = int(d["win"].astype(int).sum())
    expected_wins = float(d["p_win_10min"].sum())
    luck_diff = float(actual_wins - expected_wins)

    return {
        "games": int(len(d)),
        "actual_wins": actual_wins,
        "expected_wins": expected_wins,
        "luck_diff": luck_diff,
    }


def luck_label(luck_diff: float) -> str:
    if luck_diff >= 5:
        return "Clearly lucky 🤯"
    if luck_diff <= -5:
        return "Clearly unlucky 💀"
    if luck_diff >= 2.5:
        return "Kinda lucky 🙂"
    if luck_diff <= -2.5:
        return "Kinda unlucky 😭"
    return "About as expected 😐"

# Streamlit UI setup
st.set_page_config(page_title="Do I suck or am I unlucky?", layout="wide")
st.title("Do I suck or am I unlucky?")
st.caption("I got tired of blaming ‘team diff’ without receipts… so I built this to tell me if I’m unlucky or if I acctually just suck.")

# Load data (deploy-safe)
# - If SCORED exists, use it
# - Else, build from IMPACT + PROBS
if SCORED.exists():
    df = load_required_csv(SCORED, "my_games_scored.csv (S09)")
else:
    df = build_scored_from_parts()

# Validate required columns exist
required_cols = {"match_id", "win", "impact_score", "p_win_10min"}
missing = required_cols - set(df.columns)
if missing:
    st.error(
        f"Missing required columns: {missing}. "
        "Make sure CSVs include these columns."
    )
    st.stop()

# Make sure win is boolean
df["win"] = df["win"].astype(bool)

# If bucket column doesn't exist, create it
if "bucket" not in df.columns:
    df["bucket"] = df.apply(
        lambda r: bucket_rule(float(r["p_win_10min"]), bool(r["win"]), float(r["impact_score"])),
        axis=1
    )

# Sidebar filters
st.sidebar.header("Filters")

roles = ["ALL"] + sorted([r for r in df.get("role", pd.Series(dtype=str)).dropna().unique().tolist()])
champs = ["ALL"] + sorted([c for c in df.get("champion_name", pd.Series(dtype=str)).dropna().unique().tolist()])
buckets = ["ALL"] + sorted(df["bucket"].dropna().unique().tolist())

role_choice = st.sidebar.selectbox("Role", roles)
champ_choice = st.sidebar.selectbox("Champion", champs)
bucket_choice = st.sidebar.selectbox("Bucket", buckets)
win_choice = st.sidebar.selectbox("Result", ["ALL", "WIN", "LOSS"])

# Apply filters
f = df.copy()

if role_choice != "ALL" and "role" in f.columns:
    f = f[f["role"] == role_choice]

if champ_choice != "ALL" and "champion_name" in f.columns:
    f = f[f["champion_name"] == champ_choice]

if bucket_choice != "ALL":
    f = f[f["bucket"] == bucket_choice]

if win_choice == "WIN":
    f = f[f["win"] == True]
elif win_choice == "LOSS":
    f = f[f["win"] == False]


# Highlight: Luck differential (FULL + FILTERED)
full_luck = luck_metrics(df)
filt_luck = luck_metrics(f)

st.subheader("Luck differential")
st.caption("Luck Differential = Actual Wins − Expected Wins, where Expected Wins = Σ p_win_10min.")

lc1, lc2, lc3, lc4 = st.columns(4)
lc1.metric("Luck diff", f"{filt_luck['luck_diff']:.2f}")
lc2.metric("Actual wins", filt_luck["actual_wins"])
lc3.metric("Expected wins", f"{filt_luck['expected_wins']:.2f}")
lc4.metric("Interpretation", luck_label(filt_luck["luck_diff"]))

st.caption(
    f"Overall: luck_diff = {filt_luck['luck_diff']:.2f} "
    f"(actual {filt_luck['actual_wins']} vs expected {filt_luck['expected_wins']:.2f})."
)

st.divider()

# Top summary metrics (filtered)
col1, col2, col3, col4 = st.columns(4)

col1.metric("Games played", len(f))
col2.metric("Win rate", f"{(float(f['win'].mean())*100):.1f}%" if len(f) else "0.0%")
col3.metric("Avg impact_score", round(float(f["impact_score"].mean()), 3) if len(f) else 0.0)
col4.metric("Avg expected win @ 10 minutes",f"{(float(f['p_win_10min'].mean())*100):.1f}%" if len(f) else "0.0%")

st.divider()

# Bucket counts
st.subheader("Bucket counts")
bucket_counts = f["bucket"].value_counts().reset_index()
bucket_counts.columns = ["bucket", "count"]
st.dataframe(bucket_counts, use_container_width=True)

st.divider()

# Scatter plot: expected win vs impact score
st.subheader("Impact vs Expected Win @ 10 minutes")
st.caption(
    "Each dot represents a game. Further right = higher expected win at 10 minutes. "
    "Higher up = higher personal impact (role-aware)."
)

st.scatter_chart(
    f.rename(columns={"p_win_10min": "expected_win_10"})[["expected_win_10", "impact_score"]],
    x="expected_win_10",
    y="impact_score"
)

st.markdown("""
**How to read the scatter (quadrants):**
- **Top-right:** High expected win + high impact → you did your job and it *should* be a win.
- **Top-left:** Low expected win + high impact → “clutch/hero” type performances.
- **Bottom-right:** High expected win + low impact → “throw risk / didn’t convert lead.”
- **Bottom-left:** Low expected win + low impact → expected loss / rough game.
""")

st.divider()

# Notable Matches
st.subheader("Notable Games")

HIGH_EXP = 0.65
LOW_EXP = 0.35

unlucky = df[(df["win"] == False) & (df["p_win_10min"] >= HIGH_EXP)] \
    .sort_values("p_win_10min", ascending=False).head(10)

clutch = df[(df["win"] == True) & (df["p_win_10min"] <= LOW_EXP)] \
    .sort_values("p_win_10min", ascending=True).head(10)

base_cols = ["match_id", "win", "impact_score", "p_win_10min", "bucket"]
extra_cols = [
    "champion_name", "role", "impact_rank_on_team",
    "kda", "cs_per_min", "kill_participation", "damage_share", "vision_per_min"
]
show_cols = [c for c in base_cols + extra_cols if c in df.columns]

c1, c2 = st.columns(2)

with c1:
    st.markdown("### Most 'unlucky' losses (highest expected win but loss)")
    st.dataframe(unlucky[show_cols], use_container_width=True)

with c2:
    st.markdown("### Most 'clutch' wins (lowest expected win but win)")
    st.dataframe(clutch[show_cols], use_container_width=True)

st.divider()

# Filtered games table
st.subheader("Filtered games table")
st.dataframe(
    f[show_cols].sort_values("p_win_10min", ascending=False),
    use_container_width=True
)

st.divider()

# Match drill-down
st.subheader("Match details")
st.caption("Pick a match to inspect.")

match_options = f["match_id"].tolist() if len(f) else df["match_id"].tolist()
selected_match = st.selectbox("Select a match_id", options=match_options)

row = df[df["match_id"] == selected_match].iloc[0]

st.write("### Selected match summary")
st.json({
    "match_id": row["match_id"],
    "champion": row.get("champion_name", None),
    "role": row.get("role", None),
    "win": bool(row["win"]),
    "bucket": row.get("bucket", None),
    "impact_score": round(float(row["impact_score"]), 3),
    "impact_rank_on_team": row.get("impact_rank_on_team", None),
    "expected_win_10": round(float(row["p_win_10min"]), 3),
})

m1, m2, m3, m4 = st.columns(4)
m1.metric("KDA", round(float(row.get("kda", 0.0)), 2))
m2.metric("CS/min", round(float(row.get("cs_per_min", 0.0)), 2))
m3.metric("Kill Participation", round(float(row.get("kill_participation", 0.0)), 3))
m4.metric("Damage Share", round(float(row.get("damage_share", 0.0)), 3))

st.caption("So.... am I unlucky, or do I just suck? 🤔")
