import re
from enum import Enum


# ============================================================
# CRICKET EVENT ENUM
# ============================================================

class CricketEvent(str, Enum):

    # Match Status
    MATCH_SCHEDULED = "MATCH_SCHEDULED"
    MATCH_LIVE = "MATCH_LIVE"
    MATCH_DELAYED = "MATCH_DELAYED"
    MATCH_SUSPENDED = "MATCH_SUSPENDED"
    MATCH_ABANDONED = "MATCH_ABANDONED"
    MATCH_COMPLETED = "MATCH_COMPLETED"
    MATCH_TIED = "MATCH_TIED"

    # Toss
    TOSS_COMPLETED = "TOSS_COMPLETED"
    TOSS_BAT_FIRST = "TOSS_BAT_FIRST"
    TOSS_BOWL_FIRST = "TOSS_BOWL_FIRST"
    TOSS_DELAYED = "TOSS_DELAYED"

    # Innings
    INNINGS_START = "INNINGS_START"
    INNINGS_BREAK = "INNINGS_BREAK"
    INNINGS_COMPLETE = "INNINGS_COMPLETE"

    # Powerplay
    POWERPLAY_START = "POWERPLAY_START"
    POWERPLAY_END = "POWERPLAY_END"

    # Runs
    DOT = "DOT"
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    FOUR = "FOUR"
    FIVE = "FIVE"
    SIX = "SIX"

    # Extras
    WIDE = "WIDE"
    NO_BALL = "NO_BALL"
    BOWLER_RUNUP="BOWLER_RUNUP"
    BYE = "BYE"
    LEG_BYE = "LEG_BYE"
    PENALTY = "PENALTY"
    OVERTHROW = "OVERTHROW"
    FREE_HIT = "FREE_HIT"

    # Wickets
    WICKET = "WICKET"
    WICKET_BOWLED = "WICKET_BOWLED"
    WICKET_CAUGHT = "WICKET_CAUGHT"
    WICKET_RUN_OUT = "WICKET_RUN_OUT"
    WICKET_STUMPED = "WICKET_STUMPED"
    WICKET_LBW = "WICKET_LBW"
    WICKET_HIT_WICKET = "WICKET_HIT_WICKET"
    WICKET_OBSTRUCTING = "WICKET_OBSTRUCTING"
    WICKET_TIMED_OUT = "WICKET_TIMED_OUT"
    WICKET_RETIRED_OUT = "WICKET_RETIRED_OUT"

    # Fielding
    DROP_CATCH = "DROP_CATCH"
    BALL_IN_AIR = "BALL_IN_AIR"
    DIRECT_HIT = "DIRECT_HIT"
    GREAT_STOP = "GREAT_STOP"

    # Review
    DRS_REVIEW = "DRS_REVIEW"
    REVIEW_RETAINED = "REVIEW_RETAINED"
    REVIEW_LOST = "REVIEW_LOST"
    UMPIRES_CALL = "UMPIRES_CALL"
    BOUNDARY_CHECK = "BOUNDARY_CHECK"
    NO_BALL_CHECK = "NO_BALL_CHECK"

    # Over
    OVER_COMPLETE = "OVER_COMPLETE"
    MAIDEN_OVER = "MAIDEN_OVER"
    WICKET_MAIDEN_OVER = "WICKET_MAIDEN_OVER"

    # Breaks
    STRATEGIC_TIMEOUT = "STRATEGIC_TIMEOUT"
    DRINKS_BREAK = "DRINKS_BREAK"
    LUNCH_BREAK = "LUNCH_BREAK"
    TEA_BREAK = "TEA_BREAK"

    # Weather
    RAIN_DELAY = "RAIN_DELAY"
    RAIN_BREAK = "RAIN_BREAK"
    MATCH_STOPPED_RAIN = "MATCH_STOPPED_RAIN"

    # Injury
    PLAYER_INJURED = "PLAYER_INJURED"
    BATTER_INJURED = "BATTER_INJURED"
    BOWLER_INJURED = "BOWLER_INJURED"
    FIELDER_INJURED = "FIELDER_INJURED"

    # Appeal
    APPEAL = "APPEAL"

    # Milestones
    BATTER_50 = "BATTER_50"
    BATTER_100 = "BATTER_100"
    BATTER_150 = "BATTER_150"
    BATTER_200 = "BATTER_200"

    TEAM_50 = "TEAM_50"
    TEAM_100 = "TEAM_100"
    TEAM_150 = "TEAM_150"
    TEAM_200 = "TEAM_200"
    TEAM_250 = "TEAM_250"
    TEAM_300 = "TEAM_300"

    PARTNERSHIP_50 = "PARTNERSHIP_50"
    PARTNERSHIP_100 = "PARTNERSHIP_100"
    PARTNERSHIP_150 = "PARTNERSHIP_150"

    BOWLER_3W = "BOWLER_3W"
    BOWLER_4W = "BOWLER_4W"
    BOWLER_5W = "BOWLER_5W"

    # Result
    SUPER_OVER = "SUPER_OVER"
    WIN_BY_RUNS = "WIN_BY_RUNS"
    WIN_BY_WICKETS = "WIN_BY_WICKETS"

    UNKNOWN = "UNKNOWN_EVENT"


