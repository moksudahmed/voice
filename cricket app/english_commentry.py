import random
import re
from commentry_dic import COMMENTARY, WINNING_COMMENTARY_TEMPLATES
from utill import number_to_bangla_words

# -----------------------------
# Number → Bangla Words
# -----------------------------
BN_NUMBERS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four",
    5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine",
    10: "ten", 11: "eleven", 12: "twelve", 13: "thirteen",
    14: "fourteen", 15: "fifteen", 16: "sixteen", 17: "seventeen",
    18: "eighteen", 19: "nineteen", 20: "twenty"
}

def num_to_bn(n):
    """Convert small numbers to words, fallback to string"""
    return BN_NUMBERS.get(n, str(n))


# -----------------------------
# EVENT COMMENTARY
# -----------------------------
def generate_event_commentary2(events):
    parts = []

    if "SIX" in events:
        parts.append(random.choice(COMMENTARY["SIX"]))
    elif "FOUR" in events:
        parts.append(random.choice(COMMENTARY["FOUR"]))
    elif "DOUBLE" in events:
        parts.append(random.choice(COMMENTARY["DOUBLE"]))
    elif "SINGLE" in events:
        parts.append(random.choice(COMMENTARY["SINGLE"]))
    elif "DOT" in events:
        parts.append(random.choice(COMMENTARY["DOT"]))

    if "WIDE" in events:
        parts.append(random.choice(COMMENTARY["WIDE"]))

    if "NO_BALL" in events:
        parts.append(random.choice(COMMENTARY["NO_BALL"]))

    return " ".join(parts)


# -----------------------------
# MATCH SITUATION
# -----------------------------
def get_match_situation(current_score, target, wickets_left, balls_left, is_batting_first):

    if not is_batting_first:
        runs_needed = target - current_score
        overs_left = balls_left / 6
        required_rr = runs_needed / overs_left if overs_left > 0 else 0

        if runs_needed <= 0:
            return {"type": "TEAM_WON", "data": {}}
        elif required_rr <= 6:
            return {"type": "CHASING_EASY", "data": {"remaining": runs_needed, "wickets": wickets_left}}
        elif required_rr <= 10:
            return {"type": "CHASING_TENSE", "data": {"required_rr": round(required_rr, 2)}}
        else:
            return {"type": "CHASING_TOUGH", "data": {"required": runs_needed, "balls": balls_left}}

    else:
        runs_to_defend = target - current_score
        return {
            "type": "DEFENDING_TENSE",
            "data": {"runs_to_defend": runs_to_defend, "wickets": wickets_left}
        }


# -----------------------------
# WICKET COMMENTARY
# -----------------------------
def generate_wicket_commentary(runs, wickets, over, batsman=None):

    runs_bn = number_to_bangla_words(runs)
    wickets_bn = number_to_bangla_words(wickets)
    over_bn = str(over)

    name_part = f"{batsman} is walking back. " if batsman else ""

    templates = [
        f"WICKET! {name_part}Big moment in the match. Score is {runs_bn} in {over_bn} overs with {wickets_bn} wickets down.",
        f"Out! {name_part}A crucial breakthrough. The batting side is now under pressure.",
        f"That's out! {name_part}The momentum shifts in this game.",
    ]

    pressure_templates = [
        f"Massive blow! {name_part}This wicket could change the game completely.",
        f"Important wicket! The batting side is now under pressure at {runs_bn} runs.",
    ]

    collapse_templates = [
        f"Wickets are falling quickly! {name_part}The batting side is collapsing.",
        f"Total collapse! The innings is falling apart.",
    ]

    if wickets >= 6:
        return random.choice(collapse_templates)

    if wickets >= 4:
        return random.choice(pressure_templates)

    return random.choice(templates)


