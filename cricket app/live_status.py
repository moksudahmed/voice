import re

# ==================== EVENT MAPPING TABLES ====================

# Pattern-based detection (more flexible than exact keyword matching)
EVENT_PATTERNS = [
    # Terminal states
    (r'\b(abandoned|called off|cancelled)\b', "MATCH_ABANDONED"),
    (r'\b(suspended|postponed)\b', "SUSPENDED"),
    (r'\b(deferred|delayed start)\b', "DEFERRED"),
    
    # Toss and batting decisions - MORE FLEXIBLE PATTERNS
    (r'opt\s+to\s+bat', "TOSS_WON_BAT_FIRST"),
    (r'opt\s+to\s+field|opt\s+to\s+bowl', "TOSS_WON_BOWL_FIRST"),  # Added 'bowl' as alternative
    (r'elect(?:ed)?\s+to\s+bat', "TOSS_WON_BAT_FIRST"),
    (r'elect(?:ed)?\s+to\s+field|elect(?:ed)?\s+to\s+bowl', "TOSS_WON_BOWL_FIRST"),  # Added 'bowl'
    (r'won the toss and elected to bat', "TOSS_WON_BAT_FIRST"),
    (r'won the toss and elected to field', "TOSS_WON_BOWL_FIRST"),
    (r'won the toss and elected to bowl', "TOSS_WON_BOWL_FIRST"),  # Added
    (r'won the toss', "TOSS_COMPLETED"),
    (r'toss', "TOSS_COMPLETED"),
    
    # Rain related events
    (r'match\s+(?:stopped|halted|paused|interrupted)\s+due\s+to\s+rain', "MATCH_STOPPED_RAIN"),
    (r'play\s+(?:stopped|halted|paused)\s+due\s+to\s+rain', "MATCH_STOPPED_RAIN"),
    (r'rain\s+(?:delay|delayed|stoppage)', "RAIN_DELAY"),
    (r'start\s+delayed\s+due\s+to\s+rain', "RAIN_DELAY"),
    (r'rain\s+break', "RAIN_BREAK"),
    (r'rain\s+interruption', "RAIN_BREAK"),
    (r'wet\s+outfield', "RAIN_DELAY"),
    (r'covers?\s+on', "RAIN_DELAY"),
    
    # Injury events
    (r'batsman\s+(?:injured|hurt|retired\s+hurt)', "BATSMAN_INJURED"),
    (r'batter\s+(?:injured|hurt|retired\s+hurt)', "BATSMAN_INJURED"),
    (r'bowler\s+(?:injured|hurt)', "BOWLER_INJURED"),
    (r'fielder\s+(?:injured|hurt)', "FIELDER_INJURED"),
    (r'player\s+injured', "PLAYER_INJURED"),
    (r'medical\s+timeout', "PLAYER_INJURED"),
    (r'physio\s+attending', "PLAYER_INJURED"),
    
    # Timeouts & Breaks
    (r'strategic\s+timeout', "STRATEGIC_TIMEOUT"),
    (r'time\s*out', "TIME_OUT"),
    (r'innings\s+break', "INNINGS_BREAK"),
    (r'end\s+of\s+innings', "INNINGS_BREAK"),
    (r'drinks\s+break', "DRINKS_BREAK"),
    (r'tea\s+break', "TEA_BREAK"),
    (r'lunch\s+break', "LUNCH_BREAK"),
    
    # Players entering
    (r'players?\s+(?:are\s+)?entering', "PLAYERS_ENTERING"),
    (r'players?\s+walk\s+out', "PLAYERS_ENTERING"),
    (r'teams?\s+enter\s+the\s+field', "PLAYERS_ENTERING"),
    
    # Match results
    (r'won\s+by\s+\d+\s+runs?', "COMPLETED_WITH_RESULT"),
    (r'won\s+by\s+\d+\s+wickets?', "COMPLETED_WITH_RESULT"),
    (r'beat\s+.+?\s+by\s+\d+\s+runs?', "COMPLETED_WITH_RESULT"),
    (r'beat\s+.+?\s+by\s+\d+\s+wickets?', "COMPLETED_WITH_RESULT"),
    (r'match\s+tied', "COMPLETED_WITH_RESULT"),
    (r'super\s+over', "COMPLETED_WITH_RESULT"),
    
    # Pre-match states
    (r'match\s+hasn\'?\s*t\s*started\s+yet', "YET_TO_START"),
    (r'toss\s+delayed', "YET_TO_START"),
    (r'match\s+info', "SCHEDULED"),
    
    # Live states
    (r'\blive\b', "LIVE"),
    (r'\d+m\s+\d+s', "LIVE_COUNTDOWN"),
    (r'\d+:\d+', "LIVE_COUNTDOWN"),
    
    # Generic stopped (non-rain)
    (r'match\s+stopped', "MATCH_STOPPED"),
    (r'play\s+stopped', "MATCH_STOPPED"),
]

