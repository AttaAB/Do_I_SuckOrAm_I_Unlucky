"""
Streamlit dashboard for: "Do I suck or am I unlucky?"
"""

from pathlib import Path
from io import BytesIO
import pandas as pd
import streamlit as st
import time
import plotly.express as px

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
    LOW_EXP = 0.40
    HIGH_IMP = 0.5
    LOW_IMP = -0.5

    high_exp = p_win >= HIGH_EXP
    low_exp = p_win <= LOW_EXP
    high_imp = impact >= HIGH_IMP
    low_imp = impact <= LOW_IMP

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


def impact_tag(impact: float) -> str:
    """
    Add a small secondary tag (OPTION B):
    - High / Mid / Low impact based on impact_score thresholds
    """
    HIGH_IMP = 0.5
    LOW_IMP = -0.5
    if impact >= HIGH_IMP:
        return "HIGH IMPACT"
    if impact <= LOW_IMP:
        return "LOW IMPACT"
    return "MID IMPACT"


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

#GIf Setup
def reaction_for_game(p_win: float, win: bool, impact: float) -> dict:
    """
    Return a reaction payload for a single game:
    - title: big text
    - subtitle: small explanation
    - gif: optional gif url (or None)
    - level: one of {"success","warning","error","info"} for styling choice
    """

    # Use your existing thresholds if already defined
    # If you already have these constants earlier, delete these 4 lines.
    HIGH_EXP = 0.65
    LOW_EXP = 0.40
    HIGH_IMP = 0.5
    LOW_IMP = -0.5

    # bucket expected + impact into 3 levels
    if p_win >= HIGH_EXP:
        exp_band = "HIGH"
    elif p_win <= LOW_EXP:
        exp_band = "LOW"
    else:
        exp_band = "MID"

    if impact >= HIGH_IMP:
        imp_band = "HIGH"
    elif impact <= LOW_IMP:
        imp_band = "LOW"
    else:
        imp_band = "MID"

    outcome = "WIN" if win else "LOSS"

    key = (outcome, exp_band, imp_band)

    # GIFs: use hosted URLs or swap to local assets later (recommended for reliability)
    GIF_FAIL = "https://media.giphy.com/media/3o6ZtaO9BZHcOjmErm/giphy.gif"
    GIF_GOAT = "https://media.giphy.com/media/111ebonMs90YLu/giphy.gif"
    GIF_ROBBED = "https://media.giphy.com/media/9Y5BbDSkSTiY8/giphy.gif"
    GIF_THROW = "https://media.giphy.com/media/l0HlvtIPzPdt2usKs/giphy.gif"
    GIF_CLUTCH = "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif"

    reactions = {
        # ----------------------------
        # WIN reactions
        # ----------------------------
        ("WIN", "LOW", "HIGH"): {
            "title": "YOU’RE THE GOAT 🐐",
            "subtitle": "Low expected win @10 but you still pulled it off. Hero performance.",
            "gif": GIF_GOAT,
            "level": "success",
        },
        ("WIN", "LOW", "MID"): {
            "title": "CLUTCH ENOUGH 😤",
            "subtitle": "Expected to lose @10, but you found a way. Respect.",
            "gif": GIF_CLUTCH,
            "level": "success",
        },
        ("WIN", "LOW", "LOW"): {
            "title": "…HOW DID YOU WIN? 🤨",
            "subtitle": "Expected loss @10 and low impact — but a win is a win.",
            "gif": None,
            "level": "info",
        },

        ("WIN", "MID", "HIGH"): {
            "title": "YOU CARRIED 🔥",
            "subtitle": "Game was up in the air @10, but you showed up big.",
            "gif": None,
            "level": "success",
        },
        ("WIN", "MID", "MID"): {
            "title": "MEH, SOLID 👍",
            "subtitle": "Pretty normal win — you did alright.",
            "gif": None,
            "level": "info",
        },
        ("WIN", "MID", "LOW"): {
            "title": "YOU GOT CARried 😭",
            "subtitle": "You won, but your impact was low. Thank your teammates.",
            "gif": None,
            "level": "warning",
        },

        ("WIN", "HIGH", "HIGH"): {
            "title": "TEXTBOOK WIN ✅",
            "subtitle": "High expected win and you played well — you did your job.",
            "gif": None,
            "level": "success",
        },
        ("WIN", "HIGH", "MID"): {
            "title": "EXPECTED WIN 🙂",
            "subtitle": "High expected win @10 and you closed it out.",
            "gif": None,
            "level": "info",
        },
        ("WIN", "HIGH", "LOW"): {
            "title": "WIN… BUT YOU ALMOST SOLD 😅",
            "subtitle": "High expected win @10, low impact. Don’t push your luck next time.",
            "gif": None,
            "level": "warning",
        },

        # ----------------------------
        # LOSS reactions
        # ----------------------------
        ("LOSS", "HIGH", "HIGH"): {
            "title": "YOU WERE ROBBED 😭",
            "subtitle": "High expected win @10 and high impact — this is certified unlucky.",
            "gif": GIF_ROBBED,
            "level": "error",
        },
        ("LOSS", "HIGH", "MID"): {
            "title": "UNLUCKY LOSS 😩",
            "subtitle": "Expected win @10 but it slipped away. Review the mid/late game.",
            "gif": None,
            "level": "warning",
        },
        ("LOSS", "HIGH", "LOW"): {
            "title": "YOU REALLY SOLD THIS ONE 💥",
            "subtitle": "Expected win @10 but low impact. This one’s on you.",
            "gif": GIF_THROW,
            "level": "error",
        },

        ("LOSS", "MID", "HIGH"): {
            "title": "YOU TRIED 🫡",
            "subtitle": "Game was uncertain @10, but your impact was high. Not a bad loss.",
            "gif": None,
            "level": "info",
        },
        ("LOSS", "MID", "MID"): {
            "title": "MEH LOSS 😐",
            "subtitle": "Pretty average loss. Not tragic, not heroic.",
            "gif": None,
            "level": "info",
        },
        ("LOSS", "MID", "LOW"): {
            "title": "YOU REALLY SUCKED THIS GAME 💀",
            "subtitle": "Low impact and a loss. Queue up the VOD and be honest with yourself.",
            "gif": GIF_FAIL,
            "level": "error",
        },

        ("LOSS", "LOW", "HIGH"): {
            "title": "UNLUCKY, BUT RESPECT 👏",
            "subtitle": "Expected loss @10, but you still had high impact. You fought.",
            "gif": None,
            "level": "info",
        },
        ("LOSS", "LOW", "MID"): {
            "title": "EXPECTED LOSS 🤷",
            "subtitle": "Low expected win @10 and it happened. Go next.",
            "gif": None,
            "level": "info",
        },
        ("LOSS", "LOW", "LOW"): {
            "title": "DEMONICALLY BAD 💀",
            "subtitle": "Expected loss @10 and low impact… yeah. We move.",
            "gif": GIF_FAIL,
            "level": "error",
        },
    }

    # fallback (shouldn't hit, but safe)
    return reactions.get(key, {
        "title": "MEH 😐",
        "subtitle": "Nothing special here.",
        "gif": None,
        "level": "info",
    })


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

