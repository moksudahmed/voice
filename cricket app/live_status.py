import re

# ==================== EVENT MAPPING TABLES ====================

# Primary event categories with their keywords (priority ordered)
EVENT_PRIORITY_MAP = [
    # 1. Terminal/End states (highest priority)
    ("MATCH_ABANDONED", ["abandoned"]),
    ("SUSPENDED", ["suspended"]),
    ("DEFERRED", ["deferred"]),
    
    # 2. Injury events (high priority - game interruption)
    ("BATSMAN_INJURED", ["batsman injured", "batter injured", "batsman hurt", "batter hurt", "retired hurt"]),
    ("BOWLER_INJURED", ["bowler injured", "bowler hurt", "bowling injury"]),
    ("FIELDER_INJURED", ["fielder injured", "fielder hurt", "fielding injury", "player injured in the field"]),
    ("PLAYER_INJURED", ["player injured", "injury break", "medical timeout", "physio attending"]),
    
    # 3. Timeouts & Breaks
    ("STRATEGIC_TIMEOUT", ["strategic timeout", "strategy break", "timeout taken"]),
    ("TIME_OUT", ["time out", "time-out", "timeout called"]),
    ("INNINGS_BREAK", ["innings break", "innings interval", "end of innings", "innings ended"]),
    ("DRINKS_BREAK", ["drinks break", "drinks interval"]),
    ("TEA_BREAK", ["tea break"]),
    ("LUNCH_BREAK", ["lunch break"]),
    ("RAIN_BREAK", ["rain break", "rain interruption", "rain stopped play"]),
    ("RAIN_DELAY", ["rain delay", "delayed due to rain", "rain delayed", "wet outfield", "start delayed due to rain"]),
    ("MATCH_STOPPED_RAIN", ["match stopped due to rain", "play stopped due to rain", "match halted due to rain"]),
    
    # 4. Players entering field
    ("PLAYERS_ENTERING", ["players entering", "players are entering", "players walk out", "players make their way", "players coming out", "teams enter the field"]),
    
    # 5. Completed match results
    ("COMPLETED_WITH_RESULT", ["won by", "beat", "match tied", "tie match", "super over", "result:"]),
    
    # 6. Pre-match / Delayed start
    ("YET_TO_START", ["match hasn't started yet", "we'll be live once the toss begins", "toss delayed"]),
    ("MATCH_STOPPED", ["match stopped", "play stopped", "match halted"]),
    
    # 7. Live states
    ("LIVE", ["live"]),
    ("LIVE_COUNTDOWN", [r'\d+m\s+\d+s', r'\d+:\d+']),  # regex patterns
    
    # 8. Scheduled / Unknown
    ("SCHEDULED", ["match info"]),
]

# Result detail extractors (for completed matches)
RESULT_PATTERNS = [
    (r'(won by \d+ runs?)', "Won by runs"),
    (r'(won by \d+ wickets?)', "Won by wickets"),
    (r'(beat .+? by \d+ runs?)', "Beat by runs"),
    (r'(beat .+? by \d+ wickets?)', "Beat by wickets"),
    (r'(match tied)', "Match Tied"),
    (r'(super over)', "Super Over"),
]

# Injury-specific patterns for detailed extraction
INJURY_PATTERNS = [
    (r'batsman (?:injured|hurt|retired hurt)', "Batsman Injured"),
    (r'batter (?:injured|hurt|retired hurt)', "Batsman Injured"),
    (r'retired hurt', "Batsman Injured - Retired Hurt"),
    (r'bowler (?:injured|hurt)', "Bowler Injured"),
    (r'fielder (?:injured|hurt)', "Fielder Injured"),
    (r'(?:player|fielder|bowler) (?:injured|hurt) in the field', "Player Injured"),
    (r'medical timeout', "Medical Timeout - Player Injury"),
    (r'physio (?:attending|on the field)', "Physio Attending - Injury"),
    (r'stretcher (?:called|on the field)', "Serious Injury - Stretcher Called"),
]

# Normalized output mapping
EVENT_OUTPUT_MAP = {
    # Terminal states
    "MATCH_ABANDONED": "Match Abandoned",
    "SUSPENDED": "Suspended",
    "DEFERRED": "Deferred",
    
    # Injury events
    "BATSMAN_INJURED": "Batsman Injured",
    "BOWLER_INJURED": "Bowler Injured",
    "FIELDER_INJURED": "Fielder Injured",
    "PLAYER_INJURED": "Player Injured (Medical Timeout)",
    
    # Timeouts & Breaks
    "STRATEGIC_TIMEOUT": "Strategic Timeout",
    "TIME_OUT": "Time Out",
    "INNINGS_BREAK": "Innings Break",
    "DRINKS_BREAK": "Drinks Break",
    "TEA_BREAK": "Tea Break",
    "LUNCH_BREAK": "Lunch Break",
    "RAIN_BREAK": "Rain Break",
    "RAIN_DELAY": "Rain Delay",
    "MATCH_STOPPED_RAIN": "Match Stopped Due to Rain",
    
    # Players entering
    "PLAYERS_ENTERING": "Players Entering the Field",
    
    # Completion
    "COMPLETED_WITH_RESULT": "Completed",
    
    # Pre-match
    "YET_TO_START": "Yet to Start",
    "MATCH_STOPPED": "Match Stopped",
    
    # Live
    "LIVE": "Live",
    "LIVE_COUNTDOWN": "Live (Countdown active)",
    
    # Scheduled
    "SCHEDULED": "Scheduled (Yet to Start)",
    
    # Fallback
    "UNKNOWN_EVENT": "Unknown Event",
    "WELCOME_NEW_VIEWERS": "Welcome New Viwers"
}