# Normalized output mapping
EVENT_OUTPUT_MAP = {
    "MATCH_ABANDONED": "Match Abandoned",
    "SUSPENDED": "Suspended",
    "DEFERRED": "Deferred",
    "TOSS_COMPLETED": "Toss Completed",
    "TOSS_WON_BAT_FIRST": "Toss Won - Bat First",
    "TOSS_WON_BOWL_FIRST": "Toss Won - Bowl First",
    "MATCH_STOPPED_RAIN": "Match Stopped Due to Rain",
    "RAIN_DELAY": "Rain Delay",
    "RAIN_BREAK": "Rain Break",
    "BATSMAN_INJURED": "Batsman Injured",
    "BOWLER_INJURED": "Bowler Injured",
    "FIELDER_INJURED": "Fielder Injured",
    "PLAYER_INJURED": "Player Injured",
    "STRATEGIC_TIMEOUT": "Strategic Timeout",
    "TIME_OUT": "Time Out",
    "INNINGS_BREAK": "Innings Break",
    "DRINKS_BREAK": "Drinks Break",
    "TEA_BREAK": "Tea Break",
    "LUNCH_BREAK": "Lunch Break",
    "PLAYERS_ENTERING": "Players Entering the Field",
    "COMPLETED_WITH_RESULT": "Match Completed",
    "YET_TO_START": "Yet to Start",
    "MATCH_STOPPED": "Match Stopped",
    "LIVE": "Live",
    "TOMORROW": "Tomorrow",
    "TODAY": "Today",
    "LIVE_COUNTDOWN": "Live (Countdown)",
    "SCHEDULED": "Scheduled",
    "UNKNOWN_EVENT": "Unknown Event",
}


def detect_match_event(data):
    """
    Intelligently detect match situation (breaks, stoppages, rain, wins, toss, etc.)
    """
    
    # Input validation
    if data is None:
        return "UNKNOWN_EVENT"
    
    if not isinstance(data, str):
        data = str(data)
    
    # Clean the text
    text = data.strip()
    if not text:
        return "UNKNOWN_EVENT"
    
    text_lower = text.lower()
    
    # ========== SPECIAL HANDLING for "opt to bowl/field" ==========
    # Check for bowl/field patterns even with typos or extra spaces
    if re.search(r'opt\s+to\s+bowl', text_lower) or re.search(r'opt\s+to\s+field', text_lower):
        return "TOSS_WON_BOWL_FIRST"
    
    if re.search(r'opt\s+to\s+bat', text_lower):
        return "TOSS_WON_BAT_FIRST"
    
    # ========== STEP 1: Check for inactive/resumed states ==========
    inactive_patterns = [
        r'resumed', r'restarted', r'play\s+to\s+resume',
        r'rain\s+stopped', r'stopped\s+raining', r'cleared\s+up'
    ]
    for pattern in inactive_patterns:
        if re.search(pattern, text_lower):
            if any(word in text_lower for word in ['match', 'play', 'game']):
                return "LIVE"
            return "UNKNOWN_EVENT"
    
    # ========== STEP 2: Trophy emoji detection ==========
    if "🏆" in text or "trophy" in text_lower:
        if any(word in text_lower for word in ['won', 'champion', 'beat']):
            return "COMPLETED_WITH_RESULT"
    
    # ========== STEP 3: Pattern matching (priority ordered) ==========
    for pattern, event_key in EVENT_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return event_key
    
    # ========== STEP 4: Keyword-based fallback ==========
    # Check for bowl/field decision without "opt" or "elect"
    if 'bowl' in text_lower or 'field' in text_lower:
        if 'to' in text_lower:
            return "TOSS_WON_BOWL_FIRST"
    
    if 'bat' in text_lower and 'to' in text_lower:
        return "TOSS_WON_BAT_FIRST"
    
    # Check for result indicators
    if any(word in text_lower for word in ['won', 'beat', 'defeated', 'champion']):
        return "COMPLETED_WITH_RESULT"
    
    # Check for rain indicators
    if 'rain' in text_lower:
        if any(word in text_lower for word in ['stop', 'halt', 'pause', 'delay']):
            return "MATCH_STOPPED_RAIN"
        return "RAIN_BREAK"
    
    # Check for injury indicators
    if any(word in text_lower for word in ['injured', 'hurt', 'injury', 'medical', 'physio']):
        if 'batsman' in text_lower or 'batter' in text_lower:
            return "BATSMAN_INJURED"
        elif 'bowler' in text_lower:
            return "BOWLER_INJURED"
        elif 'fielder' in text_lower:
            return "FIELDER_INJURED"
        else:
            return "PLAYER_INJURED"
    
    # Check for break indicators
    if any(word in text_lower for word in ['break', 'interval', 'timeout']):
        if 'strategic' in text_lower:
            return "STRATEGIC_TIMEOUT"
        elif 'drinks' in text_lower:
            return "DRINKS_BREAK"
        elif 'tea' in text_lower:
            return "TEA_BREAK"
        elif 'lunch' in text_lower:
            return "LUNCH_BREAK"
        elif 'innings' in text_lower:
            return "INNINGS_BREAK"
        else:
            return "TIME_OUT"
    
    # Check for toss indicators
    if 'toss' in text_lower:
        return "TOSS_COMPLETED"
    
    # Check for stopped indicators
    if any(word in text_lower for word in ['stopped', 'halted', 'paused', 'interrupted']):
        return "MATCH_STOPPED"
    
    # Check for live indicators
    if 'live' in text_lower:
        return "LIVE"
    
    # ========== STEP 5: Fallback ==========
    return "UNKNOWN_EVENT"


def get_event_string(event_key):
    """Convert event key to human-readable string."""
    return EVENT_OUTPUT_MAP.get(event_key, event_key)


# ==================== TEST ====================
"""if __name__ == "__main__":
    test_texts = [
        "Res asa opt to bowl",  # With typo
        "SA-A opt to bat",
        "India opt to field",
        "opt to bowl",
        "opt to bat",
        "Res asa opt to bat",
    ]
    
    print("=" * 60)
    print("TESTING TOSS DETECTION")
    print("=" * 60)
    
    for text in test_texts:
        result = detect_match_event(text)
        print(f"Input: '{text:30}' → {result}")"""