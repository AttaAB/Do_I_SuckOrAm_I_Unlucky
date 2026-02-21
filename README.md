<img width="1910" height="554" alt="image" src="https://github.com/user-attachments/assets/baba3f34-3ba3-4a23-85de-e3af584c4745" />

*Do I Suck, or Am I Unlucky?* | A League of Legends analytics project powered by the Riot API

---

## Inspiration (...I kept losing)

After a long hiatus, I decided to pick up the game that continuously breaks my heart... League of Legends

Within a few days, I remembered **exactly** why I retired.

Because I kept losing games that I **clearly** should have won …or so I thought.

Instead of defaulting to “team diff”, I decided to do something different:  
I built an analytics project to answer the question once and for all: **Am I Unlucky… or do I actually just suck?**

---

## What this project tries to measure

This project separates the problem into two parts:

### 1) **Impact** (Did I personally play well?)
I compute a single **impact_score** per game for me using a mix of performance signals:
- **Kill Participation (KP)**: how involved I was in my team’s kills  
- **Damage Share**: how much of my team’s damage I contributed  
- **CS/min**: farming efficiency  
- **Vision/min**: vision contribution per minute  

Then I use that score to rank me **within my team** each game (ex: top 1, top 2, etc.).

### 2) **Luck** (Given early game state, should my team have won?)
I train a simple model to estimate:
> **P(win | early-game state at 10 minutes)**

Then I compare:
- **Actual wins** vs **Expected wins** (sum of predicted win probabilities)

This is what I call my **luck_diff**.

---

## Metric definitions (the math)

### Team-based features (to make stats comparable)
- **Kill Participation:**
  KP = (kills + assists)/(team_kills)
  
- **Damage Share:**
  damage_share = (my_damage)/(team_damage)
  
- **Vision per minute:**
  vision_per_min = (vision_score)/(game_minutes)

---

## Impact score (role-aware)

### Why role-aware?
Roles have different baselines:
- supports naturally have higher vision  
- laners naturally have higher CS  
- junglers often have different KP patterns  

So comparing raw stats across roles is… not fair.

### Z-score standardization (within each role)
For each metric **within a role group**:

z = (x - mean{role}/(standard_deviation{role})

Meaning:
- positive z = above-average for my role  
- negative z = below-average for my role  

### Final impact_score (weighted)
I combine role-aware z-scores into one number:

impact_score =
0.35 * z_damage_share + 0.30 * z_KP + 0.25 * z_CS/min + 0.10 * z_vision/min

> **Note on impact_score weights:** I realize these weights are somewhat arbitrary — I picked them based on personal experience and what *felt* most influential in-game (damage + KP > CS > vision). This can definitely be made more robust.

Then I compute:
- **impact_rank_on_team** (1 = highest impact among my 5 teammates)

This lets me flag games like:
- “I was top-2 impact on my team and still lost” → *feels unlucky*

---

## Expected win model (luck)

### Why early-game features?
Using end-of-game stats leaks the outcome.
So I use only **10-minute timeline signals**:

- `gold_diff_10`  = my team gold − enemy team gold  
- `xp_diff_10`    = my team xp − enemy team xp  
- `cs_diff_10`    = my team cs − enemy team cs  
- `kills_diff_10` = my team kills − enemy team kills (before 10:00)

Optional v2 adds:
- `dragon_kills_diff_10`
- `plates_diff_10`

### Logistic regression (probability model)
I train a **logistic regression** model because:
- outcome is binary (win/loss)
- it outputs probabilities (perfect for “expected wins”)
- it’s interpretable and a solid baseline

Conceptually:
- `P(win) = sigmoid(b0 + b1*x1 + b2*x2 + ...)`

### How I trained it (cross-validated probabilities)
To avoid “training and grading on the same test,” I use:
- **5-fold Stratified Cross Validation**
  - keeps win/loss ratio similar in each split
  - each game gets a prediction from a model that didn’t train on it

Output per game:
- `p_win_10min` = predicted win probability at 10 minutes

---

## luck_diff (how “lucky” I was overall)

Across all games:

- **actual_wins** = total wins  
- **expected_wins** = sum of predicted win probabilities  

luck_diff = actual_wins - expected_wins

Interpretation:
- **luck_diff > 0** → I won more games than expected (lucky / overperformed expectation)
- **luck_diff < 0** → I won fewer games than expected (unlucky)

In plain English:  
> “How many more games did I win (or lose) than my early-game states suggested I should?”

---

## Buckets (game review labels)

After merging impact + expected win, I label games like:
- **EXPECTED WIN:** high expected win + win
- **EXPECTED LOSS:** low expected win + loss
- **LUCKY WIN:** low expected win + low impact + win
- **UNLUCKY LOSS:** high expected win + high impact + loss
- **CLUTCH WIN:** low expected win + high impact + win
- **THROW:** high expected win + low impact + loss
- **UPSET WIN:** low expected win + win (impact not extreme)
- **UPSET LOSS:** high expected win + loss (impact not extreme)
- **TOSS-UP WIN:** neither high nor low expected win + win
- **TOSS-UP LOSS:** neither high nor low expected win + loss

Current thresholds (easy to tune):

`High expected win: p_win > 0.65`

`Low expected win: p_win < 0.40`

`High impact: impact_score > 0.5`

`Low impact: impact_score < -0.5`

> **Note on thresholds**: these thresholds are a starting point — a more robust approach would be using percentiles (ex: top/bottom 25% for “high/low”), which I’ll likely add.

---

## Setup (If you'd like to run it)

### 1) Create a virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install packages
```bash
pip install -r requirements.txt
```

### 3) Add a .env file
```
RIOT_API_KEY=PASTE_YOUR_KEY_HERE
RIOT_GAME_NAME=YourNameHere
RIOT_TAG_LINE=NA1
RIOT_REGION_GROUP=americas
RIOT_PUUID=YOUR_PUUID_HERE
```

### 4) Run the pipeline scripts (in order)
Run each `src/S0X_.py` file in sequence:
download → build tables → features → impact → timelines → expected wins → merge

### 5) Personal Streamlit dashboard
To launch the interactive dashboard locally, run:

```bash
streamlit run app.py
```

## Project outputs

You’ll end up with:
- `data/raw/` — saved match JSON files  
- `data/timeline_raw/` — timeline JSON files  
- `data/processed/` — clean CSVs (players, my games, impact, expected win probs, merged scored file)  
- `reports/` — text reports + optional plots  

---

## Notes / limitations
- This is a learning project, not a perfect “truth machine.”
- Sample size matters: small match counts = noisy model.
- The expected-win model is intentionally simple — there are definitely more robust methods.

## Future improvements (if I don’t get tilted and quit again)
- Better feature engineering (matchups, scaling champs, objective timings)
- Make wieghts and thresholds more robust
- Add game-level rankings (impact vs all 10 players, not just team)
- Better dashboard visuals + match drilldowns

## Feedback

If you have suggestions to make the analysis more robust or the code cleaner, please let me know!
New to this, but extremely willing to learn 