# Break/Timeout/Injury specific mapping (for mapped output)
EVENT_KEY_MAP = {
    # Standard breaks
    "Innings Break": "INNINGS_BREAK",
    "Drinks Break": "DRINKS_BREAK",
    "Tea Break": "TEA_BREAK",
    "Lunch Break": "LUNCH_BREAK",
    "Rain Break": "RAIN_BREAK",
    "Rain Delay": "RAIN_DELAY",
    "Match Stopped Due to Rain": "MATCH_STOPPED_RAIN",
    
    # Timeouts
    "Time Out": "TIME_OUT",
    "Strategic Timeout": "STRATEGIC_TIMEOUT",
    "Timeout": "TIME_OUT",
    
    # Injuries
    "Batsman Injured": "BATSMAN_INJURED",
    "Bowler Injured": "BOWLER_INJURED",
    "Fielder Injured": "FIELDER_INJURED",
    "Player Injured": "PLAYER_INJURED",
    "Retired Hurt": "BATSMAN_INJURED",
    
    # Players entering
    "Players Entering the Field": "PLAYERS_ENTERING",
}

def detect_match_event2(event):

    # normalize input (helps avoid mismatch like "wide " or "WIDE")
    if event is None:
        return "UNKNOWN_EVENT"

    key = str(event).strip()

    # priority order: RUN → EXTRA → BREAK
    return (
        EVENT_KEY_MAP.get(key)        
        or "UNKNOWN_EVENT"
    )
# ==================== EVENT DETECTION FUNCTIONS ====================

def get_rain_event_key(text):
    """
    Determines the rain event key from the given text.
    
    Args:
        text (str): Input text describing rain situation
    
    Returns:
        str: One of "RAIN_BREAK", "RAIN_DELAY", "MATCH_STOPPED_RAIN", or None if no rain event
    """
    
    if not text or not isinstance(text, str):
        return None
    
    text_lower = text.lower().strip()
    
    # Check for inactive/resumed states first (no active rain delay)
    inactive_indicators = ['resumed', 'restarted', 'cleared', 'stopped raining', 'rain stopped', 'play to resume']
    if any(indicator in text_lower for indicator in inactive_indicators):
        return None
    
    # Match stopped due to rain
    match_stopped_patterns = [
        'match stopped due to rain',
        'stopped due to rain',
        'play stopped due to rain',
        'match halted due to rain',
        'match interrupted due to rain'
    ]
    for pattern in match_stopped_patterns:
        if pattern in text_lower:
            return "MATCH_STOPPED_RAIN"
    
    # Start delayed due to rain
    start_delay_patterns = [
        'start delayed due to rain',
        'delayed start due to rain',
        'start delay due to rain',
        'toss delayed due to rain'
    ]
    for pattern in start_delay_patterns:
        if pattern in text_lower:
            return "RAIN_DELAY"
    
    # Rain delay
    rain_delay_patterns = [
        'rain delay',
        'delayed due to rain',
        'rain delayed',
        'wet outfield',
        'weather delay',
        'rain stopping play',
        'rain break (delayed)'
    ]
    for pattern in rain_delay_patterns:
        if pattern in text_lower:
            return "RAIN_DELAY"
    
    # Rain break (shorter interruption)
    rain_break_patterns = [
        'rain break',
        'rain interruption',
        'rain stopped play',
        'covers on'
    ]
    for pattern in rain_break_patterns:
        if pattern in text_lower:
            return "RAIN_BREAK"
    
    # Generic rain detection with delay context
    if 'rain' in text_lower and any(word in text_lower for word in ['delay', 'delayed', 'stop', 'break', 'halted']):
        return "RAIN_DELAY"
    
    return None