# ============================================================
# EXACT LOOKUP
# ============================================================

EXACT_EVENTS = {

    "0": CricketEvent.DOT.value,
    "1": CricketEvent.SINGLE.value,
    "2": CricketEvent.DOUBLE.value,
    "3": CricketEvent.TRIPLE.value,
    "4": CricketEvent.FOUR.value,
    "5": CricketEvent.FIVE.value,
    "6": CricketEvent.SIX.value,

    "dot": CricketEvent.DOT.value,
    "single": CricketEvent.SINGLE.value,
    "double": CricketEvent.DOUBLE.value,
    "triple": CricketEvent.TRIPLE.value,
    "four": CricketEvent.FOUR.value,
    "six": CricketEvent.SIX.value,
    "ball": CricketEvent.BOWLER_RUNUP.value,

    "wide": CricketEvent.WIDE.value,
    "no ball": CricketEvent.NO_BALL.value,
    "bye": CricketEvent.BYE.value,
    "leg bye": CricketEvent.LEG_BYE.value,
    "free hit": CricketEvent.FREE_HIT.value,

    "wicket": CricketEvent.WICKET.value,
    "bowled": CricketEvent.WICKET_BOWLED.value,
    "caught": CricketEvent.WICKET_CAUGHT.value,
    "run out": CricketEvent.WICKET_RUN_OUT.value,
    "stumped": CricketEvent.WICKET_STUMPED.value,
    "lbw": CricketEvent.WICKET_LBW.value,
}


# ============================================================
# REGEX PATTERNS
# PRIORITY MATTERS
# ============================================================

EVENT_PATTERNS = [

    # Results
    (r'won by \d+ runs', CricketEvent.WIN_BY_RUNS.value),
    (r'won by \d+ wickets', CricketEvent.WIN_BY_WICKETS.value),
    (r'match tied', CricketEvent.MATCH_TIED.value),
    (r'super over', CricketEvent.SUPER_OVER.value),

    # Toss
    (r'toss delayed', CricketEvent.TOSS_DELAYED.value),
    (r'won the toss and elected to bat', CricketEvent.TOSS_BAT_FIRST.value),
    (r'won the toss and elected to field', CricketEvent.TOSS_BOWL_FIRST.value),
    (r'won the toss and elected to bowl', CricketEvent.TOSS_BOWL_FIRST.value),
    (r'won the toss', CricketEvent.TOSS_COMPLETED.value),

    # Weather
    (r'wet outfield', CricketEvent.RAIN_DELAY.value),
    (r'rain delay', CricketEvent.RAIN_DELAY.value),
    (r'rain break', CricketEvent.RAIN_BREAK.value),
    (r'play stopped due to rain', CricketEvent.MATCH_STOPPED_RAIN.value),

    # Breaks
    (r'strategic timeout', CricketEvent.STRATEGIC_TIMEOUT.value),
    (r'drinks break', CricketEvent.DRINKS_BREAK.value),
    (r'lunch break', CricketEvent.LUNCH_BREAK.value),
    (r'tea break', CricketEvent.TEA_BREAK.value),

    # Reviews
    (r'umpire.?s call', CricketEvent.UMPIRES_CALL.value),
    (r'review retained', CricketEvent.REVIEW_RETAINED.value),
    (r'review lost', CricketEvent.REVIEW_LOST.value),
    (r'boundary check', CricketEvent.BOUNDARY_CHECK.value),
    (r'no ball check', CricketEvent.NO_BALL_CHECK.value),
    (r'review', CricketEvent.DRS_REVIEW.value),

    # Wickets
    (r'clean bowled|castled|bowled', CricketEvent.WICKET_BOWLED.value),
    (r'caught and bowled', CricketEvent.WICKET_CAUGHT.value),
    (r'caught', CricketEvent.WICKET_CAUGHT.value),
    (r'run\s*out', CricketEvent.WICKET_RUN_OUT.value),
    (r'stumped', CricketEvent.WICKET_STUMPED.value),
    (r'lbw', CricketEvent.WICKET_LBW.value),
    (r'hit wicket', CricketEvent.WICKET_HIT_WICKET.value),
    (r'obstructing', CricketEvent.WICKET_OBSTRUCTING.value),
    (r'timed out', CricketEvent.WICKET_TIMED_OUT.value),
    (r'retired out', CricketEvent.WICKET_RETIRED_OUT.value),

    # Extras
    (r'wide', CricketEvent.WIDE.value),
    (r'no[- ]?ball', CricketEvent.NO_BALL.value),
    (r'leg[- ]?bye', CricketEvent.LEG_BYE.value),
    (r'\bbye\b', CricketEvent.BYE.value),
    (r'overthrow', CricketEvent.OVERTHROW.value),

    # Fielding
    (r'drop(?:ped)? catch', CricketEvent.DROP_CATCH.value),
    (r'catch drop', CricketEvent.DROP_CATCH.value),
    (r'ball in air', CricketEvent.BALL_IN_AIR.value),
    (r'direct hit', CricketEvent.DIRECT_HIT.value),

    # Runs
    (r'\b0\b|\bdot ball\b|\bno run\b', CricketEvent.DOT.value),
    (r'\b1 run\b|\bsingle\b|\b1\b', CricketEvent.SINGLE.value),
    (r'\b2 runs\b|\bdouble\b|\b2\b', CricketEvent.DOUBLE.value),
    (r'\b3 runs\b|\btriple\b|\b3\b', CricketEvent.TRIPLE.value),
    (r'\b4\b|\bfour\b|\bboundary\b', CricketEvent.FOUR.value),
    (r'\b6\b|\bsix\b|\bmaximum\b', CricketEvent.SIX.value),

    # Over
    (r'over|end of over', CricketEvent.OVER_COMPLETE.value),    
    (r'wicket maiden', CricketEvent.WICKET_MAIDEN_OVER.value),
    (r'maiden over', CricketEvent.MAIDEN_OVER.value),
    

    # Innings
    (r'innings start', CricketEvent.INNINGS_START.value),
    (r'innings break', CricketEvent.INNINGS_BREAK.value),
    (r'end of innings', CricketEvent.INNINGS_COMPLETE.value),

    # Powerplay
    (r'powerplay starts', CricketEvent.POWERPLAY_START.value),
    (r'powerplay ends', CricketEvent.POWERPLAY_END.value),

    # Injury
    (r'batsman injured|batter injured', CricketEvent.BATTER_INJURED.value),
    (r'bowler injured', CricketEvent.BOWLER_INJURED.value),
    (r'fielder injured', CricketEvent.FIELDER_INJURED.value),
    (r'player injured|medical timeout', CricketEvent.PLAYER_INJURED.value),

    # Appeal
    (r'appeal', CricketEvent.APPEAL.value),

    # Match
    (r'abandoned|called off|cancelled', CricketEvent.MATCH_ABANDONED.value),
    (r'suspended|postponed', CricketEvent.MATCH_SUSPENDED.value),
    (r'live', CricketEvent.MATCH_LIVE.value),
]


