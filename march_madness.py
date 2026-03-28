import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import random

# Disable touch zoom/pan on all charts so mobile users can scroll the page normally
PLOTLY_CONFIG = {
    "scrollZoom": False,
    "displayModeBar": False,
    "doubleClick": False,
    "staticPlot": True,
}

try:
    from streamlit_cookies_manager import EncryptedCookieManager
    _cookies_available = True
except ImportError:
    _cookies_available = False

st.set_page_config(
    page_title="March Madness Pool",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ─── Mobile-friendly CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Base container ── */
  .block-container {
    padding: 0.75rem 0.75rem 2rem !important;
    max-width: 100% !important;
  }

  /* ── Hide Streamlit toolbar buttons (Fork, Star, etc.) ── */
  div[data-testid="stToolbar"] { display: none !important; }
  .stDeployButton { display: none !important; }
  button[kind="header"] { display: none !important; }
  #MainMenu { display: none !important; }
  header[data-testid="stHeader"] { display: none !important; }
  footer { display: none !important; }

  /* ── Tab bar: scrollable row, smaller text on mobile ── */
  div[data-testid="stTabs"] > div:first-child {
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  div[data-testid="stTabs"] > div:first-child::-webkit-scrollbar { display: none; }
  button[data-baseweb="tab"] {
    font-size: 13px !important;
    white-space: nowrap !important;
    padding: 6px 10px !important;
  }

  /* ── Metric cards ── */
  div[data-testid="metric-container"] {
    background: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 10px;
    padding: 8px 10px;
  }
  div[data-testid="metric-container"] label {
    font-size: 11px !important;
  }
  div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 18px !important;
  }

  /* ── Columns: only stack when truly needed (very narrow screens) ── */
  @media (max-width: 400px) {
    div[data-testid="column"] {
      min-width: 100% !important;
      width: 100% !important;
    }
  }

  /* ── DataFrames ── */
  .stDataFrame { font-size: 13px; }

  /* ── Plotly charts: block touch interactions so page scrolls normally ── */
  .js-plotly-plot .plotly,
  .js-plotly-plot .plotly svg {
    touch-action: pan-y !important;
    pointer-events: none !important;
  }

  /* ── Bracket iframe: horizontal scroll ── */
  div[data-testid="stIFrame"] {
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch !important;
    width: 100% !important;
  }
  div[data-testid="stIFrame"] iframe {
    min-width: 980px !important;
    max-width: none !important;
    width: 980px !important;
  }

  /* ── Selectboxes full width ── */
  div[data-testid="stSelectbox"] { width: 100% !important; }

  /* ── Prevent on-screen keyboard from appearing on selectbox tap ── */
  div[data-testid="stSelectbox"] input,
  div[data-baseweb="select"] input,
  div[data-testid="stDialog"] input,
  div[role="dialog"] input,
  div[data-testid="stModal"] input {
    caret-color: transparent !important;
    pointer-events: none !important;
    user-select: none !important;
    -webkit-user-select: none !important;
    readonly: readonly;
  }

  /* ── Expanders ── */
  details summary { font-size: 14px; }
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
    if 3 <= col_idx <= 34:   return "R64"
    if 35 <= col_idx <= 50:  return "R32"
    if 51 <= col_idx <= 58:  return "S16"
    if 59 <= col_idx <= 62:  return "E8"
    if 63 <= col_idx <= 64:  return "F4"
    if col_idx == 65:        return "Champ"
    return "Unknown"


UNPLAYED_RAW = {"nan", "0", "", "none", "winner", "tbd", "n/a", "-", "–"}


def is_unplayed(val: str) -> bool:
    return str(val).strip().lower() in UNPLAYED_RAW


# Keep UNPLAYED as a set for the few places that do direct membership checks
UNPLAYED = {"nan", "0", "", "None", "Winner", "TBD", "N/A", "-", "–"}

# ─── 2. DATA LOADING ──────────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_all_data():
    master_url = get_csv_url(SHEET_URL, "MasterBracket")
    picks_url  = get_csv_url(SHEET_URL, "Picks")
    teams_url  = get_csv_url(SHEET_URL, "Teams")
    if not master_url or not picks_url:
        return None

    lucky_url       = get_csv_url(SHEET_URL, "LuckyTeam")
    tiebreaker_url  = get_csv_url(SHEET_URL, "TiebreakerScores")

    df_seeds = pd.read_csv(master_url, header=None)
    seed_map: dict[str, int] = {}
    all_starting: set[str] = set()
    team_to_region: dict[str, str] = {}
    skip = {"West","East","South","Midwest","Region","Team","Seed","nan"}

    # MasterBracket layout (0-indexed rows/cols):
    # West:    rows 3-33,  team col B(1),  seed col A(0)
    # South:   rows 3-33,  team col N(13), seed col O(14)
    # East:    rows 36-65, team col B(1),  seed col A(0)   — row 35 is a label row
    # Midwest: rows 36-65, team col N(13), seed col O(14)  — row 35 is a label row
    region_specs = [
        ("West",    3, 33,  1,  0),
        ("South",   3, 33,  13, 14),
        ("East",    36, 65, 1,  0),
        ("Midwest", 36, 65, 13, 14),
    ]
    for region, row_start, row_end, team_col, seed_col in region_specs:
        for row_idx in range(row_start, min(row_end + 1, len(df_seeds))):
            row = df_seeds.iloc[row_idx]
            team_raw = str(row[team_col]).strip() if team_col < len(row) else ""
            seed = safe_int(row[seed_col]) if seed_col < len(row) else 0
            if team_raw and team_raw not in skip and seed > 0:
                seed_map[team_raw] = seed
                all_starting.add(team_raw)
                team_to_region[team_raw] = region

    # Build r1_matchups: maps each R1 col → (team_top, team_bot)
    # The Picks sheet row 0 contains the pre-tournament teams for every slot.
    # R1 cols 3–34: each cell has the original team seeded into that game slot.
    # Standard bracket: each game has a top-seed and bottom-seed participant.
    # We read the original teams from df_p row 0 (the seeding row).
    # We'll populate this after loading df_p below.

    df_p = pd.read_csv(picks_url, header=None)

    # Normalize team name abbreviations used in the sheet
    TEAM_ABBREVS = {
        "MICHST":  "Michigan St.",
        "SFLA":    "South Florida",
        "MIAOH":   "Miami (Ohio)",
        "PVAM":    "Prairie View",
        "KENSAW":  "Kennesaw St.",
        "MARYCA":  "Saint Mary's",
    }
    df_p = df_p.replace(TEAM_ABBREVS)

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

    # Build r1_matchups from TeamsKey sheet.
    # Layout: col A=Seed, col B=Team, col D=Region, one team per row, blank rows between.
    # Teams appear in bracket order: 1,16,8,9,5,12,4,13,6,11,3,14,7,10,2,15 per region.
    # Each consecutive pair within a region = one R1 matchup.
    # Regions appear in order: West, East, South, Midwest → pick cols 3-10, 11-18, 19-26, 27-34.
    r1_matchups: dict[int, tuple] = {}
    try:
        teams_key_url = get_csv_url(SHEET_URL, "TeamsKey")
        df_tk = pd.read_csv(teams_key_url, header=None)
        # Collect (seed, team, region) in sheet order, skipping blank rows
        # Also register seeds into seed_map so bracket display works regardless of name spelling
        tk_teams = []
        for i in range(len(df_tk)):
            seed_val   = str(df_tk.iloc[i, 0]).strip()
            team_val   = str(df_tk.iloc[i, 1]).strip()
            region_val = str(df_tk.iloc[i, 3]).strip() if df_tk.shape[1] > 3 else ""
            if (seed_val not in ("", "nan", "Seed") and
                team_val not in ("", "nan", "Team") and
                region_val not in ("", "nan", "Region")):
                try:
                    sd = int(float(seed_val))
                except ValueError:
                    sd = 0
                # Register this team/seed into seed_map and all_starting
                # so the bracket can always look up the seed number
                if sd > 0 and team_val not in seed_map:
                    seed_map[team_val] = sd
                    all_starting.add(team_val)
                tk_teams.append((team_val, region_val))
        # Group into regions in order of appearance
        region_order = []
        region_teams: dict[str, list] = {}
        for team, region in tk_teams:
            if region not in region_teams:
                region_order.append(region)
                region_teams[region] = []
            region_teams[region].append(team)
        # Map region order to pick col ranges
        pick_col_ranges = [range(3,11), range(11,19), range(19,27), range(27,35)]
        for reg, col_range in zip(region_order, pick_col_ranges):
            teams_in_region = region_teams[reg]
            # Pair consecutive teams: [0,1], [2,3], [4,5], ...
            for game_idx, i in enumerate(range(0, len(teams_in_region) - 1, 2)):
                if game_idx >= len(col_range):
                    break
                r1_matchups[col_range[game_idx]] = (teams_in_region[i], teams_in_region[i + 1])
    except Exception:
        pass  # fall through to picks-based fallback below

    # Fill any still-missing slots from participant picks (fallback)
    r1_picks_block = df_p.iloc[3:, 3:35].astype(str)
    for col in range(3, 35):
        if r1_matchups.get(col) in (None, ("TBD", "TBD")):
            candidates: set[str] = set()
            if col < len(winners_row) and not is_unplayed(winners_row[col]):
                t = winners_row[col].strip()
                if t in all_starting:
                    candidates.add(t)
            for t in r1_picks_block.iloc[:, col - 3].unique():
                t = t.strip()
                if t and t not in ("nan", "") and t in all_starting:
                    candidates.add(t)
            teams_list = sorted(candidates, key=lambda t: seed_map.get(t, 99))
            if len(teams_list) >= 2:
                r1_matchups[col] = (teams_list[0], teams_list[1])
            elif len(teams_list) == 1:
                r1_matchups[col] = (teams_list[0], "TBD")
            else:
                r1_matchups[col] = ("TBD", "TBD")

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

    # Slot → team mapping for R1 (to know if a specific team's game has been played)
    r1_team_to_slot: dict[str, int] = {}
    for col, (ta, tb) in r1_matchups.items():
        r1_team_to_slot[ta] = col
        r1_team_to_slot[tb] = col

    # Build a mapping from team → their slot in each round (for specific game lookup)
    # For rounds beyond R1, we derive which slot a team would play in from the winners_row
    def _team_next_slot(team, next_round_idx):
        """Find the slot in next_round_idx where this team should appear."""
        r_start, r_end = round_ranges[next_round_idx]
        for c in range(r_start, r_end):
            # The team's next slot is one whose parents include the slot they just won
            # Simpler: check if any already-played slot in the next round has this team
            # or if any unplayed slot in the next round could contain this team
            pass
        # Use round_winners to find if there's a slot we can check
        # For partial rounds: find the child slot of the slot where team won
        return None

    truly_alive: set[str] = set()
    for team in all_starting:
        # Find the latest round this team won
        last_won_round = -1
        last_won_slot = -1
        for i, (r_start, r_end) in enumerate(round_ranges):
            for c in range(r_start, r_end):
                if not is_unplayed(winners_row[c]) and winners_row[c] == team:
                    last_won_round = i
                    last_won_slot = c

        if last_won_round == -1:
            # Never won any game — only eliminate if their specific R1 game has been played
            r1_slot = r1_team_to_slot.get(team)
            if r1_slot is not None and not is_unplayed(winners_row[r1_slot]):
                continue  # R1 game played, didn't win → eliminated
            else:
                truly_alive.add(team)  # R1 game not yet played → still alive
        else:
            next_round = last_won_round + 1
            if next_round >= len(round_ranges):
                truly_alive.add(team)  # Won championship
            else:
                # Find the specific next-round slot for this team
                # Child slot index: each pair of consecutive parent slots → one child
                r_start, r_end = round_ranges[last_won_round]
                next_r_start = round_ranges[next_round][0]
                slot_offset = last_won_slot - r_start
                next_slot = next_r_start + slot_offset // 2
                if is_unplayed(winners_row[next_slot]):
                    truly_alive.add(team)  # Their next game hasn't been played yet
                elif winners_row[next_slot] == team:
                    truly_alive.add(team)  # They won their next game
                # else: they lost → eliminated

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

    # defeated_map: winner -> the team they beat in their most recent played game
    # Built by scanning each played slot and finding which teams were picked there
    # but didn't win — those are the losers.
    defeated_map: dict[str, str] = {}
    for c in range(3, 66):
        w = winners_row[c]
        if is_unplayed(w):
            continue
        losers = set()
        for i in range(3, len(df_p)):
            val = str(df_p.iloc[i][c]).strip()
            if val and val not in UNPLAYED and val != w and val in all_starting:
                losers.add(val)
        if losers:
            # Pick the loser with the most picks (most commonly the actual opponent)
            loser = max(losers, key=lambda t: sum(
                1 for i in range(3, len(df_p)) if str(df_p.iloc[i][c]).strip() == t
            ))
            defeated_map[w] = loser

    # Load final score from MasterBracket H43 (row 42, col 7, 0-indexed)
    # Only set if the cell contains a positive number — stays None if blank/invalid
    final_score = None
    try:
        h43_val = str(df_seeds.iloc[40, 7]).strip() if len(df_seeds) > 40 and len(df_seeds.columns) > 7 else ""
        if h43_val and h43_val.lower() not in ("nan", "", "none"):
            parsed = safe_int(h43_val)
            if parsed > 0:
                final_score = parsed
    except Exception:
        pass

    # Load tiebreaker guesses from "Tiebreaker Scores" sheet (col A=name, col B=guess)
    tiebreaker_guesses: dict[str, int] = {}
    try:
        if tiebreaker_url:
            df_tb = pd.read_csv(tiebreaker_url, header=None)
            for _, row in df_tb.iterrows():
                tb_name  = str(row[0]).strip() if len(row) > 0 else ""
                tb_guess = str(row[1]).strip() if len(row) > 1 else ""
                if tb_name and tb_name.lower() not in ("nan", "", "name") and tb_guess:
                    g = safe_int(tb_guess)
                    if g and g > 0:
                        tiebreaker_guesses[tb_name] = g
    except Exception:
        pass

    return df_p, winners_row, points_per_game, seed_map, all_alive, all_starting, truly_alive, lucky_map, r1_matchups, defeated_map, team_to_region, datetime.now().strftime("%I:%M %p"), final_score, tiebreaker_guesses


# ─── 3. SCORING ───────────────────────────────────────────────────────────────
def score_picks(picks: list[str], winners: list[str], pts: list[int],
                seeds: dict[str, int], alive: set[str]) -> tuple[int, int]:
    """Return (current_score, potential_score).
    Potential score = current score + points for unplayed slots where the
    picked team is still truly alive (can actually appear in that slot).
    """
    cur = pot = 0
    for c in range(3, 66):
        val = pts[c] + seeds.get(picks[c], 0)
        if picks[c] == winners[c]:
            cur += val
        elif is_unplayed(winners[c]) and picks[c] in alive:
            pot += val
    return cur, cur + pot


# ─── 4. MONTE CARLO ───────────────────────────────────────────────────────────

# Bracket structure: maps each slot to its two parent slots (or None for R1)
# R1 slots (3-34) have no parents — teams come from the original seeding
# R2 slot 35 is fed by R1 slots 3 & 4, slot 36 by 5 & 6, etc.
def _build_bracket_parents() -> dict[int, tuple[int, int] | None]:
    parents: dict[int, tuple[int, int] | None] = {}
    for c in range(3, 35):
        parents[c] = None  # R1 — no parents
    for child_start, child_end, parent_start in [
        (35, 50, 3),   # R2 from R1
        (51, 58, 35),  # S16 from R2
        (59, 62, 51),  # E8 from S16
        (63, 64, 59),  # FF from E8
        (65, 65, 63),  # Champ from FF
    ]:
        for i, c in enumerate(range(child_start, child_end + 1)):
            parents[c] = (parent_start + i * 2, parent_start + i * 2 + 1)
    return parents

_BRACKET_PARENTS = _build_bracket_parents()

@st.cache_data(ttl=300)
def run_monte_carlo(
    names: tuple,
    picks_matrix: tuple,        # tuple of tuples so it's hashable
    winners_row: tuple,
    pts_list: tuple,
    alive_tuple: tuple,
    seed_items: tuple,
    r1_contestants: tuple,      # tuple of (col, team_a, team_b) for R1 slots
    runs: int = 1000,
    top_n: int = 3,
) -> tuple[dict, dict]:
    """
    Bracket-aware simulation. For each unplayed slot, the two contestants are
    derived from the simulated winners of the parent slots (or the original R1
    matchup for first-round games). The winner is chosen randomly from whichever
    of the two contestants participants actually picked for that slot.
    """
    seed_map     = dict(seed_items)
    r1_teams     = {col: (a, b) for col, a, b in r1_contestants}
    unplayed     = [c for c in range(3, 66) if is_unplayed(winners_row[c])]
    unplayed_set = set(unplayed)

    win_c  = {n: 0 for n in names}
    top3_c = {n: 0 for n in names}

    for _ in range(runs):
        sim_w = list(winners_row)  # already-played slots have real winners

        for c in sorted(unplayed):  # must process in order (low → high)
            parents = _BRACKET_PARENTS.get(c)
            if parents is None:
                # R1: contestants are the two original seeds
                contestants = set(r1_teams.get(c, ("", "")))
            else:
                p1, p2 = parents
                # Contestants are whoever won each parent slot in this simulation
                contestants = {sim_w[p1], sim_w[p2]}
            contestants.discard("")
            contestants.discard("None")

            # 50% chance to pick from participants' picks, 50% random contestant
            # This ensures all bracket outcomes can occur in simulation
            picks_for_slot = [
                picks_matrix[i][c] for i in range(len(names))
                if picks_matrix[i][c] in contestants
            ]
            if picks_for_slot and random.random() < 0.5:
                sim_w[c] = random.choice(picks_for_slot)
            else:
                sim_w[c] = random.choice(list(contestants)) if contestants else "None"

        scored = []
        for i, name in enumerate(names):
            s = sum(
                (pts_list[c] + seed_map.get(picks_matrix[i][c], 0))
                for c in range(3, 66)
                if picks_matrix[i][c] == sim_w[c]
            )
            scored.append((name, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        top_score = scored[0][1]
        winners = [name for name, s in scored if s == top_score]
        share = 1.0 / len(winners)
        for name in winners:
            win_c[name] += share

        topn_score = scored[min(top_n - 1, len(scored)-1)][1]
        for name, s in scored[:top_n]:
            top3_c[name] += 1
        # also include anyone tied with the nth place score
        for name, s in scored[top_n:]:
            if s == topn_score:
                top3_c[name] += 1
            else:
                break

    n = runs
    return (
        {nm: (c / n) * 100 for nm, c in win_c.items()},
        {nm: (c / n) * 100 for nm, c in top3_c.items()},
    )


# ─── 4b. HEAD-TO-HEAD MONTE CARLO ────────────────────────────────────────────
@st.cache_data(ttl=300)
def run_h2h_monte_carlo(
    p1_name: str,
    p2_name: str,
    p1_picks: tuple,
    p2_picks: tuple,
    winners_row: tuple,
    pts_list: tuple,
    alive_tuple: tuple,
    seed_items: tuple,
    r1_contestants: tuple,
    runs: int = 1000,
) -> tuple[float, float, float]:
    """Bracket-aware H2H simulation."""
    seed_map  = dict(seed_items)
    r1_teams  = {col: (a, b) for col, a, b in r1_contestants}
    unplayed  = [c for c in range(3, 66) if is_unplayed(winners_row[c])]

    p1_wins = p2_wins = ties = 0

    for _ in range(runs):
        sim_w = list(winners_row)

        for c in sorted(unplayed):
            parents = _BRACKET_PARENTS.get(c)
            if parents is None:
                contestants = set(r1_teams.get(c, ("", "")))
            else:
                p1s, p2s = parents
                contestants = {sim_w[p1s], sim_w[p2s]}
            contestants.discard("")
            contestants.discard("None")

            if not contestants:
                sim_w[c] = "None"
                continue

            # Pick winner from actual contestants — bias toward players' picks
            # so that picks being correct happens at a realistic rate
            picks_in = [t for t in (p1_picks[c], p2_picks[c]) if t in contestants]
            if picks_in:
                # 50% chance of a picked team winning, 50% random
                if random.random() < 0.5:
                    winner = random.choice(picks_in)
                else:
                    winner = random.choice(list(contestants))
            else:
                winner = random.choice(list(contestants))
            sim_w[c] = winner

        p1_score = sum(
            pts_list[c] + seed_map.get(p1_picks[c], 0)
            for c in range(3, 66) if p1_picks[c] == sim_w[c]
        )
        p2_score = sum(
            pts_list[c] + seed_map.get(p2_picks[c], 0)
            for c in range(3, 66) if p2_picks[c] == sim_w[c]
        )

        if p1_score > p2_score:
            p1_wins += 1
        elif p2_score > p1_score:
            p2_wins += 1
        else:
            ties += 1

    return (p1_wins / runs * 100, p2_wins / runs * 100, ties / runs * 100)


def run_nway_monte_carlo(
    player_names: list,
    player_picks: list,  # list of tuples
    winners_row: tuple,
    pts_list: tuple,
    alive_tuple: tuple,
    seed_items: tuple,
    r1_contestants: tuple,
    runs: int = 1000,
) -> dict:
    """N-player H2H simulation — returns win % per player summing to 100%."""
    seed_map = dict(seed_items)
    r1_teams = {col: (a, b) for col, a, b in r1_contestants}
    unplayed = [c for c in range(3, 66) if is_unplayed(winners_row[c])]
    n = len(player_names)
    wins = {name: 0 for name in player_names}
    ties_count = 0

    for _ in range(runs):
        sim_w = list(winners_row)
        for c in sorted(unplayed):
            parents = _BRACKET_PARENTS.get(c)
            if parents is None:
                contestants = set(r1_teams.get(c, ("", "")))
            else:
                p1s, p2s = parents
                contestants = {sim_w[p1s], sim_w[p2s]}
            contestants.discard("")
            contestants.discard("None")
            if not contestants:
                sim_w[c] = "None"
                continue
            picks_in = [t for picks in player_picks for t in [picks[c]] if t in contestants]
            if picks_in:
                if random.random() < 0.5:
                    winner = random.choice(picks_in)
                else:
                    winner = random.choice(list(contestants))
            else:
                winner = random.choice(list(contestants))
            sim_w[c] = winner

        scores = []
        for picks in player_picks:
            sc = sum(
                pts_list[c] + seed_map.get(picks[c], 0)
                for c in range(3, 66) if picks[c] == sim_w[c]
            )
            scores.append(sc)

        max_sc = max(scores)
        winners_this = [player_names[i] for i, s in enumerate(scores) if s == max_sc]
        if len(winners_this) == 1:
            wins[winners_this[0]] += 1
        else:
            ties_count += 1
            for w in winners_this:
                wins[w] += 1 / len(winners_this)

    return {name: wins[name] / runs * 100 for name in player_names}



# ─── 5. BRACKET BUSTERS ───────────────────────────────────────────────────────
# Bust threshold per round — decreases as tournament progresses
BUST_THRESHOLDS = {
    "R64":   0.50,
    "R32":   0.40,
    "S16":   0.30,
    "E8":    0.20,
    "F4":    0.10,
    "Champ": 0.10,
}

def compute_bracket_busters(results: list[dict], winners_row: list[str],
                             pts: list[int], seeds: dict[str, int]) -> pd.DataFrame:
    """
    For each played game, count games where enough of the pool had their
    bracket busted. Threshold decreases each round since the field narrows
    and upsets become rarer/more impactful:
      R1: 50%, R2: 40%, S16: 30%, E8: 20%, FF/Champ: 10%
    """
    pool_size = max(len(results), 1)
    busters = []
    for c in range(3, 66):
        winner = winners_row[c]
        if is_unplayed(winner):
            continue
        round_name = get_round_name(c)
        threshold = BUST_THRESHOLDS.get(round_name, 0.50)
        busted = [
            r["Name"] for r in results
            if r["raw_picks"][c] != winner and r["raw_picks"][c] not in {"nan", ""}
        ]
        # Only count as a bracket buster if enough of the pool had the wrong pick
        if len(busted) / pool_size < threshold:
            continue
        loser_team = None
        loser_counts: dict[str, int] = {}
        for r in results:
            pick = r["raw_picks"][c]
            if pick != winner and pick not in {"nan", ""}:
                loser_counts[pick] = loser_counts.get(pick, 0) + 1
        if loser_counts:
            loser_team = max(loser_counts, key=loser_counts.__getitem__)
        winner_seed = seeds.get(winner, 0)
        loser_seed  = seeds.get(loser_team, 0) if loser_team else 0
        winner_str  = f"({winner_seed}) {winner}"  if winner_seed  else winner
        loser_str   = f"({loser_seed}) {loser_team}" if loser_team and loser_seed else (loser_team or "–")
        matchup_str = f"{get_round_name(c)}: {loser_str} vs. {winner_str}"
        busters.append({
            "Round":          get_round_name(c),
            "Busted Team":    loser_str,
            "Winner":         winner_str,
            "Matchup":        matchup_str,
            "Busted Picks":   len(busted),
            "% Busted":       f"{len(busted)/pool_size*100:.0f}%",
            "Pts Lost ea.":   pts[c] + winner_seed,
            "Total Pts Lost": (pts[c] + winner_seed) * len(busted),
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

        # Seed bonus comes from whoever won (or the correct pick's seed)
        winner_seed_bonus = seeds.get(w, 0) if not is_unplayed(w) else 0
        val = pts[c] + winner_seed_bonus

        if t1 == t2:
            if t1 == w:
                shared_pts += val
        else:
            p1_correct = (t1 == w) and not is_unplayed(w)
            p2_correct = (t2 == w) and not is_unplayed(w)

            # For upcoming games, potential pts based on each player's own pick seed
            p1_potential = pts[c] + seeds.get(t1, 0)
            p2_potential = pts[c] + seeds.get(t2, 0)

            divergences.append({
                "Round":      get_round_name(c),
                p1["Name"]:   t1,
                p2["Name"]:   t2,
                "Played":     not is_unplayed(w),
                "Winner":     w if not is_unplayed(w) else "–",
                "P1 Got It":  "✅" if p1_correct else ("⏳" if is_unplayed(w) else "❌"),
                "P2 Got It":  "✅" if p2_correct else ("⏳" if is_unplayed(w) else "❌"),
                "Pts":        val if (p1_correct or p2_correct) else 0,
                "P1 Pts":     p1_potential,
                "P2 Pts":     p2_potential,
            })
            if p1_correct: p1_only_pts += val
            if p2_correct: p2_only_pts += val

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


# ─── 9. AGGRID TABLE HELPER ──────────────────────────────────────────────────
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode, ColumnsAutoSizeMode

def show_table(df, user_highlight_col=None, user_highlight_val=None,
               user_highlight_contains=False, gradient_cols=None,
               pct_cols=None, height=None, key=None, col_config=None,
               pinned_cols=None, return_selected=False, nowrap_cols=None):
    """
    Render a DataFrame using AgGrid with:
    - Alternating row shading
    - Hover highlight
    - Left-aligned text and numbers
    - Optional gold highlight for the current user's row
    - Optional % formatting
    - Optional column widths (col_config: dict of col_name -> width in px)
    - Optional pinned/frozen columns (pinned_cols: list of col names to pin left)
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=False,
        floatingFilter=False,
        suppressMenu=True,
        cellStyle={"textAlign": "left", "color": "#ffffff"},
        headerClass="left-header",
    )
    gb.configure_grid_options(
        suppressStatusBar=True,
        suppressColumnVirtualisation=True,
        enableBrowserTooltips=False,
        autoHeaderHeight=True,
        wrapHeaderText=True,
        rowSelection="single" if return_selected else None,
    )
    if pct_cols:
        for col in pct_cols:
            if col in df.columns:
                gb.configure_column(col, valueFormatter="x.toFixed(1) + '%'")

    if col_config:
        for col_name, width in col_config.items():
            if col_name in df.columns:
                pinned = "left" if pinned_cols and col_name in pinned_cols else None
                gb.configure_column(col_name, width=width, pinned=pinned)

    # Apply no-wrap cell style to specified columns
    if nowrap_cols:
        for col_name in nowrap_cols:
            if col_name in df.columns:
                gb.configure_column(col_name, cellStyle={
                    "textAlign": "left", "color": "#ffffff",
                    "whiteSpace": "nowrap", "overflow": "hidden",
                    "textOverflow": "ellipsis",
                })

    # Apply pinning to any pinned cols not already handled by col_config
    if pinned_cols:
        for col_name in pinned_cols:
            if col_name in df.columns and (not col_config or col_name not in col_config):
                gb.configure_column(col_name, pinned="left")

    grid_options = gb.build()
    grid_options["statusBar"] = {"statusPanels": []}
    grid_options["domLayout"] = "normal"
    grid_options["suppressHorizontalScroll"] = False
    grid_options["alwaysShowVerticalScroll"] = True
    grid_options["suppressScrollOnNewData"] = True

    # Row styling: gold for user row, alternating grey otherwise
    if user_highlight_col:
        if user_highlight_contains:
            row_style = JsCode(f"""
            function(params) {{
                if (params.data["{user_highlight_col}"] && 
                    params.data["{user_highlight_col}"].includes("{user_highlight_val}")) {{
                    return {{'background': '#3a3000', 'color': '#f5c518', 'fontWeight': 'bold'}};
                }}
                if (params.node.rowIndex % 2 === 0) {{
                    return {{'background': '#1a1f2b', 'color': '#ffffff'}};
                }}
                return {{'background': '#13161f', 'color': '#ffffff'}};
            }}
            """)
        else:
            row_style = JsCode(f"""
            function(params) {{
                if (params.data["{user_highlight_col}"] === "{user_highlight_val}") {{
                    return {{'background': '#3a3000', 'color': '#f5c518', 'fontWeight': 'bold'}};
                }}
                if (params.node.rowIndex % 2 === 0) {{
                    return {{'background': '#1a1f2b', 'color': '#ffffff'}};
                }}
                return {{'background': '#13161f', 'color': '#ffffff'}};
            }}
            """)
    else:
        row_style = JsCode("""
        function(params) {
            if (params.node.rowIndex % 2 === 0) {
                return {'background': '#1a1f2b', 'color': '#ffffff'};
            }
            return {'background': '#13161f', 'color': '#ffffff'};
        }
        """)

    grid_options["getRowStyle"] = row_style

    custom_css = {
        ".ag-row-hover": {"background-color": "#2a3550 !important"},
        ".ag-row-hover .ag-cell": {"color": "#ffffff !important"},
        ".ag-cell": {"text-align": "left !important", "color": "#ffffff !important", "font-size": "13px !important", "padding-left": "8px !important", "padding-right": "8px !important", "white-space": "normal !important", "word-break": "keep-all !important", "overflow": "visible !important"},
        ".ag-header": {"background-color": "#1e1e2e !important", "border-bottom": "1px solid #313244 !important"},
        ".ag-header-cell": {"background-color": "#1e1e2e !important", "color": "#ffffff !important", "padding-left": "8px !important", "padding-right": "8px !important"},
        ".ag-header-cell-label": {"justify-content": "flex-start !important", "color": "#ffffff !important", "white-space": "normal !important", "word-break": "keep-all !important", "overflow-wrap": "normal !important", "line-height": "1.3 !important"},
        ".ag-header-cell-text": {"text-align": "left !important", "font-size": "12px !important", "white-space": "normal !important", "word-break": "keep-all !important", "overflow": "visible !important"},
        ".ag-right-aligned-header .ag-header-cell-label": {"flex-direction": "row !important", "justify-content": "flex-start !important"},
        ".ag-right-aligned-header .ag-header-cell-text": {"text-align": "left !important"},
        ".left-header": {"text-align": "left !important"},
        ".ag-root-wrapper": {"border": "1px solid #313244 !important"},
        ".ag-row": {"border-color": "#313244 !important"},
        ".ag-status-bar": {"display": "none !important", "height": "0 !important"},
        ".ag-floating-filter": {"display": "none !important", "height": "0 !important"},
        ".ag-popup": {"display": "none !important"},
        ".ag-icon-filter": {"display": "none !important"},
        ".ag-header-icon": {"display": "none !important"},
        ".ag-body-viewport": {"background-color": "#13161f !important", "overflow-y": "scroll !important", "-webkit-overflow-scrolling": "touch !important"},
        ".ag-center-cols-container": {"background-color": "#13161f !important"},
        ".ag-pinned-left-cols-container": {"background-color": "#13161f !important"},
        ".ag-pinned-left-header": {"background-color": "#1e1e2e !important"},
        ".ag-body-horizontal-scroll": {"display": "none !important", "height": "0 !important"},
        ".ag-root-wrapper-body": {"height": "100% !important", "min-height": "0 !important"},
    }

    row_height = 36
    header_height = 40
    exact_height = header_height + (len(df) * row_height) + 2

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        height=height or exact_height,
        use_container_width=True,
        allow_unsafe_jscode=True,
        custom_css=custom_css,
        theme="balham-dark",
        enable_enterprise_modules=False,
        columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE,
        key=key,
        update_mode="SELECTION_CHANGED" if return_selected else "NO_UPDATE",
    )

    if return_selected:
        selected = grid_response.get("selected_rows")
        if selected is not None and len(selected) > 0:
            if hasattr(selected, "to_dict"):
                return selected.to_dict("records")[0]
            return selected[0]
    return None


# ─────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────────────────────────────────────
try:
    data = load_all_data()
    if not data:
        st.error("Could not load data. Check that the Google Sheet is publicly accessible.")
        st.stop()

    df_p, actual_winners, points_per_game, seed_map, all_alive, all_starting, truly_alive, lucky_map, r1_matchups, defeated_map, team_to_region, last_update, final_score, tiebreaker_guesses = data

    # ── ESPN logo lookup (shared across tabs) ────────────────────────────────
    ESPN_IDS = {
        "Alabama": 333, "Alabama St": 2010, "Alabama St.": 2010, "American": 44,
        "Arizona": 12, "Arkansas": 8, "Auburn": 2,
        "Baylor": 239, "Bryant": 2870, "BYU": 252,
        "Clemson": 228, "Colorado St": 36, "Colorado St.": 36, "Creighton": 156,
        "Drake": 2181, "Duke": 150, "Florida": 57,
        "GC": 2253, "Grand Canyon": 2253,
        "Georgia": 61, "Gonzaga": 2250, "High Point": 2272,
        "Houston": 248, "Illinois": 356, "Iowa St": 66, "Iowa St.": 66,
        "Kansas": 2305, "Kentucky": 96, "Liberty": 2335,
        "Lipscomb": 2344, "Louisville": 97, "Marquette": 269,
        "Maryland": 120, "McNeese": 2440, "McNeese St": 2440, "McNeese St.": 2440,
        "Michigan": 130, "Michigan St": 127, "Michigan St.": 127, "Mich. St.": 127, "Mich. St": 127,
        "Mississippi St": 344, "Mississippi St.": 344,
        "Missouri": 142, "Mount St. Mary's": 2426, "Mt. St. Mary's": 2426,
        "Nebraska": 158, "New Mexico": 167,
        "Norfolk St": 2450, "Norfolk St.": 2450, "North Carolina": 153,
        "Oklahoma": 201, "Ole Miss": 145, "Oregon": 2483,
        "Purdue": 2509, "Saint Mary's": 2608, "St. Mary's": 2608,
        "SIUE": 2565, "St. John's": 2599,
        "St. Francis PA": 2620, "Tennessee": 2633,
        "Texas": 251, "Texas A&M": 245, "Texas Tech": 2641,
        "Troy": 2653, "UC San Diego": 2604, "UCLA": 26,
        "UConn": 41,
        "Utah St": 328, "Utah St.": 328,
        "Vanderbilt": 238,
        "VCU": 2670, "West Virginia": 277, "Wisconsin": 275,
        "Wofford": 2747, "Xavier": 2752, "Yale": 43,
        "Siena": 2561,
        "Ohio St": 194, "Ohio St.": 194, "Ohio State": 194,
        "TCU": 2628,
        "Cal Baptist": 2856, "California Baptist": 2856,
        "South Florida": 58,
        "N. Dakota St": 2446, "N. Dakota St.": 2446, "North Dakota St": 2446, "North Dakota State": 2446, "North Dakota State Bison": 2446,
        "UCF": 2116,
        "Furman": 231,
        "Iowa": 2294,
        "Penn": 219,
        "Idaho": 70,
        "LIU": 2351, "Long Island University": 2351, "LIU Sharks": 2351, "Long Island University Sharks": 2351,
        "Villanova": 222,
        "Hawaii": 62, "Hawai'i": 62,
        "Kennesaw St": 2309, "Kennesaw St.": 2309, "Kennesaw State": 2309, "Kennesaw State Owls": 2309,
        "Miami": 2390, "Miami FL": 2390, "Miami Hurricanes": 2390,
        "Prairie View": 2440, "Prairie View A&M": 2440, "Prairie View A&M Panthers": 2440,
        "Howard": 2275,
        "Miami Ohio": 2393, "Miami (OH)": 2393, "Miami OH": 2393, "Miami (Ohio)": 2393, "Miami (OH) RedHawks": 2393, "Miami RedHawks": 2393, "Miami of Ohio": 2393,
        "Queens": 2511, "Queens University": 2511,
        "N. Iowa": 2460, "Northern Iowa": 2460,
        "N. Carolina": 153, "N. Carolina A&T": 2428,
        "Saint Louis": 139, "St. Louis": 139,
        "Akron": 2006,
        "Hofstra": 2261, "Hofstra Pride": 2261,
        "Wright St": 2750, "Wright St.": 2750, "Wright State": 2750,
        "Santa Clara": 2541,
        "Tennessee St": 2634, "Tennessee St.": 2634, "Tennessee State": 2634,
        "Virginia": 258,
    }
    # Normalise lookup: try exact name first, then strip trailing periods
    def espn_logo_url(team_name):
        tid = ESPN_IDS.get(team_name)
        if tid is None:
            tid = ESPN_IDS.get(team_name.rstrip("."))
        if tid is None:
            tid = ESPN_IDS.get(team_name.replace(".", ""))
        return f"https://a.espncdn.com/i/teamlogos/ncaa/500/{tid}.png" if tid else None

    def pill(label, alive, detail=""):
        if alive:
            bg, border, color = "#14532d", "#16a34a", "#4ade80"
            icon = "✅"
        else:
            bg, border, color = "#2d0a0a", "#7f1d1d", "#ef4444"
            icon = "❌"
        tip = f' title="{detail}"' if detail else ""
        return (
            f'<span{tip} style="display:inline-flex;align-items:center;gap:4px;'
            f'background:{bg};border:1px solid {border};border-radius:20px;'
            f'padding:3px 10px;font-size:clamp(11px,2vw,13px);'
            f'font-weight:600;color:{color};white-space:nowrap;">'
            f'{icon} {label}</span>'
        )

    # ── Build slot_to_region ──────────────────────────────────────────────────
    # R1 is split into 4 equal groups of 8 games (cols 3-34):
    #   East:    cols 3-10
    #   South:   cols 11-18
    #   West:    cols 19-26
    #   Midwest: cols 27-34
    # R2 (cols 35-50): pairs of R1 slots feed each R2 slot
    # S16 (cols 51-58): pairs of R2 slots feed each S16 slot
    # E8  (cols 59-62): pairs of S16 slots feed each E8 slot
    slot_to_region: dict[int, str] = {}

    r1_region_ranges = [
        ("East",    3,  10),
        ("South",   11, 18),
        ("West",    19, 26),
        ("Midwest", 27, 34),
    ]
    for region, start, end in r1_region_ranges:
        for c in range(start, end + 1):
            slot_to_region[c] = region

    # Propagate forward: every 2 consecutive parent slots → 1 child slot
    for child_start, child_end, parent_start in [
        (35, 50, 3),   # R2 from R1
        (51, 58, 35),  # S16 from R2
        (59, 62, 51),  # E8 from S16
    ]:
        for i, c in enumerate(range(child_start, child_end + 1)):
            p1 = parent_start + i * 2
            p2 = parent_start + i * 2 + 1
            r = slot_to_region.get(p1) or slot_to_region.get(p2)
            if r:
                slot_to_region[c] = r

    # ── Build results ──────────────────────────────────────────────────────────
    results: list[dict] = []
    global_pick_counts: dict[str, int] = {}
    slot_pick_counts: dict[int, dict[str, int]] = {}  # slot -> {team -> count}

    for i in range(3, len(df_p)):
        row = df_p.iloc[i]
        name = str(row[0]).strip()
        if not name or name in {"Winner", ""} or name.lower() == "nan":
            continue
        p_picks = [str(row[c]).strip() if c < len(row) else "" for c in range(67)]

        cur_score, pot_score = score_picks(p_picks, actual_winners, points_per_game, seed_map, truly_alive)

        upsets, best_s, best_t = 0, 0, "None"
        upset_correct = 0
        for c in range(3, 66):
            if p_picks[c] == actual_winners[c]:
                s = seed_map.get(p_picks[c], 0)
                if s >= 8:
                    upsets += 1
                    if s > best_s:
                        best_s, best_t = s, p_picks[c]
                # Correct upset pick: winner seed - loser seed >= 3
                loser = defeated_map.get(p_picks[c], "")
                l_seed = seed_map.get(loser, 0)
                if l_seed > 0 and s > 0 and (s - l_seed) >= 3:
                    upset_correct += 1
            if p_picks[c] not in {"nan", ""}:
                global_pick_counts[p_picks[c]] = global_pick_counts.get(p_picks[c], 0) + 1
                if c not in slot_pick_counts:
                    slot_pick_counts[c] = {}
                slot_pick_counts[c][p_picks[c]] = slot_pick_counts[c].get(p_picks[c], 0) + 1

        # Regional scores: only count points from picks where the slot's region matches
        region_scores  = {"South": 0, "East": 0, "Midwest": 0, "West": 0}
        region_correct = {"South": 0, "East": 0, "Midwest": 0, "West": 0}
        for c in range(3, 63):  # R1 through Elite Eight only (region-specific rounds)
            pick = p_picks[c]
            winner = actual_winners[c]
            if pick == winner and not is_unplayed(winner):
                region = slot_to_region.get(c, "")
                if region in region_scores:
                    pts = points_per_game[c] + seed_map.get(pick, 0)
                    region_scores[region]  += pts
                    region_correct[region] += 1

        # Col 89 = "Bonus Pool" opt-in flag ("yes" = included)
        bonus_pool_val = str(row[89]).strip().lower() if len(row) > 89 else ""
        in_bonus_pool  = bonus_pool_val == "yes"

        results.append({
            "Name":          name,
            "Current Score": cur_score,
            "Potential Score": pot_score,
            "Upsets":        upsets,
            "Biggest Upset": f"#{best_s} {best_t}" if best_s else "None",
            "Upset Correct": upset_correct,
            "Bonus Pool":    in_bonus_pool,
            "raw_picks":     p_picks,
            **{f"{r} Score": region_scores[r] for r in region_scores},
            **{f"{r} Correct": region_correct[r] for r in region_correct},
        })

    # ── Monte Carlo ───────────────────────────────────────────────────────────
    names_tuple      = tuple(r["Name"] for r in results)
    picks_matrix     = tuple(tuple(r["raw_picks"]) for r in results)
    r1_contestants   = tuple((c, a, b) for c, (a, b) in r1_matchups.items())
    # Tournament progress flags
    r1_played   = sum(1 for c in range(3, 35)  if not is_unplayed(actual_winners[c]))
    r2_played   = sum(1 for c in range(35, 51) if not is_unplayed(actual_winners[c]))
    r2_complete = r1_played >= 32 and r2_played >= 16
    # Use more runs early in the tournament when variance is highest
    mc_runs = 2000 if not r2_complete else 1000
    win_probs, top3_probs = run_monte_carlo(
        names_tuple, picks_matrix,
        tuple(actual_winners), tuple(points_per_game),
        tuple(all_alive), tuple(seed_map.items()),
        r1_contestants,
        runs=mc_runs,
    )

    for r in results:
        win_pct  = win_probs.get(r["Name"], 0.0)
        top3_pct = top3_probs.get(r["Name"], 0.0)
        if not r2_complete:
            import math
            # Round up to nearest whole % so nobody shows 0% until R2 is done
            win_pct  = math.ceil(win_pct)  if win_pct  > 0 else (100.0 / len(results) if results else 0.1)
            top3_pct = math.ceil(top3_pct) if top3_pct > 0 else 1.0
        r["Win %"]   = win_pct
        r["Top 3 %"] = top3_pct

    # ── Potential Status: driven by Monte Carlo probabilities ─────────────────
    # Don't declare anyone "Out" until at least half of R1 is complete —
    # with few games played the simulation has too much variance to be meaningful.
    for r in results:
        if r["Win %"] > 0:
            r["Potential Status"] = "🏆 Champion"
        elif r["Top 3 %"] > 0:
            r["Potential Status"] = "🥉 Top 3"
        elif r2_complete:
            r["Potential Status"] = "❌ Out"
        else:
            r["Potential Status"] = "🥉 Top 3"

    _champ_complete = not is_unplayed(actual_winners[65]) if len(actual_winners) > 65 else False

    # Build tiebreaker diff for each participant (absolute difference from final score)
    # Only used for ranking when championship is complete
    def _tb_diff(name):
        if final_score is None:
            return 999999
        guess = tiebreaker_guesses.get(name)
        return abs(guess - final_score) if guess is not None else 999999

    if _champ_complete:
        # Sort by score desc, then tiebreaker diff asc
        final_df = (
            pd.DataFrame(results)
            .sort_values("Current Score", ascending=False)
            .reset_index(drop=True)
        )
        final_df = final_df[final_df["Name"].notna() & (final_df["Name"].str.strip() != "") & (final_df["Name"].str.lower() != "nan")]
        final_df["_tb_diff"] = final_df["Name"].apply(_tb_diff)
        final_df = final_df.sort_values(["Current Score", "_tb_diff"], ascending=[False, True]).reset_index(drop=True)
        # Assign ranks: tied on both score AND tiebreaker share a rank
        ranks = []
        rank = 1
        for i in range(len(final_df)):
            if i > 0 and (
                final_df.at[i, "Current Score"] == final_df.at[i-1, "Current Score"] and
                final_df.at[i, "_tb_diff"] == final_df.at[i-1, "_tb_diff"]
            ):
                ranks.append(ranks[-1])
            else:
                rank = i + 1
                ranks.append(rank)
        final_df["Current Rank"] = ranks
        final_df = final_df.drop(columns=["_tb_diff"])
    else:
        # Sort by score desc only; ties share a rank
        final_df = (
            pd.DataFrame(results)
            .sort_values("Current Score", ascending=False)
            .reset_index(drop=True)
        )
        final_df = final_df[final_df["Name"].notna() & (final_df["Name"].str.strip() != "") & (final_df["Name"].str.lower() != "nan")]
        final_df = final_df.reset_index(drop=True)
        ranks = []
        rank = 1
        for i in range(len(final_df)):
            if i > 0 and final_df.at[i, "Current Score"] == final_df.at[i-1, "Current Score"]:
                ranks.append(ranks[-1])
            else:
                rank = i + 1
                ranks.append(rank)
        final_df["Current Rank"] = ranks
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
            # Inject JS to make all inputs in this dialog readonly so mobile keyboard never appears
            import streamlit.components.v1 as _dlg_components
            _dlg_components.html("""<script>
            (function() {
                function lockInputs() {
                    var inputs = window.parent.document.querySelectorAll(
                        'div[data-testid="stDialog"] input, div[role="dialog"] input'
                    );
                    inputs.forEach(function(el) {
                        el.setAttribute('readonly', 'readonly');
                        el.setAttribute('inputmode', 'none');
                        el.style.caretColor = 'transparent';
                    });
                    if (inputs.length === 0) { setTimeout(lockInputs, 100); }
                }
                setTimeout(lockInputs, 150);
            })();
            </script>""", height=0)
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
        if st.session_state.get("_h2h_sel_p1", "— select —") in ("— select —", "") or st.session_state.get("_h2h_sel_p1") not in name_opts:
            st.session_state["_h2h_sel_p1"] = user_name

    # Pre-fill Head-to-Head players from ?p1= and ?p2= query params.
    # Only applied once (on first load) so the user can still change them manually.
    if "h2h_params_applied" not in st.session_state:
        st.session_state["h2h_params_applied"] = True
        try:
            qp1 = st.query_params.get("p1", "")
            qp2 = st.query_params.get("p2", "")
            name_lower = {n.lower(): n for n in name_opts}
            if qp1:
                matched = name_lower.get(qp1.lower())
                if matched:
                    st.session_state["_h2h_sel_p1"] = matched
            if qp2:
                matched = name_lower.get(qp2.lower())
                if matched:
                    st.session_state["_h2h_sel_p2"] = matched
        except Exception:
            pass

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

    # After dialog rerun, apply pending deep-link navigation directly
    _pending_slug = st.session_state.get("_pending_slug", "")
    if _pending_slug and st.session_state.get("modal_done"):
        st.session_state["_deeplink_pending_apply"] = _pending_slug
        st.session_state.pop("_pending_slug", None)

    # ── Grouped tab navigation ────────────────────────────────────────────────
    # Map old slugs to new group + subpage
    SLUG_TO_GROUP = {
        "standings":       ("standings", None),
        "bracket":         ("your-bracket", "bracket"),
        "win-conditions":  ("your-bracket", "win-conditions"),
        "head-to-head":    ("your-bracket", "head-to-head"),
        "scores-picks":    ("scores", None),
        "schedule":        ("scores", None),
        "bracket-dna":     ("your-bracket", "bracket-dna"),
        "bracket-busters": ("fun-stats", "bracket-busters"),
        "cinderella":      ("fun-stats", "cinderella"),
        "lucky-team":      ("bonus", "lucky-team"),
        "regional":        ("bonus", "regional"),
        "upset-picks":     ("bonus", "upset-picks"),
        "1st-weekend":     ("bonus", "1st-weekend"),
        "2nd-weekend":     ("bonus", "2nd-weekend"),
        "tiebreaker-scores": ("bonus", "tiebreaker-scores"),
        "bonus-pool":      ("bonus", "bonus-pool"),
        "correct-picks":   ("bonus", "correct-picks"),
        "hall-of-champions":    ("hall-of-champs", None),
        "classic-rivalries":    ("fun-stats", "classic-rivalries"),
        "champion-picks":      ("fun-stats", "champion-picks"),
        "current-standings":    ("standings", "current"),
        "potential-standings":  ("standings", "potential"),
    }

    try:
        slug = st.query_params.get("tab", "standings")
    except Exception:
        slug = "standings"

    # Preserve the intended deep-link slug across dialog reruns
    if slug and slug != "standings" and not st.session_state.get("_pending_slug"):
        st.session_state["_pending_slug"] = slug

    group, subpage = SLUG_TO_GROUP.get(slug, ("standings", None))

    # Set session state defaults
    if "nav_group" not in st.session_state:
        st.session_state["nav_group"] = group
    if "nav_sub_your-bracket" not in st.session_state:
        st.session_state["nav_sub_your-bracket"] = "bracket"
    if "nav_sub_fun-stats" not in st.session_state:
        st.session_state["nav_sub_fun-stats"] = "bracket-busters"
    if "nav_sub_bonus" not in st.session_state:
        st.session_state["nav_sub_bonus"] = "lucky-team"

    GROUP_TAB_INDEX = {
        "standings":       0,
        "your-bracket":    1,
        "scores":          2,
        "bonus":           3,
        "fun-stats":       4,
        "hall-of-champs":  5,
    }

    # Apply deep-link on initial page load — keyed to the slug so each unique
    # link works even if the app is already open.
    # Also handles post-dialog navigation via _deeplink_pending_apply.
    _pending_apply = st.session_state.pop("_deeplink_pending_apply", "")
    _effective_slug = _pending_apply if _pending_apply else slug
    # Handle standings sub-nav from deep-link
    if _effective_slug == "current-standings":
        st.session_state["nav_sub_standings"] = "current"
    elif _effective_slug == "potential-standings":
        st.session_state["nav_sub_standings"] = "potential"
    _applied_slug = st.session_state.get("_deeplink_applied_slug", "")
    _modal_done = st.session_state.get("modal_done", False)
    # Only apply deep-link if modal is done — otherwise save for after dialog
    if _effective_slug and _effective_slug != "standings" and _effective_slug != _applied_slug and _modal_done:
        _eff_group, _eff_subpage = SLUG_TO_GROUP.get(_effective_slug, ("standings", None))
        st.session_state["nav_group"] = _eff_group
        if _eff_subpage:
            st.session_state[f"nav_sub_{_eff_group}"] = _eff_subpage
        st.session_state["jump_to_tab_index"] = GROUP_TAB_INDEX.get(_eff_group, 0)
        st.session_state["_deeplink_applied_slug"] = _effective_slug
        # Keep ?tab= in the URL so it can be bookmarked/shared

    # Top-level tabs
    tab_standings, tab_bracket, tab_scores, tab_bonus, tab_fun, tab_hoc = st.tabs([
        "🏆 Standings", "🗂️ Your Bracket", "📺 Schedule/Scores", "🎲 Bonus Games", "🎉 Fun Stats", "👑 Hall of Champions",
    ])

    import streamlit.components.v1 as _components

    # One-shot JS tab click — only fires when jump_to_tab_index is freshly set.
    _jump_tab = st.session_state.pop("jump_to_tab_index", None)
    if _jump_tab is not None:
        _components.html(
            f"""<script>
            (function() {{
                function clickTab() {{
                    var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
                    if (tabs.length > {_jump_tab}) {{
                        tabs[{_jump_tab}].click();
                    }} else {{
                        setTimeout(clickTab, 100);
                    }}
                }}
                setTimeout(clickTab, 300);
            }})();
            </script>""",
            height=1,
        )

    # ── Tab 1: Standings ──────────────────────────────────────────────────────
    with tab_standings:
        st.subheader("Live Standings")

        # Sub-navigation: Current / Potential
        _std_sub = st.session_state.get("nav_sub_standings", "current")
        _std_c1, _std_c2 = st.columns(2)
        if _std_c1.button("📊 Current", key="std_current", use_container_width=True,
                           type="primary" if _std_sub == "current" else "secondary"):
            st.session_state["nav_sub_standings"] = "current"
            st.rerun()
        if _std_c2.button("🔮 Potential", key="std_potential", use_container_width=True,
                           type="primary" if _std_sub == "potential" else "secondary"):
            st.session_state["nav_sub_standings"] = "potential"
            st.rerun()
        st.divider()
        _std_sub = st.session_state.get("nav_sub_standings", "current")

        col_left, col_right = st.columns([3, 2], gap="medium")

        # Detect mobile via user agent header (no JS needed, works reliably)
        try:
            _ua = st.context.headers.get("User-Agent", "")
        except Exception:
            _ua = ""
        _is_mobile = any(x in _ua.lower() for x in ("mobile", "android", "iphone", "ipad", "ipod"))

        def _short_name(full_name, all_names):
            """Return first name + last initial if another player shares the first name,
            otherwise just the first name. Falls back to full name if parsing fails."""
            parts = full_name.strip().split()
            if len(parts) < 2:
                return full_name
            first = parts[0]
            # Check if any other name shares the same first name
            same_first = [n for n in all_names if n != full_name and n.strip().split()[0] == first]
            if same_first:
                return f"{first} {parts[-1][0]}."
            return first

        _all_names = final_df["Name"].tolist()

        # ── Shared H2H row-click state ─────────────────────────────────────────
        if "nav_sub_standings" not in st.session_state:
            st.session_state["nav_sub_standings"] = "current"

        # ── Build lucky team lookup: name -> list of teams ──────────────────────
        _name_to_lucky = {}
        for _lt, _lparticipants in lucky_map.items():
            for _lp in _lparticipants:
                _name_to_lucky.setdefault(_lp, []).append(_lt)

        # ── Build correct picks count per person ─────────────────────────────────
        _correct_counts = {
            r["Name"]: sum(
                1 for c in range(3, 66)
                if not is_unplayed(actual_winners[c]) and r["raw_picks"][c] == actual_winners[c]
            ) for r in results
        }

        _picks_lookup = {r["Name"]: r["raw_picks"] for r in results}
        _ff_cols = [59, 60, 61, 62]

        with col_left:
            if _std_sub == "current":
                # ── Current standings: rich HTML table with logos ────────────────
                cur_df = final_df[["Current Rank", "Name", "Current Score"]].copy()
                cur_df = cur_df.rename(columns={"Current Rank": "Rank"})
                cur_df = cur_df.reset_index(drop=True)

                def _logo_tag(team, size=18, alive=True, block=False):
                    url = espn_logo_url(team) if team else None
                    opacity = "1" if alive else "0.35"
                    display = "display:block;" if block else "vertical-align:middle;"
                    if url:
                        return f'<img src="{url}" style="width:{size}px;height:{size}px;object-fit:contain;{display}opacity:{opacity};" onerror="this.style.display=&quot;none&quot;">'
                    return ""

                trs = ""
                for _, crow in cur_df.iterrows():
                    nm = crow["Name"]
                    is_user = user_name and nm == user_name
                    row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if is_user else ""
                    disp_nm = _short_name(nm, _all_names) if _is_mobile else nm

                    # Final Four logos — dim if eliminated, normal if still alive
                    _picks = _picks_lookup.get(nm, [])
                    _ff_logo_size = 20 if _is_mobile else 18
                    _ff_teams = [
                        _picks[c] for c in _ff_cols
                        if c < len(_picks) and _picks[c] not in {"", "nan", "TBD"}
                    ]
                    if _is_mobile:
                        # 2x2 grid — centered within cell
                        _row1 = "".join(_logo_tag(t, _ff_logo_size, t in truly_alive, block=True) for t in _ff_teams[:2])
                        _row2 = "".join(_logo_tag(t, _ff_logo_size, t in truly_alive, block=True) for t in _ff_teams[2:])
                        ff_logos = (
                            f'<div style="display:inline-flex;flex-direction:column;align-items:center;gap:2px;line-height:0;">'
                            f'<div style="display:flex;flex-direction:row;gap:2px;justify-content:center;">{_row1}</div>'
                            f'<div style="display:flex;flex-direction:row;gap:2px;justify-content:center;">{_row2}</div>'
                            f'</div>'
                        )
                    else:
                        ff_logos = "".join(_logo_tag(t, _ff_logo_size, t in truly_alive) for t in _ff_teams)

                    # Champion — green if alive, red + strikethrough if eliminated
                    _champ_pick = _picks[65] if len(_picks) > 65 and _picks[65] not in {"", "nan", "TBD"} else ""
                    if _champ_pick:
                        _champ_alive = _champ_pick in truly_alive
                        _champ_style = "color:#22c55e;" if _champ_alive else "color:#ef4444;text-decoration:line-through;"
                        if _is_mobile:
                            champ_html = (
                                f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">'
                                f'{_logo_tag(_champ_pick, 18, _champ_alive)}'
                                f'<span style="font-size:10px;{_champ_style}">{_champ_pick}</span>'
                                f'</div>'
                            )
                        else:
                            champ_html = (
                                f'{_logo_tag(_champ_pick, 16, _champ_alive)}'
                                f'<span style="font-size:11px;vertical-align:middle;{_champ_style}">{_champ_pick}</span>'
                            )
                    else:
                        champ_html = "—"

                    # Lucky Team
                    _lucky_teams = _name_to_lucky.get(nm, [])
                    if _lucky_teams:
                        lt = _lucky_teams[0]
                        lt_alive = lt in truly_alive
                        lt_style = "color:#22c55e;" if lt_alive else "color:#ef4444;text-decoration:line-through;"
                        if _is_mobile:
                            lucky_html = (
                                f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">'
                                f'{_logo_tag(lt, 18, lt_alive)}'
                                f'<span style="font-size:10px;{lt_style}">{lt}</span>'
                                f'</div>'
                            )
                        else:
                            lucky_html = f'{_logo_tag(lt, 16, lt_alive)}<span style="font-size:11px;vertical-align:middle;{lt_style}">{lt}</span>'
                    else:
                        lucky_html = "—"

                    correct = _correct_counts.get(nm, 0)
                    upset = next((r["Upset Correct"] for r in results if r["Name"] == nm), 0)
                    _ff_td_style = 'padding:4px 2px;text-align:center;overflow:visible;'
                    _lucky_td = f'<td style="padding:4px 6px;text-align:center;">{lucky_html}</td>' if not _is_mobile else ""
                    trs += (
                        f'<tr{row_style}>'
                        f'<td style="width:28px;text-align:center;padding:4px 2px;">{int(crow["Rank"])}</td>'
                        f'<td style="padding:4px 6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:{"70px" if _is_mobile else "120px"};">{disp_nm}</td>'
                        f'<td style="width:36px;text-align:center;padding:4px 2px;">{int(crow["Current Score"])}</td>'
                        f'<td style="width:28px;text-align:center;padding:4px 2px;">{correct}</td>'
                        f'<td style="width:28px;text-align:center;padding:4px 2px;">{upset}</td>'
                        f'<td style="{_ff_td_style}">{ff_logos}</td>'
                        f'<td style="padding:4px 6px;text-align:center;">{champ_html}</td>'
                        f'{_lucky_td}'
                        f'</tr>'
                    )
                _lucky_th = '' if _is_mobile else '<th style="padding:5px 6px;text-align:center;border:1px solid #313244;">Lucky Team</th>'
                st.markdown(
                    '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;">'
                    '<table style="border-collapse:collapse;width:100%;font-size:12px;">'
                    '<thead><tr style="background:#1e1e2e;color:#fff;">'
                    '<th style="width:28px;padding:5px 2px;text-align:center;border:1px solid #313244;">#</th>'
                    '<th style="padding:5px 6px;text-align:center;border:1px solid #313244;">Name</th>'
                    '<th style="width:36px;padding:5px 2px;text-align:center;border:1px solid #313244;">Pts</th>'
                    '<th style="width:28px;padding:5px 2px;text-align:center;border:1px solid #313244;">✓</th>'
                    '<th style="width:28px;padding:5px 2px;text-align:center;border:1px solid #313244;">😤</th>'
                    '<th style="padding:5px 4px;text-align:center;border:1px solid #313244;">F4</th>'
                    '<th style="padding:5px 6px;text-align:center;border:1px solid #313244;">Champion</th>'
                    + _lucky_th +
                    '</tr></thead>'
                    f'<tbody style="color:#fff;">{trs}</tbody>'
                    '</table></div>',
                    unsafe_allow_html=True
                )
                st.caption("💡 Tap a row in Potential view to open a Head-to-Head comparison")

            else:
                # ── Potential standings: existing AgGrid table ───────────────────
                display_cols = ["Current Rank", "Name", "Current Score",
                                "Potential Score", "Win %", "Top 3 %", "Potential Status"]
                def highlight_user_row(row):
                    if user_name and row["Name"] == user_name:
                        return ["background-color: #3a3000; color: #f5c518; font-weight: bold"] * len(row)
                    return [""] * len(row)

                standings_df = final_df[display_cols].copy()
                standings_df = standings_df.rename(columns={"Current Rank": "Rank"})
                standings_df["Win %"]   = final_df["Win %"].map("{:.1f}%".format)
                standings_df["Top 3 %"] = final_df["Top 3 %"].map("{:.1f}%".format)
                if _is_mobile:
                    standings_df["Name"] = standings_df["Name"].apply(lambda n: _short_name(n, _all_names))
                    standings_df["Potential Status"] = standings_df["Potential Status"].apply(
                        lambda s: s.split()[0] if isinstance(s, str) and s else s
                    )

                _user_display = _short_name(user_name, _all_names) if _is_mobile and user_name else user_name
                selected_row = show_table(
                    standings_df,
                    user_highlight_col="Name", user_highlight_val=_user_display,
                    key="table_standings",
                    height=500,
                    col_config={
                        "Rank":             50,
                        "Name":             90 if _is_mobile else 160,
                        "Current Score":    80,
                        "Potential Score":  85,
                        "Win %":            60,
                        "Top 3 %":         60,
                        "Potential Status": 45 if _is_mobile else 120,
                    },
                    pinned_cols=["Rank", "Name"],
                    return_selected=True,
                    nowrap_cols=["Name"],
                )

                if selected_row:
                    clicked_name_raw = selected_row.get("Name", "")
                    if _is_mobile and clicked_name_raw:
                        _short_to_full = {_short_name(n, _all_names): n for n in _all_names}
                        clicked_name = _short_to_full.get(clicked_name_raw, clicked_name_raw)
                    else:
                        clicked_name = clicked_name_raw
                    if (clicked_name and clicked_name != user_name
                            and clicked_name != st.session_state.get("_h2h_last_processed")):
                        st.session_state["_h2h_last_processed"] = clicked_name
                        p1_val = user_name or clicked_name
                        st.session_state["_h2h_p1_pending"] = p1_val
                        st.session_state["_h2h_p2_pending"] = clicked_name
                        st.session_state["_h2h_show_banner"] = True
                        st.rerun()

                _h2h_name = st.session_state.get("_h2h_last_processed")
                if st.session_state.get("_h2h_show_banner") and _h2h_name:
                    bcol1, bcol2 = st.columns([3, 1])
                    with bcol1:
                        st.info(f"⚔️ Ready to compare vs **{_h2h_name}**")
                    with bcol2:
                        if st.button("Go to Head-to-Head →", key="go_h2h_btn", use_container_width=True, type="primary"):
                            st.session_state["_h2h_show_banner"] = False
                            st.session_state["nav_group"] = "your-bracket"
                            st.session_state["nav_sub_your-bracket"] = "head-to-head"
                            st.session_state["jump_to_tab_index"] = 1
                            st.rerun()
                else:
                    st.caption("💡 Tap any row to open a Head-to-Head comparison")

        with col_right:
            top10 = final_df.head(10).sort_values("Current Score")

            fig = px.bar(
                top10, x="Current Score", y="Name", orientation="h",
                color="Current Score", color_continuous_scale="YlOrRd",
                title="Top 10 — Current Scores",
            )
            fig.update_layout(
                dragmode=False,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                coloraxis_showscale=False, margin=dict(l=0, r=0, t=40, b=0),
                height=380,
            )

            # Overlay 4 FF logos inside each horizontal bar
            # Champion pick (col 65) is shown larger and full opacity; others are dimmed
            _max_score = top10["Current Score"].max() or 1
            _images = []
            _shapes = []
            for _yi, (_idx, _row) in enumerate(top10.iterrows()):
                _picks = _picks_lookup.get(_row["Name"], [])
                _ff_teams = [_picks[c] for c in _ff_cols if c < len(_picks) and _picks[c] not in {"", "nan", "TBD"}]
                _champ = _picks[65] if len(_picks) > 65 and _picks[65] not in {"", "nan", "TBD"} else None
                _bar_len = _row["Current Score"]
                if _bar_len <= 0:
                    continue
                _n = len(_ff_teams)
                for _li, _team in enumerate(_ff_teams):
                    _logo = espn_logo_url(_team)
                    if not _logo:
                        continue
                    _x = _bar_len * (_li + 0.5) / max(_n, 1)
                    _is_champ = (_team == _champ)
                    _sizex  = _max_score * 0.115 if _is_champ else _max_score * 0.09
                    _sizey  = 0.75 if _is_champ else 0.55
                    _opac   = 1.0  if _is_champ else 0.55
                    _images.append(dict(
                        source=_logo,
                        xref="x", yref="y",
                        x=_x,
                        y=_yi,
                        sizex=_sizex,
                        sizey=_sizey,
                        xanchor="center", yanchor="middle",
                        layer="above",
                        opacity=_opac,
                    ))
                    # Gold circle outline behind champion logo via shape
                    if _is_champ:
                        _r = _max_score * 0.065
                        _shapes.append(dict(
                            type="circle",
                            xref="x", yref="y",
                            x0=_x - _r, x1=_x + _r,
                            y0=_yi - 0.4, y1=_yi + 0.4,
                            line=dict(color="#f5c518", width=2),
                            fillcolor="rgba(0,0,0,0)",
                            layer="above",
                        ))
            _layout_extra = {}
            if _images:
                _layout_extra["images"] = _images
            if _shapes:
                _layout_extra["shapes"] = _shapes
            if _layout_extra:
                fig.update_layout(**_layout_extra)

            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

    # ── Tab 2: Your Bracket (group) ───────────────────────────────────────────
    # ── Tab 2: Your Bracket (group) ───────────────────────────────────────────
    with tab_bracket:
        # Submenu buttons
        _sub_yb = st.session_state.get("nav_sub_your-bracket", "bracket")
        _yb_options = [
            ("bracket",        "🗂️ Bracket"),
            ("bracket-dna",    "🧬 Bracket DNA"),
            ("win-conditions", "🔍 Win Conditions"),
            ("head-to-head",   "⚔️ Head-to-Head"),
        ]
        _yb_row1 = st.columns(4)
        _yb_row2 = st.columns(1)
        for _i, (_slug, _label) in enumerate(_yb_options):
            _active = _sub_yb == _slug
            _yb_col = _yb_row1[_i] if _i < 4 else _yb_row2[0]
            if _yb_col.button(_label, key=f"yb_{_slug}",
                              use_container_width=True,
                              type="primary" if _active else "secondary"):
                st.session_state["nav_sub_your-bracket"] = _slug
                st.rerun()
        st.divider()
        _sub_yb = st.session_state.get("nav_sub_your-bracket", "bracket")

        if _sub_yb == "bracket":
            st.subheader("🗂️ Your Bracket")

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
                    champ_pick = p_picks[65] if len(p_picks) > 65 else ""
                    champ_pick = champ_pick if champ_pick and not is_unplayed(champ_pick) else "TBD"

                    # 2x2 stat card grid matching Lucky Team / H2H card style
                    logo_url = espn_logo_url(champ_pick)
                    champ_eliminated = champ_pick != "TBD" and champ_pick not in truly_alive
                    champ_color = "#ef4444" if champ_eliminated else "#f5c518"
                    champ_name_style = "text-decoration:line-through;" if champ_eliminated else ""
                    champ_suffix = " ❌" if champ_eliminated else ""
                    if champ_pick != "TBD" and logo_url:
                        champ_val_html = (
                            f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">'
                            f'<img src="{logo_url}" width="36" height="36" style="object-fit:contain;margin-bottom:4px;{"opacity:0.5;" if champ_eliminated else ""}">'
                            f'<div style="font-size:clamp(13px,3vw,16px);font-weight:700;color:{champ_color};line-height:1.1;">'
                            f'<span style="{champ_name_style}">{champ_pick}</span>{champ_suffix}</div>'
                            f'</div>'
                        )
                    elif champ_pick != "TBD":
                        champ_val_html = (
                            f'<div style="font-size:clamp(16px,3vw,20px);font-weight:700;color:{champ_color};line-height:1.1;">'
                            f'<span style="{champ_name_style}">{champ_pick}</span>{champ_suffix}</div>'
                        )
                    else:
                        champ_val_html = '<div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#9ca3af;line-height:1.1;">—</div>'

                    # Rank and Potential Status from final_df
                    p_df_row = final_df[final_df["Name"] == bracket_name]
                    if not p_df_row.empty:
                        p_rank          = int(p_df_row.iloc[0]["Current Rank"])
                        p_potential     = p_df_row.iloc[0]["Potential Status"]
                        total_players   = len(final_df)
                        rank_str        = f"#{p_rank} / {total_players}"
                    else:
                        rank_str    = "—"
                        p_potential = "—"
                    potential_color = (
                        "#f5c518" if "Champion"  in str(p_potential) else
                        "#60a5fa" if "Top 3"     in str(p_potential) else
                        "#ef4444" if "Out"       in str(p_potential) else
                        "#9ca3af"
                    )

                    accuracy_str = f"{correct/played_g*100:.0f}%" if played_g else "—"
                    st.markdown(
                        f'''<div style="display:flex;gap:6px;width:100%;box-sizing:border-box;margin-bottom:6px;">
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🏆 Current Score</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#4ade80;line-height:1.1;">{cur_score}</div>
  </div>
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🥇 Champion Pick</div>
    {champ_val_html}
  </div>
</div>
<div style="display:flex;gap:6px;width:100%;box-sizing:border-box;margin-bottom:6px;">
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">📊 Current Rank</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#ffffff;line-height:1.1;">{rank_str}</div>
  </div>
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🔮 Potential Status</div>
    <div style="font-size:clamp(20px,5vw,28px);font-weight:700;color:{potential_color};line-height:1.1;">{p_potential}</div>
  </div>
</div>
<div style="display:flex;gap:6px;width:100%;box-sizing:border-box;margin-bottom:12px;">
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">✅ Correct Picks</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#60a5fa;line-height:1.1;">{correct} / {played_g}</div>
  </div>
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🎯 Accuracy</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#c084fc;line-height:1.1;">{accuracy_str}</div>
  </div>
</div>''',
                        unsafe_allow_html=True
                    )

                    # ── Bonus Chances card ────────────────────────────────────
                    # Compute per-player data for every bonus game category.
                    p_df_me = final_df[final_df["Name"] == bracket_name].iloc[0]

                    # Helper: score over a column range for a single picks list
                    def score_range(picks, col_start, col_end):
                        return sum(
                            points_per_game[c] + seed_map.get(picks[c], 0)
                            for c in range(col_start, col_end)
                            if not is_unplayed(actual_winners[c]) and picks[c] == actual_winners[c]
                        )

                    # Helper: potential score over a col range (played + unplayed alive)
                    def potential_range(picks, col_start, col_end):
                        return sum(
                            points_per_game[c] + seed_map.get(picks[c], 0)
                            for c in range(col_start, col_end)
                            if picks[c] == actual_winners[c] or
                               (is_unplayed(actual_winners[c]) and picks[c] in all_alive)
                        )

                    # Helper: correct upset picks (winner seed - loser seed >= 3)
                    def count_upsets(picks):
                        total = 0
                        for c in range(3, 66):
                            winner = actual_winners[c]
                            if is_unplayed(winner) or picks[c] != winner:
                                continue
                            loser = defeated_map.get(winner, "")
                            w_seed = seed_map.get(winner, 0)
                            l_seed = seed_map.get(loser, 0)
                            if l_seed > 0 and w_seed > 0 and (w_seed - l_seed) >= 3:
                                total += 1
                        return total

                    # Helper: could an unplayed slot still produce an upset?
                    # A slot can produce an upset if at least one alive team seeded 4+
                    # could face an alive team seeded 3+ lower than them.
                    # Conservatively: if any alive team in the slot's pick is a lower seed
                    # (seed >= 4) and there exists any alive higher-seed team (seed diff >= 3),
                    # then an upset is still possible in that slot.
                    def slot_can_produce_upset(c):
                        if not is_unplayed(actual_winners[c]):
                            return False
                        # Get seeds of all alive teams — use all_starting seeds too
                        alive_seeds = [seed_map.get(t, 0) for t in truly_alive if seed_map.get(t, 0) > 0]
                        if len(alive_seeds) < 2:
                            return False
                        return (max(alive_seeds) - min(alive_seeds)) >= 3

                    # Helper: potential upsets (earned + future slots where pick is alive
                    # and the slot could still produce an upset with seed diff >= 3)
                    def potential_upsets(picks):
                        earned = count_upsets(picks)
                        # Future potential: for each alive team that could still produce an upset,
                        # check if this person picked that team to win in ANY future slot.
                        # We don't care who they picked them to face — just whether they picked them.
                        future = 0
                        # Find all alive teams that can still produce an upset (seed diff >= 3 vs any alive opponent)
                        _potential_upset_teams = set()
                        for team in truly_alive:
                            t_seed = seed_map.get(team, 0)
                            if t_seed < 4:
                                continue
                            can_upset = any(
                                seed_map.get(opp, 0) > 0 and t_seed - seed_map.get(opp, 0) >= 3
                                for opp in truly_alive if opp != team
                            )
                            if can_upset:
                                _potential_upset_teams.add(team)
                        # Count how many of this person's future picks are potential upset teams
                        _counted = set()  # avoid double-counting same team in multiple slots
                        for c in range(3, 66):
                            if not is_unplayed(actual_winners[c]):
                                continue
                            team = picks[c]
                            if not team or team in UNPLAYED:
                                continue
                            if team in _potential_upset_teams and team not in _counted:
                                future += 1
                                _counted.add(team)
                        return earned + future

                    # Gather all participants' data for comparisons
                    all_rows = []
                    for idx in range(3, len(df_p)):
                        row = df_p.iloc[idx]
                        nm = str(row[0]).strip()
                        if not nm or nm in {"Winner", ""} or nm.lower() == "nan":
                            continue
                        pk = [str(row[c]).strip() if c < len(row) else "" for c in range(67)]
                        all_rows.append((nm, pk))

                    me_picks = p_picks  # already built above

                    # ── 1) Leader After First Weekend (R1+R2, cols 3-50) ─────
                    # First weekend = R1 (3-34) + R2 (35-50)
                    r1r2_end = 51
                    all_r1r2_complete = all(
                        not is_unplayed(actual_winners[c]) for c in range(3, r1r2_end)
                    )
                    my_r1r2 = score_range(me_picks, 3, r1r2_end)
                    my_r1r2_pot = potential_range(me_picks, 3, r1r2_end)
                    others_r1r2_max = max(
                        score_range(pk, 3, r1r2_end) if all_r1r2_complete
                        else score_range(pk, 3, r1r2_end)
                        for nm, pk in all_rows if nm != bracket_name
                    ) if len(all_rows) > 1 else 0
                    others_r1r2_cur_max = max(
                        score_range(pk, 3, r1r2_end) for nm, pk in all_rows if nm != bracket_name
                    ) if len(all_rows) > 1 else 0
                    if all_r1r2_complete:
                        can_first_weekend = my_r1r2 >= others_r1r2_cur_max
                    else:
                        can_first_weekend = my_r1r2_pot >= others_r1r2_cur_max

                    # ── 2) Leader After Second Weekend (R1-E8, cols 3-62) ────
                    e8_end = 63
                    all_e8_complete = all(
                        not is_unplayed(actual_winners[c]) for c in range(3, e8_end)
                    )
                    my_e8 = score_range(me_picks, 3, e8_end)
                    my_e8_pot = potential_range(me_picks, 3, e8_end)
                    others_e8_cur_max = max(
                        score_range(pk, 3, e8_end) for nm, pk in all_rows if nm != bracket_name
                    ) if len(all_rows) > 1 else 0
                    if all_e8_complete:
                        can_second_weekend = my_e8 >= others_e8_cur_max
                    else:
                        can_second_weekend = my_e8_pot >= others_e8_cur_max

                    # ── 3) Total Correct Picks ───────────────────────────────
                    # Until R2 is complete, everyone stays green — too early to judge.
                    # After R2, compare potentials properly.
                    def correct_potential(picks):
                        return sum(
                            1 for c in range(3, 66)
                            if (not is_unplayed(actual_winners[c]) and picks[c] == actual_winners[c])
                            or (is_unplayed(actual_winners[c]) and picks[c] in all_alive)
                        )
                    if not r2_complete:
                        can_most_correct = True
                    else:
                        my_correct_pot = correct_potential(me_picks)
                        others_correct_pot_max = max(
                            correct_potential(pk) for nm, pk in all_rows if nm != bracket_name
                        ) if len(all_rows) > 1 else 0
                        can_most_correct = my_correct_pot >= others_correct_pot_max

                    # ── 4) Most Correct Upset Picks ──────────────────────────
                    # Until R2 is complete, everyone stays green — too early to judge.
                    if not r2_complete:
                        can_most_upsets = True
                    else:
                        any_upset_possible = any(slot_can_produce_upset(c) for c in range(3, 66))
                        if any_upset_possible:
                            my_upset_pot = potential_upsets(me_picks)
                            others_upset_pot_max = max(
                                potential_upsets(pk) for nm, pk in all_rows if nm != bracket_name
                            ) if len(all_rows) > 1 else 0
                            can_most_upsets = my_upset_pot >= others_upset_pot_max
                        else:
                            my_upsets = count_upsets(me_picks)
                            others_upset_max = max(
                                count_upsets(pk) for nm, pk in all_rows if nm != bracket_name
                            ) if len(all_rows) > 1 else 0
                            can_most_upsets = my_upsets >= others_upset_max

                    # ── 5) Tiebreaker ─────────────────────────────────────────
                    champ_played = not is_unplayed(actual_winners[65])
                    if final_score is None:
                        # Final score not yet entered — everyone still has a chance
                        can_tiebreaker = True
                    else:
                        # Find the closest guess(es)
                        my_guess = tiebreaker_guesses.get(bracket_name)
                        if my_guess is None:
                            can_tiebreaker = False
                        else:
                            my_diff = abs(my_guess - final_score)
                            best_diff = min(
                                abs(g - final_score) for g in tiebreaker_guesses.values()
                            )
                            can_tiebreaker = my_diff == best_diff

                    # ── 6) Lucky Team ─────────────────────────────────────────
                    my_lucky_teams = [t for t, ps in lucky_map.items() if bracket_name in ps]
                    can_lucky = any(t in truly_alive for t in my_lucky_teams)

                    # ── 7) Last Place ─────────────────────────────────────────
                    # I can finish last if my current score (my floor — can't lose points)
                    # is <= every other player's maximum possible score (their ceiling).
                    # The only way I CANNOT finish last is if my current score is already
                    # strictly greater than at least one other player's ceiling — meaning
                    # that player will definitely finish below me no matter what.
                    my_score = int(p_df_me["Current Score"])
                    all_games_done = all(not is_unplayed(actual_winners[c]) for c in range(3, 66))
                    others_ceilings = [
                        potential_range(pk, 3, 66)
                        for nm, pk in all_rows if nm != bracket_name
                    ]
                    if all_games_done:
                        others_final = [
                            int(final_df[final_df["Name"] == nm].iloc[0]["Current Score"])
                            for nm, _ in all_rows if nm != bracket_name
                            and not final_df[final_df["Name"] == nm].empty
                        ]
                        can_last_place = my_score <= min(others_final) if others_final else True
                    else:
                        # Can finish last unless someone else's ceiling is below my floor
                        can_last_place = my_score <= min(others_ceilings) if others_ceilings else True

                    # ── 8) Regional Winner ────────────────────────────────────
                    regions_can_win = []
                    for reg in ["West", "East", "South", "Midwest"]:
                        my_reg_score = int(p_df_me.get(f"{reg} Score", 0))
                        my_reg_pot = my_reg_score + sum(
                            points_per_game[c] + seed_map.get(me_picks[c], 0)
                            for c in range(3, 63)
                            if is_unplayed(actual_winners[c])
                            and me_picks[c] in all_alive
                            and slot_to_region.get(c) == reg
                        )
                        others_reg_cur_max = max(
                            (int(final_df[final_df["Name"] == nm].iloc[0].get(f"{reg} Score", 0))
                             if not final_df[final_df["Name"] == nm].empty else 0)
                            for nm, _ in all_rows if nm != bracket_name
                        ) if len(all_rows) > 1 else 0
                        if my_reg_pot >= others_reg_cur_max:
                            regions_can_win.append(reg)

                    # ── Build pill HTML ───────────────────────────────────────
                    pills_html = "".join([
                        pill("1st Place",             p_potential == "🏆 Champion"),
                        pill("Top 3",                 p_potential in ("🏆 Champion", "🥉 Top 3")),
                        pill("1st Weekend Leader",    can_first_weekend),
                        pill("2nd Weekend Leader",    can_second_weekend),
                        pill("Most Correct Picks",    can_most_correct),
                        pill("Most Upset Picks",      can_most_upsets),
                        *[pill(f"{r} Region",         True) for r in regions_can_win],
                        *[pill(f"{r} Region",         False)
                          for r in ["West","East","South","Midwest"] if r not in regions_can_win],
                        pill("Lucky Team",            can_lucky),
                        pill("Tiebreaker",            can_tiebreaker),
                        pill("Last Place",            can_last_place),
                    ])

                    st.markdown(
                        f'''<div style="background:#1e1e2e;border:1px solid #313244;border-radius:10px;
padding:clamp(10px,2.5vw,16px);width:100%;box-sizing:border-box;margin-bottom:12px;">
  <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:10px;text-align:center;">
    🎯 Still in the Hunt
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;">
    {pills_html}
  </div>
</div>''',
                        unsafe_allow_html=True
                    )

                    # Column → region mapping for the 2025 bracket picks sheet.
                    # Cols 3-10=East, 11-18=South, 19-26=West, 27-34=Midwest.
                    # FF: 63 (East/South side), 64 (West/Midwest side)  Champ: 65
                    RCOLS = {
                        "East":    {"r1": list(range(3,11)),  "r2": list(range(35,39)), "s16":[51,52], "e8":[59]},
                        "South":   {"r1": list(range(11,19)), "r2": list(range(39,43)), "s16":[53,54], "e8":[60]},
                        "West":    {"r1": list(range(19,27)), "r2": list(range(43,47)), "s16":[55,56], "e8":[61]},
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
                            is_my_pick = (pick == team)
                            if played:
                                # Game has been decided
                                if team == actual:
                                    # This team won — correct pick
                                    cls = "tr correct" if is_my_pick else "tr won"
                                elif is_my_pick:
                                    # My pick lost this game — wrong pick
                                    cls = "tr wrong"
                                    bust = f'<span class="bust">&#8594;{actual}</span>'
                                else:
                                    # Someone else lost, not my pick
                                    cls = "tr out"
                            else:
                                # Game hasn't happened yet
                                if is_my_pick:
                                    if team not in truly_alive:
                                        # My future pick is already eliminated — wrong pick
                                        cls = "tr wrong"
                                    else:
                                        # My future pick is still alive
                                        cls = "tr future"
                                else:
                                    cls = "tr live"
                        else:
                            cls = "tr"
                        logo_url = espn_logo_url(team)
                        logo_html = (f'<img src="{logo_url}" class="tlogo" onerror="this.style.display=&quot;none&quot;">' if logo_url else '')
                        if mirror:
                            return f'<div class="{cls}">{bust}<span class="sd">{sd}</span>{logo_html}<span class="tn">{team}</span></div>'
                        return f'<div class="{cls}"><span class="sd">{sd}</span>{logo_html}<span class="tn">{team}</span>{bust}</div>'

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
                            # Always show the player's own pick — actual winner only affects highlighting
                            t = pk if pk and pk not in UNPLAYED else "TBD"
                            return f'<div class="matchup single">{trow(t, pk, ac, pl, mirror)}</div>'

                        # ── 1) First Round & Round-of-32 column ─────────────────────────
                        # Each R1 game occupies 3 grid rows (span 3).
                        # The R2 winner sits in the middle row of that same 3-row block.
                        for g, c in enumerate(r1_cols):
                            row_start = 4 * g + 1
                            team_a, team_b = r1_matchups.get(c, ("TBD", "TBD"))
                            r1_html = mu(c, team_a, team_b)
                            cells.append(
                                f'<div class="cell r1" '
                                f'style="grid-column:{col_r1}; grid-row:{row_start} / span 3;">'
                                f'{r1_html}</div>'
                            )

                            # R2 winner sits in the middle row of this R1 block
                            r2_html = single_from_col(c)
                            cells.append(
                                f'<div class="cell r2" '
                                f'style="grid-column:{col_r2}; grid-row:{row_start + 1};">'
                                f'{r2_html}</div>'
                            )

                        # ── 2) Sweet 16 column ──────────────────────────────────────────
                        # 4 S16 slots per region; each centered between two R2 rows.
                        # R2 rows are at positions 4g+2 (g=0..7).
                        # S16 slot h (0..3) sits between R2 rows of games 2h and 2h+1:
                        #   row_s16 = 8*h + 1  (span 7 covers both R2 rows)
                        for h, c in enumerate(r2_cols):
                            row_s16 = 8 * h + 1
                            s16_html = single_from_col(c)
                            cells.append(
                                f'<div class="cell s16" '
                                f'style="grid-column:{col_s16}; grid-row:{row_s16} / span 7;">'
                                f'{s16_html}</div>'
                            )

                        # ── 3) Elite 8 column ───────────────────────────────────────────
                        # 2 E8 slots per region; each centered between two S16 rows.
                        # E8 slot e sits between S16 rows 2e and 2e+1:
                        #   row_e8 = 16*e + 1  (span 15 covers both S16 rows)
                        for e, c in enumerate(s16_cols):
                            row_e8 = 16 * e + 1
                            e8_html = single_from_col(c)
                            cells.append(
                                f'<div class="cell e8" '
                                f'style="grid-column:{col_e8}; grid-row:{row_e8} / span 15;">'
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
                            # Always show the player's own pick
                            t = pk if pk and pk not in UNPLAYED else "TBD"
                            return t, pk, ac, pl

                        # Left side Final Four: West + East regional winners
                        ff_left_cols  = RCOLS["West"]["e8"] + RCOLS["East"]["e8"]
                        # Right side Final Four: South + Midwest regional winners
                        ff_right_cols = RCOLS["South"]["e8"] + RCOLS["Midwest"]["e8"]

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
                        tl = pk_l if pk_l and pk_l not in UNPLAYED else "TBD"
                        tr = pk_r if pk_r and pk_r not in UNPLAYED else "TBD"

                        ch_left  = f'<div class="matchup single champ-mu">{trow(tl, pk_l, ac_l, pl_l)}</div>'
                        ch_right = f'<div class="matchup single champ-mu">{trow(tr, pk_r, ac_r, pl_r, mirror=True)}</div>'

                        # Champion pick label at top of finals column
                        champ_team = p_picks[65] if len(p_picks) > 65 and not is_unplayed(p_picks[65]) else "TBD"
                        champ_logo_url = espn_logo_url(champ_team) if champ_team != "TBD" else None
                        champ_elim = champ_team != "TBD" and champ_team not in truly_alive
                        champ_color = "#ef4444" if champ_elim else "#f5c518"
                        champ_strike = "text-decoration:line-through;" if champ_elim else ""
                        if champ_logo_url:
                            champ_logo_tag = f'<img src="{champ_logo_url}" style="width:28px;height:28px;object-fit:contain;{"opacity:0.5;" if champ_elim else ""}margin-bottom:3px;">'
                        else:
                            champ_logo_tag = ""
                        champ_pick_html = (
                            f'<div style="display:flex;flex-direction:column;align-items:center;'
                            f'background:#1a1400;border:1px solid #7c5c00;border-radius:6px;'
                            f'padding:5px 4px;margin-bottom:6px;width:100%;box-sizing:border-box;">'
                            f'<div style="font-size:7px;font-weight:700;color:#9ca3af;letter-spacing:.8px;'
                            f'text-transform:uppercase;margin-bottom:3px;">My Pick</div>'
                            f'{champ_logo_tag}'
                            f'<div style="font-size:10px;font-weight:700;color:{champ_color};text-align:center;'
                            f'line-height:1.2;"><span style="{champ_strike}">{champ_team}</span></div>'
                            f'</div>'
                        )

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
                        return (f'<div class="finals">'
                                f'<div style="width:100%;padding:0 2px;box-sizing:border-box;">{champ_pick_html}</div>'
                                f'<div style="flex:1;display:flex;flex-direction:column;justify-content:center;gap:8px;">'
                                f'{fl}{ch}{fr}'
                                f'</div>'
                                f'</div>')

                    # West: top-left, flowing left→center (no mirror)
                    # East: bottom-left, flowing left→center (no mirror)
                    # South: top-right, flowing right→center (mirror)
                    # Midwest: bottom-right, flowing right→center (mirror)
                    west_h    = build_region("EAST",    RCOLS["East"])
                    east_h    = build_region("SOUTH",   RCOLS["South"])
                    south_h   = build_region("WEST",    RCOLS["West"],    mirror=True)
                    midwest_h = build_region("MIDWEST", RCOLS["Midwest"], mirror=True)
                    finals_h  = build_finals()

                    HTML = f"""<!DOCTYPE html>
    <html><head><meta charset="utf-8"><style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    body{{background:#0d0f14;color:#9ca3af;font-family:'Segoe UI',Arial,sans-serif;font-size:11px;padding:8px;overflow-x:auto;-webkit-overflow-scrolling:touch;}}
    .bracket{{display:flex;flex-direction:row;align-items:stretch;justify-content:flex-start;min-width:980px;}}
    .left-side,.right-side{{display:flex;flex-direction:column;flex:0 0 auto;}}
    .finals{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:0 8px;width:140px;flex-shrink:0;}}
    .region{{display:flex;flex-direction:column;flex:1;}}
    .rgn-name{{font-size:9px;font-weight:800;letter-spacing:1.5px;color:#374151;text-align:center;padding:1px 0 1px;text-transform:uppercase;border-bottom:1px solid #1a1f2b;margin-bottom:1px;}}
    .region-body.grid-region{{display:grid;grid-template-rows:repeat(8,18px 18px 18px 2px);grid-template-columns:118px 106px 98px 90px;column-gap:10px;flex:1;}}
    .right-side .region-body.grid-region{{grid-template-columns:90px 98px 106px 118px;}}
    .cell{{display:flex;align-items:center;}}
    .cell .matchup{{height:100%;display:flex;flex-direction:column;justify-content:flex-start;width:100%;}}
    .cell .matchup.single{{justify-content:center;margin-top:-16px;}}
    .rlbl{{font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.6px;color:#374151;text-align:center;padding-bottom:3px;}}
    .ff-lbl{{color:#4b5563;font-size:9px;}}
    .matchup{{position:relative;}}
    .matchup.single{{display:flex;align-items:center;}}
    .mdiv{{height:1px;background:#1a1f2b;}}
    .tr{{display:flex;align-items:center;gap:3px;padding:1px 4px 1px 5px;height:16px;
      border:1px solid #1a1f2b;overflow:hidden;background:#0d0f14;}}
    .tr+.tr{{border-top:none;}}
    .sd{{font-size:11px;color:#9ca3af;min-width:14px;text-align:right;flex-shrink:0;}}
    .tlogo{{width:12px;height:12px;object-fit:contain;flex-shrink:0;margin:0 2px;}}
    .tn{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#d1d5db;font-size:13px;}}
    .bust{{font-size:8px;color:#f87171;flex-shrink:0;margin-left:1px;white-space:nowrap;}}
    .tbd .tn{{color:#6b7280;font-style:italic;}}
    .won{{background:#052e16 !important;border-color:#14532d !important;}}
    .won .tn{{color:#d1d5db;}}
    .correct{{background:#14532d !important;border-color:#16a34a !important;}}
    .correct .tn{{color:#d1fae5 !important;font-weight:700;}}
    .wrong{{background:#2d0a0a !important;border-color:#7f1d1d !important;}}
    .wrong .tn{{color:#fca5a5 !important;font-weight:700;}}
    .future{{background:#0d0d0d !important;border-color:#555 !important;}}
    .future .tn{{color:#e5e7eb !important;font-weight:700;}}
    .out .tn{{color:#6b7280;}}
    .live .tn{{color:#9ca3af;}}

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
    .champ-mu .correct{{background:#78350f !important;}}
    .champ-mu .correct .tn{{color:#fde68a !important;}}
    .legend{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;font-size:10px;color:#6b7280;align-items:center;}}
    .leg{{display:flex;align-items:center;gap:4px;}}
    .ld{{width:10px;height:10px;border-radius:2px;flex-shrink:0;}}
    </style></head><body>
    <div class="legend">
      <div class="leg"><div class="ld" style="background:#14532d;border:1px solid #16a34a"></div><span style="color:#4ade80">✓ Correct pick</span></div>
      <div class="leg"><div class="ld" style="background:#2d0a0a;border:1px solid #7f1d1d"></div><span style="color:#ef4444">✗ Wrong / eliminated</span></div>
      <div class="leg"><div class="ld" style="background:#0d0d0d;border:1px solid #555"></div><span style="color:#ffffff">Future pick (alive)</span></div>
    </div>
    <div class="bracket">
      <div class="left-side">{west_h}{east_h}</div>
      {finals_h}
      <div class="right-side">{south_h}{midwest_h}</div>
    </div>
    </body></html>"""

                    import streamlit.components.v1 as components
                    st.caption("💡 Scroll horizontally to view the full bracket")
                    components.html(HTML, height=1005, scrolling=True)

        elif _sub_yb == "win-conditions":
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
                    st.dataframe(swing_df, use_container_width=True, hide_index=True)
                else:
                    st.success("No divergent unplayed games vs. your closest rivals.")

        elif _sub_yb == "head-to-head":
            st.subheader("⚔️ Head-to-Head Comparison")

            h2h_opts = ["— select —"] + name_opts
            PLAYER_COLORS = ["#4fc3f7", "#f5c518", "#fb923c", "#c084fc"]  # blue, yellow, orange, purple
            PLAYER_ICONS  = ["🔵", "🟡", "🟠", "🟣"]
            _name_lower = {n.lower(): n for n in name_opts}

            # Apply query params p1–p4 on first load
            if "h2h_qp_applied" not in st.session_state:
                st.session_state["h2h_qp_applied"] = True
                try:
                    for _qi, _qk in enumerate(["p1","p2","p3","p4"]):
                        _qv = st.query_params.get(_qk, "")
                        if _qv:
                            _m = _name_lower.get(_qv.lower(), "")
                            if _m:
                                st.session_state[f"_h2h_p{_qi+1}_cur"] = _m
                    for _qk in ["p1","p2","p3","p4"]:
                        st.query_params.pop(_qk, None)
                except Exception:
                    pass

            # Apply pending values from standings click
            if "_h2h_p1_pending" in st.session_state:
                st.session_state["_h2h_p1_cur"] = st.session_state.pop("_h2h_p1_pending")
            if "_h2h_p2_pending" in st.session_state:
                st.session_state["_h2h_p2_cur"] = st.session_state.pop("_h2h_p2_pending")

            # P1 always defaults to current user (overrides stale session state)
            if user_name and user_name in h2h_opts:
                _p1_default = st.session_state.get("_h2h_p1_cur", user_name)
                if not _p1_default or _p1_default not in h2h_opts:
                    _p1_default = user_name
            else:
                _p1_default = st.session_state.get("_h2h_p1_cur", "— select —")
                if _p1_default not in h2h_opts:
                    _p1_default = "— select —"

            _p_defaults = [_p1_default]
            for _pi in range(1, 4):
                _pval = st.session_state.get(f"_h2h_p{_pi+1}_cur", "— select —")
                if _pval not in h2h_opts:
                    _pval = "— select —"
                _p_defaults.append(_pval)

            _sel_cols = st.columns(4)
            _sel_names = []
            for _pi in range(4):
                _sel = _sel_cols[_pi].selectbox(
                    f"Player {_pi+1}", h2h_opts,
                    index=h2h_opts.index(_p_defaults[_pi]),
                    key=f"_h2h_sel_p{_pi+1}"
                )
                st.session_state[f"_h2h_p{_pi+1}_cur"] = _sel
                _sel_names.append(_sel)

            # Deduplicate
            _players, _seen = [], set()
            for _n in _sel_names:
                if _n != "— select —" and _n not in _seen:
                    _players.append(_n)
                    _seen.add(_n)

            if len(_players) < 2:
                st.info("Select at least 2 players to compare.")
            else:
                _pdata = [final_df[final_df["Name"] == n].iloc[0].to_dict() for n in _players]
                _np = len(_players)
                _max_score = max(p["Current Score"] for p in _pdata)

                # ── Stat cards (3-4 players only; 2-player has dedicated layout below) ──
                if _np > 2:
                    _cards_html = '<div style="display:flex;gap:6px;width:100%;margin-bottom:12px;">'
                    for _pi, (n, p) in enumerate(zip(_players, _pdata)):
                        _col = PLAYER_COLORS[_pi]
                        _ico = PLAYER_ICONS[_pi]
                        _delta = p["Current Score"] - _max_score
                        _delta_str = f"{_delta}" if _delta < 0 else ("+0" if _delta == 0 else f"+{_delta}")
                        _dcol = "#888" if _delta == 0 else ("#4caf50" if _delta > 0 else "#f44336")
                        _cards_html += (
                            f'<div style="flex:1;background:#1e1e2e;border:1px solid #313244;'
                            f'border-radius:10px;padding:10px;min-width:0;">'
                            f'<div style="font-size:clamp(11px,3vw,15px);color:{_col};font-weight:600;'
                            f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-bottom:4px;">'
                            f'{_ico} {n}</div>'
                            f'<div style="font-size:11px;color:#888;">Rank</div>'
                            f'<div style="font-size:clamp(18px,5vw,26px);font-weight:700;color:#fff;line-height:1.1;">#{int(p["Current Rank"])}</div>'
                            f'<div style="font-size:11px;color:#888;margin-top:4px;">Score</div>'
                            f'<div style="font-size:clamp(18px,5vw,26px);font-weight:700;color:#fff;line-height:1.1;">{p["Current Score"]}</div>'
                            f'<div style="font-size:12px;color:{_dcol};font-weight:600;">{_delta_str}</div>'
                            f'</div>'
                        )
                    _cards_html += '</div>'
                    st.markdown(_cards_html, unsafe_allow_html=True)

                # ── Shared picks (2-player only) ─────────────────────────────
                if _np == 2:
                    p1_name, p2_name = _players[0], _players[1]
                    p1, p2 = _pdata[0], _pdata[1]
                    h2h = head_to_head(p1, p2, actual_winners, points_per_game, seed_map)
                    p1_delta = p1["Current Score"] - p2["Current Score"]
                    p2_delta = -p1_delta
                    p1_delta_str = f"+{p1_delta}" if p1_delta >= 0 else str(p1_delta)
                    p2_delta_str = f"+{p2_delta}" if p2_delta >= 0 else str(p2_delta)
                    p1_dcol = "#4caf50" if p1_delta > 0 else ("#f44336" if p1_delta < 0 else "#888")
                    p2_dcol = "#4caf50" if p2_delta > 0 else ("#f44336" if p2_delta < 0 else "#888")
                    st.markdown(f"""
                    <div style="display:flex;gap:6px;width:100%;margin-bottom:12px;">
                      <div style="flex:2;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;">
                        <div style="font-size:clamp(14px,4vw,18px);color:#4fc3f7;font-weight:600;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">🔵 {p1_name}</div>
                        <div style="display:flex;gap:6px;">
                          <div style="flex:1;min-width:0;"><div style="font-size:clamp(11px,2.5vw,13px);color:#888;">Rank</div><div style="font-size:clamp(24px,6vw,32px);font-weight:700;color:#fff;line-height:1.1;">#{int(p1["Current Rank"])}</div></div>
                          <div style="flex:1;min-width:0;"><div style="font-size:clamp(11px,2.5vw,13px);color:#888;">Score</div><div style="font-size:clamp(24px,6vw,32px);font-weight:700;color:#fff;line-height:1.1;">{p1["Current Score"]}</div><div style="font-size:clamp(12px,2.8vw,15px);color:{p1_dcol};font-weight:600;">{p1_delta_str}</div></div>
                        </div>
                      </div>
                      <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
                        <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:2px;">🤝 Shared</div>
                        <div style="font-size:clamp(10px,2.2vw,12px);color:#666;margin-bottom:6px;">same pick,<br>both correct</div>
                        <div style="font-size:clamp(26px,6.5vw,36px);font-weight:700;color:#fff;line-height:1.1;">{h2h["shared_pts"]}</div>
                      </div>
                      <div style="flex:2;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;">
                        <div style="font-size:clamp(14px,4vw,18px);color:#f5c518;font-weight:600;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">🟡 {p2_name}</div>
                        <div style="display:flex;gap:6px;">
                          <div style="flex:1;min-width:0;"><div style="font-size:clamp(11px,2.5vw,13px);color:#888;">Score</div><div style="font-size:clamp(24px,6vw,32px);font-weight:700;color:#fff;line-height:1.1;">{p2["Current Score"]}</div><div style="font-size:clamp(12px,2.8vw,15px);color:{p2_dcol};font-weight:600;">{p2_delta_str}</div></div>
                          <div style="flex:1;min-width:0;"><div style="font-size:clamp(11px,2.5vw,13px);color:#888;">Rank</div><div style="font-size:clamp(24px,6vw,32px);font-weight:700;color:#fff;line-height:1.1;">#{int(p2["Current Rank"])}</div></div>
                        </div>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

                # ── Charts ───────────────────────────────────────────────────
                _chart_titles = ["Pool Win %", "Top 3 Finish %"]
                _chart_dicts  = [win_probs, top3_probs]

                if _np == 2:
                    # 1v1 + pool win% + top3%
                    h2h_p1_pct, h2h_p2_pct, h2h_tie_pct = run_h2h_monte_carlo(
                        p1_name, p2_name,
                        tuple(p1["raw_picks"]), tuple(p2["raw_picks"]),
                        tuple(actual_winners), tuple(points_per_game),
                        tuple(all_alive), tuple(seed_map.items()),
                        r1_contestants,
                    )
                    _chart_cols = st.columns(3)
                    for _ci, (_title, _ys, _cap) in enumerate([
                        ("1v1 Win Probability", [h2h_p1_pct, h2h_p2_pct],
                         f"Ties: {h2h_tie_pct:.1f}%" if h2h_tie_pct > 0 else None),
                        ("Pool Win %", [win_probs.get(n, 0) for n in _players], "1,000 Monte Carlo simulations"),
                        ("Top 3 Finish %", [top3_probs.get(n, 0) for n in _players], "1,000 Monte Carlo simulations"),
                    ]):
                        with _chart_cols[_ci]:
                            fig = go.Figure(go.Bar(
                                x=_players, y=_ys,
                                marker_color=PLAYER_COLORS[:_np],
                                text=[f"{v:.1f}%" for v in _ys],
                                textposition="outside",
                            ))
                            fig.update_layout(dragmode=False, title=_title, yaxis_range=[0,100], height=165,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                margin=dict(l=0,r=0,t=36,b=0), xaxis=dict(tickfont=dict(size=9)), font=dict(size=10))
                            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
                            if _cap:
                                st.caption(_cap)
                else:
                    # 3-4 players: all 3 charts showing all players together
                    _chart_cols = st.columns(3)
                    _pool_ys = [win_probs.get(n, 0) for n in _players]
                    _top3_ys = [top3_probs.get(n, 0) for n in _players]

                    # N-way H2H: single simulation, winner takes all each run
                    _h2h_result = run_nway_monte_carlo(
                        _players,
                        [tuple(p["raw_picks"]) for p in _pdata],
                        tuple(actual_winners), tuple(points_per_game),
                        tuple(all_alive), tuple(seed_map.items()),
                        r1_contestants,
                    )
                    _h2h_ys = [round(_h2h_result.get(n, 0), 1) for n in _players]

                    for _ci, (_title, _ys, _cap) in enumerate([
                        ("Head-to-Head Win %", _h2h_ys, "1v1v1 — ignoring all other pool participants"),
                        ("Pool Win %", _pool_ys, "1,000 Monte Carlo simulations"),
                        ("Top 3 Finish %", _top3_ys, "1,000 Monte Carlo simulations"),
                    ]):
                        with _chart_cols[_ci]:
                            fig = go.Figure(go.Bar(
                                x=_players, y=_ys,
                                marker_color=PLAYER_COLORS[:_np],
                                text=[f"{v:.1f}%" for v in _ys],
                                textposition="outside",
                            ))
                            fig.update_layout(dragmode=False, title=_title, yaxis_range=[0,100], height=165,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                margin=dict(l=0,r=0,t=36,b=0), xaxis=dict(tickfont=dict(size=9)), font=dict(size=10))
                            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
                            st.caption(_cap)

                # ── Divergences ──────────────────────────────────────────────
                ROUND_SHORT = {"R64":"R64","R32":"R32","S16":"S16","E8":"E8","F4":"F4","Champ":"Champ"}
                ELIM_STYLE  = "color:#e05555;text-decoration:line-through;"
                TABLE_STYLE = """<style>
                .div-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:16px;}
                .div-table{border-collapse:collapse;width:100%;font-size:13px;}
                .div-table th{background:#1e1e2e;color:#fff;padding:6px 8px;border:1px solid #313244;text-align:left;font-size:12px;vertical-align:bottom;line-height:1.3;}
                .div-table td{padding:5px 8px;border:1px solid #313244;color:#fff;background:#13161f;white-space:nowrap;}
                .div-table tr:nth-child(even) td{background:#1a1f2b;}
                .div-table td.rc,.div-table th.rc{width:1%;white-space:nowrap;}
                </style>"""
                st.markdown(TABLE_STYLE, unsafe_allow_html=True)

                def _html_table(headers, rows, col_classes, row_colors=None, cell_styles=None):
                    ths = "".join(f'<th class="{c}">{h}</th>' for h,c in zip(headers,col_classes))
                    trs = ""
                    for i,row in enumerate(rows):
                        rc = row_colors[i] if row_colors else None
                        tds = ""
                        for j,(v,c) in enumerate(zip(row,col_classes)):
                            cs = cell_styles[i][j] if cell_styles and cell_styles[i] and cell_styles[i][j] else None
                            style = f' style="{cs}"' if cs else (f' style="color:{rc};"' if rc else "")
                            tds += f'<td class="{c}"{style}>{v if v is not None else "—"}</td>'
                        trs += f"<tr>{tds}</tr>"
                    return f'<div class="div-table-wrap"><table class="div-table"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>'

                if _np == 2:
                    diverge_df = pd.DataFrame(h2h["divergences"])
                    st.markdown("#### 🔀 Where Your Brackets Split")
                    if not diverge_df.empty:
                        future = diverge_df[diverge_df["Played"] == False]
                        past   = diverge_df[diverge_df["Played"] == True]
                        if not future.empty:
                            st.markdown("**Upcoming Divergences** — where the battle will be decided")
                            fd = future.copy()
                            fd["Round"] = fd["Round"].map(lambda r: ROUND_SHORT.get(r,r))
                            hdrs = ["Rnd", p1_name, f"{p1_name} Pts", p2_name, f"{p2_name} Pts"]
                            ccs  = ["rc","","rc","","rc"]
                            rows, css = [], []
                            for _, row in fd.iterrows():
                                p1e = row[p1_name] not in truly_alive
                                p2e = row[p2_name] not in truly_alive
                                p1_style = ELIM_STYLE if p1e else "color:#4fc3f7;"
                                p2_style = ELIM_STYLE if p2e else "color:#f5c518;"
                                rows.append([row["Round"], row[p1_name], int(row.get("P1 Pts","") or 0), row[p2_name], int(row.get("P2 Pts","") or 0)])
                                css.append([None, p1_style, p1_style, p2_style, p2_style])
                            st.markdown(_html_table(hdrs, rows, ccs, cell_styles=css), unsafe_allow_html=True)
                        if not past.empty:
                            st.markdown("**Past Divergences**")
                            pd_ = past.copy()
                            pd_["Round"] = pd_["Round"].map(lambda r: ROUND_SHORT.get(r,r))
                            pd_["Pts Awarded"] = pd_.apply(lambda r: int(r["Pts"]) if r["Pts"] > 0 else pd.NA, axis=1).astype("Int64")
                            pd_ = pd_.sort_values("Pts Awarded", ascending=False, na_position="last")
                            hdrs = ["Rnd", p1_name, p2_name, "Winner", "Pts"]
                            ccs  = ["rc","","","","rc"]
                            rows, css = [], []
                            for _, row in pd_.iterrows():
                                pv = row["Pts Awarded"]
                                p1g = row["P1 Got It"] == "✅"
                                p2g = row["P2 Got It"] == "✅"
                                p1_pick = row[p1_name]
                                p2_pick = row[p2_name]
                                p1_style = "color:#4ade80;" if p1g else "color:#f87171;text-decoration:line-through;"
                                p2_style = "color:#4ade80;" if p2g else "color:#f87171;text-decoration:line-through;"
                                rows.append([row["Round"],
                                    f'{"✅ " if p1g else "❌ "}{p1_pick}',
                                    f'{"✅ " if p2g else "❌ "}{p2_pick}',
                                    row["Winner"], "—" if pd.isna(pv) else int(pv)])
                                css.append([None, p1_style, p2_style, None, None])
                            st.markdown(_html_table(hdrs, rows, ccs, cell_styles=css), unsafe_allow_html=True)
                    else:
                        st.info("These two have identical brackets!")
                else:
                    # Multi-player divergences
                    st.markdown("#### 🔀 Where Brackets Split")
                    _future_rows, _past_rows = [], []
                    for _c in range(3, 66):
                        _slot_picks = [p["raw_picks"][_c] if _c < len(p["raw_picks"]) else "" for p in _pdata]
                        if len(set(_slot_picks)) <= 1:
                            continue
                        _rnd = ROUND_SHORT.get(get_round_name(_c), get_round_name(_c))
                        _is_played = not is_unplayed(actual_winners[_c])
                        _actual_winner = actual_winners[_c] if _is_played else ""
                        # Points value for this slot
                        _slot_pts_val = points_per_game[_c] if _c < len(points_per_game) else 0

                        if not _is_played:
                            # Upcoming — show pick + potential pts
                            _row = [_rnd]
                            for _pi, (_n, _pk) in enumerate(zip(_players, _slot_picks)):
                                _elim = _pk not in truly_alive
                                _pts_val = _slot_pts_val + seed_map.get(_pk, 0)
                                if _elim:
                                    _row.append(f'<span style="color:#e05555;text-decoration:line-through;">{_pk}</span>')
                                    _row.append(f'<span style="color:#e05555;">—</span>')
                                else:
                                    _row.append(f'<span style="color:{PLAYER_COLORS[_pi]};">{_pk}</span>')
                                    _row.append(f'<span style="color:{PLAYER_COLORS[_pi]};">{_pts_val}</span>')
                            _future_rows.append(_row)
                        else:
                            # Past — show pick + ✅/❌ + pts awarded
                            _pts_awarded = 0
                            _row = [_rnd]
                            for _pi, (_n, _pk) in enumerate(zip(_players, _slot_picks)):
                                _won = _pk == _actual_winner
                                _pts_val = (_slot_pts_val + seed_map.get(_pk, 0)) if _won else 0
                                if _won:
                                    _pts_awarded = _pts_val
                                    _row.append(f'<span style="color:#4ade80;font-weight:700;">✅ {_pk}</span>')
                                else:
                                    _row.append(f'<span style="color:#f87171;text-decoration:line-through;">❌ {_pk}</span>')
                            _row.append(f'<span style="color:#9ca3af;">{_actual_winner}</span>')
                            _row.append(str(_pts_awarded) if _pts_awarded else "—")
                            _past_rows.append(_row)

                    # Build headers
                    _pick_hdrs = []
                    for _n in _players:
                        _pick_hdrs += [_n, "Pts"]
                    _future_hdrs = ["Rnd"] + _pick_hdrs
                    _past_hdrs   = ["Rnd"] + [_n for _n in _players] + ["Winner", "Pts"]

                    _t2 = """<style>
                    .div-table-wrap2{overflow-x:auto;margin-bottom:16px;}
                    .div-table2{border-collapse:collapse;width:100%;font-size:13px;}
                    .div-table2 th{background:#1e1e2e;color:#fff;padding:6px 8px;border:1px solid #313244;font-size:12px;}
                    .div-table2 td{padding:5px 8px;border:1px solid #313244;color:#fff;background:#13161f;white-space:nowrap;}
                    .div-table2 tr:nth-child(even) td{background:#1a1f2b;}
                    .div-table2 td.rc{width:1%;white-space:nowrap;}
                    </style>"""
                    st.markdown(_t2, unsafe_allow_html=True)

                    def _ht2(headers, rows):
                        ths = "".join(f'<th class="{"rc" if i==0 else ""}">{h}</th>' for i,h in enumerate(headers))
                        trs = "".join("<tr>" + "".join(f'<td class="{"rc" if j==0 else ""}">{v}</td>' for j,v in enumerate(r)) + "</tr>" for r in rows)
                        return f'<div class="div-table-wrap2"><table class="div-table2"><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>'

                    if _future_rows:
                        st.markdown("**Upcoming Divergences**")
                        st.markdown(_ht2(_future_hdrs, _future_rows), unsafe_allow_html=True)
                    if _past_rows:
                        st.markdown("**Past Divergences**")
                        st.markdown(_ht2(_past_hdrs, _past_rows), unsafe_allow_html=True)
                    if not _future_rows and not _past_rows:
                        st.success("All selected players have identical picks!")


        elif _sub_yb == "bracket-dna":
            st.subheader("🧬 Bracket DNA & Probability")
            dna_select = st.selectbox(
                "Select your name",
                ["— select —"] + name_opts,
                key="dna",
            )
            if dna_select != "— select —":
                u = final_df[final_df["Name"] == dna_select].iloc[0]

                # ── Build p_picks for this participant ────────────────────────
                dna_p_row = None
                for _i in range(3, len(df_p)):
                    if str(df_p.iloc[_i][0]).strip() == dna_select:
                        dna_p_row = df_p.iloc[_i]
                        break
                dna_picks = [str(dna_p_row[c]).strip() if dna_p_row is not None and c < len(dna_p_row) else "" for c in range(67)]

                # ── Stat values ───────────────────────────────────────────────
                dna_rank        = int(u["Current Rank"])
                dna_total       = len(final_df)
                dna_rank_str    = f"#{dna_rank} / {dna_total}"
                dna_champ_pick  = dna_picks[65] if len(dna_picks) > 65 else ""
                dna_champ_pick  = dna_champ_pick if dna_champ_pick and not is_unplayed(dna_champ_pick) else "TBD"
                dna_champ_elim  = dna_champ_pick != "TBD" and dna_champ_pick not in truly_alive
                dna_champ_color = "#ef4444" if dna_champ_elim else "#f5c518"
                dna_champ_style = "text-decoration:line-through;" if dna_champ_elim else ""
                dna_champ_sfx   = " ❌" if dna_champ_elim else ""
                dna_logo_url    = espn_logo_url(dna_champ_pick) if dna_champ_pick != "TBD" else None
                if dna_champ_pick != "TBD" and dna_logo_url:
                    dna_champ_html = (
                        f'<div style="display:flex;flex-direction:column;align-items:center;gap:2px;">'
                        f'<img src="{dna_logo_url}" width="36" height="36" style="object-fit:contain;margin-bottom:4px;{"opacity:0.5;" if dna_champ_elim else ""}">'
                        f'<div style="font-size:clamp(13px,3vw,16px);font-weight:700;color:{dna_champ_color};line-height:1.1;">'
                        f'<span style="{dna_champ_style}">{dna_champ_pick}</span>{dna_champ_sfx}</div>'
                        f'</div>'
                    )
                elif dna_champ_pick != "TBD":
                    dna_champ_html = (
                        f'<div style="font-size:clamp(16px,3vw,20px);font-weight:700;color:{dna_champ_color};line-height:1.1;">'
                        f'<span style="{dna_champ_style}">{dna_champ_pick}</span>{dna_champ_sfx}</div>'
                    )
                else:
                    dna_champ_html = '<div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#9ca3af;line-height:1.1;">—</div>'

                dna_potential       = u["Potential Status"]
                dna_pot_color       = (
                    "#f5c518" if "Champion" in str(dna_potential) else
                    "#60a5fa" if "Top 3"    in str(dna_potential) else
                    "#ef4444" if "Out"      in str(dna_potential) else "#9ca3af"
                )
                dna_win_pct         = f"{u['Win %']:.1f}%"
                dna_top3_pct        = f"{u['Top 3 %']:.1f}%"
                dna_upsets          = int(u["Upset Correct"])
                dna_correct         = sum(1 for c in range(3, 66) if not is_unplayed(actual_winners[c]) and dna_picks[c] == actual_winners[c])
                dna_played_g        = sum(1 for c in range(3, 66) if not is_unplayed(actual_winners[c]))
                dna_accuracy_str    = f"{dna_correct/dna_played_g*100:.0f}%" if dna_played_g else "—"

                st.markdown(f'''
<div style="display:flex;gap:6px;width:100%;box-sizing:border-box;margin-bottom:6px;">
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">📊 Current Rank</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#ffffff;line-height:1.1;">{dna_rank_str}</div>
  </div>
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🥇 Champion Pick</div>
    {dna_champ_html}
  </div>
</div>
<div style="display:flex;gap:6px;width:100%;box-sizing:border-box;margin-bottom:6px;">
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🏆 Win %</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#f5c518;line-height:1.1;">{dna_win_pct}</div>
  </div>
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🥉 Top 3 %</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#60a5fa;line-height:1.1;">{dna_top3_pct}</div>
  </div>
</div>
<div style="display:flex;gap:6px;width:100%;box-sizing:border-box;margin-bottom:6px;">
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🔮 Potential</div>
    <div style="font-size:clamp(20px,5vw,28px);font-weight:700;color:{dna_pot_color};line-height:1.1;">{dna_potential}</div>
  </div>
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">😤 Upset Picks ✓</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#fb923c;line-height:1.1;">{dna_upsets}</div>
  </div>
</div>
<div style="display:flex;gap:6px;width:100%;box-sizing:border-box;margin-bottom:12px;">
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">✅ Correct Picks</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#60a5fa;line-height:1.1;">{dna_correct} / {dna_played_g}</div>
  </div>
  <div style="flex:1;background:#1e1e2e;border:1px solid #313244;border-radius:10px;padding:clamp(10px,2.5vw,16px);min-width:0;text-align:center;">
    <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:4px;">🎯 Accuracy</div>
    <div style="font-size:clamp(28px,7vw,38px);font-weight:700;color:#c084fc;line-height:1.1;">{dna_accuracy_str}</div>
  </div>
</div>''', unsafe_allow_html=True)

                # ── Still in the Hunt (reuse same logic, scoped to dna_select) ─
                dna_all_rows = []
                for _idx in range(3, len(df_p)):
                    _row = df_p.iloc[_idx]
                    _nm  = str(_row[0]).strip()
                    if not _nm or _nm in {"Winner", ""} or _nm.lower() == "nan":
                        continue
                    _pk = [str(_row[c]).strip() if c < len(_row) else "" for c in range(67)]
                    dna_all_rows.append((_nm, _pk))

                def _score_range(picks, cs, ce):
                    return sum(
                        points_per_game[c] + seed_map.get(picks[c], 0)
                        for c in range(cs, ce)
                        if not is_unplayed(actual_winners[c]) and picks[c] == actual_winners[c]
                    )
                def _pot_range(picks, cs, ce):
                    return sum(
                        points_per_game[c] + seed_map.get(picks[c], 0)
                        for c in range(cs, ce)
                        if picks[c] == actual_winners[c] or
                           (is_unplayed(actual_winners[c]) and picks[c] in all_alive)
                    )
                def _count_upsets(picks):
                    total = 0
                    for c in range(3, 66):
                        winner = actual_winners[c]
                        if is_unplayed(winner) or picks[c] != winner:
                            continue
                        loser  = defeated_map.get(winner, "")
                        w_seed = seed_map.get(winner, 0)
                        l_seed = seed_map.get(loser, 0)
                        if l_seed > 0 and w_seed > 0 and (w_seed - l_seed) >= 3:
                            total += 1
                    return total
                def _slot_can_upset(c):
                    if not is_unplayed(actual_winners[c]):
                        return False
                    alive_seeds = [seed_map.get(t, 0) for t in truly_alive if seed_map.get(t, 0) > 0]
                    if not alive_seeds:
                        return False
                    return (max(alive_seeds) - min(alive_seeds)) >= 3
                def _pot_upsets(picks):
                    earned = _count_upsets(picks)
                    # Find all alive teams that could still produce an upset
                    _pu_teams = set()
                    for team in truly_alive:
                        t_seed = seed_map.get(team, 0)
                        if t_seed < 4:
                            continue
                        if any(seed_map.get(opp, 0) > 0 and t_seed - seed_map.get(opp, 0) >= 3
                               for opp in truly_alive if opp != team):
                            _pu_teams.add(team)
                    # Count future picks that are potential upset teams (no double count)
                    future = 0
                    _counted = set()
                    for c in range(3, 66):
                        if not is_unplayed(actual_winners[c]):
                            continue
                        team = picks[c]
                        if team and team not in UNPLAYED and team in _pu_teams and team not in _counted:
                            future += 1
                            _counted.add(team)
                    return earned + future
                def _correct_pot(picks):
                    return sum(
                        1 for c in range(3, 66)
                        if (not is_unplayed(actual_winners[c]) and picks[c] == actual_winners[c])
                        or (is_unplayed(actual_winners[c]) and picks[c] in all_alive)
                    )

                _me = dna_picks
                _others = [(nm, pk) for nm, pk in dna_all_rows if nm != dna_select]

                # 1st Weekend
                _r1r2_done = all(not is_unplayed(actual_winners[c]) for c in range(3, 51))
                _my_r1r2   = _score_range(_me, 3, 51)
                _my_r1r2p  = _pot_range(_me, 3, 51)
                _oth_r1r2  = max((_score_range(pk, 3, 51) for _, pk in _others), default=0)
                _can_fw    = _my_r1r2 >= _oth_r1r2 if _r1r2_done else _my_r1r2p >= _oth_r1r2

                # 2nd Weekend
                _e8_done  = all(not is_unplayed(actual_winners[c]) for c in range(3, 63))
                _my_e8    = _score_range(_me, 3, 63)
                _my_e8p   = _pot_range(_me, 3, 63)
                _oth_e8   = max((_score_range(pk, 3, 63) for _, pk in _others), default=0)
                _can_sw   = _my_e8 >= _oth_e8 if _e8_done else _my_e8p >= _oth_e8

                # Most Correct
                if not r2_complete:
                    _can_mc = True
                else:
                    _my_cp    = _correct_pot(_me)
                    _oth_cp   = max((_correct_pot(pk) for _, pk in _others), default=0)
                    _can_mc   = _my_cp >= _oth_cp

                # Most Upsets — green if my potential >= others' potential,
                # only counting future slots where an upset is still physically possible
                if not r2_complete:
                    _can_mu = True
                else:
                    _any_upset_possible = any(_slot_can_upset(c) for c in range(3, 66))
                    if _any_upset_possible:
                        _my_up_pot  = _pot_upsets(_me)
                        _oth_up_pot = max((_pot_upsets(pk) for _, pk in _others), default=0)
                        _can_mu     = _my_up_pot >= _oth_up_pot
                    else:
                        _my_up  = _count_upsets(_me)
                        _oth_up = max((_count_upsets(pk) for _, pk in _others), default=0)
                        _can_mu = _my_up >= _oth_up

                # Tiebreaker
                if final_score is None:
                    _can_tb = True
                else:
                    _my_tb_guess = tiebreaker_guesses.get(dna_select)
                    if _my_tb_guess is None:
                        _can_tb = False
                    else:
                        _my_tb_diff   = abs(_my_tb_guess - final_score)
                        _best_tb_diff = min(abs(g - final_score) for g in tiebreaker_guesses.values())
                        _can_tb = _my_tb_diff == _best_tb_diff

                # Lucky Team
                _my_lucky = [t for t, ps in lucky_map.items() if dna_select in ps]
                _can_lt   = any(t in truly_alive for t in _my_lucky)

                # Last Place
                _my_sc    = int(u["Current Score"])
                _all_done = all(not is_unplayed(actual_winners[c]) for c in range(3, 66))
                _oth_ceil = [_pot_range(pk, 3, 66) for _, pk in _others]
                if _all_done:
                    _oth_fin  = [int(final_df[final_df["Name"] == nm].iloc[0]["Current Score"])
                                 for nm, _ in _others if not final_df[final_df["Name"] == nm].empty]
                    _can_lp   = _my_sc <= min(_oth_fin) if _oth_fin else True
                else:
                    _can_lp   = _my_sc <= min(_oth_ceil) if _oth_ceil else True

                # Regional
                _regions_win = []
                for _reg in ["West", "East", "South", "Midwest"]:
                    _my_reg   = int(u.get(f"{_reg} Score", 0))
                    _my_regp  = _my_reg + sum(
                        points_per_game[c] + seed_map.get(_me[c], 0)
                        for c in range(3, 63)
                        if is_unplayed(actual_winners[c])
                        and _me[c] in all_alive
                        and slot_to_region.get(c) == _reg
                    )
                    _oth_reg  = max(
                        (int(final_df[final_df["Name"] == nm].iloc[0].get(f"{_reg} Score", 0))
                         if not final_df[final_df["Name"] == nm].empty else 0)
                        for nm, _ in _others
                    ) if _others else 0
                    if _my_regp >= _oth_reg:
                        _regions_win.append(_reg)

                _dna_pills = "".join([
                    pill("1st Place",          dna_potential == "🏆 Champion"),
                    pill("Top 3",              dna_potential in ("🏆 Champion", "🥉 Top 3")),
                    pill("1st Weekend Leader", _can_fw),
                    pill("2nd Weekend Leader", _can_sw),
                    pill("Most Correct Picks", _can_mc),
                    pill("Most Upset Picks",   _can_mu),
                    *[pill(f"{r} Region", True)  for r in _regions_win],
                    *[pill(f"{r} Region", False) for r in ["West","East","South","Midwest"] if r not in _regions_win],
                    pill("Lucky Team",         _can_lt),
                    pill("Tiebreaker",         _can_tb),
                    pill("Last Place",         _can_lp),
                ])
                st.markdown(f'''<div style="background:#1e1e2e;border:1px solid #313244;border-radius:10px;
padding:clamp(10px,2.5vw,16px);width:100%;box-sizing:border-box;margin-bottom:12px;">
  <div style="font-size:clamp(11px,2.5vw,13px);color:#888;margin-bottom:10px;text-align:center;">
    🎯 Still in the Hunt
  </div>
  <div style="display:flex;flex-wrap:wrap;gap:6px;justify-content:center;">
    {_dna_pills}
  </div>
</div>''', unsafe_allow_html=True)

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
                    twin_name = twins[0]["Name"]
                    c1.metric("Bracket Twin", twins[0]["Name"],
                              f"{twins[0]['Matches']} shared picks")
                    if c1.button("⚔️ Compare", key="dna_compare"):
                        st.session_state["nav_sub_your-bracket"] = "head-to-head"
                        st.query_params["p1"]  = dna_select
                        st.query_params["p2"]  = twin_name
                        st.session_state.pop("h2h_params_applied", None)
                        st.rerun()

                all_p = [{"T": u["raw_picks"][c], "C": global_pick_counts.get(u["raw_picks"][c], 0), "slot": c}
                         for c in range(3, 66) if u["raw_picks"][c] in all_starting]
                if all_p:
                    rarest = sorted(all_p, key=lambda x: x["C"])[0]
                    team = rarest["T"]
                    team_seed = seed_map.get(team, "")
                    team_label = f"({team_seed}) {team}" if team_seed else team
                    rarest_label = team_label
                    slot_c = rarest["slot"]
                    slot_teams = {t for t, cnt in slot_pick_counts.get(slot_c, {}).items() if t != team and t in all_starting}
                    if slot_teams:
                        bracket_opponent = max(slot_teams, key=lambda t: slot_pick_counts[slot_c].get(t, 0))
                        opp_seed = seed_map.get(bracket_opponent, "")
                        opp_label = f"({opp_seed}) {bracket_opponent}" if opp_seed else bracket_opponent
                        rarest_label += f" def. {opp_label}"
                    slot_winner = actual_winners[slot_c]
                    if is_unplayed(slot_winner):
                        rarest_color = "#ffffff"
                    elif team == slot_winner:
                        rarest_color = "#4caf50"
                    else:
                        rarest_color = "#f44336"
                    with c2:
                        st.markdown(f'<div id="rarest-pick-metric"></div>', unsafe_allow_html=True)
                        st.metric("Rarest Pick", rarest_label, f"Only {rarest['C']} others picked")
                        st.markdown(f"""
                            <style>
                            #rarest-pick-metric + div [data-testid="stMetricValue"] > div {{
                                color: {rarest_color} !important;
                            }}
                            </style>
                        """, unsafe_allow_html=True)

                correct = [{"T": u["raw_picks"][c],
                            "C": global_pick_counts.get(u["raw_picks"][c], 0)}
                           for c in range(3, 66)
                           if u["raw_picks"][c] == actual_winners[c]]
                if correct:
                    rare_correct = sorted(correct, key=lambda x: x["C"])[0]
                    team = rare_correct["T"]
                    team_seed = seed_map.get(team, "")
                    team_label = f"({team_seed}) {team}" if team_seed else team
                    rare_correct_label = team_label
                    if team in defeated_map:
                        opponent = defeated_map[team]
                        opp_seed = seed_map.get(opponent, "")
                        opp_label = f"({opp_seed}) {opponent}" if opp_seed else opponent
                        rare_correct_label += f" def. {opp_label}"
                    with c3:
                        st.markdown('<div id="rarest-correct-metric"></div>', unsafe_allow_html=True)
                        st.metric("Rarest Correct Pick", rare_correct_label, f"{rare_correct['C']} users had it")
                        st.markdown("""
                            <style>
                            #rarest-correct-metric + div [data-testid="stMetricValue"] > div {
                                color: #4caf50 !important;
                            }
                            </style>
                        """, unsafe_allow_html=True)

                # Top 10 rarest remaining picks with logos
                all_remaining = [
                    {
                        "Team": u["raw_picks"][c],
                        "Round": get_round_name(c),
                        "Count": slot_pick_counts.get(c, {}).get(u["raw_picks"][c], 0),
                        "Pool %": round(slot_pick_counts.get(c, {}).get(u["raw_picks"][c], 0) / max(len(results), 1) * 100, 1),
                    }
                    for c in range(3, 66)
                    if u["raw_picks"][c] not in {"", "nan", "TBD"}
                    and is_unplayed(actual_winners[c])
                    and u["raw_picks"][c] in all_alive
                ]
                if all_remaining:
                    st.markdown("#### 🤫 Your 10 Rarest Remaining Picks")
                    rarest_df = (
                        pd.DataFrame(all_remaining)
                        .drop_duplicates("Team")
                        .sort_values("Count")
                        .head(10)
                    )
                    # Add round abbreviation to team label for y-axis
                    rarest_df["Label"] = rarest_df["Team"] + " (" + rarest_df["Round"] + ")"
                    _pool_size = max(len(results), 1)
                    _first_name_dna = dna_select.split()[0] if dna_select and dna_select != "— select —" else "Your"
                    fig_r = px.bar(
                        rarest_df, x="Count", y="Label", orientation="h",
                        title=f"The games that might decide {_first_name_dna}'s fate",
                        labels={"Count": "# Others with this pick", "Label": ""},
                        custom_data=["Round", "Pool %", "Team"],
                        text="Count",
                    )
                    fig_r.update_traces(
                        marker_color=[
                            f"rgba({max(20, 60 - int(v/70*40))}, {max(80, 160 - int(v/70*80))}, {max(120, 220 - int(v/70*100))}, 0.85)"
                            for v in rarest_df["Count"]
                        ],
                        texttemplate="<b>%{x}</b> / 70",
                        textposition="inside",
                        insidetextanchor="start",
                        textfont=dict(color="white", size=12, family="Arial Black, Arial, sans-serif"),
                        hovertemplate="<b>%{customdata[2]}</b> (%{customdata[0]})<br>%{x} / 70 others (%{customdata[1]}%)<extra></extra>"
                    )
                    # Add logos inside each bar
                    _r_images = []
                    for _ri, (_, _rrow) in enumerate(rarest_df.iterrows()):
                        _rlogo = espn_logo_url(_rrow["Team"])
                        if _rlogo:
                            _rx = max(_rrow["Count"] - 4, 3)
                            _r_images.append(dict(
                                source=_rlogo,
                                xref="x", yref="y",
                                x=_rx,
                                y=_ri,
                                sizex=7,
                                sizey=0.6,
                                xanchor="center", yanchor="middle",
                                layer="above", opacity=0.9,
                            ))
                    if _r_images:
                        fig_r.update_layout(
                            images=_r_images,
                            dragmode=False,
                            xaxis=dict(range=[0, 70], title="# Others with this pick"),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=0, r=0, t=40, b=0),
                            height=max(280, len(rarest_df) * 32 + 60),
                            uniformtext=dict(minsize=11, mode="show"),
                        )
                    else:
                        fig_r.update_layout(
                            dragmode=False,
                            xaxis=dict(range=[0, 70], title="# Others with this pick"),
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=0, r=0, t=40, b=0),
                            height=max(280, len(rarest_df) * 32 + 60),
                            uniformtext=dict(minsize=11, mode="show"),
                        )
                    st.plotly_chart(fig_r, use_container_width=True, config=PLOTLY_CONFIG)


    # ── Tab 3: Schedule/Scores ──────────────────────────────────────────────────
    with tab_scores:
        st.subheader("📺 Schedule / Scores")
        # Inject a unique marker + CSS to force 2-col date buttons on mobile
        st.markdown("""
        <div id="sp-tab-marker"></div>
        <style>
        #sp-tab-marker ~ * [data-testid="stHorizontalBlock"],
        #sp-tab-marker + div [data-testid="stHorizontalBlock"] {
            flex-wrap: nowrap !important;
        }
        #sp-tab-marker ~ * [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
        #sp-tab-marker + div [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            min-width: 0 !important;
            flex: 1 1 0% !important;
        }
        </style>
        """, unsafe_allow_html=True)

        # ── Name selector ────────────────────────────────────────────────
        _sp_name = st.selectbox(
            "Select your name",
            ["— select —"] + name_opts,
            key="sp_name",
            index=(name_opts.index(user_name) + 1) if user_name and user_name in name_opts else 0,
        )
        if _sp_name == "— select —":
            st.info("Select your name above to see your picks highlighted.")
            _sp_picks = []
        else:
            _sp_row = next((r for r in results if r["Name"] == _sp_name), None)
            _sp_picks = _sp_row["raw_picks"] if _sp_row else []

        # ── Build pool pick counts per slot ──────────────────────────────
        # slot_pick_counts already built: slot -> {team -> count}

        # ── Tournament dates ─────────────────────────────────────────────
        TOURN_DATES = [
            "2026-03-19", "2026-03-20",  # First Round
            "2026-03-21", "2026-03-22",  # Second Round
            "2026-03-26", "2026-03-27",  # Sweet 16
            "2026-03-28", "2026-03-29",  # Elite 8
            "2026-04-04",                # Final Four
            "2026-04-06",                # Championship
        ]
        DATE_LABELS = {
            "2026-03-19": "Thu Mar 19", "2026-03-20": "Fri Mar 20",
            "2026-03-21": "Sat Mar 21", "2026-03-22": "Sun Mar 22",
            "2026-03-26": "Thu Mar 26", "2026-03-27": "Fri Mar 27",
            "2026-03-28": "Sat Mar 28", "2026-03-29": "Sun Mar 29",
            "2026-04-04": "Sat Apr 4",  "2026-04-06": "Mon Apr 6",
        }

        # ── Detect user's local timezone via JS (must run before date picker) ──
        import streamlit.components.v1 as _sp_components
        import urllib.request, json as _json
        from datetime import datetime as _dt, timezone as _tz_utc, timedelta as _td
        import zoneinfo as _zi

        if "user_tz" not in st.session_state:
            st.session_state["user_tz"] = ""

        if not st.session_state.get("user_tz"):
            _sp_components.html("""
            <script>
            (function() {
                try {
                    var tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
                    var url = new URL(window.parent.location.href);
                    if (url.searchParams.get('_tz') !== tz) {
                        url.searchParams.set('_tz', tz);
                        window.parent.history.replaceState({}, '', url.toString());
                        window.parent.location.reload();
                    }
                } catch(e) {}
            })();
            </script>
            """, height=0)
            try:
                _tz_param = st.query_params.get("_tz", "")
                if _tz_param:
                    st.session_state["user_tz"] = _tz_param
                    st.query_params.pop("_tz", None)
                    st.rerun()
            except Exception:
                pass

        _user_tz_str = st.session_state.get("user_tz", "")

        # Determine today in the user's local timezone
        from datetime import date as _date
        try:
            if _user_tz_str:
                _today_str = _dt.now(_zi.ZoneInfo(_user_tz_str)).date().isoformat()
            else:
                _today_str = _date.today().isoformat()
        except Exception:
            _today_str = _date.today().isoformat()

        # Determine default date (today or nearest past date)
        _default_date = TOURN_DATES[0]
        for _d in TOURN_DATES:
            if _d <= _today_str:
                _default_date = _d

        # Auto-select today's date if not already set or if it was the previous default
        _sel_date = st.session_state.get("sp_sel_date", _default_date)
        # If today is a tournament date and user hasn't manually picked, jump to today
        if _today_str in TOURN_DATES and st.session_state.get("sp_sel_date") is None:
            st.session_state["sp_sel_date"] = _today_str
            _sel_date = _today_str

        DATE_ROUNDS = [
            ("🏀 First Round",   ["2026-03-19", "2026-03-20"]),
            ("🔥 Second Round",  ["2026-03-21", "2026-03-22"]),
            ("✨ Sweet 16",      ["2026-03-26", "2026-03-27"]),
            ("💎 Elite 8",       ["2026-03-28", "2026-03-29"]),
            ("🏆 Final Four & Championship", ["2026-04-04", "2026-04-06"]),
        ]

        for _round_label, _round_dates in DATE_ROUNDS:
            st.markdown(f'<p style="font-size:13px;font-weight:600;color:#9ca3af;margin:8px 0 3px 0;">{_round_label}</p>', unsafe_allow_html=True)
            _rcols = st.columns(2)
            for _ri, _d in enumerate(_round_dates):
                _is_sel = _sel_date == _d
                _is_today = _d == _today_str
                _is_past = _d < _today_str
                _label = ("🔴 Today" if _is_today else
                          f"✓ {DATE_LABELS[_d]}" if _is_past else
                          DATE_LABELS[_d])
                if _rcols[_ri].button(_label, key=f"sp_date_{_d}",
                                      use_container_width=True,
                                      type="primary" if _is_sel else "secondary"):
                    st.session_state["sp_sel_date"] = _d
                    st.rerun()

        _sel_date = st.session_state.get("sp_sel_date", _default_date)
        st.markdown("---")

        _user_tz_str = st.session_state.get("user_tz", "")

        # ── Format game time in user's local timezone ─────────────────────
        def _format_game_time(utc_iso, user_tz_str):
            """Return time string in user's local timezone, falling back to ET."""
            try:
                _utc = _dt.fromisoformat(utc_iso.replace("Z", "+00:00"))
                if user_tz_str:
                    try:
                        import zoneinfo
                        _local = _utc.astimezone(zoneinfo.ZoneInfo(user_tz_str))
                        return _local.strftime("%-I:%M %p %Z")
                    except Exception:
                        pass
                # Fallback to ET
                _et = _utc.astimezone(_tz_utc(offset=_td(hours=-4)))
                return _et.strftime("%-I:%M %p ET")
            except Exception:
                return ""

        @st.cache_data(ttl=62, show_spinner=False)
        def fetch_espn_games(date_str):
            """Fetch NCAA tournament games from ESPN for a given date (YYYY-MM-DD)."""
            yyyymmdd = date_str.replace("-", "")
            url = (
                f"https://site.api.espn.com/apis/site/v2/sports/basketball/"
                f"mens-college-basketball/scoreboard?dates={yyyymmdd}&groups=50&limit=200"
            )
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = _json.loads(resp.read())
                games = []
                for ev in data.get("events", []):
                    comp = ev.get("competitions", [{}])[0]
                    competitors = comp.get("competitors", [])
                    if len(competitors) < 2:
                        continue
                    # Filter to NCAA tournament games only via notes or seeds
                    notes = comp.get("notes", [])
                    is_tourney = any("Championship" in n.get("headline", "") or "NCAA" in n.get("headline", "") for n in notes)
                    if not is_tourney:
                        has_seeds = any(c.get("rank") for c in competitors)
                        # Also check if it's a neutral site game (tournament indicator)
                        is_neutral = comp.get("neutralSite", False)
                        if not has_seeds and not is_neutral:
                            continue
                    status_type = ev.get("status", {}).get("type", {})
                    state = status_type.get("state", "pre")
                    status_detail = status_type.get("shortDetail", "")
                    # Store raw UTC for client-side timezone formatting
                    game_date_str = ev.get("date", "")
                    try:
                        _utc = _dt.fromisoformat(game_date_str.replace("Z", "+00:00"))
                        _et = _utc.astimezone(_tz_utc(offset=_td(hours=-4)))
                        game_time_et = _et.strftime("%-I:%M %p ET")
                    except Exception:
                        game_time_et = ""
                    teams = []
                    for c in competitors:
                        team_info = c.get("team", {})
                        teams.append({
                            "name":   team_info.get("displayName", team_info.get("name", "")),
                            "abbrev": team_info.get("abbreviation", ""),
                            "logo":   team_info.get("logo", ""),
                            "seed":   c.get("rank") or c.get("seed") or "",
                            "score":  c.get("score", ""),
                            "winner": c.get("winner", False),
                            "home":   c.get("homeAway", "") == "home",
                        })
                    games.append({
                        "id":        ev.get("id"),
                        "state":     state,
                        "detail":    status_detail,
                        "time":      game_time_et,
                        "utc_iso":   game_date_str,
                        "sort_time": game_date_str,
                        "teams":     teams,
                    })
                return games
            except Exception:
                return []

        _games = fetch_espn_games(_sel_date)
        # Sort by scheduled start time
        _games = sorted(_games, key=lambda g: g.get("sort_time", ""))

        if not _games:
            st.info(f"No NCAA tournament games found for {DATE_LABELS.get(_sel_date, _sel_date)}. Data loads from ESPN — try refreshing.")
        else:
            # ── Robust ESPN→pool name normaliser ─────────────────────────
            # Build reverse lookup: ESPN ID → pool name
            # Use all_starting so eliminated R1 teams are still included
            # Prefer entries whose key exactly matches an all_starting name
            _espn_id_to_pool = {}
            for _pn, _pid in ESPN_IDS.items():
                if _pn in all_starting:
                    # Exact match always wins — overwrite any prior entry
                    _espn_id_to_pool[_pid] = _pn
            # Fill remaining IDs with any variant that case-matches all_starting
            for _pn, _pid in ESPN_IDS.items():
                if _pid not in _espn_id_to_pool:
                    for _sn in all_starting:
                        if _pn.lower() == _sn.lower():
                            _espn_id_to_pool[_pid] = _sn
                            break
            # Build lowercase pool name set for fuzzy match
            _pool_names_lower = {n.lower(): n for n in all_starting}

            def _norm_name(espn_display, espn_logo_url_str=""):
                """Map ESPN display name → pool team name."""
                # 1. Direct match against all starting teams
                if espn_display in all_starting:
                    return espn_display
                # 2. Try ESPN_IDS exact/variant
                for variant in [espn_display, espn_display.rstrip("."), espn_display.replace(".", "")]:
                    if variant in ESPN_IDS:
                        cand = ESPN_IDS[variant]
                        if cand in _espn_id_to_pool:
                            return _espn_id_to_pool[cand]
                # 3. Extract ESPN ID from logo URL and reverse-lookup
                if espn_logo_url_str:
                    try:
                        import re as _re
                        _eid_match = _re.search(r'/(\d+)\.png', espn_logo_url_str)
                        if _eid_match:
                            _eid = int(_eid_match.group(1))
                            if _eid in _espn_id_to_pool:
                                return _espn_id_to_pool[_eid]
                    except Exception:
                        pass
                # 4. Fuzzy: strip common ESPN nickname suffixes
                _espn_lower = espn_display.lower()
                for suffix in [
                    " wildcats"," aggies"," tigers"," bears"," wolves"," bulldogs",
                    " cardinals"," ravens"," eagles"," hawks"," owls"," knights",
                    " trojans"," spartans"," bruins"," tar heels"," hoyas",
                    " hurricanes"," seminoles"," gators"," volunteers",
                    " razorbacks"," longhorns"," sooners"," cowboys"," cyclones",
                    " hawkeyes"," badgers"," buckeyes"," wolverines"," blue devils",
                    " blue jays"," jayhawks"," crimson tide"," mountaineers",
                    " hokies"," demon deacons"," commodores"," golden eagles",
                    " huskies"," terrapins"," terps"," catamounts"," zags",
                    " billikens"," ramblers"," phoenix"," musketeers",
                    " hilltoppers"," bison"," panthers"," flames"," friars",
                    " bonnies"," gaels"," bearcats"," flyers"," sea hawks",
                    " mean green"," red raiders"," fighting illini"," boilermakers",
                    " orange"," green wave"," rainbow warriors"," scarlet knights",
                    " cougars"," lakers"," pirates"," penguins"," anteaters",
                    " horned frogs"," colonials"," dukes"," quakers"," big red",
                    " cornhuskers"," huskers"," nittany lions"," fighting irish",
                    " longhorns"," aztecs"," toreros"," tritons"," banana slugs",
                    " gauchos"," retrievers"," retrievers"," leopards"," bucks",
                    " colonels"," paladins"," spiders"," rams"," ducks",
                    " beavers"," sun devils"," utes"," rebels"," wolf pack",
                    " bulldogs"," yellow jackets"," ramblin' wreck"," toreros",
                    " 49ers"," matadors"," roadrunners"," lumberjacks",
                    " warhawks"," ragin' cajuns"," colonels"," ospreys",
                    " sycamores"," leathernecks"," fighting hawks",
                ]:
                    if _espn_lower.endswith(suffix):
                        base = _espn_lower[:-len(suffix)].strip()
                        if base in _pool_names_lower:
                            return _pool_names_lower[base]
                # Direct lowercase match
                if _espn_lower in _pool_names_lower:
                    return _pool_names_lower[_espn_lower]
                # Partial: pool name contained in ESPN name (prefer longer matches)
                _best_match = None
                _best_len = 0
                for _pl, _pn in _pool_names_lower.items():
                    if len(_pl) >= 5 and (_pl in _espn_lower or _espn_lower.startswith(_pl)):
                        if len(_pl) > _best_len:
                            _best_match = _pn
                            _best_len = len(_pl)
                if _best_match:
                    return _best_match
                return espn_display

            # Build slot matchup map ONCE outside the game loop
            _slot_matchup: dict[int, tuple] = {}
            for _sc, (ta, tb) in r1_matchups.items():
                _slot_matchup[_sc] = (ta, tb)
            _round_starts = [3, 35, 51, 59, 63, 65]
            for _ri in range(1, len(_round_starts) - 1):
                _rs = _round_starts[_ri]
                _re = _round_starts[_ri + 1]
                _prev_rs = _round_starts[_ri - 1]
                for _i, _sc in enumerate(range(_rs, _re)):
                    _p1 = _prev_rs + _i * 2
                    _p2 = _prev_rs + _i * 2 + 1
                    _p1w = actual_winners[_p1] if _p1 < len(actual_winners) and not is_unplayed(actual_winners[_p1]) else ""
                    _p2w = actual_winners[_p2] if _p2 < len(actual_winners) and not is_unplayed(actual_winners[_p2]) else ""
                    if _p1w and _p2w:
                        _slot_matchup[_sc] = (_p1w, _p2w)

            # Build picker lists per team per slot (for expanded view)
            def _pickers_for_team(team_name, slot):
                if slot < 0:
                    return []
                return [r["Name"] for r in results
                        if slot < len(r["raw_picks"]) and r["raw_picks"][slot] == team_name]

            # ── Render each game as a card ────────────────────────────────
            for _gi, game in enumerate(_games):
                teams = game["teams"]
                if len(teams) < 2:
                    continue
                away = next((t for t in teams if not t["home"]), teams[0])
                home = next((t for t in teams if t["home"]),  teams[1])

                away_pool = _norm_name(away["name"], away.get("logo",""))
                home_pool = _norm_name(home["name"], home.get("logo",""))

                # Find the slot where these two specific teams play each other
                _match_slot = -1
                _game_set = {away_pool, home_pool}
                for _sc, (ta, tb) in _slot_matchup.items():
                    if {ta, tb} == _game_set:
                        _match_slot = _sc
                        break

                # Pick counts from the exact slot
                _away_ct = 0
                _home_ct = 0
                if _match_slot >= 0:
                    _sp = slot_pick_counts.get(_match_slot, {})
                    _away_ct = _sp.get(away_pool, 0)
                    _home_ct = _sp.get(home_pool, 0)
                _total_pool = max(len(results), 1)
                _total_slot = _away_ct + _home_ct

                # User's pick for the exact slot only
                _user_pick = ""
                if _match_slot >= 0 and _match_slot < len(_sp_picks):
                    _user_pick = _sp_picks[_match_slot]

                # Is user's pick in this game?
                _pick_in_game = _user_pick in (away_pool, home_pool)
                _pick_eliminated = bool(_user_pick and not _pick_in_game)

                # Points for this slot
                _slot_pts = points_per_game[_match_slot] if _match_slot >= 0 and _match_slot < len(points_per_game) else 0
                _winner_pts = 0
                if _match_slot >= 0:
                    _winning_team = away_pool if away.get("winner") else (home_pool if home.get("winner") else "")
                    if _winning_team:
                        _winner_pts = _slot_pts + seed_map.get(_winning_team, 0)

                # User pick points
                _user_pts = 0
                if _user_pick and _match_slot >= 0:
                    _user_pts = _slot_pts + seed_map.get(_user_pick, 0)

                # Build card
                is_pre  = game["state"] == "pre"
                is_live = game["state"] == "in"
                is_post = game["state"] == "post"
                away_winner = away.get("winner", False)
                home_winner = home.get("winner", False)
                _winning_pool = away_pool if away_winner else (home_pool if home_winner else "")

                def _pick_ring_color(pool_name):
                    """Return the border color for the user's pick highlight."""
                    if _user_pick != pool_name:
                        return ""
                    if is_pre or is_live:
                        return "#f5c518"  # gold — upcoming
                    if _user_pick == _winning_pool:
                        return "#16a34a"  # green — correct
                    return "#dc2626"      # red — wrong

                def _team_block(t, pool_name, is_winner, is_live, is_pre, user_pick):
                    seed_str = f'<span style="font-size:10px;color:#9ca3af;margin-right:4px;">({t["seed"]})</span>' if t["seed"] else ""
                    logo = t["logo"] or espn_logo_url(pool_name) or ""
                    logo_html = f'<img src="{logo}" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display=\'none\'">' if logo else '<div style="width:32px;"></div>'
                    score_html = f'<div style="font-size:32px;font-weight:800;color:{"#f5c518" if is_winner else "#fff"};">{t["score"]}</div>' if not is_pre and t["score"] else ""
                    _ring = _pick_ring_color(pool_name)
                    pick_ring = f"box-shadow:0 0 0 3px {_ring};border-radius:8px;" if _ring else ""
                    pick_count = _away_ct if pool_name == away_pool else _home_ct
                    pct = f"{round(pick_count/_total_pool*100)}%" if _total_pool > 0 else "—"
                    dim = "opacity:0.45;" if not is_winner and not is_pre and not is_live else ""
                    _pts_val = _slot_pts + seed_map.get(pool_name, 0)
                    pts_label = f'<div style="font-size:11px;color:#6b7280;">{_pts_val} pts if correct</div>' if is_pre or is_live else ""
                    return (
                        f'<div style="flex:1;display:flex;flex-direction:column;align-items:center;'
                        f'gap:4px;padding:10px 6px;{pick_ring}{dim}">'
                        f'{logo_html}'
                        f'<div style="text-align:center;">{seed_str}<span style="font-size:17px;font-weight:700;">{pool_name}</span></div>'
                        f'{score_html}'
                        f'<div style="font-size:11px;color:#9ca3af;">{pick_count} picks ({pct})</div>'
                        f'{pts_label}'
                        f'</div>'
                    )

                away_block = _team_block(away, away_pool, away_winner, is_live, is_pre, _user_pick)
                home_block = _team_block(home, home_pool, home_winner, is_live, is_pre, _user_pick)

                # Card border — neutral always
                border = "#334155"

                if is_pre:
                    _time_str = _format_game_time(game.get("utc_iso", ""), _user_tz_str)
                    if not _time_str:
                        _time_str = game.get("time", "")  # fallback to pre-formatted ET string
                    middle = (
                        f'<div style="font-size:16px;font-weight:600;color:#9ca3af;text-align:center;'
                        f'padding:0 8px;white-space:nowrap;">{_time_str or "TBD"}</div>'
                    )
                elif is_live:
                    middle = f'<div style="font-size:12px;color:#22c55e;font-weight:700;text-align:center;padding:0 6px;">🔴 LIVE<br><span style="font-size:11px;font-weight:400;color:#9ca3af;">{game["detail"]}</span></div>'
                else:
                    pts_str = f'<div style="font-size:11px;color:#9ca3af;margin-top:4px;">{_winner_pts} pts awarded</div>' if _winner_pts else ""
                    middle = f'<div style="font-size:12px;color:#6b7280;text-align:center;padding:0 6px;">Final{pts_str}</div>'

                user_pick_note = ""
                if _pick_eliminated and _sp_name != "— select —":
                    user_pick_note = (
                        f'<div style="font-size:11px;color:#9ca3af;text-align:center;margin-top:4px;">'
                        f'Your pick: <span style="color:#ef4444;">{_user_pick}</span> (eliminated)</div>'
                    )

                _game_key = f"sp_game_{_sel_date}_{_gi}"
                _is_expanded = st.session_state.get("sp_expanded_game") == _game_key

                # Card HTML
                st.markdown(
                    f'<div style="border:1px solid {border};border-bottom:none;background:#1e1e2e;'
                    f'border-radius:12px 12px 0 0;padding:12px;margin-bottom:0;">'
                    f'<div style="display:flex;align-items:center;justify-content:space-between;">'
                    f'{away_block}{middle}{home_block}'
                    f'</div>'
                    f'{user_pick_note}'
                    f'</div>',
                    unsafe_allow_html=True
                )

                # Tap bar — styled as bottom of card, full width clickable
                _bar_label = "▾ Hide picks" if _is_expanded else "▸ Show picks"
                if st.button(
                    _bar_label,
                    key=f"sp_toggle_{_sel_date}_{_gi}",
                    use_container_width=True,
                ):
                    st.session_state["sp_expanded_game"] = None if _is_expanded else _game_key
                    st.rerun()

                # Inject CSS once to style these tap bars to match the card
                st.markdown(f"""
                <style>
                button[kind="secondary"][data-testid="baseButton-secondary"]:has(+ *) {{
                    border-radius: 0 !important;
                }}
                [data-testid="stButton"]:has(button[kind="secondary"]) {{
                    margin-top: 0 !important;
                }}
                </style>
                """, unsafe_allow_html=True)

                # Expanded picker list
                if _is_expanded:
                    _away_pickers = _pickers_for_team(away_pool, _match_slot)
                    _home_pickers = _pickers_for_team(home_pool, _match_slot)

                    def _picker_chips(pickers, team_name, is_winner):
                        if not pickers:
                            return f'<span style="color:#6b7280;font-size:12px;">Nobody picked {team_name}</span>'
                        chips = ""
                        for p in sorted(pickers):
                            is_me = user_name and p == user_name
                            if is_me:
                                # Current user always yellow
                                bg = "#3a3000"
                                color = "#f5c518"
                                border_c = "#f5c518"
                            elif is_post:
                                # Past game — green if correct, red if wrong
                                if is_winner:
                                    bg, color, border_c = "#052e16", "#4ade80", "#16a34a"
                                else:
                                    bg, color, border_c = "#2d0a0a", "#f87171", "#dc2626"
                            else:
                                bg, color, border_c = "#1e293b", "#d1d5db", "#334155"
                            _rank_row = final_df[final_df["Name"] == p]
                            _rank_str = f"#{int(_rank_row.iloc[0]['Current Rank'])} " if not _rank_row.empty else ""
                            chips += (
                                f'<span style="display:inline-block;background:{bg};color:{color};'
                                f'border:1px solid {border_c};border-radius:20px;'
                                f'padding:3px 10px;font-size:12px;margin:3px 3px;">'
                                f'<span style="opacity:0.6;font-size:11px;">{_rank_str}</span>{p}</span>'
                            )
                        return chips

                    logo_a = away.get("logo") or espn_logo_url(away_pool) or ""
                    logo_h = home.get("logo") or espn_logo_url(home_pool) or ""
                    logo_a_html = f'<img src="{logo_a}" style="width:18px;height:18px;object-fit:contain;vertical-align:middle;margin-right:5px;">' if logo_a else ""
                    logo_h_html = f'<img src="{logo_h}" style="width:18px;height:18px;object-fit:contain;vertical-align:middle;margin-right:5px;">' if logo_h else ""

                    st.markdown(
                        f'<div style="background:#131320;border:1px solid #1e293b;border-top:none;'
                        f'border-radius:0 0 12px 12px;padding:12px 14px;margin-top:-4px;margin-bottom:12px;">'
                        f'<div style="margin-bottom:8px;">'
                        f'<div style="font-size:12px;font-weight:700;color:#9ca3af;margin-bottom:4px;">'
                        f'{logo_a_html}{away_pool} — {len(_away_pickers)} pick{"s" if len(_away_pickers) != 1 else ""}</div>'
                        f'<div style="line-height:2;">{_picker_chips(_away_pickers, away_pool, away_winner)}</div>'
                        f'</div>'
                        f'<div>'
                        f'<div style="font-size:12px;font-weight:700;color:#9ca3af;margin-bottom:4px;">'
                        f'{logo_h_html}{home_pool} — {len(_home_pickers)} pick{"s" if len(_home_pickers) != 1 else ""}</div>'
                        f'<div style="line-height:2;">{_picker_chips(_home_pickers, home_pool, home_winner)}</div>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )


    # ── Tab 5: Fun Stats (group) ──────────────────────────────────────────────
    with tab_fun:
        _sub_fun = st.session_state.get("nav_sub_fun-stats", "bracket-busters")
        _fun_options = [
            ("bracket-busters",   "💥 Bracket Busters"),
            ("cinderella",        "🏃 Cinderella Stories"),
            ("classic-rivalries", "⚔️ Classic Rivalries"),
            ("champion-picks",    "🏆 Champion Picks"),
        ]
        _fun_row1 = st.columns(3)
        _fun_row2 = st.columns(1)
        for _i, (_slug, _label) in enumerate(_fun_options):
            _active = _sub_fun == _slug
            _fcol = _fun_row1[_i] if _i < 3 else _fun_row2[0]
            if _fcol.button(_label, key=f"fun_{_slug}",
                            use_container_width=True,
                            type="primary" if _active else "secondary"):
                st.session_state["nav_sub_fun-stats"] = _slug
                st.rerun()
        st.divider()
        _sub_fun = st.session_state.get("nav_sub_fun-stats", "bracket-busters")

        if _sub_fun == "bracket-busters":
            st.subheader("💥 Bracket Busters — Games That Wrecked the Pool")
            busters_df = compute_bracket_busters(results, actual_winners, points_per_game, seed_map)

            if busters_df.empty:
                st.info("No completed upsets yet — check back once games are played.")
            else:
                # Summary metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Busting Games", len(busters_df))
                m2.metric("Biggest Carnage",
                          busters_df.iloc[0]["Winner"],
                          f"{busters_df.iloc[0]['Busted Picks']} picks busted")
                m3.metric("Total Pool Pts Lost",
                          f"{busters_df['Total Pts Lost'].sum():,}")

                display_cols = ["Round", "Busted Team", "Winner", "Busted Picks",
                                "% Busted", "Pts Lost ea.", "Total Pts Lost"]
                st.dataframe(busters_df[display_cols], use_container_width=True, hide_index=True)

                _chart_df = busters_df.head(10).copy()
                # Extract raw winner name (strip seed prefix like "(10) Arkansas" -> "Arkansas")
                import re as _re
                def _raw_name(s):
                    m = _re.match(r"^\(\d+\)\s+(.+)$", s)
                    return m.group(1) if m else s

                fig = px.bar(
                    _chart_df, x="Matchup", y="Busted Picks",
                    color="Total Pts Lost", color_continuous_scale="Reds",
                    title="Top 10 Pool Killers by Picks Busted",
                    labels={"Matchup": "", "Busted Picks": "# Picks Busted"},
                )
                fig.update_layout(
                    dragmode=False,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=0, r=0, t=40, b=20),
                    height=420,
                )
                # Overlay ESPN logos inside each bar
                _max_picks = _chart_df["Busted Picks"].max()
                _images = []
                for _i, (_idx, _row) in enumerate(_chart_df.iterrows()):
                    _winner_raw = _raw_name(_row["Winner"])
                    _logo = espn_logo_url(_winner_raw)
                    if _logo:
                        # Position logo at ~60% height of the bar, centred on x tick
                        _bar_top = _row["Busted Picks"]
                        _images.append(dict(
                            source=_logo,
                            xref="x", yref="y",
                            x=_i,
                            y=_bar_top * 0.55,
                            sizex=0.55, sizey=_max_picks * 0.22,
                            xanchor="center", yanchor="middle",
                            layer="above",
                            opacity=0.9,
                        ))
                if _images:
                    fig.update_layout(images=_images)
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

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

                show_table(
                    carnage_df.head(20),
                    user_highlight_col="Name", user_highlight_val=user_name,
                    key="table_carnage",
                )

        elif _sub_fun == "cinderella":
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
                show_table(upset_lb, key="table_upset_lb")

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

        elif _sub_fun == "classic-rivalries":
            st.subheader("⚔️ Classic Rivalries")

            RIVALRIES = [
                {"slug": "andy-vs-dave",    "title": "🤺 Andy vs Dave",        "names": ["Andy Yardley", "Dave Sabour"]},
                {"slug": "duel-of-dylans",  "title": "🎭 Duel of the Dylans",  "names": ["Dylan Driver", "Dylan Grassl", "Dylan Levy"]},
                {"slug": "rookies",         "title": "🐣 Rookies",             "names": ["Diana Lower", "Kellie Knight", "Marise Gaughan", "Saoirse Johnston-Dick", "Sonia Raposo", "Walter Czaya"]},
                {"slug": "past-champions",  "title": "🏆 Past Champions",      "names": ["Alana Davis", "Jaymi Lynne", "Sarah Keo", "Tenley McCladdie", "Lauren Froman", "Armando Zamudio", "James Sawaya", "Priya Gupta"]},
                {"slug": "reid-family",     "title": "👨‍👩‍👧‍👦 Reid Family Pool", "names": ["Debbie Reid", "Matt Reid", "Griffin Reid", "Jack Reid", "Elizabeth Hartmann", "Taylor Chacon"]},
                {"slug": "mountain-folk",   "title": "⛰️ Mountain Folk",       "names": ["Daniel Wright", "Dave Sabour", "Diana Lower", "Elizabeth Hartmann", "Heidi Bruce", "Hunter Phillips", "Isaiah Erichsen", "James Sawaya", "Jeff Kooring", "Kelyn Ikegami", "McKinley Hancock", "Robert Dick", "Sarah Keo", "Siobhan Sargent", "Sonia Raposo", "Andrea Racine", "Saoirse Johnston-Dick"]},
                {"slug": "boltonites",      "title": "🏘️ Boltonites",           "names": ["Anthony Snelling", "Brendan Tierney", "Brian Moske", "Bryce Carlson", "Debbie Reid", "Dylan Driver", "Greg Murphy", "Griffin Reid", "Jack Reid", "Karen Tierney", "Matt Reid", "Sam Bahre", "Walter Czaya", "Will Hillebrand"]},
                {"slug": "veterans",        "title": "🎖️ 8+ Year Veterans",    "names": ["Alana Davis", "Laura Rubin", "Jared Goldstein", "Molly Davis", "Jaymi Lynne", "Greg Murphy", "James Sawaya", "Matt Reid", "Dylan Grassl", "Sam Bahre", "Griffin Reid", "Elias Luna", "Sarah Keo", "Tony Astacio", "Will Hillebrand", "Amanda Kosack", "Siobhan Sargent", "Priya Gupta", "Sean McCoy", "Dylan Driver", "Robert Dick", "Andrea Racine", "Andy Yardley", "Dave Sabour", "Anthony Snelling", "Sara Ruggiero", "Megan Gorman", "Christian Palacios", "Heidi Bruce", "Romana Guillotte", "Sarah Simonds", "McKinley Hancock", "Alex Bahre", "Pete Mullin", "Nicki Doyamis"]},
            ]

            # Read rivalry slug from query params (e.g. ?rivalry=veterans)
            _rivalry_slug = st.query_params.get("rivalry", "")
            if _rivalry_slug:
                try:
                    st.query_params.pop("rivalry", None)
                except Exception:
                    pass

            # Build a lookup of stats per name from final_df and results
            _stats_lookup = {}
            for r in results:
                nm = r["Name"]
                fd_row = final_df[final_df["Name"] == nm]
                if fd_row.empty:
                    continue
                fd = fd_row.iloc[0]
                _stats_lookup[nm] = {
                    "Rank":           int(fd["Current Rank"]),
                    "Score":          int(fd["Current Score"]),
                    "Potential":      int(fd["Potential Score"]),
                    "Correct":        sum(
                        1 for c in range(3, 66)
                        if not is_unplayed(actual_winners[c]) and r["raw_picks"][c] == actual_winners[c]
                    ),
                    "Upsets":         int(r.get("Upset Correct", 0)),
                    "Win %":          f"{fd['Win %']:.1f}%",
                    "Potential Status": fd["Potential Status"],
                    "Champion Pick":  r["raw_picks"][65] if len(r["raw_picks"]) > 65 and r["raw_picks"][65] not in {"", "nan", "TBD"} else "TBD",
                }

            for rivalry in RIVALRIES:
                _r_slug = rivalry.get("slug", "")
                # Inject anchor div for deep-linking
                st.markdown(f'<div id="rivalry-{_r_slug}"></div>', unsafe_allow_html=True)
                # Auto-scroll if this is the target rivalry
                if _rivalry_slug and _r_slug == _rivalry_slug:
                    _components.html(
                        f"""<script>
                        (function() {{
                            function scrollToRivalry() {{
                                var el = window.parent.document.getElementById('rivalry-{_r_slug}');
                                if (el) {{ el.scrollIntoView({{behavior:'smooth', block:'start'}}); }}
                                else {{ setTimeout(scrollToRivalry, 150); }}
                            }}
                            setTimeout(scrollToRivalry, 400);
                        }})();
                        </script>""",
                        height=0,
                    )
                st.markdown(f"### {rivalry['title']}")
                members = [nm for nm in rivalry["names"] if nm in _stats_lookup]
                missing = [nm for nm in rivalry["names"] if nm not in _stats_lookup]
                if missing:
                    st.caption(f"Not in pool this year: {', '.join(missing)}")
                if not members:
                    st.info("No participants from this group are in the pool this year.")
                    st.markdown("---")
                    continue

                # Build comparison table — sorted by rank
                members_sorted = sorted(members, key=lambda n: _stats_lookup[n]["Rank"])
                trs_r = ""
                for nm in members_sorted:
                    s = _stats_lookup[nm]
                    is_user = user_name and nm == user_name
                    row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if is_user else ""
                    champ_pick = s["Champion Pick"]
                    champ_elim = champ_pick and champ_pick not in truly_alive
                    champ_logo = espn_logo_url(champ_pick)
                    champ_logo_html = (
                        f'<img src="{champ_logo}" style="width:14px;height:14px;object-fit:contain;vertical-align:middle;margin-right:3px;{"opacity:0.4;" if champ_elim else ""}" onerror="this.style.display:none">'
                        if champ_logo else ""
                    )
                    champ_text_style = "color:#e05555;text-decoration:line-through;" if champ_elim else ""
                    champ_td = f'{champ_logo_html}<span style="{champ_text_style}">{champ_pick}</span>'
                    trs_r += (
                        f'<tr{row_style}>'
                        f'<td style="text-align:center;padding:4px 5px;">{s["Rank"]}</td>'
                        f'<td style="padding:4px 6px;white-space:nowrap;font-weight:600;">{nm}</td>'
                        f'<td style="text-align:center;padding:4px 5px;">{s["Score"]}</td>'
                        f'<td style="text-align:center;padding:4px 5px;">{s["Potential"]}</td>'
                        f'<td style="text-align:center;padding:4px 5px;">{s["Correct"]}</td>'
                        f'<td style="padding:4px 6px;white-space:nowrap;">{champ_td}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin-bottom:8px;">'
                    '<table style="border-collapse:collapse;width:100%;font-size:12px;">'
                    '<thead><tr style="background:#1e1e2e;color:#9ca3af;">'
                    '<th style="padding:5px 5px;text-align:center;border:1px solid #313244;white-space:nowrap;">#</th>'
                    '<th style="padding:5px 6px;text-align:left;border:1px solid #313244;white-space:nowrap;">Name</th>'
                    '<th style="padding:5px 5px;text-align:center;border:1px solid #313244;white-space:nowrap;">Pts</th>'
                    '<th style="padding:5px 5px;text-align:center;border:1px solid #313244;white-space:nowrap;">Max</th>'
                    '<th style="padding:5px 5px;text-align:center;border:1px solid #313244;white-space:nowrap;">✓</th>'
                    '<th style="padding:5px 6px;text-align:left;border:1px solid #313244;white-space:nowrap;">Champion</th>'
                    '</tr></thead>'
                    f'<tbody style="color:#fff;">{trs_r}</tbody>'
                    '</table></div>',
                    unsafe_allow_html=True
                )
                st.markdown("---")

        elif _sub_fun == "champion-picks":
            st.subheader("🏆 Champion Picks")
            st.caption("Every team chosen as champion, and who picked them")

            # Build champion pick → list of names
            champ_picks: dict[str, list[str]] = {}
            for r in results:
                pick = r["raw_picks"][65] if len(r["raw_picks"]) > 65 else ""
                if pick and pick not in {"", "nan", "TBD"}:
                    champ_picks.setdefault(pick, []).append(r["Name"])

            if not champ_picks:
                st.info("No champion picks found yet.")
            else:
                # Sort by most popular first
                sorted_picks = sorted(champ_picks.items(), key=lambda x: len(x[1]), reverse=True)
                actual_champ = actual_winners[65] if len(actual_winners) > 65 and not is_unplayed(actual_winners[65]) else None

                for team, pickers in sorted_picks:
                    count = len(pickers)
                    logo_url = espn_logo_url(team)
                    is_correct = team == actual_champ
                    is_eliminated = team not in truly_alive and not is_correct
                    border_color = "#16a34a" if is_correct else ("#ef4444" if is_eliminated else "#334155")
                    bg_color = "#052e16" if is_correct else ("#2d0a0a" if is_eliminated else "#1e1e2e")
                    name_color = "#f5c518"

                    logo_html = (
                        f'<img src="{logo_url}" style="width:36px;height:36px;object-fit:contain;'
                        f'vertical-align:middle;margin-right:10px;{"opacity:0.4;" if is_eliminated else ""}">'
                    ) if logo_url else ""

                    result_badge = " ✅" if is_correct else (" ❌" if is_eliminated else "")

                    # Format picker names — highlight current user
                    pickers_html = ""
                    for p in sorted(pickers):
                        if user_name and p == user_name:
                            pickers_html += f'<span style="color:#f5c518;font-weight:700;">{p}</span>, '
                        else:
                            pickers_html += f'<span style="color:#d1d5db;">{p}</span>, '
                    pickers_html = pickers_html.rstrip(", ")

                    seed = seed_map.get(team, "")
                    seed_str = f"({seed}) " if seed else ""

                    st.markdown(
                        f'<div style="border:1px solid {border_color};background:{bg_color};'
                        f'border-radius:12px;padding:12px 16px;margin-bottom:10px;">'
                        f'<div style="display:flex;align-items:center;margin-bottom:6px;">'
                        f'{logo_html}'
                        f'<span style="font-size:17px;font-weight:700;color:#fff;">{seed_str}{team}{result_badge}</span>'
                        f'<span style="margin-left:auto;background:#374151;border-radius:20px;'
                        f'padding:3px 10px;font-size:13px;color:#9ca3af;font-weight:600;">'
                        f'{count} pick{"s" if count != 1 else ""}</span>'
                        f'</div>'
                        f'<div style="font-size:12px;line-height:1.8;">{pickers_html}</div>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

    # ── Tab 4: Bonus Games (group) ────────────────────────────────────────────
    with tab_bonus:
        _sub_bon = st.session_state.get("nav_sub_bonus", "regional")
        _bon_options = [
            ("lucky-team",         "🍀 Lucky Team"),
            ("regional",           "🗺️ Regional Breakdown"),
            ("upset-picks",        "😤 Upset Picks"),
            ("correct-picks",      "✅ Correct Picks"),
            ("1st-weekend",        "♓ 1st Weekend Leader"),
            ("2nd-weekend",        "♈ 2nd Weekend Leader"),
            ("tiebreaker-scores",  "🎯 Tiebreaker Scores"),
            ("bonus-pool",         "💰 Bonus Pool"),
        ]
        _bon_row1 = st.columns(4)
        _bon_row2 = st.columns(4)
        for _i, (_slug, _label) in enumerate(_bon_options):
            _active = _sub_bon == _slug
            _col = _bon_row1[_i] if _i < 4 else _bon_row2[_i - 4]
            if _col.button(_label, key=f"bon_{_slug}",
                           use_container_width=True,
                           type="primary" if _active else "secondary"):
                st.session_state["nav_sub_bonus"] = _slug
                st.rerun()
        st.divider()
        _sub_bon = st.session_state.get("nav_sub_bonus", "regional")

        if _sub_bon == "lucky-team":
            st.subheader("🍀 Lucky Team — Still in the Hunt")

            if not lucky_map:
                st.info("No Lucky Team data found. Make sure the 'LuckyTeam' sheet exists and is accessible.")
            else:

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

                # Summary metrics — use all_starting/truly_alive for accurate tournament counts
                alive_teams            = truly_alive
                elim_teams             = all_starting - truly_alive
                participants_alive     = {r["Participant"] for r in rows if r["Status"] in {"✅ Still Alive", "🏆 Champion"}}
                st.markdown(f"""
                <div style="display:flex; gap:6px; width:100%; box-sizing:border-box; margin-bottom:8px;">
                  <div style="flex:1; background:#1e1e2e; border:1px solid #313244; border-radius:10px; padding:clamp(10px,2.5vw,16px); min-width:0; text-align:center;">
                    <div style="font-size:clamp(11px,2.5vw,13px); color:#888; margin-bottom:4px;">✅ Teams Still Alive</div>
                    <div style="font-size:clamp(28px,7vw,38px); font-weight:700; color:#4caf50; line-height:1.1;">{len(alive_teams)}</div>
                  </div>
                  <div style="flex:1; background:#1e1e2e; border:1px solid #313244; border-radius:10px; padding:clamp(10px,2.5vw,16px); min-width:0; text-align:center;">
                    <div style="font-size:clamp(11px,2.5vw,13px); color:#888; margin-bottom:4px;">❌ Teams Eliminated</div>
                    <div style="font-size:clamp(28px,7vw,38px); font-weight:700; color:#f44336; line-height:1.1;">{len(elim_teams)}</div>
                  </div>
                </div>
                <div style="display:flex; justify-content:center; margin-bottom:12px;">
                  <div style="flex:1; max-width:50%; background:#1e1e2e; border:1px solid #313244; border-radius:10px; padding:clamp(10px,2.5vw,16px); text-align:center;">
                    <div style="font-size:clamp(11px,2.5vw,13px); color:#888; margin-bottom:4px;">🍀 Participants Still Alive</div>
                    <div style="font-size:clamp(28px,7vw,38px); font-weight:700; color:#f5c518; line-height:1.1;">{len(participants_alive)}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

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
                            _lt_logo_url = espn_logo_url(team)
                            _lt_logo = (
                                f'<img src="{_lt_logo_url}" style="width:32px;height:32px;'
                                f'object-fit:contain;vertical-align:middle;margin-right:8px;" '
                                f'onerror="this.style.display=&quot;none&quot;">'
                            ) if _lt_logo_url else ""
                            st.markdown(
                                f"<div style='border:2px solid {border_color}; background:{bg_color}; "
                                f"border-radius:10px; padding:14px 16px; margin-bottom:12px;'>"
                                f"<div style='font-size:18px; font-weight:800; color:{border_color}; display:flex; align-items:center;'>"
                                f"{_lt_logo}#{seed_map.get(team, '?')} {team}</div>"
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
                        st.dataframe(elim_df, use_container_width=True, hide_index=True)

        elif _sub_bon == "regional":
            st.subheader("🗺️ Regional Breakdown — Top 20 by Region")
            st.caption("Points accumulated from each region's games (First Round through Elite 8)")

            regions = ["East", "West", "South", "Midwest"]

            for i in range(0, len(regions), 2):
                reg_cols = st.columns(2)
                for j, region in enumerate(regions[i:i+2]):
                    score_col   = f"{region} Score"
                    correct_col = f"{region} Correct"
                    region_df = (
                        pd.DataFrame([{
                            "Rank": 0,
                            "Name": r["Name"],
                            "Pts":  r.get(score_col, 0),
                            "Correct": r.get(correct_col, 0),
                        } for r in results])
                        .sort_values(["Pts", "Correct"], ascending=[False, False])
                        .head(20)
                        .reset_index(drop=True)
                    )
                    # Assign shared ranks: tied on both Pts AND Correct share a rank
                    _rank = 1
                    for _ri in range(len(region_df)):
                        if _ri > 0 and (
                            region_df.at[_ri, "Pts"] == region_df.at[_ri-1, "Pts"] and
                            region_df.at[_ri, "Correct"] == region_df.at[_ri-1, "Correct"]
                        ):
                            region_df.at[_ri, "Rank"] = region_df.at[_ri-1, "Rank"]
                        else:
                            region_df.at[_ri, "Rank"] = _rank
                        _rank += 1

                    with reg_cols[j]:
                        st.markdown(f"### {region}")
                        trs = ""
                        for _, row in region_df[["Rank", "Name", "Pts", "Correct"]].iterrows():
                            is_user = user_name and row["Name"] == user_name
                            row_style = ' style="background:#3a3000; color:#f5c518; font-weight:bold;"' if is_user else ""
                            trs += (
                                f'<tr{row_style}>'
                                f'<td style="width:28px;text-align:center;">{int(row["Rank"])}</td>'
                                f'<td style="max-width:90px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{row["Name"]}</td>'
                                f'<td style="width:36px;text-align:right;">{int(row["Pts"])}</td>'
                                f'<td style="width:44px;text-align:right;">{int(row["Correct"])}</td>'
                                f'</tr>'
                            )
                        st.markdown(f"""
                        <table style="border-collapse:collapse;width:100%;font-size:12px;">
                          <thead>
                            <tr style="background:#1e1e2e;color:#fff;">
                              <th style="width:28px;padding:4px 4px;text-align:center;border:1px solid #313244;">#</th>
                              <th style="padding:4px 6px;text-align:left;border:1px solid #313244;">Name</th>
                              <th style="width:36px;padding:4px 4px;text-align:right;border:1px solid #313244;">Pts</th>
                              <th style="width:44px;padding:4px 4px;text-align:right;border:1px solid #313244;">Correct</th>
                            </tr>
                          </thead>
                          <tbody style="color:#fff;">
                            {trs}
                          </tbody>
                        </table>
                        """, unsafe_allow_html=True)

        elif _sub_bon == "upset-picks":
            st.subheader("😤 Upset Picks — Correctly Predicted Upsets")
            st.caption("An upset is when the winning team's seed is at least 3 higher than the losing team's seed (e.g. a 10 seed beating a 7 seed)")

            upset_rows = sorted(
                [{"Name": r["Name"], "Upset Picks": r.get("Upset Correct", 0)} for r in results],
                key=lambda x: x["Upset Picks"], reverse=True
            )
            # Assign ranks (tied players share the same rank)
            ranked = []
            rank = 1
            for i, row in enumerate(upset_rows):
                if i > 0 and row["Upset Picks"] < upset_rows[i-1]["Upset Picks"]:
                    rank = i + 1
                ranked.append({"Rank": rank, "Name": row["Name"], "Upset Picks": row["Upset Picks"]})

            trs = ""
            for row in ranked:
                is_user = user_name and row["Name"] == user_name
                row_style = ' style="background:#3a3000; color:#f5c518; font-weight:bold;"' if is_user else ""
                trs += (
                    f'<tr{row_style}>'
                    f'<td style="width:40px;text-align:center;">{row["Rank"]}</td>'
                    f'<td style="padding:4px 8px;">{row["Name"]}</td>'
                    f'<td style="width:80px;text-align:center;">{row["Upset Picks"]}</td>'
                    f'</tr>'
                )
            st.markdown(f"""
            <table style="border-collapse:collapse;width:100%;max-width:480px;font-size:13px;">
              <thead>
                <tr style="background:#1e1e2e;color:#fff;">
                  <th style="width:40px;padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>
                  <th style="padding:6px 8px;text-align:left;border:1px solid #313244;">Name</th>
                  <th style="width:80px;padding:6px 4px;text-align:center;border:1px solid #313244;">Correct Upsets</th>
                </tr>
              </thead>
              <tbody style="color:#fff;">
                {trs}
              </tbody>
            </table>
            """, unsafe_allow_html=True)

        elif _sub_bon == "tiebreaker-scores":
            st.subheader("🎯 Tiebreaker Scores")

            # Final score banner
            if final_score is not None:
                st.markdown(
                    f'<div style="background:#14532d;border:1px solid #16a34a;border-radius:8px;'
                    f'padding:12px 20px;display:inline-block;margin-bottom:16px;">'
                    f'<span style="color:#9ca3af;font-size:12px;">Championship Final Score</span><br>'
                    f'<span style="color:#d1fae5;font-size:32px;font-weight:700;">{final_score}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="background:#1e1e2e;border:1px solid #374151;border-radius:8px;'
                    'padding:12px 20px;display:inline-block;margin-bottom:16px;">'
                    '<span style="color:#9ca3af;font-size:12px;">Championship Final Score</span><br>'
                    '<span style="color:#6b7280;font-size:32px;font-weight:700;">TBD</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

            if not tiebreaker_guesses:
                st.info("No tiebreaker guesses found. Make sure the TiebreakerScores sheet is accessible.")
            else:
                # Build rows — include diff only if final score is known
                tb_rows = []
                for name, guess in tiebreaker_guesses.items():
                    diff = abs(guess - final_score) if final_score is not None else None
                    tb_rows.append({"Name": name, "guess": guess, "diff": diff})

                if final_score is not None:
                    tb_rows.sort(key=lambda x: x["diff"])
                else:
                    tb_rows.sort(key=lambda x: x["Name"].lower())

                # Assign ranks (tied players share rank, only when final score known)
                ranked_tb = []
                rank = 1
                for i, row in enumerate(tb_rows):
                    if final_score is not None:
                        if i > 0 and row["diff"] != tb_rows[i-1]["diff"]:
                            rank = i + 1
                        ranked_tb.append({"Rank": rank, "Name": row["Name"],
                                          "Tiebreaker Score": row["guess"],
                                          "Difference": row["diff"]})
                    else:
                        ranked_tb.append({"Rank": "—", "Name": row["Name"],
                                          "Tiebreaker Score": row["guess"],
                                          "Difference": "TBD"})

                trs = ""
                for row in ranked_tb:
                    is_user = user_name and row["Name"] == user_name
                    row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if is_user else ""
                    diff_str = f'+{row["Difference"]}' if isinstance(row["Difference"], int) and row["Difference"] >= 0 else str(row["Difference"])
                    trs += (
                        f'<tr{row_style}>'
                        f'<td style="width:40px;text-align:center;">{row["Rank"]}</td>'
                        f'<td style="padding:5px 10px;">{row["Name"]}</td>'
                        f'<td style="width:110px;text-align:center;">{row["Tiebreaker Score"]}</td>'
                        f'<td style="width:90px;text-align:center;">{diff_str}</td>'
                        f'</tr>'
                    )
                st.markdown(f"""
                <table style="border-collapse:collapse;width:100%;max-width:520px;font-size:13px;">
                  <thead>
                    <tr style="background:#1e1e2e;color:#fff;">
                      <th style="width:40px;padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>
                      <th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>
                      <th style="width:110px;padding:6px 4px;text-align:center;border:1px solid #313244;">Tiebreaker Score</th>
                      <th style="width:90px;padding:6px 4px;text-align:center;border:1px solid #313244;">Difference</th>
                    </tr>
                  </thead>
                  <tbody style="color:#fff;">
                    {trs}
                  </tbody>
                </table>
                """, unsafe_allow_html=True)

        elif _sub_bon in ("1st-weekend", "2nd-weekend"):
            is_1st = _sub_bon == "1st-weekend"
            if is_1st:
                st.subheader("♓ 1st Weekend Leader")
                st.caption("Standings at the conclusion of the Second Round")
                col_end = 51   # score cols 3..50 inclusive
                round_label = "Second Round"
            else:
                st.subheader("♈ 2nd Weekend Leader")
                st.caption("Standings at the conclusion of the Elite 8")
                col_end = 63   # score cols 3..62 inclusive
                round_label = "Elite 8"

            # Check if the relevant rounds are complete
            relevant_played = [c for c in range(3, col_end) if not is_unplayed(actual_winners[c])]
            relevant_unplayed = [c for c in range(3, col_end) if is_unplayed(actual_winners[c])]
            rounds_complete = len(relevant_unplayed) == 0

            if not rounds_complete:
                remaining = len(relevant_unplayed)
                st.info(f"⏳ {remaining} game(s) remaining before the {round_label} concludes. Standings will finalize once all games are played.")

            # Score each participant through col_end only
            wknd_rows = []
            for i in range(3, len(df_p)):
                row = df_p.iloc[i]
                nm = str(row[0]).strip()
                if not nm or nm in {"Winner", ""} or nm.lower() == "nan":
                    continue
                p_picks = [str(row[c]).strip() if c < len(row) else "" for c in range(67)]
                score = sum(
                    points_per_game[c] + seed_map.get(p_picks[c], 0)
                    for c in range(3, col_end)
                    if not is_unplayed(actual_winners[c]) and p_picks[c] == actual_winners[c]
                )
                wknd_rows.append({"Name": nm, "score": score})

            wknd_rows.sort(key=lambda x: x["score"], reverse=True)

            # Assign ranks with ties
            ranked_wknd = []
            rank = 1
            for i, row in enumerate(wknd_rows):
                if i > 0 and row["score"] < wknd_rows[i-1]["score"]:
                    rank = i + 1
                ranked_wknd.append({"Rank": rank, "Name": row["Name"], "Score": row["score"]})

            trs = ""
            for row in ranked_wknd:
                is_user = user_name and row["Name"] == user_name
                row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if is_user else ""
                trs += (
                    f'<tr{row_style}>'
                    f'<td style="width:40px;text-align:center;">{row["Rank"]}</td>'
                    f'<td style="padding:5px 10px;">{row["Name"]}</td>'
                    f'<td style="width:70px;text-align:center;">{row["Score"]}</td>'
                    f'</tr>'
                )
            st.markdown(f"""
            <table style="border-collapse:collapse;width:100%;max-width:400px;font-size:13px;">
              <thead>
                <tr style="background:#1e1e2e;color:#fff;">
                  <th style="width:40px;padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>
                  <th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>
                  <th style="width:70px;padding:6px 4px;text-align:center;border:1px solid #313244;">Score</th>
                </tr>
              </thead>
              <tbody style="color:#fff;">
                {trs}
              </tbody>
            </table>
            """, unsafe_allow_html=True)

        elif _sub_bon == "bonus-pool":
            st.subheader("💰 Bonus Pool")
            st.caption("Separate pool for opted-in participants — Top 2 finish pays out")

            # Filter to bonus pool participants only
            bonus_df = final_df[final_df["Bonus Pool"] == True].copy()
            bonus_df = bonus_df.sort_values("Current Score", ascending=False).reset_index(drop=True)

            if bonus_df.empty:
                st.info("No participants have opted into the Bonus Pool yet.")
            else:
                # Compute bonus-pool-specific Monte Carlo probabilities
                # Build a name->raw_picks lookup from results to guarantee correct ordering
                _raw_picks_map = {r["Name"]: r["raw_picks"] for r in results}
                bonus_names  = tuple(bonus_df["Name"].tolist())
                bonus_picks  = tuple(
                    tuple(_raw_picks_map[n]) for n in bonus_names if n in _raw_picks_map
                )
                # Rebuild bonus_names to only include those with picks (should be all)
                bonus_names = tuple(n for n in bonus_names if n in _raw_picks_map)
                bonus_win_probs, bonus_top3_probs = run_monte_carlo(
                    bonus_names, bonus_picks,
                    tuple(actual_winners), tuple(points_per_game),
                    tuple(all_alive), tuple(seed_map.items()),
                    r1_contestants,
                    top_n=2,
                )

                # Potential Status: Top 2 instead of Top 3
                bonus_df["Win %"]   = bonus_df["Name"].map(lambda n: bonus_win_probs.get(n, 0.0))
                bonus_df["Top 2 %"] = bonus_df["Name"].map(lambda n: bonus_top3_probs.get(n, 0.0))
                def _bonus_status(row):
                    if row["Win %"] > 0:
                        return "🏆 Champion"
                    elif row["Top 2 %"] > 0:
                        return "🥈 Top 2"
                    else:
                        return "❌ Out"
                bonus_df["Potential Status"] = bonus_df.apply(_bonus_status, axis=1)
                bonus_df["Bonus Rank"] = range(1, len(bonus_df) + 1)

                # Format for display
                bp_display = bonus_df[["Bonus Rank", "Name", "Current Score", "Potential Score", "Win %", "Top 2 %", "Potential Status"]].copy()
                bp_display = bp_display.rename(columns={"Bonus Rank": "Rank"})
                bp_display["Win %"]   = bp_display["Win %"].map("{:.1f}%".format)
                bp_display["Top 2 %"] = bp_display["Top 2 %"].map("{:.1f}%".format)

                def _bp_highlight(row):
                    if user_name and row["Name"] == user_name:
                        return ["background-color:#3a3000;color:#f5c518;font-weight:bold"] * len(row)
                    return [""] * len(row)
                styled = bp_display.style.apply(_bp_highlight, axis=1)
                st.dataframe(styled, use_container_width=True, hide_index=True,
                             height=min(500, 44 + len(bp_display) * 36))


        elif _sub_bon == "correct-picks":
            st.subheader("✅ Correct Picks — Most Individual Correct Picks")
            st.caption("Total number of correct picks regardless of points value")

            correct_rows = sorted(
                [{"Name": r["Name"], "Correct Picks": sum(
                    1 for c in range(3, 66)
                    if not is_unplayed(actual_winners[c]) and r["raw_picks"][c] == actual_winners[c]
                )} for r in results],
                key=lambda x: x["Correct Picks"], reverse=True
            )

            # Assign ranks with ties
            ranked_cp = []
            rank = 1
            for i, row in enumerate(correct_rows):
                if i > 0 and row["Correct Picks"] < correct_rows[i-1]["Correct Picks"]:
                    rank = i + 1
                ranked_cp.append({"Rank": rank, "Name": row["Name"], "Correct Picks": row["Correct Picks"]})

            trs = ""
            for row in ranked_cp:
                is_user = user_name and row["Name"] == user_name
                row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if is_user else ""
                trs += (
                    f'<tr{row_style}>'
                    f'<td style="width:40px;text-align:center;">{row["Rank"]}</td>'
                    f'<td style="padding:5px 10px;">{row["Name"]}</td>'
                    f'<td style="width:90px;text-align:center;">{row["Correct Picks"]}</td>'
                    f'</tr>'
                )
            st.markdown(f"""
            <table style="border-collapse:collapse;width:100%;max-width:420px;font-size:13px;">
              <thead>
                <tr style="background:#1e1e2e;color:#fff;">
                  <th style="width:40px;padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>
                  <th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>
                  <th style="width:90px;padding:6px 4px;text-align:center;border:1px solid #313244;">Correct Picks</th>
                </tr>
              </thead>
              <tbody style="color:#fff;">
                {trs}
              </tbody>
            </table>
            """, unsafe_allow_html=True)

        # ── Tab 5: Hall of Champions ─────────────────────────────────────────────
    with tab_hoc:
        st.subheader("👑 Hall of Champions")
        st.caption("A record of every pool champion and the tournament that crowned them.")
        st.markdown("")

        # ── Champion entries — add new years here ──────────────────────────
        # Each entry: year, champion name, image path or URL, description
        CHAMPIONS = [
            {
                "year": 2016,
                "name": "Alana Davis",
                "image": "https://mrstream.neocities.org/img/BracketCards/2016AlanaDavis.png",
                "champion_pick": "Kansas",
                "tournament_champion": "Villanova",
                "alma_mater": "SUNY New Paltz",
                "2nd_name": "Pete Mullin",
                "2nd_pick": "Kansas",
                "3rd_name": "Laura Rubin",
                "3rd_pick": "Kansas",
                                "description": "The 2016 tournament was a wild ride featuring a historic 15-over-2 upset by Middle Tennessee and a legendary Villanova buzzer-beater in the final. Alana Davis navigated the chaos to claim our inaugural title, narrowly edging out Pete Mullin in a race that came down to the very last game. By the time the nets were cut down, Alana stood alone as the first-ever champion of this storied pool!",
            },
            {
                "year": 2017,
                "name": "Sarah Keo",
                "image": "https://mrstream.neocities.org/img/BracketCards/2017SarahKeo.png",
                "champion_pick": "North Carolina",
                "tournament_champion": "North Carolina",
                "alma_mater": "University of Washington",
                "2nd_name": "Molly Davis",
                "2nd_pick": "Gonzaga",
                "3rd_name": "Jared Goldstein",
                "3rd_pick": "UCLA",
                                "description": "In 2017, rookie Sarah Keo proved that spreadsheet mastery can beat basketball knowledge by \"math-ing\" her way all the way to the top spot. The title race came down to the wire against Molly, but Sarah's faith in UNC paid off when they defeated Gonzaga 71-65. It was a clinical performance that showed the pool exactly how powerful a well-organized data set can be.",
            },
            {
                "year": 2018,
                "name": "Jaymi Lynne",
                "image": "https://mrstream.neocities.org/img/BracketCards/2018JaymiLynne.png",
                "champion_pick": "Villanova",
                "tournament_champion": "Villanova",
                "alma_mater": "Liberty University",
                "2nd_name": "Dylan Driver",
                "2nd_pick": "Kansas",
                "3rd_name": "Robert Dick",
                "3rd_pick": "Gonzaga",
                                "description": "2018 was the year of the \"Heart-Over-Head\" strategy as Jaymi Lynne rode a powerhouse Villanova team to a dominant victory over Dylan Driver and Robert. While others faltered, Jaymi's Wildcats took care of business against both Kansas and Michigan to seal her crown. She didn't just win; she set the record for the \"Largest Margin of Victory\" in pool history — a record that still stands today!",
            },
            {
                "year": 2019,
                "name": "Armando Zamudio",
                "image": "https://mrstream.neocities.org/img/BracketCards/2019ArmandoZamudio.png",
                "champion_pick": "North Carolina",
                "tournament_champion": "Virginia",
                "alma_mater": "Columbia College Chicago",
                "2nd_name": "Dylan Grassl",
                "2nd_pick": "Kentucky",
                "3rd_name": "Tenley McCladdie",
                "3rd_pick": "Duke",
                                "description": "2019 saw rookie Armando Zamudio take the crown from a New York high-rise, creating some legendary workplace tension along the way! The tournament was defined by Virginia's high-drama, controversial win over Auburn, which paved the way for Armando to clinch the title over Dylan Grassl and Tenley. Though he retired after 2021, Armando's championship run remains a classic pool legend.",
            },
            {
                "year": 2021,
                "name": "Priya Gupta",
                "image": "https://mrstream.neocities.org/img/BracketCards/2021PriyaGupta.png",
                "champion_pick": "Gonzaga",
                "tournament_champion": "Baylor",
                "alma_mater": "UCLA",
                "2nd_name": "Kelyn Ikegami",
                "2nd_pick": "Gonzaga",
                "3rd_name": "Mike Plante",
                "3rd_pick": "Gonzaga",
                                "description": "After a year away, 2021 returned with a bang as Priya Gupta rode her UCLA Bruins' miraculous \"First Four to Final Four\" run all the way to 1st place! While most brackets were busted by the 11-seed's success, Priya's alma mater loyalty combined with a Baylor championship pick secured her the win over Kelyn and Mike. It was a masterclass in \"homer\" picking actually paying off in the biggest way possible!",
            },
            {
                "year": 2022,
                "name": "James Sawaya",
                "image": "https://mrstream.neocities.org/img/BracketCards/2022JamesSawaya.png",
                "champion_pick": "Kansas",
                "tournament_champion": "Kansas",
                "alma_mater": "Westminster University",
                "2nd_name": "Bryce Carlson",
                "2nd_pick": "Kansas",
                "3rd_name": "Siobhan Doheny",
                "3rd_pick": "Kansas",
                                "description": "2022 was finally the year for James Sawaya, who capitalized on years of top-10 finishes to grab the gold. After correctly calling Richmond's upset over Iowa, James was the only person left with a perfect Final Four going into the Elite Eight. He solidified his championship when Kansas cut down the nets, likely celebrating mid-flight while his competitors watched from the ground!",
            },
            {
                "year": 2023,
                "name": "Lauren Froman",
                "image": "https://mrstream.neocities.org/img/BracketCards/2023LaurenFroman.png",
                "champion_pick": "UConn",
                "tournament_champion": "UConn",
                "alma_mater": "Grand Valley State University",
                "2nd_name": "Jaymi Lynne",
                "2nd_pick": "Penn State",
                "3rd_name": "Matt Reid",
                "3rd_pick": "UConn",
                                "description": "The 2023 tournament featured a masterclass in resilience from Lauren Froman, who climbed from 60th place all the way to the winner's circle. Despite not being from New England, she was the only participant to correctly pick UConn to go all the way, out-dueling a crowd of Connecticut loyalists in the process. She trailed Jaymi going into the final, but the Huskies' victory earned her a permanent spot in the Hall of Champions!",
            },
            {
                "year": 2024,
                "name": "Tenley McLaddie",
                "image": "https://mrstream.neocities.org/img/BracketCards/2024TenleyMcLaddie.png",
                "champion_pick": "Purdue",
                "tournament_champion": "UConn",
                "alma_mater": "George Washington University",
                "2nd_name": "Ryan Sargent",
                "2nd_pick": "UConn",
                "3rd_name": "Ryan Reyes",
                "3rd_pick": "UConn",
                                "description": "Tenley McLaddie pulled off the ultimate \"worst to first\" story in 2024, rebounding from a dead-last ranking on Day 1 to claim the overall title. Her surge began in the second round, and she officially took control of the leaderboard after Alabama's upset win over UNC in the Sweet 16. By the time Purdue punched their ticket to the Championship game, Tenley had officially secured her place as our 2024 winner!",
            },
            {
                "year": 2025,
                "name": "Alana Davis",
                "image": "https://mrstream.neocities.org/img/BracketCards/2025AlanaDavis.png",
                "champion_pick": "Florida",
                "tournament_champion": "Florida",
                "alma_mater": "SUNY New Paltz",
                "2nd_name": "Bryce Carlson",
                "2nd_pick": "Florida",
                "3rd_name": "Sarah Keo",
                "3rd_pick": "Duke",
                                "description": "History was made in 2025 as Alana Davis became our first-ever two-time champion, reclaiming the crown she first wore nearly a decade prior. Her bold pick of Houston over Gonzaga in the second round proved to be the winning move in a massive field of 65 participants. She navigated a tense Final Four with ice in her veins, proving that her 2016 victory was definitely no fluke!",
            },
        ]

        NCAA_LOGO_SLUGS = {
            "Villanova":                     "villanova",
            "North Carolina":                "north-carolina",
            "Virginia":                      "virginia",
            "UCLA":                          "ucla",
            "Baylor":                        "baylor",
            "Kansas":                        "kansas",
            "UConn":                         "uconn",
            "Connecticut":                   "uconn",
            "Florida":                       "florida",
            "Liberty University":            "liberty",
            "Liberty":                       "liberty",
            "Grand Valley State University": "grand-valley-st",
            "Grand Valley State":            "grand-valley-st",
            "George Washington University":  "george-washington",
            "George Washington":             "george-washington",
            "University of Washington":      "washington",
            "Washington":                    "washington",
            "SUNY New Paltz":                "suny-new-paltz",
            "Columbia College Chicago":      "columbia-chicago",
            "Westminster University":        "westminster-ut",
            "Gonzaga":                       "gonzaga",
            "Duke":                          "duke",
            "Kentucky":                      "kentucky",
            "Penn State":                    "penn-st",
            "Purdue":                        "purdue",
        }
        def _ncaa_logo(school, size=28):
            slug = NCAA_LOGO_SLUGS.get(school)
            if slug:
                url = f"https://www.ncaa.com/sites/default/files/images/logos/schools/bgd/{slug}.svg"
                return (f'<img src="{url}" style="width:{size}px;height:{size}px;object-fit:contain;' +
                        f'vertical-align:middle;margin-right:6px;" ' +
                        f'onerror="this.style.display=&quot;none&quot;">')
            return ""

        def _pill_simple(icon, label, pick, pick_logo, correct=False):
            """Pill without participant name (Champion and Pick pills)."""
            pick_color = "#d1fae5" if correct else "#e5e7eb"
            pick_weight = "700" if correct else "500"
            return (
                f'<div style="display:inline-flex;flex-direction:column;align-items:center;' +
                f'background:#1e1e2e;border:1px solid #313244;border-radius:16px;' +
                f'padding:10px 18px;width:100%;text-align:center;box-sizing:border-box;">' +
                f'<span style="color:#6b7280;font-size:12px;margin-bottom:8px;">{icon} {label}</span>' +
                f'<span style="display:flex;align-items:center;justify-content:center;">' +
                f'{pick_logo}<span style="color:{pick_color};font-weight:{pick_weight};font-size:14px;">{pick}</span>' +
                f'</span></div>'
            )

        def _pill_named(icon, label, name, pick, pick_logo):
            """Pill with participant name (2nd and 3rd place pills)."""
            return (
                f'<div style="display:inline-flex;flex-direction:column;align-items:center;' +
                f'background:#1e1e2e;border:1px solid #313244;border-radius:16px;' +
                f'padding:10px 18px;width:100%;text-align:center;box-sizing:border-box;">' +
                f'<span style="color:#6b7280;font-size:12px;margin-bottom:6px;">{icon} {label}</span>' +
                f'<span style="color:#fff;font-weight:600;font-size:14px;margin-bottom:6px;">{name}</span>' +
                f'<span style="display:flex;align-items:center;justify-content:center;">' +
                f'{pick_logo}<span style="color:#e5e7eb;font-weight:500;font-size:13px;">{pick}</span>' +
                f'</span></div>'
            )

        for champ in sorted(CHAMPIONS, key=lambda x: x["year"], reverse=True):
            _pick      = champ.get("champion_pick", "")
            _champ     = champ.get("tournament_champion", "")
            _2nd_name  = champ.get("2nd_name", "")
            _2nd_pick  = champ.get("2nd_pick", "")
            _3rd_name  = champ.get("3rd_name", "")
            _3rd_pick  = champ.get("3rd_pick", "")
            _correct   = _pick == _champ
            _first_name = champ["name"].split()[0]

            with st.container():
                st.markdown(
                    f'<div style="font-size:36px;font-weight:800;color:#f5c518;margin-bottom:12px;">' +
                    f'👑 {champ["year"]} — {champ["name"]}</div>',
                    unsafe_allow_html=True
                )
                img_col, txt_col = st.columns([1, 2], gap="large")
                with img_col:
                    if champ.get("image"):
                        st.markdown(
                            f'<div style="display:flex;justify-content:center;">' +
                            f'<img src="{champ["image"]}" style="width:min(260px,90%);border-radius:8px;">' +
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            '<div style="display:flex;justify-content:center;">' +
                            '<div style="width:260px;height:260px;background:#1e1e2e;border:1px solid #313244;' +
                            'border-radius:8px;display:flex;align-items:center;justify-content:center;">' +
                            '<span style="font-size:48px;">👑</span></div></div>',
                            unsafe_allow_html=True
                        )
                with txt_col:
                    pills = (
                        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">' +
                        _pill_simple("👑", "Champion",         _champ,   _ncaa_logo(_champ)) +
                        _pill_simple("🎯", f"{_first_name}'s Pick", _pick, _ncaa_logo(_pick), correct=_correct) +
                        (_pill_named("🥈", "2nd Place", _2nd_name, _2nd_pick, _ncaa_logo(_2nd_pick)) if _2nd_name else "<div></div>") +
                        (_pill_named("🥉", "3rd Place", _3rd_name, _3rd_pick, _ncaa_logo(_3rd_pick)) if _3rd_name else "<div></div>") +
                        f'</div>'
                    )
                    st.markdown(pills, unsafe_allow_html=True)
                    if champ.get("description"):
                        st.markdown(
                            f'<p style="margin-top:14px;color:#9ca3af;font-size:15px;line-height:1.7;">' +
                            champ["description"] +
                            f'</p>',
                            unsafe_allow_html=True
                        )
                st.markdown("---")



    st.markdown("---")
    st.caption(f"🕒 Last sync: {last_update} · 🔄 Monte Carlo: 1,000 runs · Built with Streamlit")

except Exception as e:
    st.error(f"Something went wrong: {e}")
    st.exception(e)