def detect_match_event(data):
    """
    Unified function to detect game events and return only the event key.
    
    Parameters:
    - data: Input string to analyze
    
    Returns:
    - str: Event key (e.g., "MATCH_ABANDONED", "RAIN_DELAY", "LIVE", "PLAYERS_ENTERING", etc.)
    """
    
    # Input validation
    if data is None:
        return "UNKNOWN_EVENT"
    
    if not isinstance(data, str):
        data = str(data)
    
    text_lower = data.lower()
    text_original = data
    
    # ========== STEP 1: Priority-based keyword matching ==========
    for event_key, keywords in EVENT_PRIORITY_MAP:
        for keyword in keywords:
            # Handle regex patterns (like countdown timer)
            if isinstance(keyword, str) and (keyword.startswith(r'\\d') or keyword.startswith(r'\d')):
                if re.search(keyword, text_lower):
                    return event_key
            
            # Handle plain text keywords
            elif isinstance(keyword, str) and keyword in text_lower:
                # Special handling for completed matches
                if event_key == "COMPLETED_WITH_RESULT":
                    return "COMPLETED_WITH_RESULT"
                
                # Special handling for injuries - still return the base key
                if event_key in ["BATSMAN_INJURED", "BOWLER_INJURED", "FIELDER_INJURED", "PLAYER_INJURED"]:
                    return event_key
                
                return event_key
    
    # ========== STEP 2: Trophy emoji as completion marker ==========
    # Check for trophy emoji (handle both string and Unicode)
    if "🏆" in data or "trophy" in text_lower:
        if "won" in text_lower or "champion" in text_lower or "beat" in text_lower:
            return "COMPLETED_WITH_RESULT"
    
    # ========== STEP 3: Match info section with winner detection ==========
    if "match info" in text_lower:
        winner = extract_winner_from_match_info(text_lower)
        if winner:
            return "COMPLETED_WITH_RESULT"
        return "SCHEDULED"
    
    # ========== STEP 4: Enhanced rain detection ==========
    rain_event = get_rain_event_key(text_original)
    if rain_event:
        return rain_event
    
    # ========== STEP 5: Players entering detection (fallback) ==========
    players_keywords = ['players entering', 'players are entering', 'players walk out', 'teams enter']
    if any(keyword in text_lower for keyword in players_keywords):
        return "PLAYERS_ENTERING"
    
    # ========== STEP 6: Fallback ==========
    return "UNKNOWN_EVENT"


# ==================== HELPER FUNCTIONS ====================

def extract_result_detail(original_text, lower_text):
    """Extracts specific result details from completed matches."""
    for pattern, _ in RESULT_PATTERNS:
        match = re.search(pattern, original_text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
    return None


def extract_winner_from_match_info(text_lower):
    """Extracts winner from 'Match info' section."""
    match_info_pos = text_lower.find("match info")
    if match_info_pos == -1:
        return None
    
    after_info = text_lower[match_info_pos:match_info_pos + 500]
    winner_match = re.search(r'([\w\s]+?)\s+won', after_info)
    if winner_match:
        return winner_match.group(1).strip()
    return None


def extract_detailed_injury(original_text, lower_text):
    """Extracts detailed injury information."""
    for pattern, injury_detail in INJURY_PATTERNS:
        if re.search(pattern, lower_text):
            return injury_detail
    return None


def get_event_string(event_key):
    """
    Converts event key to human-readable string.
    
    Parameters:
    - event_key: Event key code
    
    Returns:
    - str: Human-readable event description
    """
    return EVENT_OUTPUT_MAP.get(event_key, event_key)


# ==================== USAGE EXAMPLES ====================
"""
if __name__ == "__main__":
    test_inputs = [
        # Basic events
        "Abandoned",
        "Live",
        "Innings Break",
        
        # Injury events
        "Batsman injured",
        "Bowler injured",
        "Fielder injured",
        "Player injured in the field",
        "retired hurt",
        "medical timeout",
        
        # Timeouts
        "Strategic Timeout",
        "Time Out",
        "timeout called",
        
        # Players entering events
        "Players entering the field",
        "Players are entering the field",
        "Players walk out for the match",
        "Teams enter the field",
        
        # Rain delay events
        "Start Delayed Due to rain",
        "Match stopped due to rain",
        "Rain Break",
        "Rain Break (Delayed)",
        "Delayed due to rain",
        "Rain stopped, play to resume soon",
        "wet outfield causing delay",
        "Rain delay - covers on the pitch",
        "rain interruption",
        "stop rain",
        
        # Completion events
        "won by 5 wickets",
        "Pakistan won by 4 wickets 🏆",
        "Worcestershire Women won by 3 runs 🏆",
        "India beat Australia by 6 wickets",
        "Match tied",
        
        # Pre-match
        "match hasn't started yet",
        "toss delayed",
        
        # Match info
        "Match info: India won by 3 wickets",
    ]
    
    print("=== get_event_key() Results (Returns Event Keys Only) ===")
    print("-" * 70)
    for test in test_inputs:
        result = get_event_key(test)
        print(f"Input: {test:50} → {result}")
    
    print("\n=== With Human-Readable Conversion ===")
    print("-" * 70)
    for test in test_inputs[:15]:
        event_key = get_event_key(test)
        #event_string = get_event_string(event_key)
        print(f"Input: {test:35} → {event_key:25}")"""