"""
Streamlit dashboard for: "Do I suck or am I unlucky?"
"""

from pathlib import Path
from io import BytesIO
import pandas as pd
import streamlit as st
import time
import plotly.express as px
import streamlit.components.v1 as components

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


#GIf Setup
def gif_for_bucket(bucket: str) -> str | None:
    """
    Return a gif URL for each bucket (or None for no gif).
    """
    b = (bucket or "").strip().upper()

    gifs = {
        # Expected WIN but LOSS
        "THROW": "https://media.giphy.com/media/l0HlvtIPzPdt2usKs/giphy.gif",
        "UNLUCKY LOSS": "https://media.giphy.com/media/9Y5BbDSkSTiY8/giphy.gif",
        "UPSET LOSS": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3Y0eDlzY2MyZTRzZGhjMHVlOWhhcHlzZ2FlbHBycHBxcXlkd3Y5eCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ka6M66Z58QEcXadCd4/giphy.gif", 

        # Expected LOSS but WIN
        "CLUTCH WIN": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcnJtcThocDNwY2k4b3oyazZ4aDVsZnlrNG5rbWFxMnJqMzNiYml1ZSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/j3hqssdFfHkpndO1qP/giphy.gif",
        "LUCKY WIN": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExNmc2ZTkybXM4azlyaWc3ZHE4cjgyYmphcDZuODR4OXBkNGN5dTB0OSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/XatIdQKTrTaXnWAe1n/giphy.gif", 
        "UPSET WIN": "https://media.giphy.com/media/111ebonMs90YLu/giphy.gif",

        # Expected outcomes
        "EXPECTED WIN": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExN3Fuenc1OXFtMTRhdXRqbDF5d2R2OXVpaDVjZng2b2wxeTlmNmg5MCZlcD12MV9naWZzX3NlYXJjaCZjdD1n/tM76xlB5idOYRwB0wR/giphy.gif",    
        "EXPECTED LOSS": "https://media.giphy.com/media/7T33BLlB7NQrjozoRB/giphy.gif",

        # Toss-ups
        "TOSS-UP WIN": "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExODU2MjBzd2w4YThkZmN2aXNudW52YmZjMDB1ajhidXJicjZjcjU1ZiZlcD12MV9naWZzX3NlYXJjaCZjdD1n/dijK6WYRdSoJEikGPS/giphy.gif",  
        "TOSS-UP LOSS": "https://media.giphy.com/media/3og0IPxMM0erATueVW/giphy.gif",
    }

    return gifs.get(b)

# Comment setup
def bucket_comment(bucket: str, p_win: float, win: bool, impact: float) -> str:
    """
    One message per bucket.
    - High impact: praise / "team diff" / "you deserved better"
    - Low impact: roast (but only when it's clearly on you)
    """
    b = (bucket or "TOSS-UP LOSS").strip().upper()

    # Expected WIN but LOSS
    if b == "THROW":
        return "YOU SUCK 💀. Someone definitely spam pinged you."
    if b == "UNLUCKY LOSS":
        return "Nah you didn’t deserve this 😭 You were doing your job and still took the L. Team diff."
    if b == "UPSET LOSS":
        return "Winnable at 10… then the game turned into a disaster... Feels bad."

    # Expected LOSS but WIN
    if b == "CLUTCH WIN":
        return "Main character moment 🗿. You were moving DIFFERENT."
    if b == "LUCKY WIN":
        return "Be honest… you got carried 😭. Honor your teammates."
    if b == "UPSET WIN":
        return "Enemy team fumbled and you collected the LP ✅."

    # Expected outcomes
    if b == "EXPECTED WIN":
        return "Clean. No drama. No int. Just business ✅."
    if b == "EXPECTED LOSS":
        return "Unfortunate... blame the rift, go next 🤷."

    # Toss-ups
    if b == "TOSS-UP WIN":
        return "Nobody knew what was happening… but you ended with LP ✅."
    if b == "TOSS-UP LOSS":
        return "Nobody knew what was happening… and it ended in pain ❌."


    # Fallback (shouldn't hit, but safe)
    return "Standard game. Nothing to blame but the replay 🫡."


def bucket_level(bucket: str, win: bool, impact: float) -> str:
    """
    Styling helper.
    """
    b = (bucket or "").strip().upper()

    if win:
        if b in ("CLUTCH WIN", "UPSET WIN", "EXPECTED WIN", "TOSS-UP WIN"):
            return "success"
        if b == "LUCKY WIN":
            return "warning"
        return "info"

    # Loss
    if b == "THROW":
        return "error"
    if b in ("UNLUCKY LOSS", "UPSET LOSS"):
        return "warning" if impact < 0.5 else "error"
    if b in ("EXPECTED LOSS", "TOSS-UP LOSS"):
        return "info"
    return "info"