# -----------------------------
# WINNING COMMENTARY (SHORT)
# -----------------------------
def generate_winning_commentary2(team, margin, win_type):

    if not team:
        return None

    type_bn = "wickets" if win_type == "wickets" else "runs"

    templates = [
        f"{team} win the match by {margin} {type_bn}! A great performance overall.",
        f"Victory for {team}! They dominate and win by {margin} {type_bn}.",
        f"{team} secure a brilliant win by {margin} {type_bn}!"
    ]

    dominant = [
        f"One-sided match! {team} completely dominated the game.",
        f"Total dominance by {team} in this match!",
    ]

    if margin >= 50:
        return random.choice(dominant)

    return random.choice(templates)


# -----------------------------
# EVENT COMMENTARY CORE
# -----------------------------
def generate_event_commentary(events, context=None):

    parts = []

    scoring = ["SIX", "FOUR", "DOUBLE", "SINGLE", "DOT"]
    extras = ["WIDE", "NO_BALL"]

    for e in scoring:
        if e in events:
            parts.append(random.choice(COMMENTARY[e]))
            break

    for e in extras:
        if e in events:
            parts.append(random.choice(COMMENTARY[e]))

    if context and "match_situation" in context:
        sit = context["match_situation"]
        if sit["type"] in COMMENTARY["MATCH_SITUATION"]:
            parts.append(COMMENTARY["MATCH_SITUATION"][sit["type"]].format(**sit["data"]))

    return " ".join(parts)


# -----------------------------
# TOSS COMMENTARY
# -----------------------------
def generate_toss_commentary(team, decision, is_win=True):

    if is_win:
        key = "TOSS_WIN_BAT" if decision == "bat" else "TOSS_WIN_BOWL"
    else:
        key = "TOSS_LOSS"

    return random.choice(COMMENTARY[key])


# -----------------------------
# BREAK COMMENTARY
# -----------------------------
def generate_break_commentary(status):

    mapping = {
        "Drinks Break": "DRINKS_BREAK",
        "Innings Break": "INNINGS_BREAK",
        "Rain Break": "RAIN_DELAY"
    }

    key = mapping.get(status)

    if not key or key not in COMMENTARY:
        return "Match is currently on break."

    return random.choice(COMMENTARY[key])


# -----------------------------
# PRE-GAME COMMENTARY
# -----------------------------
def pre_game_scenario_commentary(text: str):

    if not text:
        return "No match update available."

    t = text.lower()

    if "delayed" in t:
        return "Match is delayed due to conditions."

    if "toss" in t:
        return "Toss update received."

    return "Match is about to start."


# -----------------------------
# RESULT PARSER
# -----------------------------
def parse_result(text: str):

    clean = text.lower()

    result = {
        "winning_team": None,
        "result_type": "UNKNOWN",
        "runs": None,
        "wickets": None
    }

    win = re.search(r"(.+?) won by", clean)
    if win:
        result["winning_team"] = win.group(1).strip().title()

    r = re.search(r"won by (\d+) run", clean)
    if r:
        result["runs"] = int(r.group(1))
        result["result_type"] = "WON_BY_RUNS"

    w = re.search(r"won by (\d+) wicket", clean)
    if w:
        result["wickets"] = int(w.group(1))
        result["result_type"] = "WON_BY_WICKETS"

    return result


# -----------------------------
# FULL COMMENTARY PIPELINE
# -----------------------------
def generate_full_commentary(raw_text, match_title=None):

    parsed = parse_result(raw_text)

    winning_team = parsed["winning_team"]
    losing_team = None

    if match_title and winning_team:
        teams = re.split(r"vs", match_title, flags=re.IGNORECASE)
        if len(teams) == 2:
            losing_team = teams[0].strip() if winning_team != teams[0] else teams[1].strip()

    players = []

    commentary = f"{winning_team} win the match!"

    return commentary


# -----------------------------
# CURRENT MATCH STATUS
# -----------------------------
def generate_current_match_status(action="", status="", message=""):

    try:

        if action == "WAIT":
            return message or "Match has not started yet."

        elif action == "LIVE":
            return "Live match is in progress."

        elif action == "COMPLETE":
            return f"Match completed: {status}"

        elif action == "STOP":
            return "Match stopped."

        elif action == "PAUSE":
            return "Match paused."

        return message or "Unknown match state."

    except Exception as e:
        return f"Error generating status: {str(e)}"