# Always (re)compute buckets so the dashboard matches your current logic
df["bucket"] = df.apply(
    lambda r: bucket_rule(float(r["p_win_10min"]), bool(r["win"]), float(r["impact_score"])),
    axis=1
)

# Always (re)compute impact tags (OPTION B) so filters work
df["impact_tag"] = df["impact_score"].apply(lambda x: impact_tag(float(x)))

# Sidebar filters
st.sidebar.header("Filters")

roles = ["ALL"] + sorted([r for r in df.get("role", pd.Series(dtype=str)).dropna().unique().tolist()])
champs = ["ALL"] + sorted([c for c in df.get("champion_name", pd.Series(dtype=str)).dropna().unique().tolist()])
buckets = ["ALL"] + sorted(df["bucket"].dropna().unique().tolist())
impact_tags = ["ALL"] + sorted(df["impact_tag"].dropna().unique().tolist())

#Side bar filter choices
role_choice = st.sidebar.selectbox("Role", roles)
champ_choice = st.sidebar.selectbox("Champion", champs)

# Bucket label helper (sidebar only)
bucket_defs = {
    "THROW": "expected win → loss (low impact)",
    "UNLUCKY LOSS": "expected win → loss (high impact)",
    "UPSET LOSS": "expected win → loss",
    "CLUTCH WIN": "expected loss → win (high impact)",
    "LUCKY WIN": "expected loss → win (low impact)",
    "UPSET WIN": "expected loss → win",
    "EXPECTED WIN": "expected win → win",
    "EXPECTED LOSS": "expected loss → loss",
    "TOSS-UP WIN": "toss-up @10 → win",
    "TOSS-UP LOSS": "toss-up @10 → loss",
}

