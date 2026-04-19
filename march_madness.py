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

  /* ── Recap slideshow dot buttons ── */
  #recap-dot-row button {
    min-height: unset !important;
    height: 14px !important;
    width: 14px !important;
    padding: 0 !important;
    font-size: 8px !important;
    border-radius: 50% !important;
    line-height: 1 !important;
    min-width: unset !important;
  }

  /* ── Collapse zero/minimal-height JS-only iframes ── */
  iframe[height="0"], iframe[height="1"] {
    display: none !important;
  }

  /* ── Slideshow iframe: natural height, no overflow stealing ── */
  div[data-testid="stIFrame"]:has(iframe:not([height="0"]):not([height="1"])):not(:has(iframe[width="980px"])) iframe {
    min-width: unset !important;
    width: 100% !important;
    overflow: hidden !important;
  }

</style>
""", unsafe_allow_html=True)

# ─── 0. SESSION STATE & COOKIE MANAGER ───────────────────────────────────────
if "user_name" not in st.session_state:
    st.session_state["user_name"] = None
if "modal_done" not in st.session_state:
    st.session_state["modal_done"] = False
if "user_tz" not in st.session_state:
    st.session_state["user_tz"] = ""
if "admin_page_loads" not in st.session_state:
    st.session_state["admin_page_loads"] = 0
st.session_state["admin_page_loads"] += 1
if "admin_tab_visits" not in st.session_state:
    st.session_state["admin_tab_visits"] = {}

# Initialise cookie manager (requires: pip install streamlit-cookies-manager)
_cookies = None
if _cookies_available:
    _cookies = EncryptedCookieManager(prefix="march_madness_", password="mm_pool_2025")
    if not _cookies.ready():
        st.stop()   # waits for the browser to return cookie values

# ─── 1. CONFIGURATION ─────────────────────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/1M3nBX0a2qwPyMdWqzEztN4eKY1wS5FU3OGgxUeNWamI/edit"

# ── Hoops, She Did It Again — Women's Bracket Final Standings ──────────────────
WSBB_STANDINGS = [
    {"Rank":1,  "Name":"Priya Gupta",    "Points":352, "Correct Picks":53, "First Round":179, "Second Round":70,  "Sweet 16":31, "Elite 8":36, "Final Four":14, "Championship":22},
    {"Rank":2,  "Name":"Eric Rosano",    "Points":346, "Correct Picks":52, "First Round":171, "Second Round":64,  "Sweet 16":39, "Elite 8":36, "Final Four":14, "Championship":22},
    {"Rank":3,  "Name":"Andy Yardley",   "Points":330, "Correct Picks":52, "First Round":179, "Second Round":70,  "Sweet 16":31, "Elite 8":36, "Final Four":14, "Championship":0},
    {"Rank":3,  "Name":"Bryce Carlson",  "Points":330, "Correct Picks":52, "First Round":179, "Second Round":70,  "Sweet 16":31, "Elite 8":36, "Final Four":14, "Championship":0},
    {"Rank":5,  "Name":"Mike Plante",    "Points":325, "Correct Picks":51, "First Round":165, "Second Round":79,  "Sweet 16":31, "Elite 8":36, "Final Four":14, "Championship":0},
    {"Rank":6,  "Name":"Winnie Lee",     "Points":318, "Correct Picks":48, "First Round":156, "Second Round":67,  "Sweet 16":32, "Elite 8":27, "Final Four":14, "Championship":22},
    {"Rank":7,  "Name":"Siobhan Sargent","Points":314, "Correct Picks":50, "First Round":172, "Second Round":70,  "Sweet 16":31, "Elite 8":27, "Final Four":14, "Championship":0},
    {"Rank":8,  "Name":"Kellie Knight",  "Points":312, "Correct Picks":50, "First Round":182, "Second Round":63,  "Sweet 16":31, "Elite 8":36, "Final Four":0,  "Championship":0},
    {"Rank":9,  "Name":"Sarah Simonds",  "Points":310, "Correct Picks":50, "First Round":171, "Second Round":64,  "Sweet 16":39, "Elite 8":36, "Final Four":0,  "Championship":0},
    {"Rank":9,  "Name":"Alana Davis",    "Points":310, "Correct Picks":50, "First Round":171, "Second Round":64,  "Sweet 16":39, "Elite 8":36, "Final Four":0,  "Championship":0},
    {"Rank":11, "Name":"Heidi Bruce",    "Points":303, "Correct Picks":47, "First Round":141, "Second Round":68,  "Sweet 16":31, "Elite 8":27, "Final Four":14, "Championship":22},
    {"Rank":12, "Name":"Amanda Kosack",  "Points":282, "Correct Picks":47, "First Round":143, "Second Round":64,  "Sweet 16":39, "Elite 8":36, "Final Four":0,  "Championship":0},
    {"Rank":13, "Name":"Brace Snelling", "Points":279, "Correct Picks":45, "First Round":160, "Second Round":67,  "Sweet 16":34, "Elite 8":18, "Final Four":0,  "Championship":0},
    {"Rank":14, "Name":"Matt Reid",      "Points":264, "Correct Picks":44, "First Round":138, "Second Round":60,  "Sweet 16":39, "Elite 8":27, "Final Four":0,  "Championship":0},
    {"Rank":14, "Name":"Robert Dick",    "Points":264, "Correct Picks":44, "First Round":164, "Second Round":69,  "Sweet 16":31, "Elite 8":0,  "Final Four":0,  "Championship":0},
    {"Rank":16, "Name":"Glenn Isaacs",   "Points":248, "Correct Picks":38, "First Round":107, "Second Round":60,  "Sweet 16":18, "Elite 8":27, "Final Four":14, "Championship":22},
    {"Rank":17, "Name":"Jaymi Lynne",    "Points":209, "Correct Picks":33, "First Round":154, "Second Round":33,  "Sweet 16":13, "Elite 8":9,  "Final Four":0,  "Championship":0},
    {"Rank":18, "Name":"Dylan Levy",     "Points":207, "Correct Picks":34, "First Round":143, "Second Round":41,  "Sweet 16":14, "Elite 8":9,  "Final Four":0,  "Championship":0},
    {"Rank":19, "Name":"Lauren Froman",  "Points":187, "Correct Picks":31, "First Round":137, "Second Round":35,  "Sweet 16":6,  "Elite 8":9,  "Final Four":0,  "Championship":0},
]
WSBB_CHAMP = "UCLA"

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
@st.cache_data(ttl=60, show_spinner=False)
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
    # Normalize abbreviations — must be defined before seed_map building
    TEAM_ABBREVS = {
        "MICHST":  "Michigan St.",
        "SFLA":    "South Florida",
        "MIAOH":   "Miami (Ohio)",
        "PVAM":    "Prairie View",
        "KENSAW":  "Kennesaw St.",
        "MARYCA":  "Saint Mary's",
    }
    # Apply same normalization to MasterBracket so seed_map uses identical names
    df_seeds = df_seeds.replace(TEAM_ABBREVS)

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
            team_raw = TEAM_ABBREVS.get(team_raw, team_raw)  # normalize abbreviations
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

    # Apply abbreviation normalization to picks sheet
    df_p = df_p.replace(TEAM_ABBREVS)

    # Build case-insensitive seed lookup for name-variant resolution
    _seed_lower = {k.lower(): v for k, v in seed_map.items()}

    def _register_name(name):
        if name and name not in UNPLAYED and name not in seed_map:
            s = _seed_lower.get(name.lower())
            if s:
                seed_map[name] = s
                _seed_lower[name.lower()] = s

    # Register all normalized TEAM_ABBREVS values
    for name in TEAM_ABBREVS.values():
        _register_name(name)

    # Register all team names that appear in picks row 0 (original seedings per slot)
    try:
        _p0 = [str(df_p.iloc[0][c]).strip() for c in range(len(df_p.columns))]
        for name in _p0:
            _register_name(name)
    except Exception:
        pass

    winners_row      = [str(x).strip() for x in df_p.iloc[2].values]
    points_per_game  = [safe_int(p) for p in df_p.iloc[1].values]

    # Register all actual winners
    for name in winners_row:
        _register_name(name)

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
        df_tk = df_tk.replace(TEAM_ABBREVS)
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
    # slot_loser_map: slot -> loser (for per-game upset detection)
    # Built by scanning each played slot and finding which teams were picked there
    # but didn't win — those are the losers.
    defeated_map: dict[str, str] = {}
    slot_loser_map: dict[int, str] = {}
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
            slot_loser_map[c] = loser

    # Load final score from MasterBracket H43 (row 43, col 7, 0-indexed = iloc[42, 7])
    # Only set if the cell contains a positive number — stays None if blank/invalid
    final_score = None
    try:
        h43_val = str(df_seeds.iloc[42, 7]).strip() if len(df_seeds) > 42 and len(df_seeds.columns) > 7 else ""
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

    # Build seed_map from picks to ensure exact team name variants resolve correctly.
    # Builds a lowercase→seed lookup once, then registers any unmatched names.
    try:
        _seed_lower = {k.lower(): v for k, v in seed_map.items()}
        picks_row0 = [str(df_p.iloc[0][c]).strip() for c in range(len(df_p.columns))]

        def _ensure_seed(name):
            if name and name not in UNPLAYED and name not in seed_map:
                s = _seed_lower.get(name.lower())
                if s:
                    seed_map[name] = s
                    _seed_lower[name.lower()] = s

        # Register all actual winners
        for w in winners_row:
            _ensure_seed(w)

        # Register all participant picks
        for c in range(3, 66):
            for i in range(3, len(df_p)):
                pick = str(df_p.iloc[i][c]).strip() if c < len(df_p.columns) else ""
                _ensure_seed(pick)
    except Exception:
        pass

    return df_p, winners_row, points_per_game, seed_map, all_alive, all_starting, truly_alive, lucky_map, r1_matchups, defeated_map, slot_loser_map, team_to_region, datetime.now().strftime("%I:%M %p"), final_score, tiebreaker_guesses


# ─── 3. SCORING ───────────────────────────────────────────────────────────────
def score_picks(picks: list[str], winners: list[str], pts: list[int],
                seeds: dict[str, int], alive: set[str]) -> tuple[int, int]:
    """Return (current_score, potential_score)."""
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

            # Pure 50/50: pick randomly from the two actual contestants
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

            # Pure 50/50: pick randomly from the two actual contestants
            sim_w[c] = random.choice(list(contestants)) if contestants else "None"

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
            # Pure 50/50: pick randomly from the two actual contestants
            sim_w[c] = random.choice(list(contestants))

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
               pinned_cols=None, return_selected=False, nowrap_cols=None,
               desc_cols=None, asc_cols=None, comparator_cols=None):
    """
    Render a DataFrame using AgGrid with:
    - Alternating row shading
    - Hover highlight
    - Left-aligned text and numbers
    - Optional gold highlight for the current user's row
    - Optional % formatting
    - Optional column widths (col_config: dict of col_name -> width in px)
    - Optional pinned/frozen columns (pinned_cols: list of col names to pin left)
    - desc_cols: list of col names that sort descending on first click
    - asc_cols: list of col names that sort ascending on first click
    - comparator_cols: dict of col_name -> JS comparator function string
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
    )
    if return_selected:
        gb.configure_grid_options(rowSelection="single")
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

    # Apply first-click sort directions
    if desc_cols:
        for col_name in desc_cols:
            if col_name in df.columns:
                gb.configure_column(col_name, sortingOrder=["desc", "asc", None])
    if asc_cols:
        for col_name in asc_cols:
            if col_name in df.columns:
                gb.configure_column(col_name, sortingOrder=["asc", "desc", None])

    # Apply custom JS comparators
    if comparator_cols:
        for col_name, comparator_js in comparator_cols.items():
            if col_name in df.columns:
                gb.configure_column(col_name, comparator=JsCode(comparator_js))

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
    with st.spinner("🏀 Loading pool data..."):
        data = load_all_data()
    if not data:
        st.error("Could not load data. Check that the Google Sheet is publicly accessible.")
        st.stop()

    df_p, actual_winners, points_per_game, seed_map, all_alive, all_starting, truly_alive, lucky_map, r1_matchups, defeated_map, slot_loser_map, team_to_region, last_update, final_score, tiebreaker_guesses = data

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
                # Correct upset pick: winner seed - loser seed >= 3 (per-slot loser)
                loser = slot_loser_map.get(c, "")
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

    # Count remaining games to decide simulation vs exact enumeration
    _unplayed_slots = [c for c in range(3, 66) if is_unplayed(actual_winners[c])]
    _n_unplayed = len(_unplayed_slots)

    if _n_unplayed <= 8:
        # Exact enumeration — try all 2^n outcomes with equal probability
        import itertools
        win_probs  = {n: 0.0 for n in names_tuple}
        top3_probs = {n: 0.0 for n in names_tuple}

        # Build contestants for each unplayed slot using bracket parent structure
        _slot_contestants = {}
        for _c in _unplayed_slots:
            _parents = _BRACKET_PARENTS.get(_c)
            if _parents is None:
                _ta, _tb = r1_matchups.get(_c, ("", ""))
                _slot_contestants[_c] = [t for t in [_ta, _tb] if t]
            else:
                # For unplayed parents, we'll resolve during enumeration
                _slot_contestants[_c] = None  # resolved dynamically

        _n_outcomes = 0
        for _outcome_bits in itertools.product([0, 1], repeat=_n_unplayed):
            # Build simulated winners for this outcome
            _sim_w = list(actual_winners)
            for _i, _c in enumerate(_unplayed_slots):
                _parents = _BRACKET_PARENTS.get(_c)
                if _parents is None:
                    _teams = list(r1_matchups.get(_c, ("", "")))
                else:
                    _p1, _p2 = _parents
                    _t1 = _sim_w[_p1]
                    _t2 = _sim_w[_p2]
                    _teams = [t for t in [_t1, _t2] if t and not is_unplayed(t)]
                if len(_teams) >= 2:
                    _sim_w[_c] = _teams[_outcome_bits[_i] % len(_teams)]
                elif len(_teams) == 1:
                    _sim_w[_c] = _teams[0]

            # Score each participant
            _scored = []
            for _ni, _nm in enumerate(names_tuple):
                _pk = picks_matrix[_ni]
                _s = sum(
                    tuple(points_per_game)[_c] + seed_map.get(_pk[_c], 0)
                    for _c in range(3, 66)
                    if _pk[_c] == _sim_w[_c]
                )
                _scored.append((_nm, _s))
            _scored.sort(key=lambda x: x[1], reverse=True)
            _top_score = _scored[0][1]
            _winners_this = [n for n, s in _scored if s == _top_score]
            _share = 1.0 / len(_winners_this)
            for _nm in _winners_this:
                win_probs[_nm] += _share

            _top3_score = _scored[min(2, len(_scored)-1)][1]
            for _nm, _s in _scored[:3]:
                top3_probs[_nm] += 1
            for _nm, _s in _scored[3:]:
                if _s == _top3_score:
                    top3_probs[_nm] += 1
                else:
                    break
            _n_outcomes += 1

        # Normalize to percentages
        if _n_outcomes > 0:
            win_probs  = {n: v / _n_outcomes * 100 for n, v in win_probs.items()}
            top3_probs = {n: v / _n_outcomes * 100 for n, v in top3_probs.items()}
    else:
        # Monte Carlo simulation for larger numbers of remaining games
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

    # Build a lookup of potential score (ceiling) per person for Last Place calc
    _pot_lookup = {r["Name"]: r["Potential Score"] for r in results}

    for r in results:
        if r["Win %"] > 0:
            r["Potential Status"] = "🏆 Champion"
        elif r["Top 3 %"] > 0:
            r["Potential Status"] = "🥉 Top 3"
        elif r2_complete:
            # Mathematically out of Top 3 — check if still in contention for Last Place
            # Can finish last if current score <= at least one other player's ceiling
            _my_score = r["Current Score"]
            _others_ceilings = [
                _pot_lookup[other["Name"]]
                for other in results if other["Name"] != r["Name"]
            ]
            _can_last = _my_score <= min(_others_ceilings) if _others_ceilings else False
            if _can_last:
                r["Potential Status"] = "💩 Out/Last"
            else:
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

    # Pre-fill players from query params — applied once per navigation, then cleared
    try:
        _qp_tab  = st.query_params.get("tab", "")
        _qp_p1   = st.query_params.get("p1", "")
        _qp_p2   = st.query_params.get("p2", "")
        _name_lower_map = {n.lower(): n for n in name_opts}
        if _qp_tab == "my-recap" and _qp_p1:
            _m = _name_lower_map.get(_qp_p1.lower(), "")
            if _m:
                st.session_state["recap_my_name"] = _m
                st.session_state["nav_sub_recap"] = "mine"
            st.query_params.pop("p1", None)
        elif _qp_p1 or _qp_p2:
            if _qp_tab == "bracket-dna" and _qp_p1:
                _m = _name_lower_map.get(_qp_p1.lower(), "")
                if _m:
                    st.session_state["dna_sel"] = _m
                    st.session_state["dna"] = _m
                # Clear p1 from URL so user can freely change selection
                st.query_params.pop("p1", None)
            elif _qp_tab == "standings-progress":
                if _qp_p1:
                    _m = _name_lower_map.get(_qp_p1.lower(), "")
                    if _m:
                        st.session_state["sp_prog_name_sel"] = _m
                _sp_key = "sp_prog_highlighted"
                if _sp_key not in st.session_state:
                    st.session_state[_sp_key] = set()
                for _qi in range(2, 11):
                    _qv = st.query_params.get(f"p{_qi}", "")
                    if _qv:
                        _m = _name_lower_map.get(_qv.lower(), "")
                        if _m:
                            st.session_state[_sp_key].add(_m)
                # Clear params from URL
                for _qk in [f"p{i}" for i in range(1, 11)]:
                    st.query_params.pop(_qk, None)
            else:
                if _qp_p1:
                    _m = _name_lower_map.get(_qp_p1.lower(), "")
                    if _m:
                        st.session_state["_h2h_sel_p1"] = _m
                if _qp_p2:
                    _m = _name_lower_map.get(_qp_p2.lower(), "")
                    if _m:
                        st.session_state["_h2h_sel_p2"] = _m
                st.query_params.pop("p1", None)
                st.query_params.pop("p2", None)
    except Exception:
        pass

    # ── Admin Panel ──────────────────────────────────────────────────────────
    _admin_param = st.query_params.get("admin", "")
    if _admin_param == "1":
        if "admin_authenticated" not in st.session_state:
            st.session_state["admin_authenticated"] = False

        if not st.session_state["admin_authenticated"]:
            with st.expander("🔐 Admin Login", expanded=True):
                _admin_pw = st.text_input("Password", type="password", key="admin_pw_input")
                if st.button("Unlock", key="admin_unlock"):
                    try:
                        _correct = st.secrets.get("ADMIN_PASSWORD", "")
                    except Exception:
                        _correct = ""
                    if _admin_pw and _admin_pw == _correct:
                        st.session_state["admin_authenticated"] = True
                        st.rerun()
                    else:
                        st.error("Incorrect password.")
        else:
            with st.expander("⚙️ Admin Panel", expanded=True):
                st.markdown("### ⚙️ Admin Panel")
                _adm_tabs = st.tabs(["🔄 Cache", "📊 Raw Data", "🚨 Announcement", "🎚️ Feature Flags", "📈 Usage"])

                # ── Cache ─────────────────────────────────────────────────────
                with _adm_tabs[0]:
                    st.markdown("**Force data refresh** (clears the 60-second cache)")
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        st.metric("Last sync", last_update)
                    with _c2:
                        if st.button("🔄 Clear Cache & Reload", key="adm_clear_cache", type="primary"):
                            load_all_data.clear()
                            st.success("Cache cleared! Reloading...")
                            st.rerun()

                # ── Raw Data ─────────────────────────────────────────────────
                with _adm_tabs[1]:
                    _rd_choice = st.selectbox("View", ["Standings", "All Picks", "Tiebreaker Guesses", "Lucky Team", "Seeds"], key="adm_rd")
                    if _rd_choice == "Standings":
                        st.dataframe(final_df, use_container_width=True)
                    elif _rd_choice == "All Picks":
                        _picks_display = []
                        for _r in results:
                            _row = {"Name": _r["Name"], "Score": int(final_df[final_df["Name"]==_r["Name"]].iloc[0]["Current Score"]) if not final_df[final_df["Name"]==_r["Name"]].empty else 0}
                            for c in range(65, 66):
                                _row["Champ Pick"] = _r["raw_picks"][c] if c < len(_r["raw_picks"]) else ""
                            _picks_display.append(_row)
                        st.dataframe(pd.DataFrame(_picks_display).sort_values("Score", ascending=False), use_container_width=True)
                    elif _rd_choice == "Tiebreaker Guesses":
                        if tiebreaker_guesses and final_score:
                            _tb_disp = sorted([
                                {"Name": n, "Guess": g, "Diff": g - final_score, "Abs Diff": abs(g - final_score)}
                                for n, g in tiebreaker_guesses.items()
                            ], key=lambda x: x["Abs Diff"])
                            st.dataframe(pd.DataFrame(_tb_disp), use_container_width=True)
                        else:
                            st.info("No tiebreaker data or final score not set.")
                    elif _rd_choice == "Lucky Team":
                        if lucky_map:
                            _lm_rows = [{"Team": t, "Participants": ", ".join(ps)} for t, ps in lucky_map.items()]
                            st.dataframe(pd.DataFrame(_lm_rows), use_container_width=True)
                        else:
                            st.info("No lucky team data.")
                    elif _rd_choice == "Seeds":
                        _seed_rows = sorted([{"Team": t, "Seed": s} for t, s in seed_map.items() if s > 0], key=lambda x: x["Seed"])
                        st.dataframe(pd.DataFrame(_seed_rows), use_container_width=True)

                # ── Announcement ─────────────────────────────────────────────
                with _adm_tabs[2]:
                    st.markdown("Set a banner message shown to all users at the top of the page.")
                    _cur_ann = st.session_state.get("admin_announcement", "")
                    _ann_type = st.session_state.get("admin_announcement_type", "info")
                    _new_ann = st.text_area("Announcement text (leave blank to hide)", value=_cur_ann, key="adm_ann_text", height=80)
                    _new_type = st.selectbox("Style", ["info", "warning", "success", "error"], index=["info","warning","success","error"].index(_ann_type), key="adm_ann_type")
                    _ac1, _ac2 = st.columns(2)
                    with _ac1:
                        if st.button("💾 Save Announcement", key="adm_ann_save", type="primary"):
                            st.session_state["admin_announcement"] = _new_ann.strip()
                            st.session_state["admin_announcement_type"] = _new_type
                            st.success("Saved!")
                    with _ac2:
                        if st.button("🗑️ Clear Announcement", key="adm_ann_clear"):
                            st.session_state["admin_announcement"] = ""
                            st.success("Cleared!")

                # ── Feature Flags ─────────────────────────────────────────────
                with _adm_tabs[3]:
                    st.markdown("Toggle features on/off for all users.")
                    _ff_defaults = {
                        "ff_show_win_conditions": True,
                        "ff_show_lucky_team": True,
                        "ff_show_bonus_pool": True,
                        "ff_show_standings_progress": True,
                        "ff_show_pool_recap": True,
                        "ff_show_hoops_pool": True,
                    }
                    _ff_labels = {
                        "ff_show_win_conditions": "🔍 Win Conditions tab",
                        "ff_show_lucky_team": "🍀 Lucky Team section",
                        "ff_show_bonus_pool": "💰 Bonus Pool section",
                        "ff_show_standings_progress": "📈 Standings Progress tab",
                        "ff_show_pool_recap": "🎊 Pool Recap tab",
                        "ff_show_hoops_pool": "🏀 Hoops, She Did It Again section",
                    }
                    for _ffk, _ffd in _ff_defaults.items():
                        _cur_val = st.session_state.get(_ffk, _ffd)
                        _new_val = st.toggle(_ff_labels[_ffk], value=_cur_val, key=f"adm_{_ffk}")
                        if _new_val != _cur_val:
                            st.session_state[_ffk] = _new_val

                # ── Usage ─────────────────────────────────────────────────────
                with _adm_tabs[4]:
                    st.markdown("**Session stats**")
                    st.metric("Page loads this session", st.session_state.get("admin_page_loads", 0))
                    st.markdown("**Current session state**")
                    st.json({
                        "user_name": st.session_state.get("user_name", ""),
                        "modal_done": st.session_state.get("modal_done", False),
                        "nav_group": st.session_state.get("nav_group", ""),
                        "nav_sub_recap": st.session_state.get("nav_sub_recap", ""),
                        "nav_sub_standings": st.session_state.get("nav_sub_standings", ""),
                        "nav_sub_bonus": st.session_state.get("nav_sub_bonus", ""),
                        "final_score": final_score,
                        "total_participants": len(results),
                        "tiebreaker_count": len(tiebreaker_guesses) if tiebreaker_guesses else 0,
                        "last_sync": last_update,
                        "feature_flags": {
                            "pool_recap": st.session_state.get("ff_show_pool_recap", True),
                            "win_conditions": st.session_state.get("ff_show_win_conditions", True),
                            "lucky_team": st.session_state.get("ff_show_lucky_team", True),
                            "bonus_pool": st.session_state.get("ff_show_bonus_pool", True),
                            "standings_progress": st.session_state.get("ff_show_standings_progress", True),
                            "hoops_pool": st.session_state.get("ff_show_hoops_pool", True),
                        }
                    })
                    if st.button("🚪 Log out of admin", key="adm_logout"):
                        st.session_state["admin_authenticated"] = False
                        st.rerun()

    # ── Announcement banner (shown to all users if set) ──────────────────────
    _ann_text = st.session_state.get("admin_announcement", "")
    _ann_type = st.session_state.get("admin_announcement_type", "info")
    if _ann_text:
        getattr(st, _ann_type)(_ann_text)

    # ── Feature flag reads (used throughout app) ──────────────────────────────
    _ff_win_conditions     = st.session_state.get("ff_show_win_conditions", True)
    _ff_lucky_team         = st.session_state.get("ff_show_lucky_team", True)
    _ff_bonus_pool         = st.session_state.get("ff_show_bonus_pool", True)
    _ff_standings_progress = st.session_state.get("ff_show_standings_progress", True)
    _ff_pool_recap         = st.session_state.get("ff_show_pool_recap", True)
    _ff_hoops_pool         = st.session_state.get("ff_show_hoops_pool", True)


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
        "recap":           ("recap", None),
        "pool-highlights": ("recap", "highlights"),
        "my-recap":        ("recap", "mine"),
        "standings":       ("standings", None),
        "bracket":         ("your-bracket", "bracket"),
        "win-conditions":  ("your-bracket", "win-conditions"),
        "head-to-head":       ("your-bracket", "head-to-head"),
        "standings-progress": ("your-bracket", "standings-progress"),
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
        "snapshot-standings":   ("standings", "snapshot"),
        "still-alive":          ("standings", "alive"),
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
        st.session_state["nav_group"] = "recap"
    if "nav_sub_your-bracket" not in st.session_state:
        st.session_state["nav_sub_your-bracket"] = "bracket"
    if "nav_sub_fun-stats" not in st.session_state:
        st.session_state["nav_sub_fun-stats"] = "bracket-busters"
    if "nav_sub_bonus" not in st.session_state:
        st.session_state["nav_sub_bonus"] = "lucky-team"

    GROUP_TAB_INDEX = {
        "recap":           0,
        "hall-of-champs":  1,
        "standings":       2,
        "your-bracket":    3,
        "bonus":           4,
        "fun-stats":       5,
        "scores":          6,
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
    tab_recap, tab_hoc, tab_standings, tab_bracket, tab_bonus, tab_fun, tab_scores = st.tabs([
        "🎊 Pool Recap", "👑 Hall of Champions", "🏆 Standings", "🗂️ Your Bracket", "🎲 Bonus Games", "🎉 Fun Stats", "📺 Schedule/Scores",
    ])

    import streamlit.components.v1 as _components

    # Fire JS tab click on every rerun to keep the correct tab visually active.
    # Uses nav_group session state so it always reflects the user's current location.
    _jump_tab = st.session_state.pop("jump_to_tab_index", None)
    _current_group = st.session_state.get("nav_group", "standings")
    _active_tab_idx = GROUP_TAB_INDEX.get(_current_group, 0)
    # Only fire JS click if we need to switch away from tab 0, or have an explicit jump
    if _jump_tab is not None:
        _fire_idx = _jump_tab
        _components.html(
            f"""<script>
            (function() {{
                function clickTab() {{
                    var tabs = window.parent.document.querySelectorAll('button[data-baseweb="tab"]');
                    if (tabs.length > {_fire_idx}) {{
                        tabs[{_fire_idx}].click();
                    }} else {{
                        setTimeout(clickTab, 100);
                    }}
                }}
                setTimeout(clickTab, 150);
            }})();
            </script>""",
            height=1,
        )


    # ── Tab 0: Pool Recap ─────────────────────────────────────────────────────
    with tab_recap:
        if not _ff_pool_recap:
            st.info("🎊 Pool Recap is currently disabled by the admin.")
        if _ff_pool_recap:
            _recap_sub = st.session_state.get("nav_sub_recap", "highlights")
            _rc1, _rc2 = st.columns(2)
            if _rc1.button("🏆 Pool Highlights", key="recap_highlights", use_container_width=True,
                            type="primary" if _recap_sub == "highlights" else "secondary"):
                st.session_state["nav_sub_recap"] = "highlights"
                st.rerun()
            if _rc2.button("🪞 My Recap", key="recap_mine", use_container_width=True,
                            type="primary" if _recap_sub == "mine" else "secondary"):
                st.session_state["nav_sub_recap"] = "mine"
                st.rerun()
            st.divider()
            _recap_sub = st.session_state.get("nav_sub_recap", "highlights")

            def _recap_card(icon, label, value, sub="", c1="#1e1e2e", c2="#313244", extra_html=""):
                return (
                    f'<div style="background:linear-gradient(135deg,{c1},{c2});border-radius:16px;padding:20px 18px;margin-bottom:12px;text-align:center;">' +
                    f'<div style="font-size:26px;margin-bottom:6px;">{icon}</div>' +
                    f'<div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">{label}</div>' +
                    f'<div style="font-size:20px;font-weight:800;color:#fff;line-height:1.2;">{value}</div>' +
                    (f'<div style="font-size:12px;color:#9ca3af;margin-top:4px;">{sub}</div>' if sub else "") +
                    (f'<div style="margin-top:8px;display:flex;flex-wrap:wrap;justify-content:center;gap:2px;">{extra_html}</div>' if extra_html else "") +
                    '</div>'
                )

            if _recap_sub == "highlights":
                st.subheader("🎊 2026 Pool Highlights")

                _top3 = final_df.head(3)
                _champ_name  = _top3.iloc[0]["Name"]  if len(_top3) > 0 else "—"
                _champ_score = int(_top3.iloc[0]["Current Score"]) if len(_top3) > 0 else 0
                _2nd_name    = _top3.iloc[1]["Name"]  if len(_top3) > 1 else "—"
                _2nd_score   = int(_top3.iloc[1]["Current Score"]) if len(_top3) > 1 else 0
                _3rd_name    = _top3.iloc[2]["Name"]  if len(_top3) > 2 else "—"
                _3rd_score   = int(_top3.iloc[2]["Current Score"]) if len(_top3) > 2 else 0

                _tb_winner, _tb_diff_val, _tb_guess_val = "—", None, None
                _tb_2nd_name, _tb_2nd_diff, _tb_2nd_guess = "—", None, None
                if final_score and tiebreaker_guesses:
                    _tb_sorted = sorted(tiebreaker_guesses.items(), key=lambda x: abs(x[1] - final_score))
                    _tb_winner = _tb_sorted[0][0]
                    _tb_guess_val = _tb_sorted[0][1]
                    _tb_diff_val = _tb_guess_val - final_score
                    if len(_tb_sorted) > 1:
                        _tb_2nd_name  = _tb_sorted[1][0]
                        _tb_2nd_guess = _tb_sorted[1][1]
                        _tb_2nd_diff  = _tb_2nd_guess - final_score

                _bp_df2 = final_df[final_df["Bonus Pool"] == True].copy() if "Bonus Pool" in final_df.columns else pd.DataFrame()
                _bp_winner = _bp_df2.iloc[0]["Name"] if not _bp_df2.empty else "—"
                _bp_score2  = int(_bp_df2.iloc[0]["Current Score"]) if not _bp_df2.empty else 0
                _bp_2nd_name  = _bp_df2.iloc[1]["Name"] if len(_bp_df2) > 1 else "—"
                _bp_2nd_score = int(_bp_df2.iloc[1]["Current Score"]) if len(_bp_df2) > 1 else 0

                _upset_sorted2 = sorted(results, key=lambda r: r.get("Upset Correct", 0), reverse=True)
                _upset_count2 = _upset_sorted2[0].get("Upset Correct", 0) if _upset_sorted2 else 0
                _upset_winners2 = [r["Name"] for r in _upset_sorted2 if r.get("Upset Correct", 0) == _upset_count2]
                _upset_teams_map = {}
                for r in _upset_sorted2:
                    if r["Name"] in _upset_winners2:
                        _pk = r["raw_picks"]
                        _uts = []
                        for c in range(3, 66):
                            if c < len(_pk) and _pk[c] == actual_winners[c] and not is_unplayed(actual_winners[c]):
                                _w2 = _pk[c]; _ws2 = seed_map.get(_w2, 0)
                                _lo2 = slot_loser_map.get(c, ""); _ls2 = seed_map.get(_lo2, 0)
                                if _ws2 > 0 and _ls2 > 0 and (_ws2 - _ls2) >= 3:
                                    _uts.append(_w2)
                        _upset_teams_map[r["Name"]] = list(dict.fromkeys(_uts))

                _correct_sorted2 = sorted(results, key=lambda r: sum(
                    1 for c in range(3, 66) if not is_unplayed(actual_winners[c]) and r["raw_picks"][c] == actual_winners[c]
                ), reverse=True)
                _correct_count2 = sum(1 for c in range(3, 66) if not is_unplayed(actual_winners[c]) and _correct_sorted2[0]["raw_picks"][c] == actual_winners[c]) if _correct_sorted2 else 0
                _correct_winners2 = [r["Name"] for r in _correct_sorted2 if sum(
                    1 for c in range(3, 66) if not is_unplayed(actual_winners[c]) and r["raw_picks"][c] == actual_winners[c]
                ) == _correct_count2]

                def _wknd_pts2(r, col_end):
                    _pk = r["raw_picks"]
                    return sum(points_per_game[c] + seed_map.get(_pk[c], 0) for c in range(3, col_end)
                               if not is_unplayed(actual_winners[c]) and _pk[c] == actual_winners[c])
                _fw_sorted2 = sorted(results, key=lambda r: _wknd_pts2(r, 51), reverse=True)
                _fw_winner2 = _fw_sorted2[0]["Name"] if _fw_sorted2 else "—"
                _fw_score2  = _wknd_pts2(_fw_sorted2[0], 51) if _fw_sorted2 else 0
                _sw_sorted2 = sorted(results, key=lambda r: _wknd_pts2(r, 63), reverse=True)
                _sw_winner2 = _sw_sorted2[0]["Name"] if _sw_sorted2 else "—"
                _sw_score2  = _wknd_pts2(_sw_sorted2[0], 63) if _sw_sorted2 else 0

                _region_ff_team = {}
                for _ec in range(59, 63):
                    _ew = actual_winners[_ec] if _ec < len(actual_winners) and not is_unplayed(actual_winners[_ec]) else None
                    if _ew:
                        _er = slot_to_region.get(_ec, "")
                        if _er:
                            _region_ff_team[_er] = _ew

                _reg_tied_winners = {}
                for _reg2 in ["East", "West", "South", "Midwest"]:
                    _rgs = sorted(results, key=lambda r: r.get(f"{_reg2} Score", 0), reverse=True)
                    if _rgs:
                        _top_score = _rgs[0].get(f"{_reg2} Score", 0)
                        _tied = [r["Name"] for r in _rgs if r.get(f"{_reg2} Score", 0) == _top_score]
                        _reg_tied_winners[_reg2] = (_tied, int(_top_score))

                _tc = actual_winners[65] if len(actual_winners) > 65 and not is_unplayed(actual_winners[65]) else "TBD"
                _tc_seed = seed_map.get(_tc, 0)
                _tc_logo = espn_logo_url(_tc) or ""
                _tc_logo_html = (f'<img src="{_tc_logo}" style="width:44px;height:44px;object-fit:contain;vertical-align:middle;margin-right:10px;" onerror="this.style.display:none">') if _tc_logo else ""
                _lw = [p for t, ps in lucky_map.items() for p in ps if t == _tc]

                def _join_names(names):
                    if len(names) == 1: return names[0]
                    return ", ".join(names[:-1]) + ", and " + names[-1]

                def _hl(name):
                    if user_name and name == user_name:
                        return f'<span style="color:#f5c518;font-weight:900;">{name}</span>'
                    return name

                def _hl_names(names):
                    highlighted = [_hl(n) for n in names]
                    if len(highlighted) == 1: return highlighted[0]
                    return ", ".join(highlighted[:-1]) + ", and " + highlighted[-1]

                def _img(team, size=22):
                    u = espn_logo_url(team) or ""
                    return f'<img src="{u}" title="{team}" style="width:{size}px;height:{size}px;object-fit:contain;" onerror="this.style.display:none">' if u else ""

                # ── Build slide HTML list ─────────────────────────────────────────
                _slides = []

                # Slide 1: Tournament + Pool champion
                _s1 = (
                    f'<div style="text-align:center;">' +
                    f'<div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:16px;padding:20px;margin-bottom:12px;">' +
                    f'<div style="font-size:11px;color:#9ca3af;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;">2026 Tournament Champion</div>' +
                    f'<div style="display:flex;align-items:center;justify-content:center;">{_tc_logo_html}<span style="font-size:24px;font-weight:900;color:#f5c518;">({_tc_seed}) {_tc}</span></div>' +
                    f'</div>' +
                    f'<div style="background:linear-gradient(135deg,#FFCB05,#e6b800);border-radius:16px;padding:20px;">' +
                    f'<div style="font-size:32px;">🏆</div>' +
                    f'<div style="font-size:11px;color:#00274C;letter-spacing:2px;text-transform:uppercase;margin:4px 0;font-weight:700;">Pool Champion</div>' +
                    f'<div style="font-size:28px;font-weight:900;color:#00274C;">{_hl(_champ_name)}</div>' +
                    f'<div style="font-size:15px;color:#00274C;font-weight:600;">{_champ_score} pts</div>' +
                    f'<div style="margin-top:10px;"><img src="https://mrstream.neocities.org/img/BracketCards/2026ChrisCard.png" style="width:85%;max-width:260px;border-radius:10px;object-fit:contain;" onerror="this.style.display:none"></div>' +
                    f'</div></div>'
                )
                _slides.append(("🏆 Pool Champion", _s1))

                # Slide 2: Runner Ups
                _s2 = (
                    f'<div style="display:flex;flex-direction:column;gap:12px;text-align:center;">' +
                    f'<div style="background:#374151;border-radius:14px;padding:18px;"><div style="font-size:28px;">🥈</div><div style="font-size:10px;color:#9ca3af;text-transform:uppercase;margin:4px 0;">2nd Place</div><div style="font-size:20px;font-weight:800;color:#e5e7eb;">{_hl(_2nd_name)}</div><div style="font-size:13px;color:#9ca3af;">{_2nd_score} pts</div></div>' +
                    f'<div style="background:#374151;border-radius:14px;padding:18px;"><div style="font-size:28px;">🥉</div><div style="font-size:10px;color:#9ca3af;text-transform:uppercase;margin:4px 0;">3rd Place</div><div style="font-size:20px;font-weight:800;color:#e5e7eb;">{_hl(_3rd_name)}</div><div style="font-size:13px;color:#9ca3af;">{_3rd_score} pts</div></div>' +
                    f'</div>'
                )
                _slides.append(("🎀 Runner Ups", _s2))

                # Slide 3: Lucky Team
                if _lw:
                    _lt_logo_url = espn_logo_url(_tc) or ""
                    _lt_logo = _img(_tc, 32)
                    _s3 = (
                        f'<div style="background:linear-gradient(135deg,#14532d,#166534);border-radius:16px;padding:24px;text-align:center;">' +
                        f'<div style="font-size:32px;margin-bottom:6px;">🍀</div>' +
                        f'<div style="font-size:11px;color:#86efac;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Lucky Team Winner</div>' +
                        f'<div style="font-size:22px;font-weight:800;color:#fff;line-height:1.2;">{_hl_names(_lw)}</div>' +
                        f'<div style="font-size:12px;color:#86efac;margin-top:6px;">Lucky Team: ({_tc_seed}) {_tc}</div>' +
                        f'<div style="margin-top:10px;display:flex;justify-content:center;">{_lt_logo}</div>' +
                        f'</div>'
                    )
                    _slides.append(("🍀 Lucky Team", _s3))

                # Slide 4: Upset Picks — logos specific to each player's correct upset picks
                _upset_names_str = _hl_names(_upset_winners2)
                _per_player_logos = ""
                for _un in _upset_winners2:
                    # Find this player's row in results
                    _ur = next((r for r in results if r["Name"] == _un), None)
                    if not _ur:
                        continue
                    _u_logos = ""
                    for c in range(3, 66):
                        if (_ur["raw_picks"][c] == actual_winners[c] and not is_unplayed(actual_winners[c])):
                            _w = actual_winners[c]
                            _ws = seed_map.get(_w, 0)
                            _lo = slot_loser_map.get(c, "")
                            _ls = seed_map.get(_lo, 0)
                            if _ws > 0 and _ls > 0 and (_ws - _ls) >= 3:
                                _ut_url = espn_logo_url(_w) or ""
                                if _ut_url:
                                    _u_logos += f'<img src="{_ut_url}" title="{_w}" style="width:22px;height:22px;object-fit:contain;" onerror="this.style.display:none">'
                    if _u_logos:
                        _per_player_logos += f'<div style="margin-top:8px;text-align:center;"><span style="font-size:11px;color:#d8b4fe;">{_un.split()[0]}:</span> <span style="display:inline-flex;flex-wrap:wrap;justify-content:center;gap:2px;">{_u_logos}</span></div>'
                _s4 = (
                    f'<div style="background:linear-gradient(135deg,#4a1942,#6b21a8);border-radius:16px;padding:24px;text-align:center;">' +
                    f'<div style="font-size:32px;margin-bottom:6px;">😤</div>' +
                    f'<div style="font-size:11px;color:#d8b4fe;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Upset Picks</div>' +
                    f'<div style="font-size:22px;font-weight:800;color:#fff;line-height:1.2;">{_upset_names_str}</div>' +
                    f'<div style="font-size:12px;color:#d8b4fe;margin-top:4px;">{_upset_count2} correct upset picks</div>' +
                    _per_player_logos +
                    f'</div>'
                )
                _slides.append(("😤 Upset Picks", _s4))

                # Slide 5: Most Correct Picks — names alphabetical, stacked
                _correct_logos = ""
                if _correct_winners2:
                    _correct_teams = list(dict.fromkeys(
                        actual_winners[c]
                        for r in _correct_sorted2[:len(_correct_winners2)]
                        for c in range(3, 66)
                        if not is_unplayed(actual_winners[c]) and r["raw_picks"][c] == actual_winners[c]
                    ))
                    _correct_logos = "".join(_img(t, 20) for t in _correct_teams if espn_logo_url(t))
                _correct_names_alpha = sorted(_correct_winners2)
                _correct_names_stacked = "<br>".join(_hl(n) for n in _correct_names_alpha)
                _s5 = (
                    f'<div style="background:linear-gradient(135deg,#14532d,#166534);border-radius:16px;padding:24px;text-align:center;">' +
                    f'<div style="font-size:32px;margin-bottom:6px;">✅</div>' +
                    f'<div style="font-size:11px;color:#86efac;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Most Correct Picks</div>' +
                    f'<div style="font-size:22px;font-weight:800;color:#fff;line-height:1.4;">{_correct_names_stacked}</div>' +
                    f'<div style="font-size:12px;color:#86efac;margin-top:4px;">{_correct_count2} correct picks</div>' +
                    (f'<div style="margin-top:8px;display:flex;flex-wrap:wrap;justify-content:center;gap:2px;">{_correct_logos}</div>' if _correct_logos else "") +
                    f'</div>'
                )
                _slides.append(("✅ Most Correct Picks", _s5))

                # Slide 6: Tiebreaker — winner + grouped by proximity
                _tb_sub = f'Guessed {_tb_guess_val} · {"+" if _tb_diff_val and _tb_diff_val >= 0 else ""}{_tb_diff_val if _tb_diff_val is not None else "—"} off' if _tb_winner != "—" else ""

                # Group all guessers by absolute distance from final score
                _tb_groups = {}  # abs_diff -> list of (name, signed_diff, guess)
                if final_score and tiebreaker_guesses:
                    for _tbn, _tbg in tiebreaker_guesses.items():
                        _abd = abs(_tbg - final_score)
                        _snd = _tbg - final_score
                        _tb_groups.setdefault(_abd, []).append((_tbn, _snd, _tbg))

                _winner_abs = abs(_tb_diff_val) if _tb_diff_val is not None else None

                def _tb_sign_str(signed_diff):
                    if signed_diff is None: return ""
                    if signed_diff == 0: return "Exactly Correct! 🎯"
                    p = "+" if signed_diff > 0 else ""
                    return f'{p}{signed_diff} off'

                _s6_parts = ['<div style="display:flex;flex-direction:column;gap:10px;text-align:center;">']

                # Championship game score pill — hardcoded: Michigan 69, UConn 63
                _champ_w_team = "Michigan"
                _champ_l_team = "UConn"
                _champ_w_score = 69
                _champ_l_score = 63
                _cw_logo = f'<img src="{espn_logo_url(_champ_w_team)}" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display:none">' if espn_logo_url(_champ_w_team) else ""
                _cl_logo = f'<img src="{espn_logo_url(_champ_l_team)}" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display:none">' if espn_logo_url(_champ_l_team) else ""
                if final_score:
                    _s6_parts.append(
                        f'<div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:14px;padding:16px;">'
                        f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">🏆 Championship Final</div>'
                        f'<div style="display:flex;align-items:center;justify-content:center;gap:12px;">'
                        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;">'
                        f'{_cw_logo}<span style="font-size:13px;font-weight:700;color:#fff;">{_champ_w_team}</span>'
                        f'<span style="font-size:28px;font-weight:900;color:#FFCB05;">{_champ_w_score}</span>'
                        f'</div>'
                        f'<span style="font-size:14px;color:#6b7280;align-self:center;">—</span>'
                        f'<div style="display:flex;flex-direction:column;align-items:center;gap:4px;">'
                        f'{_cl_logo}<span style="font-size:13px;font-weight:700;color:#9ca3af;">{_champ_l_team}</span>'
                        f'<span style="font-size:28px;font-weight:900;color:#9ca3af;">{_champ_l_score}</span>'
                        f'</div>'
                        f'</div>'
                        f'<div style="font-size:13px;color:#6ee7b7;margin-top:8px;">Total combined score: <span style="font-weight:900;color:#f5c518;font-size:18px;">{final_score}</span></div>'
                        f'</div>'
                    )
                _s6_parts.append(
                    f'<div style="background:linear-gradient(135deg,#064e3b,#065f46);border-radius:16px;padding:22px;">'
                    f'<div style="font-size:28px;margin-bottom:4px;">🎯</div>'
                    f'<div style="font-size:11px;color:#6ee7b7;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Tiebreaker Champion</div>'
                    f'<div style="font-size:28px;font-weight:900;color:#fff;">{_hl(_tb_winner)}</div>'
                    + (f'<div style="font-size:14px;color:#6ee7b7;margin-top:5px;">Guessed {_tb_guess_val} · {_tb_sign_str(_tb_diff_val)}</div>' if _tb_guess_val else "") +
                    f'</div>'
                )

                # Proximity pills — grey, just distance label + names + guesses
                _prox_labels = {1: "1 point off", 2: "2 points off", 3: "3 points off"}
                for _d in [1, 2, 3]:
                    if _winner_abs is not None and _d == _winner_abs:
                        continue
                    _group = _tb_groups.get(_d, [])
                    if not _group:
                        continue
                    _names_in_group = _hl_names([g[0] for g in _group])
                    _guesses_str = ", ".join(f'{_hl(g[0].split()[0])}: {g[2]}' for g in _group)
                    _s6_parts.append(
                        f'<div style="background:linear-gradient(135deg,#1f2937,#374151);border-radius:14px;padding:14px;">'
                        f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">{_prox_labels[_d]}</div>'
                        f'<div style="font-size:16px;font-weight:700;color:#e5e7eb;">{_names_in_group}</div>'
                        f'<div style="font-size:11px;color:#9ca3af;margin-top:3px;">{_guesses_str}</div>'
                        f'</div>'
                    )

                _s6_parts.append('</div>')
                _s6 = "".join(_s6_parts)
                _slides.append(("🎯 Tiebreaker", _s6))

                # Slide 7: Weekend Leaders with 2nd/3rd
                def _wknd_row(r, col_end):
                    return _wknd_pts2(r, col_end)
                _fw_top3 = sorted(results, key=lambda r: _wknd_pts2(r, 51), reverse=True)[:3]
                _sw_top3 = sorted(results, key=lambda r: _wknd_pts2(r, 63), reverse=True)[:3]

                def _wknd_pill(r, col_end, medal, color):
                    nm = _hl(r["Name"]); sc = _wknd_pts2(r, col_end)
                    return f'<div style="background:{color};border-radius:10px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;"><span style="font-size:16px;">{medal}</span><span style="font-size:14px;font-weight:700;">{nm}</span><span style="font-size:12px;color:#9ca3af;">{sc} pts</span></div>'

                _s7 = (
                    f'<div style="display:flex;flex-direction:column;gap:12px;">' +
                    f'<div style="background:linear-gradient(135deg,#0c4a6e,#075985);border-radius:14px;padding:14px;">' +
                    f'<div style="font-size:10px;color:#7dd3fc;text-transform:uppercase;text-align:center;margin-bottom:8px;">♓ 1st Weekend Leader</div>' +
                    f'<div style="display:flex;flex-direction:column;gap:6px;">' +
                    "".join(_wknd_pill(r, 51, m, c) for r, m, c in zip(_fw_top3, ["🥇","🥈","🥉"], ["#1a4a6e","#16375a","#112a45"])) +
                    f'</div></div>' +
                    f'<div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);border-radius:14px;padding:14px;">' +
                    f'<div style="font-size:10px;color:#93c5fd;text-transform:uppercase;text-align:center;margin-bottom:8px;">♈ 2nd Weekend Leader</div>' +
                    f'<div style="display:flex;flex-direction:column;gap:6px;">' +
                    "".join(_wknd_pill(r, 63, m, c) for r, m, c in zip(_sw_top3, ["🥇","🥈","🥉"], ["#1a2f50","#14243e","#0e1a2d"])) +
                    f'</div></div>' +
                    f'</div>'
                )
                _slides.append(("♓♈ Weekend Leaders", _s7))

                # Slide 8: Regional Champions with 2nd/3rd
                _reg_html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;text-align:center;">'
                for _rreg in ["East", "West", "South", "Midwest"]:
                    _rgs_all = sorted(results, key=lambda r: r.get(f"{_rreg} Score", 0), reverse=True)
                    _top_score = _rgs_all[0].get(f"{_rreg} Score", 0) if _rgs_all else 0
                    _tied_names = [r["Name"] for r in _rgs_all if r.get(f"{_rreg} Score", 0) == _top_score]
                    _rrscore = int(_top_score)
                    _not_tied = [r for r in _rgs_all if r["Name"] not in _tied_names]
                    _r2nd = _not_tied[0] if _not_tied else None
                    _r3rd = _not_tied[1] if len(_not_tied) > 1 else None
                    _rr_ff = _region_ff_team.get(_rreg, "")
                    _rr_logo_html = _img(_rr_ff, 42) if _rr_ff else '<div style="font-size:30px;">🏅</div>'
                    _r2_html = f'<div style="font-size:12px;color:#9ca3af;margin-top:4px;">🥈 {_hl(_r2nd["Name"])} · {int(_r2nd.get(f"{_rreg} Score",0))} pts</div>' if _r2nd else ""
                    _r3_html = f'<div style="font-size:12px;color:#6b7280;">🥉 {_hl(_r3rd["Name"])} · {int(_r3rd.get(f"{_rreg} Score",0))} pts</div>' if _r3rd else ""
                    _reg_html += (
                        f'<div style="background:linear-gradient(135deg,#1e1e2e,#2d2d44);border-radius:12px;padding:14px;">' +
                        _rr_logo_html +
                        f'<div style="font-size:13px;color:#9ca3af;text-transform:uppercase;font-weight:600;margin:6px 0 3px;">{_rreg}</div>' +
                        f'<div style="font-size:15px;font-weight:800;color:#fff;line-height:1.3;">{_hl_names(_tied_names)}</div>' +
                        f'<div style="font-size:13px;color:#9ca3af;margin-bottom:3px;">{_rrscore} pts</div>' +
                        _r2_html + _r3_html +
                        '</div>'
                    )
                _reg_html += '</div>'
                _slides.append(("🗺️ Regional Champions", _reg_html))

                # Slide 9: Hoops, She Did It Again
                _wsbb_1st = WSBB_STANDINGS[0]
                _wsbb_2nd = next((r for r in WSBB_STANDINGS if r["Rank"] == 2), None)
                _wsbb_3rd = next((r for r in WSBB_STANDINGS if r["Rank"] == 3), None)
                _wsbb_3rd_all = [r for r in WSBB_STANDINGS if r["Rank"] == 3]
                _wsbb_champ_logo = espn_logo_url(WSBB_CHAMP) or ""
                _wsbb_logo_html = f'<img src="{_wsbb_champ_logo}" style="width:40px;height:40px;object-fit:contain;vertical-align:middle;margin-right:8px;" onerror="this.style.display:none">' if _wsbb_champ_logo else ""
                _wsbb_3rd_names = _hl_names([r["Name"] for r in _wsbb_3rd_all])
                _s_wsbb = (
                    f'<div style="text-align:center;">'
                    f'<div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:16px;padding:16px;margin-bottom:10px;">'
                    f'<div style="font-size:11px;color:#9ca3af;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;">2026 Women\'s Tournament Champion</div>'
                    f'<div style="display:flex;align-items:center;justify-content:center;">{_wsbb_logo_html}<span style="font-size:20px;font-weight:900;color:#f5c518;">{WSBB_CHAMP}</span></div>'
                    f'</div>'
                    f'<div style="background:linear-gradient(135deg,#78350f,#b45309);border-radius:16px;padding:16px;margin-bottom:10px;">'
                    f'<div style="font-size:26px;">🏆</div>'
                    f'<div style="font-size:11px;color:#fde68a;letter-spacing:2px;text-transform:uppercase;margin:3px 0;">Pool Champion</div>'
                    f'<div style="font-size:24px;font-weight:900;color:#fff;">{_hl(_wsbb_1st["Name"])}</div>'
                    f'<div style="font-size:13px;color:#fde68a;">{_wsbb_1st["Points"]} pts</div>'
                    f'</div>'
                    f'<div style="display:flex;gap:8px;">'
                    f'<div style="flex:1;background:#374151;border-radius:12px;padding:12px;">'
                    f'<div style="font-size:20px;">🥈</div>'
                    f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;margin:3px 0;">2nd Place</div>'
                    f'<div style="font-size:14px;font-weight:800;color:#e5e7eb;">{_hl(_wsbb_2nd["Name"]) if _wsbb_2nd else "—"}</div>'
                    f'<div style="font-size:11px;color:#9ca3af;">{_wsbb_2nd["Points"] if _wsbb_2nd else ""} pts</div>'
                    f'</div>'
                    f'<div style="flex:1;background:#374151;border-radius:12px;padding:12px;">'
                    f'<div style="font-size:20px;">🥉</div>'
                    f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;margin:3px 0;">3rd Place</div>'
                    f'<div style="font-size:14px;font-weight:800;color:#e5e7eb;">{_wsbb_3rd_names}</div>'
                    f'<div style="font-size:11px;color:#9ca3af;">{_wsbb_3rd["Points"] if _wsbb_3rd else ""} pts</div>'
                    f'</div>'
                    f'</div>'
                    f'</div>'
                )
                _slides.append(("🏀 Hoops, She Did It Again", _s_wsbb))

                # Slide 10: Bonus Pool with 1st/2nd/3rd
                _bp_3rd_name  = _bp_df2.iloc[2]["Name"] if len(_bp_df2) > 2 else "—"
                _bp_3rd_score = int(_bp_df2.iloc[2]["Current Score"]) if len(_bp_df2) > 2 else 0
                _s9 = (
                    f'<div style="display:flex;flex-direction:column;gap:12px;text-align:center;">' +
                    f'<div style="font-size:11px;color:#9ca3af;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;">💰 Bonus Pool</div>' +
                    f'<div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:14px;padding:18px;"><div style="font-size:28px;">🏆</div><div style="font-size:10px;color:#a5b4fc;text-transform:uppercase;margin:4px 0;">1st Place</div><div style="font-size:20px;font-weight:800;color:#fff;">{_hl(_bp_winner)}</div><div style="font-size:12px;color:#a5b4fc;">{_bp_score2} pts</div></div>' +
                    f'<div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:14px;padding:18px;"><div style="font-size:28px;">🥈</div><div style="font-size:10px;color:#a5b4fc;text-transform:uppercase;margin:4px 0;">2nd Place</div><div style="font-size:20px;font-weight:800;color:#e5e7eb;">{_hl(_bp_2nd_name)}</div><div style="font-size:12px;color:#a5b4fc;">{_bp_2nd_score} pts</div></div>' +
                    f'<div style="background:linear-gradient(135deg,#1e1b4b,#312e81);border-radius:14px;padding:18px;"><div style="font-size:28px;">🥉</div><div style="font-size:10px;color:#a5b4fc;text-transform:uppercase;margin:4px 0;">3rd Place</div><div style="font-size:20px;font-weight:800;color:#e5e7eb;">{_hl(_bp_3rd_name)}</div><div style="font-size:12px;color:#a5b4fc;">{_bp_3rd_score} pts</div></div>' +
                    f'</div>'
                )
                _slides.append(("💰 Bonus Pool", _s9))

                # ── Iframe slideshow (all slides client-side, no Streamlit reruns) ─
                _n_slides = len(_slides)
                if "recap_slide" not in st.session_state:
                    st.session_state["recap_slide"] = 0
                _initial_idx = st.session_state["recap_slide"] % _n_slides

                _titles_js = "[" + ",".join(
                    '"' + t.replace('"', '\\"'). replace("&", "&amp;") + '"' for t, _ in _slides
                ) + "]"
                _slides_inner = "".join(
                    f'<div class="slide">{html}</div>'
                    for _, html in _slides
                )
                _dots_inner = "".join(
                    f'<span class="dot" data-i="{i}"></span>'
                    for i in range(_n_slides)
                )

                import streamlit.components.v1 as _cv1
                _cv1.html(f"""<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    html,body{{background:#0e1117;color:#fff;font-family:sans-serif;overflow:hidden;}}
    #title{{text-align:center;font-size:22px;color:#fff;font-weight:800;padding:6px 0 2px;}}
    #counter{{text-align:center;font-size:11px;color:#6b7280;margin-bottom:4px;}}
    #wrap{{width:100%;overflow:hidden;}}
    #track{{display:flex;will-change:transform;align-items:flex-start;}}
    .slide{{min-width:100%;padding:0 2px;}}
    #dots{{text-align:center;margin:6px 0 2px;}}
    .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;background:#4b5563;
         margin:0 4px;cursor:pointer;vertical-align:middle;transition:background 0.2s;}}
    #nav{{display:flex;align-items:center;justify-content:space-between;padding:4px 0 6px;}}
    .btn{{background:#1e1e2e;border:1px solid #374151;color:#e5e7eb;
         padding:7px 16px;border-radius:8px;cursor:pointer;font-size:13px;}}
    .btn:disabled{{opacity:0.3;cursor:default;}}
    #navcount{{font-size:12px;color:#6b7280;}}
    img{{max-width:100%;}}
    #swipe-hint{{display:none;text-align:center;font-size:12px;color:#9ca3af;padding:3px 0;animation:fadeInOut 2s ease-in-out infinite;}}
    @keyframes fadeInOut{{0%,100%{{opacity:0.3;}}50%{{opacity:1;}}}}
    </style></head><body>
    <div id="title"></div>
    <div id="counter"></div>
    <div id="swipe-hint">← swipe to navigate →</div>
    <div id="wrap"><div id="track">{_slides_inner}</div></div>
    <div id="dots">{_dots_inner}</div>
    <div id="nav">
      <button class="btn" id="bp">← Prev</button>
      <span id="navcount"></span>
      <button class="btn" id="bn">Next →</button>
    </div>
    <script>
    var T={_titles_js},N={_n_slides},cur={_initial_idx};
    var track=document.getElementById('track'),
        dots=document.querySelectorAll('.dot'),
        bp=document.getElementById('bp'),
        bn=document.getElementById('bn');
    var sx=null,sy=null,sw=false;

    function goTo(i,anim){{
      if(i<0||i>=N)return;
      cur=i;
      track.style.transition=(anim===false)?'none':'transform 0.3s ease';
      track.style.transform='translateX('+(-cur*100)+'%)';
      dots.forEach(function(d,j){{d.style.background=j===cur?'#f5c518':'#4b5563';}});
      document.getElementById('title').textContent=T[cur];
      document.getElementById('counter').textContent=(cur+1)+' / '+N;
      document.getElementById('navcount').textContent=(cur+1)+' of '+N;
      bp.disabled=cur===0; bn.disabled=cur===N-1;
    }}
    goTo(cur,false);
    bp.onclick=function(){{goTo(cur-1);}};
    bn.onclick=function(){{goTo(cur+1);}};
    dots.forEach(function(d){{d.onclick=function(){{goTo(+d.dataset.i);}};}});
    // Show swipe hint on touch devices
    var hint=document.getElementById('swipe-hint');
    if('ontouchstart' in window||navigator.maxTouchPoints>0){{hint.style.display='block';}}
    track.addEventListener('touchstart',function(e){{
      sx=e.touches[0].clientX;sy=e.touches[0].clientY;sw=true;
      track.style.transition='none';
      if(hint){{hint.style.display='none';}}
    }},{{passive:true}});
    track.addEventListener('touchmove',function(e){{
      if(!sw||sx===null)return;
      var dx=e.touches[0].clientX-sx,dy=e.touches[0].clientY-sy;
      if(Math.abs(dy)>Math.abs(dx)){{sw=false;return;}}
      track.style.transform='translateX(calc('+(-cur*100)+'% + '+dx+'px))';
    }},{{passive:true}});
    track.addEventListener('touchend',function(e){{
      if(!sw||sx===null)return;
      var dx=e.changedTouches[0].clientX-sx;sx=null;sw=false;
      goTo(Math.abs(dx)>50?(dx<0?cur+1:cur-1):cur);
    }});
    </script></body></html>""", height=900, scrolling=False)


            elif _recap_sub == "mine":
                st.subheader("🪞 My Tournament Recap")
                _mn = st.selectbox("Select your name", ["— select —"] + name_opts, key="recap_my_name",
                    index=(name_opts.index(user_name) + 1) if user_name and user_name in name_opts else 0)
                if _mn != "— select —":
                    _mr_df = final_df[final_df["Name"] == _mn]
                    _mr = next((r for r in results if r["Name"] == _mn), None)
                    if not _mr_df.empty and _mr:
                        _mr_row  = _mr_df.iloc[0]
                        _mr_rank = int(_mr_row["Current Rank"])
                        _mr_score= int(_mr_row["Current Score"])
                        _mr_picks= _mr["raw_picks"]
                        _ps      = len(results)
                        _pct     = round(((_ps - _mr_rank) / _ps) * 100)

                        # Total correct picks (slots 3-65, R1 through Champ)
                        _mr_correct = sum(1 for c in range(3,66) if c < len(_mr_picks)
                                          and not is_unplayed(actual_winners[c])
                                          and _mr_picks[c] == actual_winners[c])

                        # Championship pick
                        _mrcp = _mr_picks[65] if len(_mr_picks) > 65 and _mr_picks[65] not in {"","nan","TBD"} else "—"
                        _cc   = (_mrcp == actual_winners[65]) if not is_unplayed(actual_winners[65]) else False

                        # When was their champ pick eliminated, and by whom?
                        _champ_elim_round = None
                        _champ_elim_by    = None
                        if _mrcp and _mrcp != "—" and not _cc:
                            _round_names = [("First Round",3,35),("Second Round",35,51),("Sweet 16",51,59),("Elite Eight",59,63),("Final Four",63,65),("Championship",65,66)]
                            for _rn, _rs, _re in _round_names:
                                for c in range(_rs, _re):
                                    if c < len(actual_winners) and not is_unplayed(actual_winners[c]):
                                        if slot_loser_map.get(c) == _mrcp:
                                            _champ_elim_round = _rn
                                            _champ_elim_by    = actual_winners[c]
                                            break
                                if _champ_elim_round:
                                    break

                        # Points by round + per-round rank
                        _round_defs = [("R1",3,35),("R2",35,51),("S16",51,59),("E8",59,63),("FF",63,65),("🏆",65,66)]
                        _rpts = {}
                        _rrank = {}
                        for _rn, _rs, _re in _round_defs:
                            def _rnd_score(r, rs=_rs, re=_re):
                                return sum(points_per_game[c]+seed_map.get(r["raw_picks"][c],0)
                                           for c in range(rs,re)
                                           if c<len(r["raw_picks"]) and r["raw_picks"][c]==actual_winners[c]
                                           and not is_unplayed(actual_winners[c]))
                            _rpts[_rn] = _rnd_score(_mr)
                            _all_rnd = sorted([_rnd_score(r) for r in results], reverse=True)
                            _rrank[_rn] = next((i+1 for i,v in enumerate(_all_rnd) if v <= _rpts[_rn]), _ps)

                        # Rarest correct pick (with round)
                        _slot_to_round = {}
                        for _rn, _rs, _re in _round_defs:
                            for c in range(_rs, _re):
                                _slot_to_round[c] = _rn
                        _cpl = [{"team":_mr_picks[c],"count":slot_pick_counts.get(c,{}).get(_mr_picks[c],0),"round":_slot_to_round.get(c,"")}
                                for c in range(3,66) if c<len(_mr_picks) and _mr_picks[c]==actual_winners[c]
                                and not is_unplayed(actual_winners[c])]
                        _rarest2 = min(_cpl, key=lambda x: x["count"]) if _cpl else None

                        # Biggest upset (with round)
                        _upl = []
                        for c in range(3,66):
                            if c<len(_mr_picks) and _mr_picks[c]==actual_winners[c] and not is_unplayed(actual_winners[c]):
                                _w2=_mr_picks[c]; _ws2=seed_map.get(_w2,0); _lo2=slot_loser_map.get(c,""); _ls2=seed_map.get(_lo2,0)
                                if _ws2>0 and _ls2>0 and (_ws2-_ls2)>=3:
                                    _upl.append({"team":_w2,"seed":_ws2,"loser":_lo2,"loser_seed":_ls2,"diff":_ws2-_ls2,"round":_slot_to_round.get(c,"")})
                        _bu2 = max(_upl, key=lambda x: x["diff"]) if _upl else None

                        # Tiebreaker
                        _mtb  = tiebreaker_guesses.get(_mn)
                        _mtbd = (_mtb - final_score) if _mtb and final_score else None

                        # Round name display map (no abbreviations)
                        _rnd_display = {
                            "R1": "First Round", "R2": "Second Round",
                            "S16": "Sweet 16",   "E8": "Elite Eight",
                            "FF": "Final Four",  "🏆": "Championship"
                        }

                        # Which team did player pick for FF from each region?
                        # FF slots 63-64 (col 63 = FF game 1, col 64 = FF game 2)
                        # E8 slots 59-62 map to regions; winners of each pair feed FF
                        # Region→FF pick: find the player's pick in the E8 slot for that region
                        _reg_ff_pick = {}  # region -> team player picked to reach FF
                        for _ec in range(59, 63):
                            _er = slot_to_region.get(_ec, "")
                            if _er and _ec < len(_mr_picks):
                                _reg_ff_pick[_er] = _mr_picks[_ec]

                        # Regional rank
                        _reg_rank = {}
                        for _reg in ["East","West","South","Midwest"]:
                            _all_reg = sorted([r.get(f"{_reg} Score",0) for r in results], reverse=True)
                            _my_reg_score = int(_mr.get(f"{_reg} Score",0))
                            _reg_rank[_reg] = next((i+1 for i,v in enumerate(_all_reg) if v <= _my_reg_score), _ps)

                        # ── Build my-recap slides ─────────────────────────────────
                        _my_slides = []

                        # Slide 1: Final Standing + Championship Pick (combined)
                        _rb_bg = "linear-gradient(135deg,#78350f,#b45309)" if _mr_rank==1 else "linear-gradient(135deg,#1e1e2e,#374151)"
                        _rbc   = "#f5c518" if _mr_rank==1 else "#fff"
                        _rank_emoji = "🏆" if _mr_rank==1 else ("🥈" if _mr_rank==2 else ("🥉" if _mr_rank==3 else ""))
                        _cpbg = "linear-gradient(135deg,#14532d,#166534)" if _cc else "linear-gradient(135deg,#450a0a,#7f1d1d)"
                        _cpi  = "🎉" if _cc else "😔"
                        _cp_logo_url = espn_logo_url(_mrcp) or "" if _mrcp != "—" else ""
                        _cp_img = f'<img src="{_cp_logo_url}" style="width:36px;height:36px;object-fit:contain;" onerror="this.style.display:none">' if _cp_logo_url else ""
                        if _cc:
                            _cp_msg = f"You called it! {_mrcp} won it all!"
                            _cp_sub = ""
                        elif _champ_elim_round and _champ_elim_by:
                            _elim_logo = espn_logo_url(_champ_elim_by) or ""
                            _elim_img  = f'<img src="{_elim_logo}" style="width:18px;height:18px;object-fit:contain;vertical-align:middle;margin-right:4px;" onerror="this.style.display:none">' if _elim_logo else ""
                            _cp_msg = f"Eliminated in the {_champ_elim_round}"
                            _cp_sub = f'<div style="display:flex;align-items:center;justify-content:center;margin-top:4px;font-size:12px;color:#fca5a5;">Lost to {_elim_img}{_champ_elim_by}</div>'
                        else:
                            _cp_msg = f"{_mrcp} fell short."
                            _cp_sub = ""
                        _my_slides.append(("🏅 Standing & Pick",
                            f'<div style="display:flex;flex-direction:column;gap:10px;">'
                            f'<div style="background:{_rb_bg};border-radius:16px;padding:18px;text-align:center;">'
                            f'<div style="font-size:11px;color:#9ca3af;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">Final Standing</div>'
                            f'<div style="font-size:44px;font-weight:900;color:{_rbc};line-height:1;">{(_rank_emoji + " ") if _rank_emoji else ""}#{_mr_rank}</div>'
                            f'<div style="font-size:13px;color:#9ca3af;margin-top:4px;">out of {_ps}</div>'
                            f'<div style="display:flex;justify-content:center;gap:20px;margin-top:10px;">'
                            f'<div><div style="font-size:18px;font-weight:800;color:#f5c518;">{_mr_score}</div><div style="font-size:10px;color:#9ca3af;">points</div></div>'
                            f'<div><div style="font-size:18px;font-weight:800;color:#4fc3f7;">{_mr_correct}</div><div style="font-size:10px;color:#9ca3af;">correct / 63</div></div>'
                            f'</div>'
                            f'</div>'
                            f'<div style="background:{_cpbg};border-radius:16px;padding:14px;text-align:center;">'
                            f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">{_cpi} Championship Pick</div>'
                            f'<div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:4px;">{_cp_img}'
                            f'<span style="font-size:18px;font-weight:900;color:#fff;">{_mrcp}</span></div>'
                            f'<div style="font-size:12px;color:#9ca3af;">{_cp_msg}</div>'
                            f'{_cp_sub}'
                            f'</div>'
                            f'</div>'
                        ))

                        # Slide 2: Journey Through the Standings + Points by Round
                        _rnd_cells = ""
                        for _rn, _, _ in _round_defs:
                            _rv = _rpts[_rn]; _rr = _rrank[_rn]
                            _rank_col = "#4ade80" if _rr==1 else ("#f5c518" if _rr<=3 else ("#60a5fa" if _rr<=10 else "#9ca3af"))
                            _disp = _rnd_display.get(_rn, _rn)
                            _rnd_cells += (
                                f'<div style="flex:1;min-width:44px;background:#374151;border-radius:9px;padding:8px 4px;text-align:center;">'
                                f'<div style="font-size:9px;color:#9ca3af;line-height:1.2;">{_disp}</div>'
                                f'<div style="font-size:18px;font-weight:800;color:#f5c518;">{_rv}</div>'
                                f'<div style="font-size:10px;color:{_rank_col};">#{_rr}</div>'
                                f'</div>'
                            )
                        _my_slides.append(("📈 Journey Through the Standings",
                            f'<div style="background:linear-gradient(135deg,#1e1e2e,#2d2d44);border-radius:16px;padding:18px;">'
                            f'<div style="font-size:11px;color:#9ca3af;text-transform:uppercase;margin-bottom:10px;text-align:center;">📊 Points by Round <span style="font-size:10px;">(rank among {_ps})</span></div>'
                            f'<div style="display:flex;flex-wrap:wrap;gap:5px;">{_rnd_cells}</div>'
                            f'<div style="font-size:11px;color:#6b7280;text-align:center;margin-top:10px;">📈 Rank chart shown below ↓</div>'
                            f'</div>'
                        ))

                        # Slide 3: Rarest Pick + Biggest Upset (combined)
                        if _rarest2 or _bu2:
                            _slide3_parts = '<div style="display:flex;flex-direction:column;gap:10px;">'
                            if _rarest2:
                                _ru = espn_logo_url(_rarest2["team"]) or ""
                                _ri2 = f'<img src="{_ru}" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display:none">' if _ru else ""
                                _rare_rnd = _rnd_display.get(_rarest2["round"], _rarest2["round"])
                                _slide3_parts += (
                                    f'<div style="background:linear-gradient(135deg,#0c4a6e,#0369a1);border-radius:16px;padding:16px;text-align:center;">'
                                    f'<div style="font-size:11px;color:#7dd3fc;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">🤫 Rarest Correct Pick</div>'
                                    f'<div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:4px;">{_ri2}'
                                    f'<span style="font-size:18px;font-weight:800;color:#fff;">{_rarest2["team"]}</span></div>'
                                    f'<div style="font-size:11px;color:#7dd3fc;">{_rare_rnd} · only {_rarest2["count"]} of {_ps} had this</div>'
                                    f'</div>'
                                )
                            if _bu2:
                                _bu2u = espn_logo_url(_bu2["team"]) or ""
                                _bu2i = f'<img src="{_bu2u}" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display:none">' if _bu2u else ""
                                _upset_rnd = _rnd_display.get(_bu2["round"], _bu2["round"])
                                _slide3_parts += (
                                    f'<div style="background:linear-gradient(135deg,#4a1942,#7c3aed);border-radius:16px;padding:16px;text-align:center;">'
                                    f'<div style="font-size:11px;color:#d8b4fe;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">😤 Biggest Upset Called</div>'
                                    f'<div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-bottom:4px;">{_bu2i}'
                                    f'<span style="font-size:18px;font-weight:800;color:#fff;">({_bu2["seed"]}) {_bu2["team"]}</span></div>'
                                    f'<div style="font-size:11px;color:#d8b4fe;">{_upset_rnd} · def. ({_bu2["loser_seed"]}) {_bu2["loser"]} · {_bu2["diff"]}-seed upset</div>'
                                    f'</div>'
                                )
                            _slide3_parts += '</div>'
                            _my_slides.append(("🤫😤 Picks & Upsets", _slide3_parts))

                        # Slide 4: Regional Breakdown with rank + FF pick logo
                        _reg_cells = ""
                        for _reg in ["East","West","South","Midwest"]:
                            _rv = int(_mr.get(f"{_reg} Score",0))
                            _rr = _reg_rank[_reg]
                            _rank_col = "#4ade80" if _rr==1 else ("#f5c518" if _rr<=3 else ("#60a5fa" if _rr<=10 else "#9ca3af"))
                            _rank_bg  = "#14532d" if _rr==1 else "#1e1e2e"
                            _border   = "#4ade80" if _rr==1 else "#374151"
                            # FF pick logo for this region
                            _ff_pick_team = _reg_ff_pick.get(_reg, "")
                            _ff_correct   = not is_unplayed(actual_winners[63] if _reg in ("East","West") else actual_winners[64]) if False else any(
                                actual_winners[c] == _ff_pick_team for c in range(59, 63)
                                if not is_unplayed(actual_winners[c]) and slot_to_region.get(c) == _reg
                            ) if _ff_pick_team else False
                            # More precise: did the player's FF pick actually win their E8 game?
                            _ff_correct = False
                            if _ff_pick_team:
                                for c in range(59, 63):
                                    if slot_to_region.get(c) == _reg and not is_unplayed(actual_winners[c]):
                                        if actual_winners[c] == _ff_pick_team:
                                            _ff_correct = True
                            _ff_logo_url = espn_logo_url(_ff_pick_team) or "" if _ff_pick_team else ""
                            if _ff_logo_url:
                                if _ff_correct:
                                    _ff_logo_html = f'<img src="{_ff_logo_url}" style="width:24px;height:24px;object-fit:contain;" onerror="this.style.display:none">'
                                else:
                                    # Red X overlay using a wrapper div
                                    _ff_logo_html = (
                                        f'<div style="position:relative;display:inline-block;width:24px;height:24px;">'
                                        f'<img src="{_ff_logo_url}" style="width:24px;height:24px;object-fit:contain;opacity:0.5;" onerror="this.style.display:none">'
                                        f'<div style="position:absolute;top:0;left:0;width:100%;height:100%;display:flex;align-items:center;justify-content:center;'
                                        f'font-size:18px;color:#ef4444;font-weight:900;line-height:1;">✕</div>'
                                        f'</div>'
                                    )
                            else:
                                _ff_logo_html = ""
                            _reg_cells += (
                                f'<div style="flex:1;min-width:70px;background:{_rank_bg};border:1px solid {_border};border-radius:10px;padding:12px 8px;text-align:center;">'
                                + (f'<div style="margin-bottom:5px;">{_ff_logo_html}</div>' if _ff_logo_html else "")
                                + f'<div style="font-size:12px;color:#9ca3af;">{_reg}</div>'
                                f'<div style="font-size:26px;font-weight:900;color:{_rank_col};">#{_rr}</div>'
                                f'<div style="font-size:13px;color:#9ca3af;">{_rv} pts</div>'
                                f'</div>'
                            )
                        _my_slides.append(("🗺️ Regional Breakdown",
                            f'<div style="background:linear-gradient(135deg,#1e1e2e,#2d2d44);border-radius:16px;padding:18px;">'
                            f'<div style="font-size:11px;color:#9ca3af;text-transform:uppercase;margin-bottom:10px;text-align:center;">🗺️ Regional Breakdown <span style="font-size:10px;">(rank among {_ps})</span></div>'
                            f'<div style="display:flex;flex-wrap:wrap;gap:6px;">{_reg_cells}</div>'
                            f'</div>'
                        ))

                        # Tiebreaker slide with rank, offense/defense flavor text
                        if _mtb and final_score:
                            _ts2    = "+" if _mtbd >= 0 else ""
                            _tb_bg2 = "linear-gradient(135deg,#14532d,#166534)" if abs(_mtbd) <= 3 else "linear-gradient(135deg,#1e1e2e,#374151)"
                            _tb_msg = "Exactly Correct! 🎯" if _mtbd == 0 else f"{_ts2}{_mtbd} off"
                            if _mtbd == 0:
                                _tb_flavor = ""
                            elif _mtbd > 0:
                                _tb_flavor = '<div style="font-size:12px;color:#9ca3af;margin-top:4px;">Too much offense in the Championship game for you 🏀</div>'
                            else:
                                _tb_flavor = '<div style="font-size:12px;color:#9ca3af;margin-top:4px;">Too much defense in the Championship game for you 🛡️</div>'
                            # Compute tiebreaker rank
                            _tb_rank = None
                            if tiebreaker_guesses and final_score:
                                _tb_diffs = sorted(tiebreaker_guesses.items(), key=lambda x: abs(x[1] - final_score))
                                _my_abs   = abs(_mtbd)
                                _tb_rank  = next((i+1 for i,(n,g) in enumerate(_tb_diffs) if abs(g-final_score) >= _my_abs), len(_tb_diffs))
                            _tb_rank_html = ""
                            if _tb_rank:
                                _tr_col = "#4ade80" if _tb_rank==1 else ("#f5c518" if _tb_rank<=3 else "#9ca3af")
                                _tb_rank_html = f'<div style="font-size:22px;font-weight:900;color:{_tr_col};margin-top:8px;">#{_tb_rank} closest</div>'
                            _my_slides.append(("🎯 Tiebreaker",
                                f'<div style="background:{_tb_bg2};border:1px solid #374151;border-radius:16px;padding:24px;text-align:center;">'
                                f'<div style="font-size:28px;margin-bottom:6px;">🎯</div>'
                                f'<div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Tiebreaker Guess</div>'
                                f'<div style="font-size:32px;font-weight:900;color:#fff;">{_mtb}</div>'
                                f'<div style="font-size:13px;color:#6ee7b7;margin-top:6px;">Final score: {final_score} · {_tb_msg}</div>'
                                f'{_tb_rank_html}'
                                f'{_tb_flavor}'
                                f'</div>'
                            ))

                        # Hoops, She Did It Again slide (if they participated)
                        _wsbb_row = next((r for r in WSBB_STANDINGS if r["Name"] == _mn), None)
                        if _wsbb_row:
                            _wr_rank  = int(_wsbb_row["Rank"])
                            _wr_pts   = int(_wsbb_row["Points"])
                            _wr_cp    = int(_wsbb_row["Correct Picks"])
                            _wr_pct   = round(((len(WSBB_STANDINGS) - _wr_rank) / len(WSBB_STANDINGS)) * 100)
                            _wr_rb_bg = "linear-gradient(135deg,#78350f,#b45309)" if _wr_rank==1 else "linear-gradient(135deg,#1e1e2e,#374151)"
                            _wr_rbc   = "#f5c518" if _wr_rank==1 else "#fff"
                            _wr_emoji = "🏆" if _wr_rank==1 else ("🥈" if _wr_rank==2 else ("🥉" if _wr_rank==3 else ""))
                            _wsbb_logo_url = espn_logo_url(WSBB_CHAMP) or ""
                            _wsbb_img = f'<img src="{_wsbb_logo_url}" style="width:32px;height:32px;object-fit:contain;" onerror="this.style.display:none">' if _wsbb_logo_url else ""
                            # Round breakdown for this player
                            _wr_rounds = [("First Round","First Round"),("R2","Second Round"),("S16","Sweet 16"),("E8","Elite Eight"),("FF","Final Four"),("🏆","Championship")]
                            _wr_cells  = "".join(
                                f'<div style="flex:1;min-width:36px;background:#374151;border-radius:7px;padding:6px 2px;text-align:center;"><div style="font-size:9px;color:#9ca3af;line-height:1.2;">{disp}</div><div style="font-size:14px;font-weight:800;color:#f5c518;">{_wsbb_row[full]}</div></div>'
                                for full, disp in [("First Round","First Round"),("Second Round","Second Round"),("Sweet 16","Sweet 16"),("Elite 8","Elite Eight"),("Final Four","Final Four"),("Championship","Championship")]
                            )
                            _my_slides.append(("🏀 Women's Pool",
                                f'<div style="display:flex;flex-direction:column;gap:10px;text-align:center;">'
                                f'<div style="background:linear-gradient(135deg,#1a1a2e,#0f3460);border-radius:12px;padding:10px;display:flex;align-items:center;justify-content:center;gap:8px;">'
                                f'{_wsbb_img}<span style="font-size:13px;font-weight:700;color:#f5c518;">Hoops, She Did It Again · {WSBB_CHAMP}</span>'
                                f'</div>'
                                f'<div style="background:{_wr_rb_bg};border-radius:16px;padding:18px;">'
                                f'<div style="font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">Final Standing</div>'
                                f'<div style="font-size:44px;font-weight:900;color:{_wr_rbc};line-height:1;">{(_wr_emoji + " ") if _wr_emoji else ""}#{_wr_rank}</div>'
                                f'<div style="font-size:13px;color:#9ca3af;margin-top:4px;">out of {len(WSBB_STANDINGS)}</div>'
                                f'<div style="display:flex;justify-content:center;gap:20px;margin-top:10px;">'
                                f'<div><div style="font-size:18px;font-weight:800;color:#f5c518;">{_wr_pts}</div><div style="font-size:10px;color:#9ca3af;">points</div></div>'
                                f'<div><div style="font-size:18px;font-weight:800;color:#4fc3f7;">{_wr_cp}</div><div style="font-size:10px;color:#9ca3af;">correct picks</div></div>'
                                f'</div>'
                                f'</div>'
                                f'<div style="background:linear-gradient(135deg,#1e1e2e,#2d2d44);border-radius:12px;padding:12px;">'
                                f'<div style="font-size:10px;color:#9ca3af;text-transform:uppercase;margin-bottom:8px;">Points by Round</div>'
                                f'<div style="display:flex;gap:4px;">{_wr_cells}</div>'
                                f'</div>'
                                f'</div>'
                            ))

                        # Bonus Pool slide (if they're in the pool)
                        _in_bp = "Bonus Pool" in final_df.columns and not final_df[final_df["Name"] == _mn].empty and final_df[final_df["Name"] == _mn].iloc[0].get("Bonus Pool", False) == True
                        if _in_bp:
                            _bp_all = final_df[final_df["Bonus Pool"] == True].copy().sort_values("Current Score", ascending=False).reset_index(drop=True)
                            _bp_my_rank = next((i+1 for i,r in _bp_all.iterrows() if r["Name"] == _mn), None)
                            _bp_my_score = int(final_df[final_df["Name"] == _mn].iloc[0]["Current Score"])
                            _bp_rb_bg = "linear-gradient(135deg,#78350f,#b45309)" if _bp_my_rank==1 else "linear-gradient(135deg,#1e1b4b,#312e81)"
                            _bp_rbc   = "#f5c518" if _bp_my_rank==1 else "#fff"
                            _bp_emoji = "🏆" if _bp_my_rank==1 else ("🥈" if _bp_my_rank==2 else ("🥉" if _bp_my_rank==3 else ""))
                            _my_slides.append(("💰 Bonus Pool",
                                f'<div style="background:{_bp_rb_bg};border-radius:20px;padding:28px;text-align:center;">'
                                f'<div style="font-size:11px;color:#a5b4fc;letter-spacing:2px;text-transform:uppercase;margin-bottom:6px;">💰 Bonus Pool Standing</div>'
                                f'<div style="font-size:52px;font-weight:900;color:{_bp_rbc};line-height:1;">{(_bp_emoji + " ") if _bp_emoji else ""}#{_bp_my_rank}</div>'
                                f'<div style="font-size:14px;color:#9ca3af;margin-top:6px;">out of {len(_bp_all)} · {_bp_my_score} pts</div>'
                                f'</div>'
                            ))

                        # Summary slide — always shows key stats, plus any wins/top-3s
                        _summary_items = []

                        # Recompute variables that may not be defined if highlights wasn't rendered
                        _tc_mine = actual_winners[65] if len(actual_winners) > 65 and not is_unplayed(actual_winners[65]) else "TBD"
                        _lw_mine = [p for t, ps in lucky_map.items() for p in ps if t == _tc_mine]

                        def _wknd_pts_mine(r, col_end):
                            _pk = r["raw_picks"]
                            return sum(points_per_game[c] + seed_map.get(_pk[c], 0)
                                       for c in range(3, col_end)
                                       if not is_unplayed(actual_winners[c]) and _pk[c] == actual_winners[c])
                        _fw_sorted_mine = sorted(results, key=lambda r: _wknd_pts_mine(r, 51), reverse=True)
                        _fw_winner_mine  = _fw_sorted_mine[0]["Name"] if _fw_sorted_mine else "—"
                        _fw_score_mine   = _wknd_pts_mine(_fw_sorted_mine[0], 51) if _fw_sorted_mine else 0
                        _sw_sorted_mine  = sorted(results, key=lambda r: _wknd_pts_mine(r, 63), reverse=True)
                        _sw_winner_mine  = _sw_sorted_mine[0]["Name"] if _sw_sorted_mine else "—"
                        _sw_score_mine   = _wknd_pts_mine(_sw_sorted_mine[0], 63) if _sw_sorted_mine else 0

                        _upset_sorted_mine = sorted(results, key=lambda r: r.get("Upset Correct", 0), reverse=True)
                        _upset_top_mine    = _upset_sorted_mine[0].get("Upset Correct", 0) if _upset_sorted_mine else 0
                        _my_upset_count    = _mr.get("Upset Correct", 0)
                        # Upset rank
                        _my_upset_rank = next((i+1 for i,r in enumerate(_upset_sorted_mine) if r["Name"] == _mn), _ps)

                        _correct_sorted_mine = sorted(results, key=lambda r: sum(
                            1 for c in range(3,66) if not is_unplayed(actual_winners[c]) and r["raw_picks"][c] == actual_winners[c]
                        ), reverse=True)
                        _correct_top_mine = sum(1 for c in range(3,66) if not is_unplayed(actual_winners[c]) and _correct_sorted_mine[0]["raw_picks"][c] == actual_winners[c]) if _correct_sorted_mine else 0
                        # Correct picks rank
                        _my_correct_rank = next((i+1 for i,r in enumerate(_correct_sorted_mine) if r["Name"] == _mn), _ps)

                        # ── ALWAYS-SHOWN section ──────────────────────────────────
                        # Overall rank
                        _ov_medal = {1:"🏆",2:"🥈",3:"🥉"}.get(_mr_rank, "")
                        _ov_suffix = " 🥴" if _mr_rank == _ps else ""
                        _summary_items.append(f'{_ov_medal} <b>#{_mr_rank} Overall</b> out of {_ps}{_ov_suffix} ({_mr_score} pts)')

                        # Upset rank
                        _up_medal = {1:"🏆",2:"🥈",3:"🥉"}.get(_my_upset_rank, "")
                        _summary_items.append(f'{_up_medal} <b>#{_my_upset_rank} Upset Picks</b> ({_my_upset_count} correct upsets)')

                        # Correct picks rank
                        _cp_medal = {1:"🏆",2:"🥈",3:"🥉"}.get(_my_correct_rank, "")
                        _summary_items.append(f'{_cp_medal} <b>#{_my_correct_rank} Most Correct Picks</b> ({_mr_correct} picks)')

                        # Classic Rivalries — always show rank for every group they're in
                        _my_rivalries = [
                            {"slug":"andy-vs-dave","title":"🤺 Andy vs Dave","names":["Andy Yardley","Dave Sabour"]},
                            {"slug":"duel-of-dylans","title":"🎭 Duel of the Dylans","names":["Dylan Driver","Dylan Grassl","Dylan Levy"]},
                            {"slug":"rookies","title":"🐣 Rookies","names":["Diana Lower","Kellie Knight","Marise Gaughan","Saoirse Johnston-Dick","Sonia Raposo","Walter Czaya"]},
                            {"slug":"past-champions","title":"🏆 Past Champions","names":["Alana Davis","Jaymi Lynne","Sarah Keo","Tenley McCladdie","Lauren Froman","Armando Zamudio","James Sawaya","Priya Gupta"]},
                            {"slug":"reid-family","title":"👨‍👩‍👧‍👦 Reid Family Pool","names":["Debbie Reid","Matt Reid","Griffin Reid","Jack Reid","Elizabeth Hartmann","Taylor Chacon"]},
                            {"slug":"mountain-folk","title":"⛰️ Mountain Folk","names":["Daniel Wright","Dave Sabour","Diana Lower","Elizabeth Hartmann","Heidi Bruce","Hunter Phillips","Isaiah Erichsen","James Sawaya","Jeff Kooring","Kelyn Ikegami","McKinley Hancock","Robert Dick","Sarah Keo","Siobhan Sargent","Sonia Raposo","Andrea Racine","Saoirse Johnston-Dick"]},
                            {"slug":"boltonites","title":"🏘️ Boltonites","names":["Anthony Snelling","Brendan Tierney","Brian Moske","Bryce Carlson","Debbie Reid","Dylan Driver","Greg Murphy","Griffin Reid","Jack Reid","Karen Tierney","Matt Reid","Sam Bahre","Walter Czaya","Will Hillebrand"]},
                            {"slug":"veterans","title":"🎖️ 8+ Year Veterans","names":["Alana Davis","Laura Rubin","Jared Goldstein","Molly Davis","Jaymi Lynne","Greg Murphy","James Sawaya","Matt Reid","Dylan Grassl","Sam Bahre","Griffin Reid","Elias Luna","Sarah Keo","Tony Astacio","Will Hillebrand","Amanda Kosack","Siobhan Sargent","Priya Gupta","Sean McCoy","Dylan Driver","Robert Dick","Andrea Racine","Andy Yardley","Dave Sabour","Anthony Snelling","Sara Ruggiero","Megan Gorman","Christian Palacios","Heidi Bruce","Romana Guillotte","Sarah Simonds","McKinley Hancock","Alex Bahre","Pete Mullin","Nicki Doyamis"]},
                        ]
                        for _rv in _my_rivalries:
                            if _mn not in _rv["names"]:
                                continue
                            _grp_members = [r for r in results if r["Name"] in _rv["names"]]
                            _grp_sorted  = sorted(_grp_members, key=lambda r: int(final_df[final_df["Name"]==r["Name"]].iloc[0]["Current Score"]) if not final_df[final_df["Name"]==r["Name"]].empty else 0, reverse=True)
                            _grp_rank = next((i+1 for i,r in enumerate(_grp_sorted) if r["Name"]==_mn), None)
                            if _grp_rank:
                                _rv_medal = {1:"🏆",2:"🥈",3:"🥉"}.get(_grp_rank, "")
                                _summary_items.append(f'{_rv_medal} <b>#{_grp_rank} {_rv["title"]}</b> (of {len(_grp_sorted)})')

                        # ── BONUS WINS section (only if they won/placed) ──────────
                        _bonus_items = []

                        # Tiebreaker rank
                        if _tb_rank:
                            _tb_medal = {1:"🏆",2:"🥈",3:"🥉"}.get(_tb_rank, "")
                            if _tb_rank <= 3:
                                _bonus_items.append(f'{_tb_medal} <b>#{_tb_rank} Tiebreaker</b> (guessed {_mtb})')

                        # Lucky team
                        if _mn in _lw_mine:
                            _bonus_items.append(f'🍀 <b>Lucky Team Winner</b> ({_tc_mine})')

                        # Weekend leaders (top 3)
                        for _wknd_label, _wknd_sorted, _wknd_col in [
                            ("1st Weekend Leader", _fw_sorted_mine, 51),
                            ("2nd Weekend Leader", _sw_sorted_mine, 63),
                        ]:
                            _wknd_scores = [(_wknd_pts_mine(r, _wknd_col), r["Name"]) for r in _wknd_sorted]
                            _wknd_rank = next((i+1 for i,(s,n) in enumerate(_wknd_scores) if n == _mn), None)
                            if _wknd_rank and _wknd_rank <= 3:
                                _wknd_medal = {1:"🏆",2:"🥈",3:"🥉"}[_wknd_rank]
                                _wknd_pts_val = _wknd_pts_mine(next(r for r in results if r["Name"] == _mn), _wknd_col)
                                _bonus_items.append(f'{"♓" if "1st" in _wknd_label else "♈"} {_wknd_medal} <b>#{_wknd_rank} {_wknd_label}</b> ({_wknd_pts_val} pts)')

                        # Regional top 3
                        for _reg in ["East","West","South","Midwest"]:
                            _rgs2 = sorted(results, key=lambda r: r.get(f"{_reg} Score", 0), reverse=True)
                            _prev_s2 = None; _cur_rk2 = 0
                            for _rr2 in _rgs2:
                                _s2 = _rr2.get(f"{_reg} Score", 0)
                                if _s2 != _prev_s2:
                                    _cur_rk2 += 1; _prev_s2 = _s2
                                if _cur_rk2 > 3: break
                                if _rr2["Name"] == _mn:
                                    _reg_medal = {1:"🏆",2:"🥈",3:"🥉"}.get(_cur_rk2,"")
                                    _bonus_items.append(f'{_reg_medal} <b>#{_cur_rk2} {_reg} Region</b> ({int(_rr2.get(f"{_reg} Score",0))} pts)')

                        # Women's pool — always show if they participated
                        if _wsbb_row:
                            _wb_medal = {1:"🏆",2:"🥈",3:"🥉"}.get(_wr_rank, "")
                            _bonus_items.append(f'{_wb_medal} <b>#{_wr_rank} Women\'s Pool</b> ({_wr_pts} pts)')

                        # Bonus Pool top 3
                        if _in_bp and _bp_my_rank and _bp_my_rank <= 3:
                            _bpm = {1:"🏆",2:"🥈",3:"🥉"}[_bp_my_rank]
                            _bonus_items.append(f'{_bpm} <b>#{_bp_my_rank} Bonus Pool</b> ({_bp_my_score} pts)')

                        # Build summary HTML
                        def _sum_row(item, highlight=False):
                            bg = "#14532d" if "🏆" in item else ("#1e1b4b" if "🥈" in item or "🥉" in item else "#1e1e2e")
                            return f'<div style="background:{bg};border-radius:10px;padding:9px 13px;font-size:13px;color:#e5e7eb;text-align:left;">{item}</div>'

                        _always_rows = "".join(_sum_row(i) for i in _summary_items)
                        _bonus_rows  = "".join(_sum_row(i) for i in _bonus_items)

                        _sum_html = (
                            f'<div style="text-align:center;margin-bottom:8px;">'
                            f'<div style="font-size:28px;">🌟</div>'
                            f'<div style="font-size:12px;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;">Your Highlights</div>'
                            f'</div>'
                            f'<div style="display:flex;flex-direction:column;gap:5px;">{_always_rows}</div>'
                            + (
                                f'<div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin:8px 0 4px;">🎁 Bonus Wins</div>'
                                f'<div style="display:flex;flex-direction:column;gap:5px;">{_bonus_rows}</div>'
                                if _bonus_items else ""
                            )
                        )
                        _my_slides.append(("🌟 Your Highlights", _sum_html))

                        # ── Render as iframe slideshow ────────────────────────────
                        _mn_slides     = len(_my_slides)
                        _mn_init       = st.session_state.get("my_recap_slide", 0) % _mn_slides
                        _mn_titles_js  = "[" + ",".join('"' + t.replace('"','\\"') + '"' for t,_ in _my_slides) + "]"
                        _mn_inner      = "".join(f'<div class="slide">{h}</div>' for _,h in _my_slides)
                        _mn_dots       = "".join(f'<span class="dot" data-i="{i}"></span>' for i in range(_mn_slides))
                        # Index of the journey slide (always slide 2, index 1)
                        _journey_slide_idx = 1

                        import streamlit.components.v1 as _cv1b
                        _cv1b.html(f"""<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    *{{box-sizing:border-box;margin:0;padding:0;}}
    html,body{{background:#0e1117;color:#fff;font-family:sans-serif;overflow:hidden;}}
    #title{{text-align:center;font-size:20px;color:#fff;font-weight:800;padding:6px 0 2px;}}
    #counter{{text-align:center;font-size:11px;color:#6b7280;margin-bottom:4px;}}
    #wrap{{width:100%;overflow:hidden;}}
    #track{{display:flex;will-change:transform;align-items:flex-start;}}
    .slide{{min-width:100%;padding:0 2px;}}
    #dots{{text-align:center;margin:6px 0 2px;}}
    .dot{{display:inline-block;width:10px;height:10px;border-radius:50%;background:#4b5563;margin:0 4px;cursor:pointer;vertical-align:middle;transition:background 0.2s;}}
    #nav{{display:flex;align-items:center;justify-content:space-between;padding:4px 0 6px;}}
    .btn{{background:#1e1e2e;border:1px solid #374151;color:#e5e7eb;padding:7px 16px;border-radius:8px;cursor:pointer;font-size:13px;}}
    .btn:disabled{{opacity:0.3;cursor:default;}}
    #navcount{{font-size:12px;color:#6b7280;}}
    img{{max-width:100%;}}
    #swipe-hint{{display:none;text-align:center;font-size:12px;color:#9ca3af;padding:2px 0;animation:fadeInOut 2s ease-in-out infinite;}}
    @keyframes fadeInOut{{0%,100%{{opacity:0.3;}}50%{{opacity:1;}}}}
    </style></head><body>
    <div id="title"></div>
    <div id="counter"></div>
    <div id="swipe-hint">← swipe to navigate →</div>
    <div id="wrap"><div id="track">{_mn_inner}</div></div>
    <div id="dots">{_mn_dots}</div>
    <div id="nav">
      <button class="btn" id="bp">← Prev</button>
      <span id="navcount"></span>
      <button class="btn" id="bn">Next →</button>
    </div>
    <script>
    var T={_mn_titles_js},N={_mn_slides},cur={_mn_init};
    var track=document.getElementById('track'),dots=document.querySelectorAll('.dot'),bp=document.getElementById('bp'),bn=document.getElementById('bn');
    var sx=null,sy=null,sw=false;
    function goTo(i,anim){{
      if(i<0||i>=N)return; cur=i;
      track.style.transition=(anim===false)?'none':'transform 0.3s ease';
      track.style.transform='translateX('+(-cur*100)+'%)';
      dots.forEach(function(d,j){{d.style.background=j===cur?'#f5c518':'#4b5563';}});
      document.getElementById('title').textContent=T[cur];
      document.getElementById('counter').textContent=(cur+1)+' / '+N;
      document.getElementById('navcount').textContent=(cur+1)+' of '+N;
      bp.disabled=cur===0; bn.disabled=cur===N-1;
    }}
    goTo(cur,false);
    bp.onclick=function(){{goTo(cur-1);}};
    bn.onclick=function(){{goTo(cur+1);}};
    dots.forEach(function(d){{d.onclick=function(){{goTo(+d.dataset.i);}};}});
    var hint2=document.getElementById('swipe-hint');
    if('ontouchstart' in window||navigator.maxTouchPoints>0){{hint2.style.display='block';}}
    track.addEventListener('touchstart',function(e){{sx=e.touches[0].clientX;sy=e.touches[0].clientY;sw=true;track.style.transition='none';if(hint2)hint2.style.display='none';}},{{passive:true}});
    track.addEventListener('touchmove',function(e){{
      if(!sw||sx===null)return;
      var dx=e.touches[0].clientX-sx,dy=e.touches[0].clientY-sy;
      if(Math.abs(dy)>Math.abs(dx)){{sw=false;return;}}
      track.style.transform='translateX(calc('+(-cur*100)+'% + '+dx+'px))';
    }},{{passive:true}});
    track.addEventListener('touchend',function(e){{
      if(!sw||sx===null)return;
      var dx=e.changedTouches[0].clientX-sx;sx=null;sw=false;
      goTo(Math.abs(dx)>50?(dx<0?cur+1:cur-1):cur);
    }});
    </script></body></html>""", height=900, scrolling=False)

                        # ── Standings progress chart (always shown below slideshow) ─
                        _CHRON_MR = {
                            "R64": ["TCU","Nebraska","Louisville","High Point","Duke","Vanderbilt",
                                    "Michigan St.","Arkansas","VCU","Michigan","Texas","Texas A&M",
                                    "Illinois","Saint Louis","Gonzaga","Houston",
                                    "Kentucky","Texas Tech","Arizona","Virginia","Iowa St.","Alabama",
                                    "Utah St.","Tennessee","Iowa","St. John's","Purdue","UCLA",
                                    "Florida","Kansas","Miami (Fla.)","UConn"],
                            "R32": ["Michigan","Michigan St.","Duke","Houston","Texas","Illinois","Nebraska","Arkansas",
                                    "Purdue","Iowa St.","St. John's","Tennessee","Iowa","Arizona","UConn","Alabama"],
                            "S16": ["Purdue","Iowa","Arizona","Illinois","Duke","Michigan","UConn","Tennessee"],
                            "E8":  ["Illinois","Arizona","Michigan","UConn"],
                            "F4":  [], "Champ": [],
                        }
                        _RO_MR = {"R64":0,"R32":1,"S16":2,"E8":3,"F4":4,"Champ":5}
                        def _mr_chron_key(c):
                            _w = actual_winners[c]; _r = get_round_name(c)
                            _lst = _CHRON_MR.get(_r, [])
                            try: _pos = _lst.index(_w)
                            except ValueError: _pos = 999
                            return (_RO_MR.get(_r, 9), _pos)
                        _mr_played = sorted([c for c in range(3,66) if not is_unplayed(actual_winners[c])], key=_mr_chron_key)

                        if _mr_played:
                            _all_picks_mr = {r["Name"]: r["raw_picks"] for r in results}
                            _names_mr = list(_all_picks_mr.keys())
                            _running_mr = {n:0 for n in _names_mr}
                            _rank_hist_mr = {n:[] for n in _names_mr}
                            _round_short_mr = {"R64":"R1","R32":"R2","S16":"S16","E8":"E8","F4":"FF","Champ":"🏆"}
                            _slot_rnds_mr = [get_round_name(c) for c in _mr_played]
                            _seen_rnds_mr = list(dict.fromkeys(_slot_rnds_mr))
                            n_rnds_mr = len(_seen_rnds_mr)
                            _rnd_counts_mr = {rn: _slot_rnds_mr.count(rn) for rn in _seen_rnds_mr}

                            for _c in _mr_played:
                                _winner = actual_winners[_c]
                                _pts_c = points_per_game[_c] + seed_map.get(_winner, 0)
                                for _n in _names_mr:
                                    if _c < len(_all_picks_mr[_n]) and _all_picks_mr[_n][_c] == _winner:
                                        _running_mr[_n] += _pts_c
                                _scores_mr = sorted([(n, _running_mr[n]) for n in _names_mr], key=lambda x: x[1], reverse=True)
                                _prev_sc_mr, _prev_rk_mr = None, 0
                                _rank_map_mr = {}
                                for _ri_mr, (_n_mr, _sc_mr) in enumerate(_scores_mr):
                                    if _sc_mr != _prev_sc_mr:
                                        _prev_rk_mr = _ri_mr + 1; _prev_sc_mr = _sc_mr
                                    _rank_map_mr[_n_mr] = _prev_rk_mr
                                for _n in _names_mr:
                                    _rank_hist_mr[_n].append(_rank_map_mr[_n])

                            # X positions (by round)
                            _x_mr = []
                            for _gi, _rn in enumerate(_slot_rnds_mr):
                                _ri = _seen_rnds_mr.index(_rn)
                                _gc = sum(1 for r in _slot_rnds_mr[:_gi] if r == _rn)
                                _frac = (_gc + 0.5) / _rnd_counts_mr[_rn]
                                _x_mr.append((_ri + _frac) / n_rnds_mr)

                            fig_mr = go.Figure()
                            # Grey background players
                            for _n in _names_mr:
                                if _n == _mn: continue
                                fig_mr.add_trace(go.Scatter(x=_x_mr, y=_rank_hist_mr[_n], mode="lines",
                                    line=dict(color="rgba(100,100,120,0.15)", width=1),
                                    showlegend=False, hoverinfo="skip"))
                            # User line — gold
                            if _mn in _rank_hist_mr:
                                _ur = _rank_hist_mr[_mn]
                                fig_mr.add_trace(go.Scatter(x=_x_mr, y=_ur, mode="lines+markers",
                                    line=dict(color="#f5c518", width=3),
                                    marker=dict(size=6, color="#f5c518", line=dict(color="#fff", width=1)),
                                    name=_mn, hovertemplate="<b>"+_mn+"</b><br>#%{y}<extra></extra>"))

                            # Round boundary lines + labels
                            _shapes_mr, _annots_mr = [], []
                            for _ri, _rn in enumerate(_seen_rnds_mr):
                                _bx = _ri / n_rnds_mr
                                if _ri > 0:
                                    _shapes_mr.append(dict(type="line", x0=_bx, x1=_bx,
                                        y0=0.5, y1=len(_names_mr)+0.5, xref="x", yref="y",
                                        line=dict(color="rgba(255,255,255,0.15)", width=1, dash="dot")))
                                _cx = (_ri + 0.5) / n_rnds_mr
                                _annots_mr.append(dict(x=_cx, y=0.3,
                                    text=_round_short_mr.get(_rn, _rn),
                                    showarrow=False, font=dict(size=11, color="rgba(255,255,255,0.5)"),
                                    xanchor="center", yanchor="bottom", xref="x", yref="y"))

                            _cur_rank_mr = _rank_hist_mr[_mn][-1] if _rank_hist_mr.get(_mn) else "?"
                            fig_mr.update_layout(
                                dragmode=False,
                                title=dict(text=f"{_mn.split()[0]}'s Rank Journey — Finished #{_cur_rank_mr}", font=dict(size=14)),
                                yaxis=dict(autorange="reversed", range=[len(_names_mr)+1, 0],
                                           title="Rank", tickmode="linear", dtick=10,
                                           gridcolor="rgba(255,255,255,0.05)"),
                                xaxis=dict(showticklabels=False, showgrid=False, range=[-0.01, 1.01]),
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                                height=320, margin=dict(l=0, r=0, t=40, b=10),
                                shapes=_shapes_mr, annotations=_annots_mr,
                                showlegend=False,
                            )
                            st.plotly_chart(fig_mr, use_container_width=True, config={"displayModeBar": False})

    # ── Tab 1: Standings ──────────────────────────────────────────────────────
    with tab_standings:
        st.subheader("Live Standings")

        # Sub-navigation: Current / Potential / Snapshot
        _std_sub = st.session_state.get("nav_sub_standings", "current")
        _std_c1, _std_c2, _std_c3, _std_c4 = st.columns(4)
        if _std_c1.button("📊 Current", key="std_current", use_container_width=True,
                           type="primary" if _std_sub == "current" else "secondary"):
            st.session_state["nav_sub_standings"] = "current"
            st.rerun()
        if _std_c2.button("🔮 Potential", key="std_potential", use_container_width=True,
                           type="primary" if _std_sub == "potential" else "secondary"):
            st.session_state["nav_sub_standings"] = "potential"
            st.rerun()
        if _std_c3.button("💚 Still Alive", key="std_alive", use_container_width=True,
                           type="primary" if _std_sub == "alive" else "secondary"):
            st.session_state["nav_sub_standings"] = "alive"
            st.rerun()
        if _std_c4.button("📸 Snapshot", key="std_snapshot", use_container_width=True,
                           type="primary" if _std_sub == "snapshot" else "secondary"):
            st.session_state["nav_sub_standings"] = "snapshot"
            st.rerun()
        st.divider()
        _std_sub = st.session_state.get("nav_sub_standings", "current")

        if _std_sub == "snapshot":
            _SNAPSHOT_SECTION = True
        else:
            _SNAPSHOT_SECTION = False
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
            if not _SNAPSHOT_SECTION and _std_sub not in ("alive",) and _std_sub == "current":
                # ── Current standings: rich HTML table with logos ────────────────
                cur_df = final_df[["Current Rank", "Name", "Current Score"]].copy()
                cur_df = cur_df.rename(columns={"Current Rank": "Rank"})
                cur_df = cur_df.reset_index(drop=True)

                def _logo_tag(team, size=18, alive=True, block=False, show_x=True):
                    url = espn_logo_url(team) if team else None
                    display = "display:block;" if block else "display:inline-block;"
                    if url:
                        if alive:
                            return (
                                f'<span style="{display}vertical-align:middle;">'
                                f'<img src="{url}" style="width:{size}px;height:{size}px;object-fit:contain;display:block;" onerror="this.style.display=&quot;none&quot;">'
                                f'</span>'
                            )
                        else:
                            x_html = (
                                f'<span style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);'
                                f'font-size:{int(size*0.80)}px;line-height:1;color:#ef444499;font-weight:700;pointer-events:none;">✕</span>'
                            ) if show_x else ""
                            return (
                                f'<span style="position:relative;{display}vertical-align:middle;">'
                                f'<img src="{url}" style="width:{size}px;height:{size}px;object-fit:contain;display:block;opacity:0.50;" onerror="this.style.display=&quot;none&quot;">'
                                f'{x_html}'
                                f'</span>'
                            )
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
                                f'{_logo_tag(_champ_pick, 18, _champ_alive, show_x=False)}'
                                f'<span style="font-size:10px;{_champ_style}">{_champ_pick}</span>'
                                f'</div>'
                            )
                        else:
                            champ_html = (
                                f'{_logo_tag(_champ_pick, 16, _champ_alive, show_x=False)}'
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
                            lucky_html = f'{_logo_tag(lt, 16, lt_alive, show_x=False)}<span style="font-size:11px;vertical-align:middle;{lt_style}">{lt}</span>'
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

            elif not _SNAPSHOT_SECTION and _std_sub != "alive":
                # ── Potential standings: existing AgGrid table ───────────────────
                display_cols = ["Current Rank", "Name", "Current Score",
                                "Potential Score", "Win %", "Top 3 %", "Potential Status"]
                def highlight_user_row(row):
                    if user_name and row["Name"] == user_name:
                        return ["background-color: #3a3000; color: #f5c518; font-weight: bold"] * len(row)
                    return [""] * len(row)

                standings_df = final_df[display_cols].copy()
                standings_df = standings_df.rename(columns={"Current Rank": "Rank"})
                # Keep Win % and Top 3 % as floats so AgGrid sorts numerically
                # (formatting handled via pct_cols valueFormatter)
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
                    pct_cols=["Win %", "Top 3 %"],
                    desc_cols=["Current Score", "Potential Score", "Win %", "Top 3 %"],
                    asc_cols=["Rank", "Name"],
                    comparator_cols={
                        "Potential Status": """
                        function(a, b) {
                            var order = {'🏆 Champion': 0, '🥉 Top 3': 1, '💩 Out/Last': 2, '❌ Out': 3};
                            var oa = (a in order) ? order[a] : 99;
                            var ob = (b in order) ? order[b] : 99;
                            return oa - ob;
                        }
                        """
                    },
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
            if not _SNAPSHOT_SECTION and _std_sub != "alive":
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
                _annotations = []
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
                        _is_alive = _team in truly_alive
                        _sizex  = _max_score * 0.115 if _is_champ else _max_score * 0.09
                        _sizey  = 0.75 if _is_champ else 0.55
                        _opac   = 1.0 if _is_alive else 0.5
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
                        # Gold circle outline behind champion logo
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
                        # Red ✕ annotation over eliminated logos
                        if not _is_alive:
                            _annotations.append(dict(
                                x=_x, y=_yi,
                                xref="x", yref="y",
                                text="✕",
                                showarrow=False,
                                font=dict(size=18, color="rgba(239,68,68,0.9)", family="Arial Black"),
                                xanchor="center", yanchor="middle",
                            ))
                _layout_extra = {}
                if _images:
                    _layout_extra["images"] = _images
                if _shapes:
                    _layout_extra["shapes"] = _shapes
                if _annotations:
                    _layout_extra["annotations"] = _annotations
                if _layout_extra:
                    fig.update_layout(**_layout_extra)
    
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        if _std_sub == "alive":
            st.subheader("💚 Still Alive — Top 3 Contenders")
            st.caption("Only showing participants who still have a chance to finish in the Top 3.")

            _alive_rows = [r for r in results if r.get("Top 3 %", 0) > 0]
            _alive_rows.sort(key=lambda r: (-r.get("Top 3 %", 0), -r["Current Score"]))

            if not _alive_rows:
                st.info("No participants with a Top 3 chance remaining.")
            else:
                st.markdown(f"**{len(_alive_rows)} participant{'s' if len(_alive_rows) != 1 else ''} still in contention**")
                _trs = ""
                for _rank_i, _r in enumerate(_alive_rows, 1):
                    _is_user = user_name and _r["Name"] == user_name
                    _row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if _is_user else ""
                    _top3_pct = _r.get("Top 3 %", 0)
                    _win_pct  = _r.get("Win %", 0)
                    _medal = "🏆" if _rank_i == 1 else ("🥈" if _rank_i == 2 else ("🥉" if _rank_i == 3 else str(_rank_i)))
                    _cur_rank = int(_r.get("Current Rank", _rank_i))
                    # Champion pick
                    _picks = _r.get("raw_picks", [])
                    _champ_pick = _picks[65] if len(_picks) > 65 and _picks[65] not in {"", "nan", "TBD"} else ""
                    if _champ_pick:
                        _champ_alive = _champ_pick in truly_alive
                        _champ_style = "color:#22c55e;" if _champ_alive else "color:#ef4444;text-decoration:line-through;"
                        _logo_url = espn_logo_url(_champ_pick) or ""
                        _logo_img = f'<img src="{_logo_url}" style="width:16px;height:16px;object-fit:contain;vertical-align:middle;margin-right:3px;" onerror="this.style.display=\'none\'">' if _logo_url else ""
                        _champ_html = f'{_logo_img}<span style="font-size:11px;{_champ_style}">{_champ_pick}</span>'
                    else:
                        _champ_html = "—"
                    _trs += (
                        f'<tr{_row_style}>'
                        f'<td style="width:32px;text-align:center;">{_medal}</td>'
                        f'<td style="padding:5px 10px;font-weight:600;">{_r["Name"]}</td>'
                        f'<td style="width:50px;text-align:center;">#{_cur_rank}</td>'
                        f'<td style="width:50px;text-align:center;">{int(_r["Current Score"])}</td>'
                        f'<td style="padding:5px 8px;">{_champ_html}</td>'
                        f'<td style="width:56px;text-align:center;">{_win_pct:.1f}%</td>'
                        f'<td style="width:56px;text-align:center;">{_top3_pct:.1f}%</td>'
                        f'</tr>'
                    )
                st.markdown(
                    '<div style="overflow-x:auto;">'
                    '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
                    '<thead><tr style="background:#1e1e2e;color:#9ca3af;">'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;"></th>'
                    '<th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Rank</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Score</th>'
                    '<th style="padding:6px 8px;text-align:left;border:1px solid #313244;">Champion</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Win %</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Top 3 %</th>'
                    '</tr></thead>'
                    f'<tbody style="color:#fff;">{_trs}</tbody>'
                    '</table></div>',
                    unsafe_allow_html=True
                )

        if _SNAPSHOT_SECTION and _std_sub == "snapshot":
            st.subheader("📸 Standings Snapshot")
            st.caption("View the full standings as they stood after any game in the tournament.")

            # Chronological order of game winners within each round
            _CHRON_BY_ROUND = {
                "R64": ["TCU","Nebraska","Louisville","High Point","Duke","Vanderbilt",
                        "Michigan St.","Arkansas","VCU","Michigan","Texas","Texas A&M",
                        "Illinois","Saint Louis","Gonzaga","Houston",
                        "Kentucky","Texas Tech","Arizona","Virginia","Iowa St.","Alabama",
                        "Utah St.","Tennessee","Iowa","St. John's","Purdue","UCLA",
                        "Florida","Kansas","Miami (Fla.)","UConn"],
                "R32": ["Michigan","Michigan St.","Duke","Houston","Texas","Illinois","Nebraska","Arkansas",
                        "Purdue","Iowa St.","St. John's","Tennessee","Iowa","Arizona","UConn","Alabama"],
                "S16": ["Purdue","Iowa","Arizona","Illinois","Duke","Michigan","UConn","Tennessee"],
                "E8":  ["Illinois","Arizona","Michigan","UConn"],
                "F4":  [],
                "Champ": [],
            }
            _ROUND_ORDER = {"R64": 0, "R32": 1, "S16": 2, "E8": 3, "F4": 4, "Champ": 5}

            def _chron_sort_key(c):
                _w = actual_winners[c]
                _r = get_round_name(c)
                _round_idx = _ROUND_ORDER.get(_r, 9)
                _lst = _CHRON_BY_ROUND.get(_r, [])
                try:
                    _pos = _lst.index(_w)
                except ValueError:
                    _pos = 999
                return (_round_idx, _pos)

            _snap_slots = sorted(
                [c for c in range(3, 66) if not is_unplayed(actual_winners[c])],
                key=_chron_sort_key
            )

            if not _snap_slots:
                st.info("No games have been played yet.")
            else:
                _snap_all_picks = {r["Name"]: r["raw_picks"] for r in results}
                _snap_names = list(_snap_all_picks.keys())
                _snap_running = {n: 0 for n in _snap_names}
                _snap_rank_history = {n: [] for n in _snap_names}  # rank after each game
                _snap_score_history = {n: [] for n in _snap_names}  # score after each game

                _rshort = {"R64":"R1","R32":"R2","S16":"S16","E8":"E8","F4":"FF","Champ":"🏆"}

                _snap_game_labels = []
                _snap_rnd_counts = {}
                for _c in _snap_slots:
                    _winner = actual_winners[_c]
                    _pts = points_per_game[_c] + seed_map.get(_winner, 0)
                    for _n in _snap_names:
                        _pk = _snap_all_picks[_n]
                        if _c < len(_pk) and _pk[_c] == _winner:
                            _snap_running[_n] += _pts
                    _scores = sorted([(n, _snap_running[n]) for n in _snap_names], key=lambda x: x[1], reverse=True)
                    _rm, _ps, _pr = {}, None, 0
                    for _ri, (_n, _sc) in enumerate(_scores):
                        if _sc != _ps:
                            _pr = _ri + 1
                            _ps = _sc
                        _rm[_n] = _pr
                    for _n in _snap_names:
                        _snap_rank_history[_n].append(_rm[_n])
                        _snap_score_history[_n].append(_snap_running[_n])

                    _rnd = _rshort.get(get_round_name(_c), get_round_name(_c))
                    _snap_rnd_counts[_rnd] = _snap_rnd_counts.get(_rnd, 0) + 1
                    _loser = defeated_map.get(_winner, "")
                    _ws = seed_map.get(_winner, 0)
                    _ls = seed_map.get(_loser, 0)
                    if _loser:
                        _matchup = f"({_ws}) {_winner} def. ({_ls}) {_loser}" if _ws and _ls else f"{_winner} def. {_loser}"
                    else:
                        _matchup = f"({_ws}) {_winner}" if _ws else _winner
                    _snap_game_labels.append(f"{_rnd} G{_snap_rnd_counts[_rnd]}: {_matchup}")

                # Game selector
                _snap_idx = st.select_slider(
                    "Select game",
                    options=list(range(len(_snap_slots))),
                    value=len(_snap_slots) - 1,
                    format_func=lambda i: _snap_game_labels[i],
                    key="snap_game_idx",
                )

                # Build standings at selected game
                _snap_data = []
                for _n in _snap_names:
                    _snap_data.append({
                        "Name": _n,
                        "Score": _snap_score_history[_n][_snap_idx],
                        "Rank": _snap_rank_history[_n][_snap_idx],
                    })
                _snap_df = pd.DataFrame(_snap_data).sort_values(["Rank", "Name"]).reset_index(drop=True)

                st.markdown(f"**After: {_snap_game_labels[_snap_idx]}**")
                st.markdown(f"*Game {_snap_idx + 1} of {len(_snap_slots)}*")

                # Render as HTML table with user highlight
                _snap_trs = ""
                for _, _sr in _snap_df.iterrows():
                    _is_user = user_name and _sr["Name"] == user_name
                    _row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if _is_user else ""
                    _snap_trs += (
                        f'<tr{_row_style}>'
                        f'<td style="text-align:center;padding:5px 8px;">{int(_sr["Rank"])}</td>'
                        f'<td style="padding:5px 10px;font-weight:600;">{_sr["Name"]}</td>'
                        f'<td style="text-align:center;padding:5px 8px;">{int(_sr["Score"])}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    '<div style="overflow-x:auto;">'
                    '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
                    '<thead><tr style="background:#1e1e2e;color:#9ca3af;">'
                    '<th style="padding:6px 8px;text-align:center;border:1px solid #313244;">Rank</th>'
                    '<th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>'
                    '<th style="padding:6px 8px;text-align:center;border:1px solid #313244;">Score</th>'
                    '</tr></thead>'
                    f'<tbody style="color:#fff;">{_snap_trs}</tbody>'
                    '</table></div>',
                    unsafe_allow_html=True
                )


    # ── Tab 2: Your Bracket (group) ───────────────────────────────────────────
    with tab_bracket:
        # Submenu buttons
        _sub_yb = st.session_state.get("nav_sub_your-bracket", "bracket")
        # Win Conditions hidden until after the Final Four (re-enables April 16 2026)
        _show_win_conditions = _ff_win_conditions and datetime.now() >= datetime(2026, 4, 16)
        _yb_options = [
            ("bracket",            "🗂️ Bracket"),
            ("bracket-dna",        "🧬 Bracket DNA"),
            *([("win-conditions",  "🔍 Win Conditions")] if _show_win_conditions else []),
            ("head-to-head",       "⚔️ Head-to-Head"),
            *([("standings-progress", "📈 Standings Progress")] if _ff_standings_progress else []),
        ]
        _yb_ncols = len(_yb_options)
        _yb_row1 = st.columns(_yb_ncols)
        _yb_row2 = st.columns(1)
        for _i, (_slug, _label) in enumerate(_yb_options):
            _active = _sub_yb == _slug
            _yb_col = _yb_row1[_i] if _i < _yb_ncols else _yb_row2[0]
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
                        "#a855f7" if "Last"      in str(p_potential) else
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


        elif _sub_yb == "standings-progress":
            st.subheader("📈 Standings Progress")

            _sp_name_lower = {n.lower(): n for n in name_opts}

            # Determine default for primary player selectbox
            _sp_prog_default = st.session_state.get("sp_prog_name_sel", "")
            if not _sp_prog_default or _sp_prog_default not in name_opts:
                _sp_prog_default = user_name if user_name and user_name in name_opts else "— select —"

            sp_name = st.selectbox(
                "Select your name",
                ["— select —"] + name_opts,
                key="sp_prog_name",
                index=(name_opts.index(_sp_prog_default) + 1) if _sp_prog_default in name_opts else 0,
            )
            st.session_state["sp_prog_name_sel"] = sp_name

            if sp_name != "— select —":
                _CHRON_BY_ROUND_SP = {
                    "R64": ["TCU","Nebraska","Louisville","High Point","Duke","Vanderbilt",
                            "Michigan St.","Arkansas","VCU","Michigan","Texas","Texas A&M",
                            "Illinois","Saint Louis","Gonzaga","Houston",
                            "Kentucky","Texas Tech","Arizona","Virginia","Iowa St.","Alabama",
                            "Utah St.","Tennessee","Iowa","St. John's","Purdue","UCLA",
                            "Florida","Kansas","Miami (Fla.)","UConn"],
                    "R32": ["Michigan","Michigan St.","Duke","Houston","Texas","Illinois","Nebraska","Arkansas",
                            "Purdue","Iowa St.","St. John's","Tennessee","Iowa","Arizona","UConn","Alabama"],
                    "S16": ["Purdue","Iowa","Arizona","Illinois","Duke","Michigan","UConn","Tennessee"],
                    "E8":  ["Illinois","Arizona","Michigan","UConn"],
                    "F4":  [], "Champ": [],
                }
                _ROUND_ORDER_SP = {"R64": 0, "R32": 1, "S16": 2, "E8": 3, "F4": 4, "Champ": 5}

                def _sp_chron_key(c):
                    _w = actual_winners[c]
                    _r = get_round_name(c)
                    _lst = _CHRON_BY_ROUND_SP.get(_r, [])
                    try:
                        _pos = _lst.index(_w)
                    except ValueError:
                        _pos = 999
                    return (_ROUND_ORDER_SP.get(_r, 9), _pos)

                _played_slots = sorted(
                    [c for c in range(3, 66) if not is_unplayed(actual_winners[c])],
                    key=_sp_chron_key
                )

                if not _played_slots:
                    st.info("No games played yet.")
                else:
                    # Manage highlighted players in session state
                    _sp_key = "sp_prog_highlighted"
                    if _sp_key not in st.session_state:
                        st.session_state[_sp_key] = set()
                    # Always ensure primary player is highlighted
                    _highlighted = st.session_state[_sp_key] | {sp_name}

                    # Colors for highlighted players (first = primary = gold)
                    _HIGHLIGHT_COLORS = [
                        "#f5c518", "#4fc3f7", "#fb923c", "#c084fc",
                        "#4ade80", "#f87171", "#38bdf8", "#fde68a",
                        "#a78bfa", "#34d399",
                    ]
                    # Assign colors: primary player always gets gold
                    _color_map = {sp_name: _HIGHLIGHT_COLORS[0]}
                    _color_idx = 1
                    for _n in sorted(_highlighted):
                        if _n != sp_name:
                            _color_map[_n] = _HIGHLIGHT_COLORS[_color_idx % len(_HIGHLIGHT_COLORS)]
                            _color_idx += 1

                    # Build cumulative rank history
                    _all_picks = {r["Name"]: r["raw_picks"] for r in results}
                    _names = list(_all_picks.keys())
                    _n_players = len(_names)
                    _running = {n: 0 for n in _names}
                    _rank_history = {n: [] for n in _names}

                    _round_short = {"R64":"R1","R32":"R2","S16":"S16","E8":"E8","F4":"FF","Champ":"🏆"}

                    for _c in _played_slots:
                        _winner = actual_winners[_c]
                        _pts_total = points_per_game[_c] + seed_map.get(_winner, 0)
                        for _n in _names:
                            _picks = _all_picks[_n]
                            if _c < len(_picks) and _picks[_c] == _winner:
                                _running[_n] += _pts_total
                        _scores = sorted([(n, _running[n]) for n in _names], key=lambda x: x[1], reverse=True)
                        _rank_map = {}
                        _prev_sc, _prev_rk = None, 0
                        for _ri, (_n, _sc) in enumerate(_scores):
                            if _sc != _prev_sc:
                                _prev_rk = _ri + 1
                                _prev_sc = _sc
                            _rank_map[_n] = _prev_rk
                        for _n in _names:
                            _rank_history[_n].append(_rank_map[_n])

                    # Build game descriptions for hover
                    _game_descs = []
                    for _c in _played_slots:
                        _winner = actual_winners[_c]
                        _ws = seed_map.get(_winner, 0)
                        _loser = defeated_map.get(_winner, "")
                        _ls = seed_map.get(_loser, 0)
                        if _loser:
                            _game_descs.append(f"({_ws}) {_winner} def. ({_ls}) {_loser}" if _ws and _ls else f"{_winner} def. {_loser}")
                        else:
                            _game_descs.append(f"({_ws}) {_winner}" if _ws else _winner)

                    # Zoom toggle
                    _zoom_key = "sp_prog_zoom"
                    if _zoom_key not in st.session_state:
                        st.session_state[_zoom_key] = "rounds"
                    _z1, _z2 = st.columns(2)
                    if _z1.button("📅 By Round", key="sp_zoom_rounds", use_container_width=True,
                                  type="primary" if st.session_state[_zoom_key] == "rounds" else "secondary"):
                        st.session_state[_zoom_key] = "rounds"
                        st.rerun()
                    if _z2.button("📊 By Game", key="sp_zoom_games", use_container_width=True,
                                  type="primary" if st.session_state[_zoom_key] == "games" else "secondary"):
                        st.session_state[_zoom_key] = "games"
                        st.rerun()
                    _zoom_mode = st.session_state[_zoom_key]

                    # Build x positions based on zoom mode
                    # For "rounds" mode: divide [0,1] equally per round, then space games evenly within
                    _round_names_order = ["R64", "R32", "S16", "E8", "F4", "Champ"]
                    _slot_rounds = [get_round_name(c) for c in _played_slots]

                    if _zoom_mode == "rounds":
                        # Group slots by round
                        _rounds_played = []
                        _seen_rnds = []
                        for _rn in _slot_rounds:
                            if _rn not in _seen_rnds:
                                _seen_rnds.append(_rn)
                        # Count games per round
                        _rnd_counts = {rn: _slot_rounds.count(rn) for rn in _seen_rnds}
                        n_rounds = len(_seen_rnds)
                        # Each round gets equal width = 1/n_rounds of total
                        # Within each round, games are evenly spaced
                        _x_positions = []
                        _rnd_x_start = {}
                        for _ri, _rn in enumerate(_seen_rnds):
                            _rnd_x_start[_rn] = _ri / n_rounds
                        for _gi, _rn in enumerate(_slot_rounds):
                            _ri = _seen_rnds.index(_rn)
                            _games_in_rnd = _rnd_counts[_rn]
                            _game_num = sum(1 for r in _slot_rounds[:_gi] if r == _rn)
                            # Position within round: evenly spaced, centered
                            _frac = (_game_num + 0.5) / _games_in_rnd
                            _x_pos = (_ri + _frac) / n_rounds
                            _x_positions.append(_x_pos)
                    else:
                        _x_positions = list(range(1, len(_played_slots) + 1))

                    # Rotation note
                    st.markdown('<p style="font-size:12px;color:#6b7280;text-align:center;margin-bottom:4px;">📱 Rotate phone horizontally for a better view</p>', unsafe_allow_html=True)

                    # Build chart
                    fig_sp = go.Figure()

                    # Grey lines for non-highlighted players
                    for _n in _names:
                        if _n in _highlighted:
                            continue
                        fig_sp.add_trace(go.Scatter(
                            x=_x_positions,
                            y=_rank_history[_n],
                            mode="lines",
                            line=dict(color="rgba(100,100,120,0.15)", width=1),
                            showlegend=False,
                            hoverinfo="skip",
                        ))

                    # Highlighted players — colored lines with hover
                    for _n in _highlighted:
                        _col = _color_map.get(_n, "#ffffff")
                        _ranks = _rank_history[_n]
                        _htexts = []
                        for _gi, (_rank, _desc) in enumerate(zip(_ranks, _game_descs)):
                            _prev = _ranks[_gi - 1] if _gi > 0 else _rank
                            _delta = _prev - _rank
                            _dstr = f"▲ {_delta}" if _delta > 0 else (f"▼ {abs(_delta)}" if _delta < 0 else "—")
                            _rnd_lbl = _round_short.get(get_round_name(_played_slots[_gi]), "")
                            _htexts.append(f"<b>{_n}</b><br><b>#{_rank}</b> after game {_gi+1}<br>{_rnd_lbl}: {_desc}<br>Rank change: {_dstr}")
                        _is_primary = (_n == sp_name)
                        fig_sp.add_trace(go.Scatter(
                            x=_x_positions,
                            y=_ranks,
                            mode="lines+markers" if _is_primary else "lines+markers",
                            line=dict(color=_col, width=3 if _is_primary else 2),
                            marker=dict(size=7 if _is_primary else 5, color=_col,
                                       line=dict(color="#fff", width=1) if _is_primary else dict(width=0)),
                            name=_n,
                            text=_htexts,
                            hovertemplate="%{text}<extra></extra>",
                        ))

                    # Round boundary lines & labels
                    _shapes_sp, _rnd_labels_sp = [], []
                    if _zoom_mode == "rounds":
                        # Boundaries at round edges
                        for _ri, _rn in enumerate(_seen_rnds):
                            _bx = _ri / n_rounds
                            if _ri > 0:
                                _shapes_sp.append(dict(type="line", x0=_bx, x1=_bx,
                                    y0=0.5, y1=_n_players+0.5, xref="x", yref="y",
                                    line=dict(color="rgba(255,255,255,0.15)", width=1, dash="dot")))
                            # Label at center of round
                            _cx = (_ri + 0.5) / n_rounds
                            _rnd_labels_sp.append(dict(x=_cx, y=0.3,
                                text=_round_short.get(_rn, _rn),
                                showarrow=False, font=dict(size=11, color="rgba(255,255,255,0.5)"),
                                xanchor="center", yanchor="bottom", xref="x", yref="y"))
                        _xaxis_opts = dict(
                            showticklabels=False, showgrid=False,
                            range=[-0.01, 1.01],
                            gridcolor="rgba(255,255,255,0.05)",
                        )
                    else:
                        _prev_rnd, _rnd_start = None, {}
                        for _gi, _c in enumerate(_played_slots):
                            _rnd = get_round_name(_c)
                            if _rnd != _prev_rnd:
                                if _gi > 0:
                                    _shapes_sp.append(dict(type="line", x0=_gi+0.5, x1=_gi+0.5,
                                        y0=0.5, y1=_n_players+0.5, xref="x", yref="y",
                                        line=dict(color="rgba(255,255,255,0.1)", width=1, dash="dot")))
                                _rnd_start[_rnd] = _gi + 1
                                _prev_rnd = _rnd
                        for _rnd, _gs in _rnd_start.items():
                            _rnd_labels_sp.append(dict(x=_gs, y=0.3, text=_round_short.get(_rnd, _rnd),
                                showarrow=False, font=dict(size=10, color="rgba(255,255,255,0.4)"),
                                xanchor="left", yanchor="bottom", xref="x", yref="y"))
                        _xaxis_opts = dict(
                            title="Game #",
                            gridcolor="rgba(255,255,255,0.05)",
                            range=[0.5, len(_played_slots)+0.5],
                        )

                    _cur_rank = _rank_history[sp_name][-1] if _rank_history[sp_name] else "?"
                    _first_name_sp = sp_name.split()[0]

                    fig_sp.update_layout(
                        dragmode=False,
                        title=f"{_first_name_sp}'s Rank Journey — Currently #{_cur_rank}",
                        yaxis=dict(autorange="reversed", range=[_n_players+1, 0], title="Rank",
                                   tickmode="linear", dtick=10, gridcolor="rgba(255,255,255,0.05)"),
                        xaxis=_xaxis_opts,
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                        height=420,
                        margin=dict(l=0, r=0, t=50, b=40),
                        shapes=_shapes_sp, annotations=_rnd_labels_sp,
                        hovermode="closest", hoverdistance=20,
                        legend=dict(
                            orientation="h", yanchor="top", y=-0.15,
                            xanchor="center", x=0.5,
                            font=dict(size=12), bgcolor="rgba(0,0,0,0)",
                        ),
                    )

                    _interactive_config = {"scrollZoom": False, "displayModeBar": False,
                                           "doubleClick": False, "staticPlot": False}
                    st.plotly_chart(fig_sp, use_container_width=True, config=_interactive_config)

                    # Player highlight buttons
                    st.markdown("**Highlight additional players:**")
                    _btn_cols = st.columns(5)
                    _sorted_names = sorted(name_opts)
                    for _bi, _bn in enumerate(_sorted_names):
                        if _bn == sp_name:
                            continue
                        _is_hl = _bn in st.session_state[_sp_key]
                        _btn_color = _color_map.get(_bn, "#6b7280") if _is_hl else "#6b7280"
                        _col_idx = _bi % 5
                        if _btn_cols[_col_idx].button(
                            _bn, key=f"sp_hl_{_bn}",
                            use_container_width=True,
                            type="primary" if _is_hl else "secondary",
                        ):
                            if _bn in st.session_state[_sp_key]:
                                st.session_state[_sp_key].discard(_bn)
                            else:
                                if len(st.session_state[_sp_key]) < 9:
                                    st.session_state[_sp_key].add(_bn)
                            st.rerun()

        elif _sub_yb == "bracket-dna":
            st.subheader("🧬 Bracket DNA & Probability")

            _dna_name_lower = {n.lower(): n for n in name_opts}
            dna_select = st.selectbox(
                "Select your name",
                ["— select —"] + name_opts,
                key="dna",
            )
            st.session_state["dna_sel"] = dna_select
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
                    "#a855f7" if "Last"     in str(dna_potential) else
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
                    and u["raw_picks"][c] in truly_alive
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

                # ── Championship Scenarios (Final Four stage only) ────────────
                _ff_unplayed = [c for c in range(63, 65) if is_unplayed(actual_winners[c])]
                _champ_unplayed = is_unplayed(actual_winners[65])

                def _sim_rank_sc(base_scores, game_awards):
                    _sc = dict(base_scores)
                    for _slot, _winner in game_awards:
                        _pts = points_per_game[_slot] + seed_map.get(_winner, 0)
                        for _r in results:
                            if _r["raw_picks"][_slot] == _winner:
                                _sc[_r["Name"]] = _sc[_r["Name"]] + _pts
                    _sorted = sorted(_sc.items(), key=lambda x: x[1], reverse=True)
                    _me_score = _sc.get(dna_select, 0)
                    _rank = next((i+1 for i,(n,s) in enumerate(_sorted) if s == _me_score), len(results))
                    _tied = [n for n,s in _sc.items() if s == _me_score and n != dna_select]
                    return _rank, _tied

                def _slabel(team):
                    s = seed_map.get(team, 0)
                    return f"({s}) {team}" if s else team

                def _lhtml(team, size=18):
                    url = espn_logo_url(team) if team else ""
                    if url:
                        return f'<img src="{url}" style="width:{size}px;height:{size}px;object-fit:contain;vertical-align:middle;margin-right:4px;" onerror="this.style.display=\'none\'">'
                    return ""

                if len(_ff_unplayed) == 2 and _champ_unplayed:
                    # Both FF games + Championship unplayed — show all 8 scenarios
                    _ff1_c, _ff2_c = _ff_unplayed[0], _ff_unplayed[1]
                    _p1a, _p1b = _BRACKET_PARENTS[_ff1_c]
                    _p2a, _p2b = _BRACKET_PARENTS[_ff2_c]
                    _ff1_a = actual_winners[_p1a] if not is_unplayed(actual_winners[_p1a]) else None
                    _ff1_b = actual_winners[_p1b] if not is_unplayed(actual_winners[_p1b]) else None
                    _ff2_a = actual_winners[_p2a] if not is_unplayed(actual_winners[_p2a]) else None
                    _ff2_b = actual_winners[_p2b] if not is_unplayed(actual_winners[_p2b]) else None

                    if all([_ff1_a, _ff1_b, _ff2_a, _ff2_b]):
                        _rg_scores = {r["Name"]: r["Current Score"] for r in results}
                        _me_name = dna_select

                        _my_ff1 = u["raw_picks"][_ff1_c] if _ff1_c < len(u["raw_picks"]) else ""
                        _my_ff2 = u["raw_picks"][_ff2_c] if _ff2_c < len(u["raw_picks"]) else ""
                        _my_ch  = u["raw_picks"][65] if 65 < len(u["raw_picks"]) else ""

                        _scenarios = []
                        for _w1 in [_ff1_a, _ff1_b]:
                            for _w2 in [_ff2_a, _ff2_b]:
                                for _wc in [_w1, _w2]:
                                    _rank, _tied = _sim_rank_sc(_rg_scores, [(_ff1_c, _w1), (_ff2_c, _w2), (65, _wc)])
                                    _scenarios.append({"ff1": _w1, "ff2": _w2, "champ": _wc, "rank": _rank, "tied": _tied})

                        _scenarios.sort(key=lambda x: x["rank"])
                        _best_possible = _scenarios[0]["rank"]
                        _worst_possible = _scenarios[-1]["rank"]

                        st.markdown(f"#### 🏆 All Championship Scenarios")
                        st.caption(f"Every possible path to the championship. Best possible: **#{_best_possible}** · Worst possible: **#{_worst_possible}**")

                        for _sc in _scenarios:
                            _w1, _w2, _wc = _sc["ff1"], _sc["ff2"], _sc["champ"]
                            _rank = _sc["rank"]
                            _tied = _sc["tied"]
                            if _rank == _best_possible:
                                _border, _rank_color = "#16a34a", "#4ade80"
                            elif _rank == _worst_possible:
                                _border, _rank_color = "#dc2626", "#f87171"
                            else:
                                _border, _rank_color = "#4b5563", "#e5e7eb"

                            def _tspan(team, my_pick):
                                _col = "#4ade80" if team == my_pick else "#9ca3af"
                                _wt = "700" if team == my_pick else "400"
                                return f'{_lhtml(team)}<span style="color:{_col};font-weight:{_wt};">{_slabel(team)}</span>'

                            _tie_html = ""
                            if _tied:
                                _tie_names = ", ".join(n.split()[0] for n in _tied[:3])
                                if len(_tied) > 3:
                                    _tie_names += f" +{len(_tied)-3}"
                                _tie_html = f'<div style="font-size:11px;color:#9ca3af;margin-top:4px;">Tie with {_tie_names}</div>'

                            st.markdown(
                                f'<div style="border:1px solid {_border};border-radius:10px;padding:10px 14px;'
                                f'margin-bottom:6px;background:#1e1e2e;">'
                                f'<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">'
                                f'<div style="font-size:13px;color:#e5e7eb;display:flex;flex-wrap:wrap;gap:6px;align-items:center;">'
                                f'<span style="color:#6b7280;font-size:11px;">FF:</span> {_tspan(_w1,_my_ff1)} '
                                f'<span style="color:#6b7280;">vs</span> {_tspan(_w2,_my_ff2)} '
                                f'<span style="color:#6b7280;font-size:11px;margin-left:4px;">🏆 Champion:</span> {_tspan(_wc,_my_ch)}'
                                f'</div>'
                                f'<div style="font-size:18px;font-weight:800;color:{_rank_color};white-space:nowrap;">#{_rank}</div>'
                                f'</div>'
                                f'{_tie_html}'
                                f'</div>',
                                unsafe_allow_html=True
                            )

                elif len(_ff_unplayed) == 1 and _champ_unplayed:
                    # One FF game done, one left + Championship — show 4 scenarios
                    _rem_ff_c = _ff_unplayed[0]
                    _done_ff_c = 64 if _rem_ff_c == 63 else 63
                    _known_ff_winner = actual_winners[_done_ff_c]
                    _pa, _pb = _BRACKET_PARENTS[_rem_ff_c]
                    _rem_a = actual_winners[_pa] if not is_unplayed(actual_winners[_pa]) else None
                    _rem_b = actual_winners[_pb] if not is_unplayed(actual_winners[_pb]) else None

                    if _rem_a and _rem_b and not is_unplayed(_known_ff_winner):
                        _rg_scores = {r["Name"]: r["Current Score"] for r in results}
                        _me_name = dna_select
                        _my_ff = u["raw_picks"][_rem_ff_c] if _rem_ff_c < len(u["raw_picks"]) else ""
                        _my_ch = u["raw_picks"][65] if 65 < len(u["raw_picks"]) else ""

                        _scenarios = []
                        for _wff in [_rem_a, _rem_b]:
                            for _wch in [_wff, _known_ff_winner]:
                                _rank, _tied = _sim_rank_sc(_rg_scores, [(_rem_ff_c, _wff), (65, _wch)])
                                _scenarios.append({"ff": _wff, "champ": _wch, "rank": _rank, "tied": _tied})
                        _scenarios.sort(key=lambda x: x["rank"])
                        _best_p = _scenarios[0]["rank"]
                        _worst_p = _scenarios[-1]["rank"]

                        st.markdown("#### 🏆 Remaining Scenarios")
                        st.caption(f"Best possible: **#{_best_p}** · Worst possible: **#{_worst_p}**")
                        for _sc in _scenarios:
                            _border = "#16a34a" if _sc["rank"] == _best_p else ("#dc2626" if _sc["rank"] == _worst_p else "#4b5563")
                            _rc = "#4ade80" if _sc["rank"] == _best_p else ("#f87171" if _sc["rank"] == _worst_p else "#e5e7eb")
                            _tie_html = ""
                            if _sc["tied"]:
                                _tn = ", ".join(n.split()[0] for n in _sc["tied"][:3])
                                _tie_html = f'<div style="font-size:11px;color:#9ca3af;margin-top:4px;">Tie with {_tn}</div>'
                            st.markdown(
                                f'<div style="border:1px solid {_border};border-radius:10px;padding:10px 14px;margin-bottom:6px;background:#1e1e2e;">'
                                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                f'<span style="font-size:13px;color:#e5e7eb;">{_lhtml(_sc["ff"])}{_slabel(_sc["ff"])} wins FF vs {_lhtml(_sc["champ"])}{_slabel(_sc["champ"])} wins 🏆</span>'
                                f'<span style="font-size:18px;font-weight:800;color:{_rc};">#{_sc["rank"]}</span>'
                                f'</div>{_tie_html}</div>', unsafe_allow_html=True)

                elif not _ff_unplayed and _champ_unplayed:
                    # Both FF done, just Championship left — show 2 scenarios
                    _f1 = actual_winners[63]
                    _f2 = actual_winners[64]
                    if not is_unplayed(_f1) and not is_unplayed(_f2):
                        _rg_scores = {r["Name"]: r["Current Score"] for r in results}
                        _me_name = dna_select
                        _my_ch = u["raw_picks"][65] if 65 < len(u["raw_picks"]) else ""

                        _scenarios = []
                        for _wch in [_f1, _f2]:
                            _rank, _tied = _sim_rank_sc(_rg_scores, [(65, _wch)])
                            _scenarios.append({"champ": _wch, "rank": _rank, "tied": _tied})
                        _scenarios.sort(key=lambda x: x["rank"])

                        st.markdown("#### 🏆 Championship Scenarios")
                        for _sc in _scenarios:
                            _border = "#16a34a" if _sc["rank"] == _scenarios[0]["rank"] else "#dc2626"
                            _rc = "#4ade80" if _sc["rank"] == _scenarios[0]["rank"] else "#f87171"
                            _tie_html = ""
                            if _sc["tied"]:
                                _tn = ", ".join(n.split()[0] for n in _sc["tied"][:3])
                                _tie_html = f'<div style="font-size:11px;color:#9ca3af;margin-top:4px;">Tie with {_tn}</div>'
                            st.markdown(
                                f'<div style="border:1px solid {_border};border-radius:10px;padding:10px 14px;margin-bottom:6px;background:#1e1e2e;">'
                                f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                                f'<span style="font-size:13px;color:#e5e7eb;">🏆 Champion: {_lhtml(_sc["champ"])}{_slabel(_sc["champ"])}</span>'
                                f'<span style="font-size:18px;font-weight:800;color:{_rc};">#{_sc["rank"]}</span>'
                                f'</div>{_tie_html}</div>', unsafe_allow_html=True)



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

        _user_tz_str = st.session_state.get("user_tz", "")

        # Apply date and game query params on first load
        if "sp_qp_applied" not in st.session_state:
            st.session_state["sp_qp_applied"] = True
            try:
                _qdate = st.query_params.get("date", "")
                if _qdate and _qdate in TOURN_DATES:
                    st.session_state["sp_sel_date"] = _qdate
                _qgame = st.query_params.get("game", "")
                if _qgame != "" and _qdate:
                    try:
                        _qgi = int(_qgame)
                        st.session_state["sp_expanded_game"] = f"sp_game_{_qdate}_{_qgi}"
                    except (ValueError, TypeError):
                        pass
                st.query_params.pop("date", None)
                st.query_params.pop("game", None)
            except Exception:
                pass
        from datetime import datetime as _dt, date as _date, timezone as _tz_utc, timedelta as _td
        import zoneinfo as _zi
        import streamlit.components.v1 as _sp_components
        import urllib.request as _urllib_req
        import json as _json
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

        # Read ?game= query param — navigate to date and auto-expand that game
        try:
            _qgame = st.query_params.get("game", "")
            if _qgame and not st.session_state.get("_sp_game_qp_applied"):
                st.session_state["_sp_game_qp_applied"] = True
                st.session_state["_sp_expand_game_id"] = _qgame
                st.query_params.pop("game", None)
        except Exception:
            pass

        st.markdown("---")

        _user_tz_str = st.session_state.get("user_tz", "")

        # ── Format game time in user's local timezone ─────────────────────
        def _format_game_time(utc_iso, user_tz_str):
            """Return time string in user's local timezone, falling back to ET."""
            try:
                _utc = _dt.fromisoformat(utc_iso.replace("Z", "+00:00"))
                if user_tz_str:
                    try:
                        _local = _utc.astimezone(_zi.ZoneInfo(user_tz_str))
                        _t = _local.strftime("%I:%M %p %Z").lstrip("0")
                        return _t
                    except Exception:
                        pass
                # Fallback to ET
                _et = _utc.astimezone(_tz_utc(offset=_td(hours=-4)))
                return _et.strftime("%I:%M %p ET").lstrip("0")
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
                req = _urllib_req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with _urllib_req.urlopen(req, timeout=8) as resp:
                    data = _json.loads(resp.read())
                games = []
                for ev in data.get("events", []):
                    comp = ev.get("competitions", [{}])[0]
                    competitors = comp.get("competitors", [])
                    if len(competitors) < 2:
                        continue
                    # For known tournament dates, accept all games with seeds or neutral site
                    # (ESPN note headlines vary by round — don't rely on them exclusively)
                    notes = comp.get("notes", [])
                    is_tourney = any(
                        "Championship" in n.get("headline", "") or
                        "NCAA" in n.get("headline", "") or
                        "Elite" in n.get("headline", "") or
                        "Sweet" in n.get("headline", "") or
                        "Final Four" in n.get("headline", "") or
                        "Regional" in n.get("headline", "")
                        for n in notes
                    )
                    if not is_tourney:
                        has_seeds = any(c.get("rank") or c.get("seed") for c in competitors)
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
                        game_time_et = _et.strftime("%I:%M %p ET").lstrip("0")
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
                    # Extract broadcast network
                    _broadcasts = comp.get("broadcasts", [])
                    _network = ""
                    for _b in _broadcasts:
                        _names = _b.get("names", [])
                        if _names:
                            _network = _names[0]
                            break
                    # Also check geoBroadcasts
                    if not _network:
                        for _gb in comp.get("geoBroadcasts", []):
                            _media = _gb.get("media", {})
                            if _media.get("shortName"):
                                _network = _media["shortName"]
                                break

                    games.append({
                        "id":        ev.get("id"),
                        "state":     state,
                        "detail":    status_detail,
                        "time":      game_time_et,
                        "utc_iso":   game_date_str,
                        "sort_time": game_date_str,
                        "network":   _network,
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
                        _time_str = game.get("time", "")
                    _network = game.get("network", "")
                    _network_html = ""
                    if _network:
                        _net_upper = _network.upper()
                        if any(x in _net_upper for x in ("TBS", "TNT", "TRUTV")):
                            _streaming = "HBO Max · Paramount+ · March Madness Live"
                        elif "CBS" in _net_upper:
                            _streaming = "Paramount+ · March Madness Live"
                        else:
                            _streaming = ""
                        _network_html = (
                            f'<div style="font-size:13px;color:#6b7280;text-align:center;margin-top:2px;">{_network}</div>'
                            + (f'<div style="font-size:11px;color:#4b5563;text-align:center;margin-top:1px;line-height:1.6;">'
                               + "".join(f'{s}<br>' for s in _streaming.split(" · "))
                               + '</div>' if _streaming else "")
                        )
                    middle = (
                        f'<div style="text-align:center;padding:0 8px;">'
                        f'<div style="font-size:16px;font-weight:600;color:#9ca3af;white-space:nowrap;">{_time_str or "TBD"}</div>'
                        f'{_network_html}'
                        f'</div>'
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

                # Auto-expand if this game's ESPN ID matches ?game= param
                _expand_id = st.session_state.get("_sp_expand_game_id", "")
                if _expand_id and str(game.get("id", "")) == str(_expand_id):
                    if not _is_expanded:
                        st.session_state["sp_expanded_game"] = _game_key
                        _is_expanded = True
                    st.session_state.pop("_sp_expand_game_id", None)

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

                # Biggest carnage: sum Busted Picks per winner team across all rounds
                _team_busts = busters_df.groupby("Winner")["Busted Picks"].sum().sort_values(ascending=False)
                _top_buster = _team_busts.index[0]
                _top_buster_picks = int(_team_busts.iloc[0])
                m2.metric("Biggest Carnage", _top_buster, f"{_top_buster_picks} total picks busted")

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
            *([("lucky-team",         "🍀 Lucky Team")] if _ff_lucky_team else []),
            ("regional",           "🗺️ Regional Breakdown"),
            ("upset-picks",        "😤 Upset Picks"),
            ("correct-picks",      "✅ Correct Picks"),
            ("1st-weekend",        "♓ 1st Weekend Leader"),
            ("2nd-weekend",        "♈ 2nd Weekend Leader"),
            ("tiebreaker-scores",  "🎯 Tiebreaker Scores"),
            *([("hoops-she-did-it",   "🏀 Hoops, She Did It Again")] if _ff_hoops_pool else []),
            *([("bonus-pool",         "💰 Bonus Pool")] if _ff_bonus_pool else []),
        ]
        _bon_row1 = st.columns(4)
        _bon_row2 = st.columns(4)
        _bon_row3 = st.columns(1)
        for _i, (_slug, _label) in enumerate(_bon_options):
            _active = _sub_bon == _slug
            if _i < 4:
                _col = _bon_row1[_i]
            elif _i < 8:
                _col = _bon_row2[_i - 4]
            else:
                _col = _bon_row3[0]
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
                            _rk = int(row["Rank"])
                            _medal = "🏆" if _rk == 1 else ("🥈" if _rk == 2 else ("🥉" if _rk == 3 else str(_rk)))
                            trs += (
                                f'<tr{row_style}>'
                                f'<td style="width:28px;text-align:center;">{_medal}</td>'
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

            # Build per-participant upset team lists
            _upset_data = []
            for r in results:
                _picks = r["raw_picks"]
                _upset_teams = []
                for c in range(3, 66):
                    if _picks[c] == actual_winners[c] and not is_unplayed(actual_winners[c]):
                        _w = _picks[c]
                        _ws = seed_map.get(_w, 0)
                        _loser = slot_loser_map.get(c, "")
                        _ls = seed_map.get(_loser, 0)
                        if _ws > 0 and _ls > 0 and (_ws - _ls) >= 3:
                            _upset_teams.append(_w)
                _upset_data.append({
                    "Name": r["Name"],
                    "Upset Picks": len(_upset_teams),
                    "Teams": _upset_teams,
                })

            _upset_data.sort(key=lambda x: x["Upset Picks"], reverse=True)

            # Assign ranks (tied players share the same rank)
            ranked = []
            rank = 1
            for i, row in enumerate(_upset_data):
                if i > 0 and row["Upset Picks"] < _upset_data[i-1]["Upset Picks"]:
                    rank = i + 1
                ranked.append({**row, "Rank": rank})

            trs = ""
            for row in ranked:
                is_user = user_name and row["Name"] == user_name
                row_style = ' style="background:#3a3000; color:#f5c518; font-weight:bold;"' if is_user else ""
                _rk = row["Rank"]
                _medal = "🏆" if _rk == 1 else ("🥈" if _rk == 2 else ("🥉" if _rk == 3 else str(_rk)))
                # Build logo row for each upset team
                _logos_html = ""
                for _team in row["Teams"]:
                    _url = espn_logo_url(_team) or ""
                    _seed = seed_map.get(_team, 0)
                    _tip = f"({_seed}) {_team}"
                    if _url:
                        _logos_html += (
                            f'<img src="{_url}" title="{_tip}" '
                            f'style="width:20px;height:20px;object-fit:contain;vertical-align:middle;margin-right:2px;" '
                            f'onerror="this.style.display=\'none\'">'
                        )
                    else:
                        _logos_html += f'<span style="font-size:10px;margin-right:4px;">{_tip}</span>'
                if not _logos_html:
                    _logos_html = '<span style="color:#6b7280;font-size:11px;">—</span>'
                trs += (
                    f'<tr{row_style}>'
                    f'<td style="width:36px;text-align:center;">{_medal}</td>'
                    f'<td style="padding:4px 8px;">{row["Name"]}</td>'
                    f'<td style="width:64px;text-align:center;">{row["Upset Picks"]}</td>'
                    f'<td style="padding:4px 8px;">{_logos_html}</td>'
                    f'</tr>'
                )
            st.markdown(
                '<div style="overflow-x:auto;">'
                '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
                '<thead><tr style="background:#1e1e2e;color:#fff;">'
                '<th style="width:36px;padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>'
                '<th style="padding:6px 8px;text-align:left;border:1px solid #313244;">Name</th>'
                '<th style="width:64px;padding:6px 4px;text-align:center;border:1px solid #313244;">Upsets</th>'
                '<th style="padding:6px 8px;text-align:left;border:1px solid #313244;">Teams</th>'
                '</tr></thead>'
                f'<tbody style="color:#fff;">{trs}</tbody>'
                '</table></div>',
                unsafe_allow_html=True
            )

        elif _sub_bon == "tiebreaker-scores":
            st.subheader("🎯 Tiebreaker Scores")
            st.caption("In addition to breaking any ties in the Standings, the overall closest to the total Championship points is our Tiebreaker Champion!")

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
                # Build rows — include signed diff only if final score is known
                tb_rows = []
                for name, guess in tiebreaker_guesses.items():
                    if final_score is not None:
                        signed_diff = guess - final_score  # positive = over, negative = under
                        abs_diff = abs(signed_diff)
                    else:
                        signed_diff = None
                        abs_diff = None
                    tb_rows.append({"Name": name, "guess": guess, "signed_diff": signed_diff, "diff": abs_diff})

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
                                          "signed_diff": row["signed_diff"],
                                          "diff": row["diff"]})
                    else:
                        ranked_tb.append({"Rank": "—", "Name": row["Name"],
                                          "Tiebreaker Score": row["guess"],
                                          "signed_diff": None,
                                          "diff": None})

                trs = ""
                for row in ranked_tb:
                    is_user = user_name and row["Name"] == user_name
                    is_first = row["Rank"] == 1 and final_score is not None
                    if is_first and not is_user:
                        row_style = ' style="background:#14532d;color:#4ade80;font-weight:bold;"'
                    elif is_user:
                        row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"'
                    else:
                        row_style = ""
                    # Rank cell: trophy for 1st
                    _rk = row["Rank"]
                    _rank_cell = "🏆" if is_first else (str(_rk) if _rk != "—" else "—")
                    # Name with trophy prefix for 1st
                    _name_display = row["Name"]
                    # Signed diff string
                    if row["signed_diff"] is None:
                        diff_str = "TBD"
                        diff_color = "#9ca3af"
                    elif row["signed_diff"] > 0:
                        diff_str = f'+{row["signed_diff"]}'
                        diff_color = "#f87171"  # over = red
                    elif row["signed_diff"] < 0:
                        diff_str = f'{row["signed_diff"]}'
                        diff_color = "#60a5fa"  # under = blue
                    else:
                        diff_str = "Exact!"
                        diff_color = "#4ade80"  # exact = green
                    trs += (
                        f'<tr{row_style}>'
                        f'<td style="width:40px;text-align:center;">{_rank_cell}</td>'
                        f'<td style="padding:5px 10px;">{_name_display}</td>'
                        f'<td style="width:110px;text-align:center;">{row["Tiebreaker Score"]}</td>'
                        f'<td style="width:90px;text-align:center;color:{diff_color};font-weight:600;">{diff_str}</td>'
                        f'</tr>'
                    )
                st.markdown(f"""
                <table style="border-collapse:collapse;width:100%;max-width:520px;font-size:13px;">
                  <thead>
                    <tr style="background:#1e1e2e;color:#fff;">
                      <th style="width:40px;padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>
                      <th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>
                      <th style="width:110px;padding:6px 4px;text-align:center;border:1px solid #313244;">Tiebreaker Score</th>
                      <th style="width:90px;padding:6px 4px;text-align:center;border:1px solid #313244;">+/−</th>
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
                _rk = int(row["Rank"])
                _medal = "🏆" if _rk == 1 else ("🥈" if _rk == 2 else ("🥉" if _rk == 3 else str(_rk)))
                trs += (
                    f'<tr{row_style}>'
                    f'<td style="width:40px;text-align:center;">{_medal}</td>'
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

        elif _sub_bon == "hoops-she-did-it":
            st.subheader("🏀 Hoops, She Did It Again")
            st.caption(f"Final standings for the women's bracket pool. Tournament Champion: **{WSBB_CHAMP}**")

            _wsbb_df = pd.DataFrame(WSBB_STANDINGS)
            _medal_map = {1: "🏆", 2: "🥈", 3: "🥉"}

            _wsbb_trs = ""
            for _, _wr in _wsbb_df.iterrows():
                _wrank = int(_wr["Rank"])
                _wname = str(_wr["Name"])
                _wpts  = int(_wr["Points"])
                _wcp   = int(_wr["Correct Picks"])
                _medal = _medal_map.get(_wrank, "")
                _is_user = user_name and _wname == user_name
                _row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if _is_user else (
                    ' style="background:#2a1a00;color:#fde68a;"' if _wrank == 1 else ""
                )
                _rank_cell = f"{_medal}" if _medal else str(_wrank)
                _wsbb_trs += (
                    f'<tr{_row_style}>'
                    f'<td style="width:36px;text-align:center;padding:5px 4px;">{_rank_cell}</td>'
                    f'<td style="padding:5px 10px;">{_wname}</td>'
                    f'<td style="width:60px;text-align:center;">{_wpts}</td>'
                    f'<td style="width:54px;text-align:center;">{_wcp}</td>'
                    f'</tr>'
                )

            st.markdown(
                '<div style="overflow-x:auto;">'
                '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
                '<thead><tr style="background:#1e1e2e;color:#fff;">'
                '<th style="width:36px;padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>'
                '<th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>'
                '<th style="width:60px;padding:6px 4px;text-align:center;border:1px solid #313244;">Pts</th>'
                '<th style="width:54px;padding:6px 4px;text-align:center;border:1px solid #313244;">✅</th>'
                '</tr></thead>'
                f'<tbody style="color:#fff;">{_wsbb_trs}</tbody>'
                '</table></div>',
                unsafe_allow_html=True
            )

            # Round breakdown expander
            with st.expander("Round-by-Round Breakdown"):
                _wsbb_round_trs = ""
                for _, _wr in _wsbb_df.iterrows():
                    _wrank = int(_wr["Rank"])
                    _wname = str(_wr["Name"])
                    _is_user = user_name and _wname == user_name
                    _row_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if _is_user else (
                        ' style="background:#2a1a00;color:#fde68a;"' if _wrank == 1 else ""
                    )
                    _wsbb_round_trs += (
                        f'<tr{_row_style}>'
                        f'<td style="padding:4px 8px;">{_wname}</td>'
                        f'<td style="width:46px;text-align:center;">{int(_wr["First Round"])}</td>'
                        f'<td style="width:46px;text-align:center;">{int(_wr["Second Round"])}</td>'
                        f'<td style="width:46px;text-align:center;">{int(_wr["Sweet 16"])}</td>'
                        f'<td style="width:46px;text-align:center;">{int(_wr["Elite 8"])}</td>'
                        f'<td style="width:46px;text-align:center;">{int(_wr["Final Four"])}</td>'
                        f'<td style="width:46px;text-align:center;">{int(_wr["Championship"])}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    '<div style="overflow-x:auto;">'
                    '<table style="border-collapse:collapse;width:100%;font-size:12px;">'
                    '<thead><tr style="background:#1e1e2e;color:#fff;">'
                    '<th style="padding:5px 8px;text-align:left;border:1px solid #313244;">Name</th>'
                    '<th style="width:46px;padding:5px 4px;text-align:center;border:1px solid #313244;">R1</th>'
                    '<th style="width:46px;padding:5px 4px;text-align:center;border:1px solid #313244;">R2</th>'
                    '<th style="width:46px;padding:5px 4px;text-align:center;border:1px solid #313244;">S16</th>'
                    '<th style="width:46px;padding:5px 4px;text-align:center;border:1px solid #313244;">E8</th>'
                    '<th style="width:46px;padding:5px 4px;text-align:center;border:1px solid #313244;">FF</th>'
                    '<th style="width:46px;padding:5px 4px;text-align:center;border:1px solid #313244;">🏆</th>'
                    '</tr></thead>'
                    f'<tbody style="color:#fff;">{_wsbb_round_trs}</tbody>'
                    '</table></div>',
                    unsafe_allow_html=True
                )

        elif _sub_bon == "bonus-pool":
            st.subheader("💰 Bonus Pool")
            st.caption("Separate pool for opted-in participants — Top 2 finish pays out")

            # Filter to bonus pool participants only
            bonus_df = final_df[final_df["Bonus Pool"] == True].copy()
            bonus_df = bonus_df.sort_values("Current Score", ascending=False).reset_index(drop=True)

            if bonus_df.empty:
                st.info("No participants have opted into the Bonus Pool yet.")
            else:
                # Compute bonus-pool-specific probabilities using exact enumeration
                # when few games remain, otherwise Monte Carlo
                _raw_picks_map = {r["Name"]: r["raw_picks"] for r in results}
                bonus_names  = tuple(bonus_df["Name"].tolist())
                bonus_picks  = tuple(
                    tuple(_raw_picks_map[n]) for n in bonus_names if n in _raw_picks_map
                )
                bonus_names = tuple(n for n in bonus_names if n in _raw_picks_map)

                _bp_unplayed = [c for c in range(3, 66) if is_unplayed(actual_winners[c])]
                if len(_bp_unplayed) <= 8:
                    import itertools as _itertools
                    bonus_win_probs  = {n: 0.0 for n in bonus_names}
                    bonus_top3_probs = {n: 0.0 for n in bonus_names}
                    _bp_outcomes = 0
                    for _bits in _itertools.product([0, 1], repeat=len(_bp_unplayed)):
                        _sim_w = list(actual_winners)
                        for _i, _c in enumerate(_bp_unplayed):
                            _par = _BRACKET_PARENTS.get(_c)
                            if _par is None:
                                _teams = list(r1_matchups.get(_c, ("", "")))
                            else:
                                _p1, _p2 = _par
                                _teams = [t for t in [_sim_w[_p1], _sim_w[_p2]] if t and not is_unplayed(t)]
                            if len(_teams) >= 2:
                                _sim_w[_c] = _teams[_bits[_i] % 2]
                            elif len(_teams) == 1:
                                _sim_w[_c] = _teams[0]
                        _bp_scored = []
                        for _ni, _nm in enumerate(bonus_names):
                            _pk = bonus_picks[_ni]
                            _s = sum(
                                points_per_game[_c] + seed_map.get(_pk[_c], 0)
                                for _c in range(3, 66) if _pk[_c] == _sim_w[_c]
                            )
                            _bp_scored.append((_nm, _s))
                        _bp_scored.sort(key=lambda x: x[1], reverse=True)
                        _top_s = _bp_scored[0][1]
                        _bp_winners = [n for n, s in _bp_scored if s == _top_s]
                        for _nm in _bp_winners:
                            bonus_win_probs[_nm] += 1.0 / len(_bp_winners)
                        _top2_s = _bp_scored[min(1, len(_bp_scored)-1)][1]
                        for _nm, _s in _bp_scored[:2]:
                            bonus_top3_probs[_nm] += 1
                        for _nm, _s in _bp_scored[2:]:
                            if _s == _top2_s:
                                bonus_top3_probs[_nm] += 1
                            else:
                                break
                        _bp_outcomes += 1
                    if _bp_outcomes > 0:
                        bonus_win_probs  = {n: v / _bp_outcomes * 100 for n, v in bonus_win_probs.items()}
                        bonus_top3_probs = {n: v / _bp_outcomes * 100 for n, v in bonus_top3_probs.items()}
                else:
                    bonus_win_probs, bonus_top3_probs = run_monte_carlo(
                        bonus_names, bonus_picks,
                        tuple(actual_winners), tuple(points_per_game),
                        tuple(all_alive), tuple(seed_map.items()),
                        r1_contestants,
                        top_n=2,
                    )

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

                # Render as HTML table with Champion column
                _bp_trs = ""
                for _, _brow in bonus_df.iterrows():
                    _is_user = user_name and _brow["Name"] == user_name
                    _brow_style = ' style="background:#3a3000;color:#f5c518;font-weight:bold;"' if _is_user else ""
                    _brk = int(_brow["Bonus Rank"])
                    _medal = "🏆" if _brk == 1 else ("🥈" if _brk == 2 else ("🥉" if _brk == 3 else str(_brk)))
                    # Champion pick
                    _bp_picks = _raw_picks_map.get(_brow["Name"], [])
                    _bp_champ = _bp_picks[65] if len(_bp_picks) > 65 and _bp_picks[65] not in {"", "nan", "TBD"} else ""
                    if _bp_champ:
                        _bp_alive = _bp_champ in truly_alive
                        _bp_style = "color:#22c55e;" if _bp_alive else "color:#ef4444;text-decoration:line-through;"
                        _bp_logo = espn_logo_url(_bp_champ) or ""
                        _bp_img = f'<img src="{_bp_logo}" style="width:16px;height:16px;object-fit:contain;vertical-align:middle;margin-right:3px;" onerror="this.style.display=\'none\'">' if _bp_logo else ""
                        _bp_champ_html = f'{_bp_img}<span style="font-size:11px;{_bp_style}">{_bp_champ}</span>'
                    else:
                        _bp_champ_html = "—"
                    _bp_status = _brow["Potential Status"]
                    _bp_trs += (
                        f'<tr{_brow_style}>'
                        f'<td style="width:36px;text-align:center;">{_medal}</td>'
                        f'<td style="padding:5px 10px;font-weight:600;">{_brow["Name"]}</td>'
                        f'<td style="width:54px;text-align:center;">{int(_brow["Current Score"])}</td>'
                        f'<td style="width:64px;text-align:center;">{int(_brow["Potential Score"])}</td>'
                        f'<td style="padding:5px 8px;">{_bp_champ_html}</td>'
                        f'<td style="width:54px;text-align:center;">{_brow["Win %"]:.1f}%</td>'
                        f'<td style="width:54px;text-align:center;">{_brow["Top 2 %"]:.1f}%</td>'
                        f'<td style="width:80px;text-align:center;">{_bp_status}</td>'
                        f'</tr>'
                    )
                st.markdown(
                    '<div style="overflow-x:auto;">'
                    '<table style="border-collapse:collapse;width:100%;font-size:13px;">'
                    '<thead><tr style="background:#1e1e2e;color:#9ca3af;">'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">#</th>'
                    '<th style="padding:6px 10px;text-align:left;border:1px solid #313244;">Name</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Score</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Potential</th>'
                    '<th style="padding:6px 8px;text-align:left;border:1px solid #313244;">Champion</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Win %</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Top 2 %</th>'
                    '<th style="padding:6px 4px;text-align:center;border:1px solid #313244;">Status</th>'
                    '</tr></thead>'
                    f'<tbody style="color:#fff;">{_bp_trs}</tbody>'
                    '</table></div>',
                    unsafe_allow_html=True
                )


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
                "name": "Tenley McCladdie",
                "image": "https://mrstream.neocities.org/img/BracketCards/2024TenleyMcLaddie.png",
                "champion_pick": "Purdue",
                "tournament_champion": "UConn",
                "alma_mater": "George Washington University",
                "2nd_name": "Ryan Sargent",
                "2nd_pick": "UConn",
                "3rd_name": "Ryan Reyes",
                "3rd_pick": "UConn",
                                "description": "Tenley McCladdie pulled off the ultimate \"worst to first\" story in 2024, rebounding from a dead-last ranking on Day 1 to claim the overall title. Her surge began in the second round, and she officially took control of the leaderboard after Alabama's upset win over UNC in the Sweet 16. By the time Purdue punched their ticket to the Championship game, Tenley had officially secured her place as our 2024 winner!",
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
            {
                "year": 2026,
                "name": "Chris Harmantzis",
                "image": "https://mrstream.neocities.org/img/BracketCards/2026ChrisCard.png",
                "champion_pick": "Michigan",
                "tournament_champion": "Michigan",
                "alma_mater": "Michigan",
                "2nd_name": "Matt Reid",
                "2nd_pick": "Arizona",
                "3rd_name": "Dylan Grassl",
                "3rd_pick": "Michigan",
                "description": "Chris Harmantzis pulled off one of the most dramatic comebacks in pool history, climbing all the way from 63rd place mid-way through the First Round to claim the 2026 title. He spent most of the tournament outside the Top 10 of the standings, but his Michigan pick kept him alive. When the Wolverines defeated UConn 69-63 in the Championship game, Chris rocketed past the field and snatched the crown from Matt Reid and Dylan Grassl at the very last moment. Chris' faith in Michigan helped prove the Championship pick can be the difference-maker, while cementing himself as our first non-festival champion and the 10th champion of Hoops, I Did It Again.",
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
            "Michigan":                      "michigan",
            "Arizona":                       "arizona",
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
                    # Look up this champion's 2026 current rank and score
                    _champ_name = champ["name"]
                    _champ_2026 = next((r for r in results if r["Name"] == _champ_name), None)
                    _champ_first = _champ_name.split()[0]

                    _pill_2026 = ""
                    if _champ_2026:
                        _c26_rank = next(
                            (r["Current Rank"] for r in final_df.to_dict("records") if r["Name"] == _champ_name),
                            None
                        ) if hasattr(final_df, "to_dict") else None
                        # Get rank from final_df
                        _c26_row = final_df[final_df["Name"] == _champ_name]
                        if not _c26_row.empty:
                            _c26_rank  = int(_c26_row.iloc[0]["Current Rank"])
                            _c26_score = int(_c26_row.iloc[0]["Current Score"])
                            _pill_2026 = (
                                _pill_simple("📊", f"{_champ_first}'s 2026 Rank",  f"#{_c26_rank}",  "") +
                                _pill_simple("🏅", f"{_champ_first}'s 2026 Score", str(_c26_score), "")
                            )

                    pills = (
                        f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">' +
                        _pill_simple("👑", "Champion",         _champ,   _ncaa_logo(_champ)) +
                        _pill_simple("🎯", f"{_first_name}'s Pick", _pick, _ncaa_logo(_pick), correct=_correct) +
                        (_pill_named("🥈", "2nd Place", _2nd_name, _2nd_pick, _ncaa_logo(_2nd_pick)) if _2nd_name else "<div></div>") +
                        (_pill_named("🥉", "3rd Place", _3rd_name, _3rd_pick, _ncaa_logo(_3rd_pick)) if _3rd_name else "<div></div>") +
                        _pill_2026 +
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
