import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import random

try:
    from streamlit_cookies_manager import EncryptedCookieManager
    _cookies_available = True
except ImportError:
    _cookies_available = False

st.set_page_config(
    page_title="March Madness Pool",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─── Mobile-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Tight padding on mobile */
  @media (max-width: 768px) {
    .block-container { padding: 1rem !important; }
    div[data-testid="column"] { min-width: 0 !important; }
  }
  /* Metric card polish */
  div[data-testid="metric-container"] {
    background: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 10px 14px;
  }
  /* Tab styling */
  button[data-baseweb="tab"] { font-size: 14px !important; }
  /* Slightly larger dataframe text */
  .stDataFrame { font-size: 13px; }
</style>
""", unsafe_allow_html=True)

# ─── 0. SESSION STATE & COOKIE MANAGER ───────────────────────────────────────
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "modal_done" not in st.session_state:
    st.session_state["modal_done"] = False

# Initialise cookie manager (requires: pip install streamlit-cookies-manager)
_cookies = None
if _cookies_available:
    _cookies = EncryptedCookieManager(prefix="march_madness_", password="mm_pool_2025")
    if not _cookies.ready():
        st.stop()   # waits for the browser to return cookie values

# ─── 1. CONFIGURATION ─────────────────────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/1M3nBX0a2qwPyMdWqzEztN4eKY1wS5FU3OGgxUeNWamI/edit"

def get_csv_url(base_url: str, sheet_name: str) -> str | None:
    try:
        sheet_id = base_url.split("/d/")[1].split("/")[0]
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    except Exception:
        return None


def safe_int(val) -> int:
    try:
        if pd.isna(val):
            return 0
        return int(float(str(val).replace("#", "").split()[0].strip()))
    except Exception:
        return 0


def get_round_name(col_idx: int) -> str:
    if 3 <= col_idx <= 34:   return "First Round"
    if 35 <= col_idx <= 50:  return "Second Round"
    if 51 <= col_idx <= 58:  return "Sweet Sixteen"
    if 59 <= col_idx <= 62:  return "Elite Eight"
    if 63 <= col_idx <= 64:  return "Final Four"
    if col_idx == 65:        return "Championship"
    return "Unknown"


UNPLAYED = {"nan", "0", "", "None", "Winner"}


def is_unplayed(val: str) -> bool:
    return val in UNPLAYED


# ─── 2. DATA LOADING ──────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_all_data():
    master_url = get_csv_url(SHEET_URL, "MasterBracket")
    picks_url  = get_csv_url(SHEET_URL, "Picks")
    if not master_url or not picks_url:
        return None

    lucky_url  = get_csv_url(SHEET_URL, "LuckyTeam")

    df_seeds = pd.read_csv(master_url, header=None)
    seed_map: dict[str, int] = {}
    all_starting: set[str] = set()
    skip = {"West","East","South","Midwest","Region","Team","Seed","nan"}
    for _, row in df_seeds.iterrows():
        for col_idx in [1, 13]:
            team_raw = str(row[col_idx]).strip()
            seed = safe_int(row[col_idx - 1] if col_idx == 1 else row[col_idx + 1])
            if team_raw and team_raw not in skip and seed > 0:
                seed_map[team_raw] = seed
                all_starting.add(team_raw)

    # Build r1_matchups: maps each R1 col → (team_top, team_bot)
    # The Picks sheet row 0 contains the pre-tournament teams for every slot.
    # R1 cols 3–34: each cell has the original team seeded into that game slot.
    # Standard bracket: each game has a top-seed and bottom-seed participant.
    # We read the original teams from df_p row 0 (the seeding row).
    # We'll populate this after loading df_p below.

    df_p = pd.read_csv(picks_url, header=None)
    winners_row      = [str(x).strip() for x in df_p.iloc[2].values]
    points_per_game  = [safe_int(p) for p in df_p.iloc[1].values]

    # Build eliminated set from picks (used for bracket scoring)
    eliminated: set[str] = set()
    for c in range(3, 66):
        actual_w = winners_row[c]
        if is_unplayed(actual_w):
            continue
        for p_val in df_p.iloc[3:, c].astype(str):
            p_clean = p_val.strip()
            if p_clean != actual_w and p_clean in all_starting:
                eliminated.add(p_clean)

    all_alive = (all_starting - eliminated) | {w for w in winners_row if w in all_starting}

    # r1_matchups[c] = (team_a, team_b) — the two teams that played in R1 slot c.
    # We derive this by collecting all unique picks made for each R1 slot.
    # Every participant picked exactly one of the two teams, so the union gives both.
    r1_matchups: dict[int, tuple] = {}
    for c in range(3, 35):
        teams_in_slot = set()
        for i in range(3, len(df_p)):
            val = str(df_p.iloc[i][c]).strip()
            if val and val not in UNPLAYED and val in all_starting:
                teams_in_slot.add(val)
        # If only 1 unique pick exists (everyone picked the same team),
        # try winners_row to get the actual winner, then infer the other from seed_map
        if len(teams_in_slot) >= 2:
            teams_list = sorted(teams_in_slot, key=lambda t: seed_map.get(t, 99))
            r1_matchups[c] = (teams_list[0], teams_list[1])
        elif len(teams_in_slot) == 1:
            known = list(teams_in_slot)[0]
            # fallback: pair with actual winner if different
            actual = winners_row[c] if not is_unplayed(winners_row[c]) else ""
            other  = actual if actual and actual != known and actual in all_starting else ""
            if other:
                a, b = sorted([known, other], key=lambda t: seed_map.get(t, 99))
                r1_matchups[c] = (a, b)
            else:
                r1_matchups[c] = (known, "TBD")
        else:
            r1_matchups[c] = ("TBD", "TBD")

    # truly_alive: a team is alive iff, for every round that has been fully or partially
    # played, they either WON a game in that round or haven't reached it yet.
    # Concretely: find the deepest round with ANY played game. A team is alive if they
    # appear as a winner in that round OR in any later (unplayed) round slot — meaning
    # they're still competing. A team that last appears as a winner in an earlier round
    # but the next round has started and they didn't win = eliminated.
    round_ranges = [(3, 35), (35, 51), (51, 59), (59, 63), (63, 65), (65, 66)]

    # For each round, determine if it has any played games
    round_has_played = [
        any(not is_unplayed(winners_row[c]) for c in range(r_start, r_end))
        for r_start, r_end in round_ranges
    ]

    # Winners in each round
    round_winners = [
        {winners_row[c] for c in range(r_start, r_end) if not is_unplayed(winners_row[c])}
        for r_start, r_end in round_ranges
    ]

    truly_alive: set[str] = set()
    for team in all_starting:
        # Find the latest round this team won
        last_won_round = -1
        for i, winners in enumerate(round_winners):
            if team in winners:
                last_won_round = i

        if last_won_round == -1:
            # Never won any game — check if round 1 has been played at all
            # If round 1 has played games and this team never won one, they're out
            if round_has_played[0]:
                # Eliminated in round 1
                continue
            else:
                # Tournament hasn't started
                truly_alive.add(team)
        else:
            # They won round `last_won_round`. Check if the next round has started.
            next_round = last_won_round + 1
            if next_round >= len(round_ranges):
                # Won the championship
                truly_alive.add(team)
            elif not round_has_played[next_round]:
                # Next round hasn't started yet — still alive
                truly_alive.add(team)
            else:
                # Next round has started — did they win in it?
                if team in round_winners[next_round]:
                    truly_alive.add(team)
                # else: they lost in the next round, not alive

    # ── Lucky Team sheet ──────────────────────────────────────────────────────
    lucky_map: dict[str, list[str]] = {}   # team → list of participant names
    try:
        if lucky_url:
            df_lucky = pd.read_csv(lucky_url, header=None)
            for _, row in df_lucky.iterrows():
                a, b = str(row[0]).strip(), str(row[1]).strip()
                if a in {"nan", ""} or b in {"nan", ""}:
                    continue
                # Detect which column is the team name
                if a in all_starting:
                    team, participant = a, b
                elif b in all_starting:
                    team, participant = b, a
                else:
                    continue
                lucky_map.setdefault(team, []).append(participant)
    except Exception:
        pass  # Lucky Team tab is optional; silently skip if unavailable

    return df_p, winners_row, points_per_game, seed_map, all_alive, all_starting, truly_alive, lucky_map, r1_matchups, datetime.now().strftime("%I:%M %p")


# ─── 3. SCORING ───────────────────────────────────────────────────────────────
def score_picks(picks: list[str], winners: list[str], pts: list[int],
                seeds: dict[str, int], alive: set[str]) -> tuple[int, int]:
    """Return (current_score, potential_score)."""
    cur = pot = 0
    for c in range(3, 66):
        val = pts[c] + seeds.get(picks[c], 0)
        if picks[c] == winners[c]:
            cur += val
        if picks[c] in alive:
            pot += val
    return cur, pot


# ─── 4. MONTE CARLO ───────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def run_monte_carlo(
    names: tuple,
    picks_matrix: tuple,        # tuple of tuples so it's hashable
    winners_row: tuple,
    pts_list: tuple,
    alive_tuple: tuple,
    seed_items: tuple,
    runs: int = 1000,
) -> tuple[dict, dict]:
    """
    Proper simulation that respects bracket structure.
    For each unplayed column, randomly select a winner from the ALIVE teams
    that were actually picked for that column (plausible winners only).
    Falls back to global alive set if no picks remain.
    """
    seed_map = dict(seed_items)
    alive    = set(alive_tuple)
    unplayed = [c for c in range(3, 66) if is_unplayed(winners_row[c])]

    win_c  = {n: 0 for n in names}
    top3_c = {n: 0 for n in names}

    for _ in range(runs):
        sim_w = list(winners_row)
        for c in unplayed:
            # Candidates = picks made for this slot that are still alive
            candidates = [picks_matrix[i][c] for i in range(len(names))
                          if picks_matrix[i][c] in alive]
            sim_w[c] = random.choice(candidates) if candidates else (
                random.choice(list(alive)) if alive else "None"
            )

        scored = []
        for i, name in enumerate(names):
            s = sum(
                (pts_list[c] + seed_map.get(picks_matrix[i][c], 0))
                for c in range(3, 66)
                if picks_matrix[i][c] == sim_w[c]
            )
            scored.append((name, s))
        scored.sort(key=lambda x: x[1], reverse=True)

        win_c[scored[0][0]] += 1
        for k in range(min(3, len(scored))):
            top3_c[scored[k][0]] += 1

    n = runs
    return (
        {nm: (c / n) * 100 for nm, c in win_c.items()},
        {nm: (c / n) * 100 for nm, c in top3_c.items()},
    )


# ─── 5. BRACKET BUSTERS ───────────────────────────────────────────────────────
def compute_bracket_busters(results: list[dict], winners_row: list[str],
                             pts: list[int], seeds: dict[str, int]) -> pd.DataFrame:
    """
    For each played game, count how many participants had that team picked
    and lost points because the upset happened.
    """
    busters = []
    for c in range(3, 66):
        winner = winners_row[c]
        if is_unplayed(winner):
            continue
        busted = [
            r["Name"] for r in results
            if r["raw_picks"][c] != winner and r["raw_picks"][c] not in {"nan", ""}
        ]
        if busted:
            loser_team = None
            # Find the most-commonly-busted team in this slot
            loser_counts: dict[str, int] = {}
            for r in results:
                pick = r["raw_picks"][c]
                if pick != winner and pick not in {"nan", ""}:
                    loser_counts[pick] = loser_counts.get(pick, 0) + 1
            if loser_counts:
                loser_team = max(loser_counts, key=loser_counts.__getitem__)
            busters.append({
                "Round":        get_round_name(c),
                "Winner":       winner,
                "Upset Seed":   f"#{seeds.get(winner, '?')}",
                "Busted Team":  loser_team or "–",
                "Busted Picks": len(busted),
                "Pts Lost ea.": pts[c] + seeds.get(winner, 0),
                "Total Pts Lost": (pts[c] + seeds.get(winner, 0)) * len(busted),
            })

    if not busters:
        return pd.DataFrame()
    return (
        pd.DataFrame(busters)
        .sort_values("Busted Picks", ascending=False)
        .reset_index(drop=True)
    )


# ─── 6. CINDERELLA STORIES ────────────────────────────────────────────────────
def build_cinderella_stories(results: list[dict], winners_row: list[str],
                              seeds: dict[str, int], pts: list[int],
                              global_pick_counts: dict[str, int]) -> list[dict]:
    """
    One story per unique upset event (team + round). All believers are grouped
    together so the narrative is about the Cinderella team, not repeated per person.
    """
    pool_size = max(len(results), 1)

    # Collect believers per (col_index) upset slot
    # Key: col index → list of participant dicts who correctly called it
    upset_believers: dict[int, list[dict]] = {}
    for c in range(3, 66):
        winner = winners_row[c]
        if is_unplayed(winner) or seeds.get(winner, 0) < 5:
            continue
        believers = [r for r in results if r["raw_picks"][c] == winner]
        if believers:
            upset_believers[c] = believers

    stories = []
    for c, believers in upset_believers.items():
        winner   = winners_row[c]
        seed     = seeds.get(winner, 0)
        rnd      = get_round_name(c)
        pts_val  = pts[c] + seed
        n        = len(believers)
        surv_pct = round(n / pool_size * 100, 1)
        names    = [b["Name"] for b in believers]

        # Format believer list: "Alice, Bob & 3 others" if long
        if len(names) <= 3:
            believers_str = " & ".join(names) if len(names) > 1 else names[0]
        else:
            believers_str = f"{', '.join(names[:2])} & {len(names) - 2} others"

        # Tier by seed
        if seed >= 13:
            mood = "☠️ BRACKET TERRORIST"
            quip = (f"A #{seed} seed making it to the {rnd}. "
                    f"Only {n} {'person' if n == 1 else 'people'} in this pool ({surv_pct}%) called it. "
                    f"The rest of us were cowards.")
        elif seed == 12:
            mood = "🚨 CHAOS AGENT"
            quip = (f"#{seed} {winner} to the {rnd} — {surv_pct}% of the pool agreed. "
                    f"Deranged. Brilliant. Both.")
        elif seed >= 10:
            mood = "🔥 Certified Upset Merchant"
            quip = (f"#{seed} {winner} in the {rnd}. The scouting report said dangerous. "
                    f"{n} {'person' if n == 1 else 'people'} ({surv_pct}%) listened. They all ate.")
        elif seed >= 8:
            mood = "🎯 Upset Whisperer"
            quip = (f"#{seed} {winner} advancing to the {rnd}. Quiet confidence. "
                    f"{surv_pct}% pool agreement. Aged beautifully.")
        else:
            mood = "🎲 Contrarian Caller"
            quip = (f"#{seed} {winner} wasn't a trendy pick — only {surv_pct}% of the pool went there. "
                    f"Points in the bank.")

        stories.append({
            "team":         winner,
            "seed":         seed,
            "round":        rnd,
            "points":       pts_val,
            "n_believers":  n,
            "surv_pct":     surv_pct,
            "believers_str": believers_str,
            "names":        names,
            "mood":         mood,
            "quip":         quip,
        })

    # Sort: biggest seed first, then rarest (fewest believers)
    stories.sort(key=lambda x: (x["seed"], -x["n_believers"]), reverse=True)
    return stories


# ─── 7. HEAD-TO-HEAD ──────────────────────────────────────────────────────────
def head_to_head(p1: dict, p2: dict, winners_row: list[str],
                 pts: list[int], seeds: dict[str, int]) -> dict:
    """Compare two players across every game slot."""
    p1_only_pts = p2_only_pts = shared_pts = 0
    divergences = []

    for c in range(3, 66):
        w  = winners_row[c]
        t1 = p1["raw_picks"][c]
        t2 = p2["raw_picks"][c]
        val = pts[c] + seeds.get(t1, 0)

        if t1 == t2:
            if t1 == w:
                shared_pts += val
        else:
            # They diverge — track future games too
            divergences.append({
                "Round":    get_round_name(c),
                p1["Name"]: t1,
                p2["Name"]: t2,
                "Played":   not is_unplayed(w),
                "Winner":   w if not is_unplayed(w) else "–",
                "P1 Got It": "✅" if t1 == w else ("⏳" if is_unplayed(w) else "❌"),
                "P2 Got It": "✅" if t2 == w else ("⏳" if is_unplayed(w) else "❌"),
                "Pts":       val,
            })
            if t1 == w: p1_only_pts += val
            if t2 == w: p2_only_pts += val

    return {
        "p1_pts":     p1_only_pts,
        "p2_pts":     p2_only_pts,
        "shared_pts": shared_pts,
        "divergences": divergences,
    }


# ─── 8. NAME HIGHLIGHT HELPER ────────────────────────────────────────────────
def hl(text: str, user_name: str | None) -> str:
    """Wrap user's name in a gold highlight span wherever it appears in text."""
    if not user_name or user_name not in text:
        return text
    return text.replace(
        user_name,
        f'<span style="color:#f5c518; font-weight:700;">{user_name}</span>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────
try:
    data = load_all_data()
    if not data:
        st.error("Could not load data. Check that the Google Sheet is publicly accessible.")
        st.stop()

    df_p, actual_winners, points_per_game, seed_map, all_alive, all_starting, truly_alive, lucky_map, r1_matchups, last_update = data

    # ── Build results ──────────────────────────────────────────────────────────
    results: list[dict] = []
    global_pick_counts: dict[str, int] = {}

    for i in range(3, len(df_p)):
        row = df_p.iloc[i]
        name = str(row[0]).strip()
        if not name or name in {"Winner", ""}:
            continue
        p_picks = [str(row[c]).strip() if c < len(row) else "" for c in range(67)]

        cur_score, pot_score = score_picks(p_picks, actual_winners, points_per_game, seed_map, all_alive)

        upsets, best_s, best_t = 0, 0, "None"
        for c in range(3, 66):
            if p_picks[c] == actual_winners[c]:
                s = seed_map.get(p_picks[c], 0)
                if s >= 8:
                    upsets += 1
                    if s > best_s:
                        best_s, best_t = s, p_picks[c]
            if p_picks[c] not in {"nan", ""}:
                global_pick_counts[p_picks[c]] = global_pick_counts.get(p_picks[c], 0) + 1

        results.append({
            "Name":          name,
            "Current Score": cur_score,
            "Potential Score": pot_score,
            "Upsets":        upsets,
            "Biggest Upset": f"#{best_s} {best_t}" if best_s else "None",
            "raw_picks":     p_picks,
        })

    if not results:
        st.warning("No participant data found.")
        st.stop()

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    names_tuple   = tuple(r["Name"] for r in results)
    picks_matrix  = tuple(tuple(r["raw_picks"]) for r in results)
    win_probs, top3_probs = run_monte_carlo(
        names_tuple, picks_matrix,
        tuple(actual_winners), tuple(points_per_game),
        tuple(all_alive), tuple(seed_map.items()),
    )

    for r in results:
        r["Win %"]   = win_probs.get(r["Name"], 0.0)
        r["Top 3 %"] = top3_probs.get(r["Name"], 0.0)

    # ── Potential Status: driven by Monte Carlo probabilities ─────────────────
    # Champion if Win % > 0, Top 3 if Top 3 % > 0 (but Win % = 0), else Out
    for r in results:
        if r["Win %"] > 0:
            r["Potential Status"] = "🏆 Champion"
        elif r["Top 3 %"] > 0:
            r["Potential Status"] = "🥉 Top 3"
        else:
            r["Potential Status"] = "❌ Out"

    final_df = (
        pd.DataFrame(results)
        .sort_values("Current Score", ascending=False)
        .reset_index(drop=True)
    )
    final_df["Current Rank"] = range(1, len(final_df) + 1)
    name_opts = sorted(final_df["Name"].tolist())

    # Try to restore user from cookie (persists across sessions)
    user_name = st.session_state.get("user_name")
    if not user_name and _cookies is not None:
        cookie_user = _cookies.get("user_name", "")
        if cookie_user and cookie_user in name_opts:
            st.session_state["user_name"] = cookie_user
            st.session_state["modal_done"] = True
            user_name = cookie_user
    # Fallback: try URL query params if cookies unavailable
    if not user_name:
        try:
            q_user = st.query_params.get("user", None)
            if q_user and q_user in name_opts:
                st.session_state["user_name"] = q_user
                st.session_state["modal_done"] = True
                user_name = q_user
        except Exception:
            pass

    # ── Welcome modal — shown once until user picks a name ────────────────────
    if not st.session_state["modal_done"]:
        @st.dialog("👋 Welcome to the March Madness Pool!")
        def welcome_dialog():
            st.markdown("Select your name to personalise your experience across all tabs.")
            picked = st.selectbox("Who are you?", ["— select —"] + name_opts, key="modal_pick")
            if st.button("Let's go →", use_container_width=True, type="primary"):
                if picked != "— select —":
                    st.session_state["user_name"] = picked
                    st.session_state["modal_done"] = True
                    # Save to cookie so it's remembered on future visits
                    if _cookies is not None:
                        _cookies["user_name"] = picked
                        _cookies.save()
                    # Also persist in URL as fallback
                    try:
                        st.query_params["user"] = picked
                    except Exception:
                        pass
                    st.rerun()
                else:
                    st.warning("Please select your name first.")
        welcome_dialog()

    user_name = st.session_state.get("user_name")  # refresh after possible modal submit

    # Pre-seed selectbox session state keys so the widgets default to user_name.
    # This must happen before any st.selectbox call with these keys.
    if user_name in name_opts:
        for key in ("path", "dna", "bracket_name"):
            if key not in st.session_state or st.session_state[key] == "— select —":
                st.session_state[key] = user_name
        if "h2h_p1" not in st.session_state or st.session_state["h2h_p1"] == "— select —":
            st.session_state["h2h_p1"] = user_name

    # ─────────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────────
    st.title("🏀 March Madness Pool")
    if user_name:
        col_greet, col_switch = st.columns([6, 1])
        with col_greet:
            st.markdown(f"Welcome back, **{user_name}** 👋")
        with col_switch:
            if st.button("Switch name", key="switch_name_btn", help="Change your selected name"):
                st.session_state["user_name"] = None
                st.session_state["modal_done"] = False
                if _cookies is not None:
                    _cookies["user_name"] = ""
                    _cookies.save()
                st.rerun()
    st.caption(f"Last synced: {last_update} · Monte Carlo: 1,000 runs")

    # ── Tab deep-linking via ?tab= query param ────────────────────────────────
    TAB_SLUGS = [
        "standings", "bracket", "win-conditions", "head-to-head",
        "bracket-dna", "bracket-busters", "cinderella", "lucky-team",
    ]
    TAB_LABELS = [
        "🏆 Standings", "🗂️ Your Bracket", "🔍 Win Conditions", "⚔️ Head-to-Head",
        "🧬 Bracket DNA", "💥 Bracket Busters", "🏃 Cinderella Stories", "🍀 Lucky Team",
    ]

    # Read ?tab= param once on first load and store in session state
    if "active_tab" not in st.session_state:
        try:
            slug = st.query_params.get("tab", "standings")
        except Exception:
            slug = "standings"
        st.session_state["active_tab"] = TAB_SLUGS.index(slug) if slug in TAB_SLUGS else 0

    # st.tabs doesn't accept a default index natively, so we use a workaround:
    # render a hidden radio that holds the active index, then select the matching tab.
    _tab_index = st.session_state["active_tab"]
    tab1, tab2_bracket, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(TAB_LABELS)
    _all_tabs = [tab1, tab2_bracket, tab3, tab4, tab5, tab6, tab7, tab8]
    # Auto-expand the requested tab on first load
    if _tab_index > 0:
        with _all_tabs[_tab_index]:
            # Writing an invisible element forces Streamlit to open this tab
            st.markdown('<span style="display:none">_</span>', unsafe_allow_html=True)
        st.session_state["active_tab"] = 0  # reset so navigating away works normally

    # ── Tab 1: Standings ──────────────────────────────────────────────────────
    with tab1:
        st.subheader("Live Standings")
        col_left, col_right = st.columns([3, 2], gap="medium")

        display_cols = ["Current Rank", "Name", "Current Score",
                        "Potential Score", "Win %", "Top 3 %", "Potential Status"]
        with col_left:
            def highlight_user_row(row):
                if user_name and row["Name"] == user_name:
                    return ["background-color: #3a3000; color: #f5c518; font-weight: bold"] * len(row)
                return [""] * len(row)

            st.dataframe(
                final_df[display_cols].style
                    .apply(highlight_user_row, axis=1)
                    .background_gradient(cmap="YlOrRd", subset=["Current Score", "Potential Score"])
                    .format({"Win %": "{:.1f}%", "Top 3 %": "{:.1f}%"}),
                hide_index=True, use_container_width=True,
            )

        with col_right:
            top10 = final_df.head(10).sort_values("Current Score")
            fig = px.bar(
                top10, x="Current Score", y="Name", orientation="h",
                color="Current Score", color_continuous_scale="YlOrRd",
                title="Top 10 — Current Scores",
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False, margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ── Tab 2: Your Bracket ───────────────────────────────────────────────────
    # ── Tab 2: Your Bracket ───────────────────────────────────────────────────
    with tab2_bracket:
        st.subheader("🗂️ Your Bracket")
        import streamlit.components.v1 as components

        bracket_name = st.selectbox(
            "Select your name",
            ["— select —"] + name_opts,
            key="bracket_name",
        )

        if bracket_name == "— select —":
            st.info("Select your name above to view your bracket.")
        else:
            p_row = None
            for i in range(3, len(df_p)):
                if str(df_p.iloc[i][0]).strip() == bracket_name:
                    p_row = df_p.iloc[i]
                    break

            if p_row is None:
                st.warning("Could not find picks for this participant.")
            else:
                p_picks = [str(p_row[c]).strip() if c < len(p_row) else "" for c in range(67)]

                cur_score, _ = score_picks(p_picks, actual_winners, points_per_game, seed_map, all_alive)
                correct  = sum(1 for c in range(3, 66) if not is_unplayed(actual_winners[c]) and p_picks[c] == actual_winners[c])
                played_g = sum(1 for c in range(3, 66) if not is_unplayed(actual_winners[c]))
                m1, m2, m3 = st.columns(3)
                m1.metric("Current Score", cur_score)
                m2.metric("Correct Picks", f"{correct} / {played_g}")
                m3.metric("Accuracy", f"{correct/played_g*100:.0f}%" if played_g else "—")

                # Column → region mapping tailored to the 2025
                # PrintYourBrackets layout:
                # South:   R1 3-10,  R2 35-38, S16 51-52, E8 59
                # East:    R1 19-26, R2 43-46, S16 55-56, E8 61
                # West:    R1 11-18, R2 39-42, S16 53-54, E8 60
                # Midwest: R1 27-34, R2 47-50, S16 57-58, E8 62
                # FF: 63 (South/West side), 64 (East/Midwest side)  Champ: 65
                RCOLS = {
                    "South":   {"r1": list(range(3,11)),  "r2": list(range(35,39)), "s16":[51,52], "e8":[59]},
                    "East":    {"r1": list(range(19,27)), "r2": list(range(43,47)), "s16":[55,56], "e8":[61]},
                    "West":    {"r1": list(range(11,19)), "r2": list(range(39,43)), "s16":[53,54], "e8":[60]},
                    "Midwest": {"r1": list(range(27,35)), "r2": list(range(47,51)), "s16":[57,58], "e8":[62]},
                }

                def gs(c):
                    act = actual_winners[c] if c < len(actual_winners) else ""
                    pk  = p_picks[c] if c < len(p_picks) else ""
                    return pk, act, not is_unplayed(act)

                def trow(team, pick, actual, played, mirror=False, neutral=False):
                    if not team or team in UNPLAYED:
                        return '<div class="tr tbd"><span class="sd"></span><span class="tn">TBD</span></div>'
                    sd  = seed_map.get(team, "")
                    bust = ""
                    if not neutral:
                        if played and pick == team and team != actual:
                            bust = f'<span class="bust">&#8594;{actual}</span>'
                        if played:
                            if team == actual:
                                cls = "tr won mypick" if pick == team else "tr won"
                            elif pick == team:
                                cls = "tr lost"
                            else:
                                cls = "tr out"
                        else:
                            cls = "tr live mypick" if pick == team else "tr live"
                    else:
                        cls = "tr"
                    if mirror:
                        return f'<div class="{cls}">{bust}<span class="sd">{sd}</span><span class="tn">{team}</span></div>'
                    return f'<div class="{cls}"><span class="sd">{sd}</span><span class="tn">{team}</span>{bust}</div>'

                def build_region(name, cols, mirror=False):
                    """
                    Grid-based layout that mirrors a spreadsheet-style bracket:
                    - 8 first-round matchups per region
                    - Each R1 game occupies 3 grid rows (top team, spacer, bottom team)
                    - A spacer row sits between consecutive games
                    - R2 winners sit in the middle row of each 3-row game block
                    - Sweet 16 winners sit centered between pairs of R2 winners
                    - Elite 8 winners sit centered between pairs of Sweet 16 winners
                    This guarantees that every winner is vertically centered relative
                    to the game(s) that produced them, eliminating drift.
                    """

                    r1_cols   = cols["r1"]      # 8 slots per region
                    r2_cols   = cols["r2"]      # 4 columns (used to derive Sweet 16)
                    s16_cols  = cols["s16"]     # 2 columns (used to derive Elite 8)
                    # e8_cols not needed directly for grid; Elite 8 is derived from s16_cols

                    cells: list[str] = []

                    # Column indices within the region grid (1-based for CSS grid-column)
                    if not mirror:
                        col_r1, col_r2, col_s16, col_e8 = 1, 2, 3, 4
                    else:
                        col_r1, col_r2, col_s16, col_e8 = 4, 3, 2, 1

                    # Helper: R1 matchup HTML (two teams stacked)
                    def mu(c, team_a, team_b):
                        pk, ac, pl = gs(c)
                        return (f'<div class="matchup">'
                                f'{trow(team_a, pk, ac, pl, mirror, neutral=True)}'
                                f'<div class="mdiv"></div>'
                                f'{trow(team_b, pk, ac, pl, mirror, neutral=True)}'
                                f'</div>')

                    # Helper: single-team slot (winner/placeholder)
                    def single_from_col(c):
                        pk, ac, pl = gs(c)
                        t = ac if pl else (pk if pk not in UNPLAYED else "TBD")
                        return f'<div class="matchup single">{trow(t, pk, ac, pl, mirror)}</div>'

                    # ── 1) First Round & Round-of-32 column (R1 + "Second Round") ──
                    # We model 8 games; each game uses 4 grid rows:
                    # rows (1-based within the region):
                    #   game g (0–7):
                    #     R1 block spans rows [4g+1 .. 4g+3]   (3 rows tall)
                    #     R2 winner sits in row 4g+2
                    for g, c in enumerate(r1_cols):
                        row_start = 4 * g + 1
                        team_a, team_b = r1_matchups.get(c, ("TBD", "TBD"))

                        # First Round matchup (3-row tall block)
                        r1_html = mu(c, team_a, team_b)
                        cells.append(
                            f'<div class="cell r1" '
                            f'style="grid-column:{col_r1}; grid-row:{row_start} / span 3;">'
                            f'{r1_html}</div>'
                        )

                        # "Second Round" column = winner of that specific R1 game
                        r2_html = single_from_col(c)
                        cells.append(
                            f'<div class="cell r2" '
                            f'style="grid-column:{col_r2}; grid-row:{row_start + 1};">'
                            f'{r2_html}</div>'
                        )

                    # ── 2) Sweet 16 column: winners of the Round-of-32 games ────────
                    # 4 Sweet 16 participants per region.
                    # Each S16 participant sits centered between the two R2 rows
                    # that feed into it:
                    #   R2 rows: 4g+2  (g=0..7)
                    #   S16 rows (index h = 0..3, from R2 games 2h and 2h+1):
                    #       row_s16 = 8*h + 4
                    for h, c in enumerate(r2_cols):
                        row_s16 = 8 * h + 4
                        s16_html = single_from_col(c)
                        cells.append(
                            f'<div class="cell s16" '
                            f'style="grid-column:{col_s16}; grid-row:{row_s16};">'
                            f'{s16_html}</div>'
                        )

                    # ── 3) Elite 8 column: winners of the Sweet 16 games ───────────
                    # 2 Elite 8 participants per region.
                    # Sweet 16 rows: 8*h + 4  (h=0..3)
                    # Elite 8 rows (index e = 0..1, from S16 games 2e and 2e+1):
                    #     row_e8 = 16*e + 8
                    for e, c in enumerate(s16_cols):
                        row_e8 = 16 * e + 8
                        e8_html = single_from_col(c)
                        cells.append(
                            f'<div class="cell e8" '
                            f'style="grid-column:{col_e8}; grid-row:{row_e8};">'
                            f'{e8_html}</div>'
                        )

                    inner = "".join(cells)
                    return (
                        f'<div class="region">'
                        f'<div class="rgn-name">{name}</div>'
                        f'<div class="region-body grid-region">{inner}</div>'
                        f'</div>'
                    )

                def build_finals():
                    # Final Four participants: winners of the Elite 8 games
                    # (one per region) → 4 total teams.
                    def team_from_col(c):
                        pk, ac, pl = gs(c)
                        if pl and not is_unplayed(ac):
                            t = ac
                        else:
                            t = "TBD"
                        return t, pk, ac, pl

                    # Left side Final Four: South + West regional winners
                    ff_left_cols  = RCOLS["South"]["e8"] + RCOLS["West"]["e8"]
                    # Right side Final Four: East + Midwest regional winners
                    ff_right_cols = RCOLS["East"]["e8"] + RCOLS["Midwest"]["e8"]

                    left_ff  = []
                    for c in ff_left_cols:
                        t, pk, ac, pl = team_from_col(c)
                        left_ff.append(f'<div class="matchup single">{trow(t, pk, ac, pl)}</div>')

                    right_ff = []
                    for c in ff_right_cols:
                        t, pk, ac, pl = team_from_col(c)
                        right_ff.append(f'<div class="matchup single">{trow(t, pk, ac, pl, mirror=True)}</div>')

                    # Championship participants: winners of the two Final Four games
                    # (columns 63 and 64) → 2 total teams.
                    pk_l, ac_l, pl_l = gs(63)
                    pk_r, ac_r, pl_r = gs(64)
                    tl = ac_l if pl_l else (pk_l if pk_l not in UNPLAYED else "TBD")
                    tr = ac_r if pl_r else (pk_r if pk_r not in UNPLAYED else "TBD")

                    ch_left  = f'<div class="matchup single champ-mu">{trow(tl, pk_l, ac_l, pl_l)}</div>'
                    ch_right = f'<div class="matchup single champ-mu">{trow(tr, pk_r, ac_r, pl_r, mirror=True)}</div>'

                    fl = (f'<div class="ff-wrap">'
                          f'<div class="rlbl ff-lbl">Final Four</div>'
                          f'{"".join(left_ff)}'
                          f'</div>')
                    fr = (f'<div class="ff-wrap">'
                          f'<div class="rlbl ff-lbl">Final Four</div>'
                          f'{"".join(right_ff)}'
                          f'</div>')
                    ch = (f'<div class="champ-wrap">'
                          f'<div class="trophy-lbl">&#127942; Championship</div>'
                          f'{ch_left}{ch_right}'
                          f'</div>')
                    return f'<div class="finals">{fl}{ch}{fr}</div>'

                # Place South/West on the left (top/bottom) flowing left → center,
                # and East/Midwest on the right flowing right → center to match
                # the 2025 bracket layout from printyourbrackets.com.
                south_h   = build_region("SOUTH",   RCOLS["South"])
                west_h    = build_region("WEST",    RCOLS["West"])
                east_h    = build_region("EAST",    RCOLS["East"],    mirror=True)
                midwest_h = build_region("MIDWEST", RCOLS["Midwest"], mirror=True)
                finals_h  = build_finals()

                HTML = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:#0d0f14;color:#9ca3af;font-family:'Segoe UI',Arial,sans-serif;font-size:11px;padding:8px;}}
.bracket{{display:flex;flex-direction:row;align-items:stretch;justify-content:center;min-width:980px;}}
.left-side,.right-side{{display:flex;flex-direction:column;flex:0 0 auto;}}
.finals{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:0 8px;width:140px;flex-shrink:0;}}
.region{{display:flex;flex-direction:column;flex:1;}}
.rgn-name{{font-size:9px;font-weight:800;letter-spacing:1.5px;color:#374151;text-align:center;padding:1px 0 1px;text-transform:uppercase;border-bottom:1px solid #1a1f2b;margin-bottom:1px;}}
.region-body.grid-region{{display:grid;grid-template-rows:repeat(8,18px 18px 18px 2px);grid-template-columns:118px 106px 98px 90px;column-gap:10px;flex:1;}}
.right-side .region-body.grid-region{{grid-template-columns:90px 98px 106px 118px;}}
.cell .matchup{{height:100%;display:flex;flex-direction:column;justify-content:flex-start;}}
.cell .matchup.single{{justify-content:center;}}
.rlbl{{font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#374151;text-align:center;padding-bottom:3px;}}
.ff-lbl{{color:#4b5563;font-size:9px;}}
.matchup{{position:relative;}}
.matchup.single{{display:flex;align-items:center;}}
.mdiv{{height:1px;background:#1a1f2b;}}
.tr{{display:flex;align-items:center;gap:2px;padding:1px 3px;height:16px;
  border:1px solid #1a1f2b;overflow:hidden;background:#0d0f14;}}
.tr+.tr{{border-top:none;}}
.sd{{font-size:11px;color:#374151;min-width:11px;text-align:right;flex-shrink:0;}}
.tn{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#e5e7eb;font-size:13px;}}
.bust{{font-size:8px;color:#f87171;flex-shrink:0;margin-left:1px;white-space:nowrap;}}
.tbd .tn{{color:#1f2937;font-style:italic;}}
.won{{background:#052e16 !important;border-color:#14532d !important;}}
.won .tn{{color:#86efac;}}
.mypick{{background:#14532d !important;border-color:#16a34a !important;}}
.mypick .tn{{color:#4ade80 !important;font-weight:700;}}
.lost{{background:#2d0a0a !important;border-color:#7f1d1d !important;}}
.lost .tn{{text-decoration:line-through;color:#ef4444;}}
.out .tn{{color:#1e2432;}}
.live .tn{{color:#9ca3af;}}
.live.mypick{{background:#172035 !important;border-color:#1d4ed8 !important;}}
.live.mypick .tn{{color:#93c5fd !important;font-weight:700;}}

/* ── CONNECTOR LINES ──
   Right-border on each .tr acts as vertical spine.
   ::after pseudo on .matchup draws horizontal stub to next round.
   .mdiv right-border bridges the gap between top and bottom rows.
*/
.conn-l .matchup:not(.single){{padding-right:9px;}}
.conn-l .matchup:not(.single) .tr{{border-right:1px solid #334155 !important;}}
.conn-l .matchup:not(.single) .mdiv{{border-right:1px solid #334155;margin-right:9px;height:1px;}}
.conn-l .matchup:not(.single)::after{{content:'';position:absolute;right:0;top:50%;width:9px;height:1px;background:#334155;}}

.conn-r .matchup:not(.single){{padding-left:9px;}}
.conn-r .matchup:not(.single) .tr{{border-left:1px solid #334155 !important;}}
.conn-r .matchup:not(.single) .mdiv{{border-left:1px solid #334155;margin-left:9px;height:1px;}}
.conn-r .matchup:not(.single)::before{{content:'';position:absolute;left:0;top:50%;width:9px;height:1px;background:#334155;}}

.ff-wrap{{width:130px;border:1px solid #1a1f2b;border-radius:3px;overflow:hidden;}}
.champ-wrap{{width:130px;border:2px solid #92400e;border-radius:5px;overflow:hidden;box-shadow:0 0 16px rgba(251,191,36,.18);}}
.trophy-lbl{{font-size:9px;font-weight:800;text-align:center;padding:3px;background:#422006;color:#fbbf24;border-bottom:1px solid #92400e;}}
.champ-mu .tr{{background:#1c0f00 !important;border-color:#92400e !important;}}
.champ-mu .tr .tn,.champ-mu .won .tn,.champ-mu .live .tn{{color:#fbbf24 !important;font-weight:800;font-size:12px;}}
.champ-mu .mypick{{background:#78350f !important;}}
.champ-mu .mypick .tn{{color:#fde68a !important;}}
.legend{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;font-size:10px;color:#6b7280;align-items:center;}}
.leg{{display:flex;align-items:center;gap:4px;}}
.ld{{width:10px;height:10px;border-radius:2px;flex-shrink:0;}}
</style></head><body>
<div class="legend">
  <div class="leg"><div class="ld" style="background:#14532d;border:1px solid #16a34a"></div><span style="color:#4ade80">Your correct pick</span></div>
  <div class="leg"><div class="ld" style="background:#052e16;border:1px solid #14532d"></div><span style="color:#86efac">Correct (not yours)</span></div>
  <div class="leg"><div class="ld" style="background:#2d0a0a;border:1px solid #7f1d1d"></div><span style="color:#ef4444">Your wrong pick</span></div>
  <div class="leg"><div class="ld" style="background:#172035;border:1px solid #1d4ed8"></div><span style="color:#93c5fd">Your future pick</span></div>
  <div class="leg"><div class="ld" style="background:#0a0c10;border:1px solid #1a1f2b"></div><span>Eliminated</span></div>
</div>
<div class="bracket">
  <div class="left-side">{south_h}{west_h}</div>
  {finals_h}
  <div class="right-side">{east_h}{midwest_h}</div>
</div>
</body></html>"""

                components.html(HTML, height=900, scrolling=False)

    # ── Tab 2: Win Conditions ─────────────────────────────────────────────────
    with tab3:
        st.subheader("Your Path to the Money")
        p_select = st.selectbox(
            "Select your name",
            ["— select —"] + name_opts,
            key="path",
        )
        if p_select != "— select —":
            p_data = final_df[final_df["Name"] == p_select].iloc[0]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Current Rank",   f"#{p_data['Current Rank']}")
            c2.metric("Current Score",  p_data["Current Score"])
            c3.metric("Max Potential",  p_data["Potential Score"])
            c4.metric("Win Probability", f"{p_data['Win %']:.1f}%")

            st.markdown("---")
            st.markdown("#### ⚔️ Swing Games vs. Your Closest Rivals")

            # 3 most similar rivals
            similarity = []
            for _, other in final_df.iterrows():
                if other["Name"] == p_select:
                    continue
                matches = sum(1 for c in range(3, 66)
                              if p_data["raw_picks"][c] == other["raw_picks"][c])
                similarity.append({"Name": other["Name"], "Matches": matches,
                                   "raw_picks": other["raw_picks"]})

            top3 = sorted(similarity, key=lambda x: x["Matches"], reverse=True)[:3]
            sim_names = [s["Name"] for s in top3]
            st.info(f"Your closest rivals: **{', '.join(sim_names)}**")

            swings = []
            for c in range(3, 66):
                if not is_unplayed(actual_winners[c]):
                    continue
                my_pick = p_data["raw_picks"][c]
                if my_pick not in all_alive:
                    continue
                rival_picks = [s["raw_picks"][c] for s in top3]
                if any(my_pick != rp for rp in rival_picks):
                    val = points_per_game[c] + seed_map.get(my_pick, 0)
                    row = {
                        "Round":    get_round_name(c),
                        "My Pick":  my_pick,
                        "Pts":      val,
                    }
                    for k, s in enumerate(top3):
                        row[s["Name"]] = rival_picks[k]
                    swings.append(row)

            if swings:
                swing_df = pd.DataFrame(swings).sort_values("Pts", ascending=False)
                st.dataframe(swing_df, hide_index=True, use_container_width=True)
            else:
                st.success("No divergent unplayed games vs. your closest rivals.")

    # ── Tab 3: Head-to-Head ───────────────────────────────────────────────────
    with tab4:
        st.subheader("⚔️ Head-to-Head Comparison")
        col_a, col_b = st.columns(2)
        with col_a:
            p1_name = st.selectbox(
                "Player 1",
                ["— select —"] + name_opts,
                key="h2h_p1",
            )
        with col_b:
            p2_name = st.selectbox("Player 2", ["— select —"] + name_opts, key="h2h_p2")

        if p1_name != "— select —" and p2_name != "— select —" and p1_name != p2_name:
            p1 = final_df[final_df["Name"] == p1_name].iloc[0].to_dict()
            p2 = final_df[final_df["Name"] == p2_name].iloc[0].to_dict()

            h2h = head_to_head(p1, p2, actual_winners, points_per_game, seed_map)

            # Score comparison
            m1, m2, m3 = st.columns(3)
            m1.metric(f"🔵 {p1_name}", p1["Current Score"],
                      delta=f"{p1['Current Score'] - p2['Current Score']:+d} pts vs rival")
            m2.metric("Shared Points (same pick, both correct)", h2h["shared_pts"])
            m3.metric(f"🔴 {p2_name}", p2["Current Score"],
                      delta=f"{p2['Current Score'] - p1['Current Score']:+d} pts vs rival")

            # Win probability gauge
            fig = go.Figure(go.Bar(
                x=[p1_name, p2_name],
                y=[p1["Win %"], p2["Win %"]],
                marker_color=["#4fc3f7", "#ff6b6b"],
                text=[f"{p1['Win %']:.1f}%", f"{p2['Win %']:.1f}%"],
                textposition="outside",
            ))
            fig.update_layout(
                title="Win Probability (Monte Carlo)",
                yaxis_title="Win %", yaxis_range=[0, max(p1["Win %"], p2["Win %"]) * 1.4 + 5],
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### 🔀 Where Your Brackets Split")
            diverge_df = pd.DataFrame(h2h["divergences"])
            if not diverge_df.empty:
                future = diverge_df[diverge_df["Played"] == False]  # noqa: E712
                past   = diverge_df[diverge_df["Played"] == True]   # noqa: E712

                if not future.empty:
                    st.markdown("**Upcoming Divergences** — where the battle will be decided")
                    show_cols = ["Round", p1_name, p2_name, "Pts"]
                    st.dataframe(future[show_cols].reset_index(drop=True),
                                 hide_index=True, use_container_width=True)

                if not past.empty:
                    st.markdown("**Past Divergences**")
                    show_cols = ["Round", p1_name, "P1 Got It", p2_name, "P2 Got It", "Winner"]
                    st.dataframe(past[show_cols].reset_index(drop=True),
                                 hide_index=True, use_container_width=True)
            else:
                st.info("These two have identical brackets!")

        elif p1_name == p2_name and p1_name != "— select —":
            st.warning("Please select two different players.")

    # ── Tab 4: Bracket DNA ────────────────────────────────────────────────────
    with tab5:
        st.subheader("🧬 Bracket DNA & Probability")
        dna_select = st.selectbox(
            "Select your name",
            ["— select —"] + name_opts,
            key="dna",
        )
        if dna_select != "— select —":
            u = final_df[final_df["Name"] == dna_select].iloc[0]

            pr1, pr2, pr3, pr4, pr5 = st.columns(5)
            pr1.metric("Current Rank",  f"#{u['Current Rank']}")
            pr2.metric("Win Chance",    f"{u['Win %']:.1f}%")
            pr3.metric("Top 3 Chance",  f"{u['Top 3 %']:.1f}%")
            pr4.metric("Potential",     u["Potential Status"])
            pr5.metric("Upset Correct", u["Upsets"])

            st.markdown("---")
            c1, c2, c3 = st.columns(3)

            twins = sorted(
                [{"Name": r["Name"],
                  "Matches": sum(1 for c in range(3, 66)
                                 if u["raw_picks"][c] == r["raw_picks"][c])}
                 for _, r in final_df.iterrows() if r["Name"] != dna_select],
                key=lambda x: x["Matches"], reverse=True,
            )
            if twins:
                c1.metric("Bracket Twin", twins[0]["Name"],
                          f"{twins[0]['Matches']} shared picks")

            all_p = [{"T": u["raw_picks"][c],
                      "C": global_pick_counts.get(u["raw_picks"][c], 0)}
                     for c in range(3, 66) if u["raw_picks"][c] in all_starting]
            if all_p:
                rarest = sorted(all_p, key=lambda x: x["C"])[0]
                c2.metric("Rarest Pick", rarest["T"],
                          f"Only {rarest['C']} others picked")

            correct = [{"T": u["raw_picks"][c],
                        "C": global_pick_counts.get(u["raw_picks"][c], 0)}
                       for c in range(3, 66)
                       if u["raw_picks"][c] == actual_winners[c]]
            if correct:
                rare_correct = sorted(correct, key=lambda x: x["C"])[0]
                c3.metric("Rarest Correct Pick", rare_correct["T"],
                          f"{rare_correct['C']} users had it")

            # Popularity of remaining alive picks
            alive_picks = [
                {"Team": u["raw_picks"][c], "Round": get_round_name(c),
                 "Pool %": round(global_pick_counts.get(u["raw_picks"][c], 0) / max(len(results), 1) * 100, 1)}
                for c in range(3, 66)
                if u["raw_picks"][c] in all_alive and is_unplayed(actual_winners[c])
            ]
            if alive_picks:
                st.markdown("#### Your Remaining Live Picks vs. Pool Popularity")
                ap_df = (
                    pd.DataFrame(alive_picks)
                    .drop_duplicates("Team")
                    .sort_values("Pool %")
                )
                fig = px.bar(
                    ap_df, x="Pool %", y="Team", orientation="h",
                    color="Pool %", color_continuous_scale="Blues",
                    title="How contrarian are your remaining picks?",
                )
                fig.update_layout(
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=40, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Tab 5: Bracket Busters ────────────────────────────────────────────────
    with tab6:
        st.subheader("💥 Bracket Busters — Games That Wrecked the Pool")
        busters_df = compute_bracket_busters(results, actual_winners, points_per_game, seed_map)

        if busters_df.empty:
            st.info("No completed upsets yet — check back once games are played.")
        else:
            # Summary metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Busting Games", len(busters_df))
            m2.metric("Biggest Carnage",
                      busters_df.iloc[0]["Winner"] + " " + busters_df.iloc[0]["Upset Seed"],
                      f"{busters_df.iloc[0]['Busted Picks']} picks busted")
            m3.metric("Total Pool Pts Lost",
                      f"{busters_df['Total Pts Lost'].sum():,}")

            st.dataframe(busters_df, hide_index=True, use_container_width=True)

            fig = px.bar(
                busters_df.head(10), x="Winner", y="Busted Picks",
                color="Total Pts Lost", color_continuous_scale="Reds",
                title="Top 10 Pool Killers by Picks Busted",
                labels={"Winner": "Winning Team", "Busted Picks": "# Picks Busted"},
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig, use_container_width=True)

            # Per-participant carnage
            st.markdown("#### 🩸 Damage Report — Who's Been Hurt the Most?")
            carnage = []
            for r in results:
                lost = sum(
                    (points_per_game[c] + seed_map.get(r["raw_picks"][c], 0))
                    for c in range(3, 66)
                    if not is_unplayed(actual_winners[c])
                    and r["raw_picks"][c] != actual_winners[c]
                    and r["raw_picks"][c] not in {"nan", ""}
                )
                still_live = sum(
                    1 for c in range(3, 66)
                    if r["raw_picks"][c] in all_alive and is_unplayed(actual_winners[c])
                )
                carnage.append({
                    "Name": r["Name"],
                    "Points Left on Table": lost,
                    "Still-Live Picks": still_live,
                    "Current Rank": r.get("Current Rank", "?"),
                })
            carnage_df = pd.DataFrame(carnage).sort_values("Points Left on Table", ascending=False)

            # Dramatic callout for the biggest victim
            top_victim = carnage_df.iloc[0]
            victim_name_hl = (
                f'<span style="color:#f5c518; font-weight:700;">{top_victim["Name"]}</span>'
                if top_victim["Name"] == user_name else f'**{top_victim["Name"]}**'
            )
            st.markdown(
                f"> ☠️ {victim_name_hl} has hemorrhaged the most points — "
                f"**{top_victim['Points Left on Table']} pts** vanished due to upsets. "
                f"Still has **{top_victim['Still-Live Picks']}** picks alive though. The comeback arc isn't dead.",
                unsafe_allow_html=True,
            )

            st.dataframe(
                carnage_df.head(20).style.apply(
                    lambda row: (
                        ["background-color: #3a3000; color: #f5c518; font-weight: bold"] * len(row)
                        if user_name and row["Name"] == user_name else [""] * len(row)
                    ),
                    axis=1,
                ),
                hide_index=True, use_container_width=True,
            )

    # ── Tab 6: Cinderella Stories ─────────────────────────────────────────────
    with tab7:
        st.subheader("🏃 Cinderella Stories — Upset Heroes")
        stories = build_cinderella_stories(results, actual_winners, seed_map, points_per_game, global_pick_counts)

        if not stories:
            st.info("No upset correct picks yet. Check back once some underdogs pull through.")
        else:
            # Quick leaderboard: one row per upset event
            st.markdown("#### 🏅 Upset Leaderboard")
            upset_lb = pd.DataFrame([{
                "Team":        f"#{s['seed']} {s['team']}",
                "Round":       s["round"],
                "Pts Value":   s["points"],
                "Believers":   s["n_believers"],
                "Pool %":      f"{s['surv_pct']}%",
                "Who Called It": s["believers_str"],
            } for s in stories])
            st.dataframe(upset_lb, hide_index=True, use_container_width=True)

            st.markdown("---")
            st.markdown("#### 📖 The Stories")

            for s in stories:
                seed_badge = s["seed"]
                color = ("#ff4444" if seed_badge >= 13 else
                         "#ff6b6b" if seed_badge >= 12 else
                         "#ff9f43" if seed_badge >= 10 else
                         "#ffb547" if seed_badge >= 8  else "#4fc3f7")

                with st.container():
                    col_l, col_r = st.columns([3, 1])
                    with col_l:
                        st.markdown(f"### {s['mood']} — #{s['seed']} {s['team']}")
                        st.markdown(f"> _{s['quip']}_", unsafe_allow_html=True)
                        n = s["n_believers"]
                        label = "The lone believer" if n == 1 else f"The {n} believers"
                        believers_hl = ", ".join(
                            f'<span style="color:#f5c518; font-weight:700;">{nm}</span>'
                            if nm == user_name else nm
                            for nm in s["names"]
                        )
                        st.markdown(f"**{label}:** {believers_hl}", unsafe_allow_html=True)
                        st.caption(f"{s['round']} · {s['points']} pts per correct pick")
                    with col_r:
                        st.markdown(
                            f"<div style='text-align:center; padding:20px 12px; "
                            f"background:{color}18; border:2px solid {color}; "
                            f"border-radius:14px; margin-top:8px;'>"
                            f"<div style='font-size:44px; font-weight:900; color:{color}; line-height:1;'>#{seed_badge}</div>"
                            f"<div style='font-size:12px; color:#bbb; margin-top:6px; font-weight:600;'>{s['team']}</div>"
                            f"<div style='font-size:11px; color:#888; margin-top:4px;'>{s['round']}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    st.divider()

    # ── Tab 7: Lucky Team ─────────────────────────────────────────────────────
    with tab8:
        st.subheader("🍀 Lucky Team — Still in the Hunt")

        if not lucky_map:
            st.info("No Lucky Team data found. Make sure the 'LuckyTeam' sheet exists and is accessible.")
        else:
            # ── Temporary debug panel ────────────────────────────────────────
            with st.expander("🔧 Debug info (share with admin)", expanded=False):
                st.write(f"**teams in lucky_map:** {len(lucky_map)}")
                st.write(f"**teams in all_starting:** {len(all_starting)}")
                st.write(f"**teams in truly_alive:** {len(truly_alive)}")
                unmatched = [t for t in lucky_map if t not in all_starting]
                st.write(f"**Lucky Team names NOT found in MasterBracket ({len(unmatched)}):**")
                st.write(unmatched if unmatched else "none — all matched ✅")
                sample_master = sorted(list(all_starting))[:10]
                st.write(f"**Sample MasterBracket team names:** {sample_master}")
                sample_lucky = sorted(list(lucky_map.keys()))[:10]
                st.write(f"**Sample LuckyTeam team names:** {sample_lucky}")
            # ─────────────────────────────────────────────────────────────────

            champ = actual_winners[65] if len(actual_winners) > 65 and not is_unplayed(actual_winners[65]) else None

            # Build one row per (team, participant) pair
            rows = []
            for team, participants in lucky_map.items():
                if champ and team == champ:
                    status = "🏆 Champion"
                elif team in truly_alive:
                    status = "✅ Still Alive"
                else:
                    status = "❌ Eliminated"
                for participant in participants:
                    rows.append({
                        "Status":      status,
                        "Team":        team,
                        "Seed":        f"#{seed_map.get(team, '?')}",
                        "Participant": participant,
                    })

            # Sort: Champion → Alive → Eliminated, then by seed within each group
            status_order = {"🏆 Champion": 0, "✅ Still Alive": 1, "❌ Eliminated": 2}
            rows.sort(key=lambda r: (status_order[r["Status"]], seed_map.get(r["Team"], 99)))

            # Summary metrics
            alive_teams = {r["Team"] for r in rows if r["Status"] in {"✅ Still Alive", "🏆 Champion"}}
            elim_teams  = {r["Team"] for r in rows if r["Status"] == "❌ Eliminated"}
            m1, m2, m3 = st.columns(3)
            m1.metric("Teams Still Alive", len(alive_teams))
            m2.metric("Teams Eliminated",  len(elim_teams))
            m3.metric("Total Teams",       len(lucky_map))

            if champ:
                champ_participants = lucky_map.get(champ, [])
                champ_hl = ", ".join(
                    f'<span style="color:#f5c518; font-weight:700;">{p}</span>'
                    if p == user_name else f"**{p}**"
                    for p in champ_participants
                )
                st.markdown(
                    f"🏆 **{champ}** won the Championship — Lucky Team Winner(s): {champ_hl}!",
                    unsafe_allow_html=True,
                )

            st.markdown("---")

            alive_rows = [r for r in rows if r["Status"] in {"🏆 Champion", "✅ Still Alive"}]
            elim_rows  = [r for r in rows if r["Status"] == "❌ Eliminated"]

            if alive_rows:
                st.markdown("#### 🟢 Teams Still Alive")
                # Group by team so multi-participant teams render as one card
                seen_teams: dict[str, list[str]] = {}
                for r in alive_rows:
                    seen_teams.setdefault(r["Team"], []).append(r["Participant"])

                cols = st.columns(3)
                for i, (team, participants) in enumerate(seen_teams.items()):
                    with cols[i % 3]:
                        is_user      = user_name in participants
                        border_color = "#f5c518" if is_user else "#2ecc71"
                        bg_color     = "#3a3000" if is_user else "#0e2a1a"
                        participants_html = "<br>".join(
                            f'<span style="color:#f5c518; font-weight:700;">{p}</span>'
                            if p == user_name else
                            f'<span style="color:#e8eaf0; font-weight:600;">{p}</span>'
                            for p in participants
                        )
                        st.markdown(
                            f"<div style='border:2px solid {border_color}; background:{bg_color}; "
                            f"border-radius:10px; padding:14px 16px; margin-bottom:12px;'>"
                            f"<div style='font-size:18px; font-weight:800; color:{border_color};'>"
                            f"#{seed_map.get(team, '?')} {team}</div>"
                            f"<div style='font-size:13px; margin-top:6px;'>{participants_html}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

            if elim_rows:
                # Group eliminated by team too
                elim_by_team: dict[str, list[str]] = {}
                for r in elim_rows:
                    elim_by_team.setdefault(r["Team"], []).append(r["Participant"])
                elim_display = [
                    {"Seed": f"#{seed_map.get(t, '?')}", "Team": t, "Participant(s)": ", ".join(ps)}
                    for t, ps in elim_by_team.items()
                ]
                with st.expander(f"❌ Eliminated Teams ({len(elim_by_team)})", expanded=False):
                    elim_df = pd.DataFrame(elim_display)
                    st.dataframe(
                        elim_df.style.apply(
                            lambda row: (
                                ["background-color: #3a3000; color: #f5c518; font-weight: bold"] * len(row)
                                if user_name and user_name in row["Participant(s)"] else
                                ["color: #6b7280"] * len(row)
                            ),
                            axis=1,
                        ),
                        hide_index=True, use_container_width=True,
                    )

    st.markdown("---")
    st.caption(f"🕒 Last sync: {last_update} · 🔄 Monte Carlo: 1,000 runs · Built with Streamlit")

except Exception as e:
    st.error(f"Something went wrong: {e}")
    st.exception(e)