bucket_choice = st.sidebar.selectbox(
    "Bucket",
    buckets,
    format_func=lambda b: "ALL" if b == "ALL" else f"{b} — {bucket_defs.get(b, '')}".strip(" —"),
)
impact_choice = st.sidebar.selectbox("Impact tag", impact_tags)
win_choice = st.sidebar.selectbox("Result", ["ALL", "WIN", "LOSS"])

# Apply filters

f = df.copy()

if role_choice != "ALL" and "role" in f.columns:
    f = f[f["role"] == role_choice]

if champ_choice != "ALL" and "champion_name" in f.columns:
    f = f[f["champion_name"] == champ_choice]

if bucket_choice != "ALL":
    f = f[f["bucket"] == bucket_choice]

if impact_choice != "ALL":
    f = f[f["impact_tag"] == impact_choice]

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
    "Each dot is one of your games. Further right = higher expected win at 10 minutes. "
    "Higher up = higher personal impact (role-aware)."
)

plot_df = f.rename(columns={"p_win_10min": "expected_win_10"})

cols = ["expected_win_10", "impact_score", "impact_tag", "match_id", "win", "champion_name", "role"]
cols = [c for c in cols if c in plot_df.columns]  # keep only columns that exist
plot_df = plot_df[cols].copy()

fig = px.scatter(
    plot_df,
    x="expected_win_10",
    y="impact_score",
    hover_data={
        "match_id": True,
        "champion_name": ("champion_name" in plot_df.columns),
        "role": ("role" in plot_df.columns),
        "win": ("win" in plot_df.columns),
        "impact_tag": ("impact_tag" in plot_df.columns),
        "expected_win_10": ":.3f",
        "impact_score": ":.3f",
    },
)

st.plotly_chart(fig, use_container_width=True)

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
LOW_EXP = 0.40

unlucky = df[(df["win"] == False) & (df["p_win_10min"] >= HIGH_EXP)] \
    .sort_values("p_win_10min", ascending=False).head(10)

clutch = df[(df["win"] == True) & (df["p_win_10min"] <= LOW_EXP)] \
    .sort_values("p_win_10min", ascending=True).head(10)

base_cols = ["match_id", "win", "impact_score", "impact_tag", "p_win_10min", "bucket"]
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

#-----------------
exp10 = float(row["p_win_10min"])
imp = float(row["impact_score"])
outcome = bool(row["win"])

r = reaction_for_game(exp10, outcome, imp)

# show message
if r["level"] == "success":
    st.success(f"{r['title']} — {r['subtitle']}")
elif r["level"] == "warning":
    st.warning(f"{r['title']} — {r['subtitle']}")
elif r["level"] == "error":
    st.error(f"{r['title']} — {r['subtitle']}")
else:
    st.info(f"{r['title']} — {r['subtitle']}")

# show gif if present
if r["gif"]:
    st.image(r["gif"], caption=r["title"], use_container_width=True)
    
#---------------

st.write("### Selected match summary")
st.json({
    "match_id": row["match_id"],
    "champion": row.get("champion_name", None),
    "role": row.get("role", None),
    "win": bool(row["win"]),
    "bucket": row.get("bucket", None),
    "impact_tag": row.get("impact_tag", None),
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