# Streamlit UI setup
st.set_page_config(page_title="Do I suck or am I unlucky?", layout="wide")
#Title
st.markdown(
    """
    <style>
    .hero-card{
        max-width: 1100px;
        margin: 10px auto 22px auto;
        padding: 22px 22px;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.04);
        box-shadow: 0 10px 28px rgba(0,0,0,0.35);
        text-align: center;
    }
    .hero-title{
        font-size: 52px;
        font-weight: 900;
        letter-spacing: -1px;
        line-height: 1.05;
        margin: 0 0 10px 0;
    }
    .hero-sub{
        font-size: 15px;
        opacity: 0.85;
        margin: 0;
    }
    </style>

    <div class="hero-card">
      <div class="hero-title">Do I suck or am I unlucky?</div>
      <div class="hero-sub">
        I got tired of blaming ‘team diff’ without receipts… so I built this to tell me if I’m unlucky or if I actually just suck.
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


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

# Always (re)compute impact tags so filters work
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

ld = float(filt_luck["luck_diff"])
if ld > 0:
    msg = f"You won {ld:.2f} more than expected"
elif ld < 0:
    msg = f"You lost {abs(ld):.2f} more than expected"
else:
    msg = "You won exactly as expected"

lc4.metric("Summary", msg)

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
col4.metric("Avg expected win @ 10 minutes", f"{(float(f['p_win_10min'].mean())*100):.1f}%" if len(f) else "0.0%")

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

match_ids = f["match_id"].tolist() if len(f) else df["match_id"].tolist()
match_options = ["— Select a match —"] + match_ids
selected_match = st.selectbox("Select a match_id", options=match_options, index=0)

if selected_match == "— Select a match —":
    st.info("Pick a match to review.")
    st.stop()

row = df[df["match_id"] == selected_match].iloc[0]

exp10 = float(row["p_win_10min"])
imp = float(row["impact_score"])
outcome = bool(row["win"])
b = str(row.get("bucket", ""))

comment = bucket_comment(b, exp10, outcome, imp)
level = bucket_level(b, outcome, imp)


# show message (animated + centered) (cannot figure out how to show the animation on streamlit)
css = """
<style>
@keyframes popZoom {
  0%   { transform: scale(0.75); opacity: 0; filter: blur(2px); }
  60%  { transform: scale(1.06); opacity: 1; filter: blur(0px); }
  100% { transform: scale(1.00); opacity: 1; }
}

@keyframes smokeFloat {
  0%   { transform: translate(-50%, 0) scale(0.9); opacity: 0.0; }
  30%  { opacity: 0.28; }
  100% { transform: translate(-50%, -55px) scale(1.25); opacity: 0.0; }
}

.dramatic-wrap{
  margin: 10px 0 18px 0;
  padding: 18px 16px;
  border-radius: 18px;
  text-align: center;
  position: relative;
  overflow: hidden;
  animation: popZoom 420ms ease-out;
}

.dramatic-text{
  font-size: 34px;
  font-weight: 900;
  letter-spacing: 0.6px;
  line-height: 1.12;
}

.dramatic-sub{
  margin-top: 8px;
  font-size: 16px;
  opacity: 0.9;
}

.smoke{
  position: absolute;
  left: 50%;
  top: 58%;
  width: 240px;
  height: 240px;
  border-radius: 999px;
  background: radial-gradient(circle, rgba(255,255,255,0.20), rgba(255,255,255,0.0) 60%);
  filter: blur(6px);
  transform: translateX(-50%);
  animation: smokeFloat 1100ms ease-out;
  pointer-events: none;
}

.theme-success { border: 2px solid rgba(0, 255, 140, 0.35); background: rgba(0, 255, 140, 0.09); }
.theme-warning { border: 2px solid rgba(255, 190, 0, 0.35); background: rgba(255, 190, 0, 0.10); }
.theme-error   { border: 2px solid rgba(255, 60, 60, 0.42);  background: rgba(255, 60, 60, 0.12); }
.theme-info    { border: 2px solid rgba(180, 180, 180, 0.35); background: rgba(180, 180, 180, 0.10); }
</style>
"""

theme_class = {
    "success": "theme-success",
    "warning": "theme-warning",
    "error": "theme-error",
    "info": "theme-info",
}.get(level, "theme-info")

bucket_label = b if b else "RESULT"

html = f"""
{css}
<div class="dramatic-wrap {theme_class}">
  <div class="smoke"></div>
  <div class="dramatic-text">{comment}</div>
  <div class="dramatic-sub">Verdict: <b>{bucket_label}</b> • p(win@10)={exp10:.2f} • impact={imp:.2f}</div>
</div>
"""

gif = gif_for_bucket(b)
if gif:
    st.markdown(
    """
    <style>
    .gif-wrap{
      max-width: 520px;
      margin: 0 auto 14px auto;
      border-radius: 16px;
      overflow: hidden;
      border: 1px solid rgba(255,255,255,0.14);
      background: rgba(255,255,255,0.03);
      box-shadow: 0 6px 20px rgba(0,0,0,0.35);
      aspect-ratio: 16 / 9;          /* forces consistent box height */
    }
    .gif-wrap img{
      width: 100%;
      height: 100%;
      object-fit: cover;             /* fill the box, crop if needed */
      display: block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

    st.markdown(
        f"""
        <div class="gif-wrap">
          <img src="{gif}" alt="reaction gif">
        </div>
        """,
        unsafe_allow_html=True,
    )



st.markdown(html, unsafe_allow_html=True)

# Match Summary
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