# ============================================================
# MILESTONE DETECTION
# ============================================================

def detect_milestone(text):

    if re.search(r'200|double century', text):
        return CricketEvent.BATTER_200.value

    if re.search(r'150', text):
        return CricketEvent.BATTER_150.value

    if re.search(r'century|100', text):
        return CricketEvent.BATTER_100.value

    if re.search(r'fifty|50', text):
        return CricketEvent.BATTER_50.value

    if re.search(r'100 partnership', text):
        return CricketEvent.PARTNERSHIP_100.value

    if re.search(r'50 partnership', text):
        return CricketEvent.PARTNERSHIP_50.value

    if re.search(r'150 partnership', text):
        return CricketEvent.PARTNERSHIP_150.value

    return None


# ============================================================
# MAIN DETECTOR
# ============================================================

def detect_cricket_event(text):

    if not text:
        return CricketEvent.UNKNOWN.value

    text = str(text).lower().strip()

    if text in EXACT_EVENTS:
        return EXACT_EVENTS[text]

    milestone = detect_milestone(text)

    if milestone:
        return milestone

    for pattern, event in EVENT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return event

    return CricketEvent.UNKNOWN.value


# ============================================================
# EXCITEMENT ENGINE
# ============================================================

EXCITEMENT_LEVEL = {

    "DOT": 1,
    "SINGLE": 1,
    "DOUBLE": 2,
    "TRIPLE": 3,
    "FOUR": 5,
    "SIX": 6,

    "DROP_CATCH": 7,

    "WICKET": 8,
    "WICKET_BOWLED": 9,
    "WICKET_CAUGHT": 9,
    "WICKET_RUN_OUT": 10,

    "BATTER_100": 10,
    "BATTER_200": 10,

    "SUPER_OVER": 10,
    "WIN_BY_RUNS": 10,
    "WIN_BY_WICKETS": 10,
}


# ============================================================
# TESTS
# ============================================================
"""
if __name__ == "__main__":

    tests = [

        "Four",
        "SIX",
        "Wide",
        "No Ball",
        "Caught",
        "Bowled",
        "Run Out",
        "LBW",
        "Review Lost",
        "Strategic Timeout",
        "Rain Delay",
        "Won the toss and elected to bat",
        "Powerplay starts",
        "Batter reaches century",
        "Won by 5 wickets",
        "Super Over",
    ]

    for t in tests:
        print(f"{t} -> {detect_cricket_event(t)}")"""