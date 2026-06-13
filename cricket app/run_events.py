import re
from live_status import detect_match_event, get_event_string
# ==================== EVENT MAPPING TABLES ====================

EVENT_MAP = [
    "DOT",
    "SINGLE",
    "DOUBLE",
    "TRIPLE",
    "FOUR",
    "SIX",
    "BOWLER_RUNUP",
    "WIDE",    
    "NO_BALL",
    "BYE",
    "LEG_BYE",
    "PENALTY",
    "WICKET",
    "WICKET_BOWLED",
    "WICKET_CAUGHT",
    "WICKET_RUN_OUT",
    "WICKET_STUMPED",
    "WICKET_LBW",
    "WICKET_HIT_WICKET",
    "WICKET_OBSTRUCTING",
    "WICKET_RETIRED_OUT",
    "WICKET_TIMED_OUT",
    "OVER_COMPLETE",    
    "MAIDEN_OVER",
    "WICKET_MAIDEN_OVER",
    "DROP_CATCH",
    "APPEAL",
    "REVIEW_LOST",
    "BOUNDARY_CHECK",
    "BALL_IN_AIR",
    "FREE_HIT",
    "REVIEW_RETAINDE",
    "OVERTHROW"
]

RUN_EVENT_MAP = {
    "0": "DOT",
    "1": "SINGLE",
    "2": "DOUBLE",
    "3": "TRIPLE",
    "4": "FOUR",
    "6": "SIX",
    "dot": "DOT",
    "single": "SINGLE",
    "double": "DOUBLE",
    "triple": "TRIPLE",
    "four": "FOUR",
    "six": "SIX",
}

EXTRA_EVENT_MAP = {
    "ball":"BOWLER_RUNUP",
    "wide": "WIDE",
    "no ball": "NO_BALL",
    "noball": "NO_BALL",
    "bye": "BYE",
    "leg bye": "LEG_BYE",
    "legbye": "LEG_BYE",
    "penalty": "PENALTY",
    "catch drop":"DROP_CATCH",
    "ball in air": "BALL_IN_AIR",
    "overthrow" :"OVERTHROW",
    "strategic timeout": "STRATEGIC_TIMEOUT",
    "time out": "TIME_OUT",
    "no ball check":"No_Ball_Check",
    "Wide Ball Check":"Wide Ball Check",
}

WICKET_EVENT_MAP = {
    "wicket": "WICKET",
    "bowled": "WICKET_BOWLED",
    "caught": "WICKET_CAUGHT",
    "caught out": "WICKET_CAUGHT",
    "run out": "WICKET_RUN_OUT",
    "runout": "WICKET_RUN_OUT",
    "stumped": "WICKET_STUMPED",
    "lbw": "WICKET_LBW",
    "hit wicket": "WICKET_HIT_WICKET",
    "obstructing": "WICKET_OBSTRUCTING",    
}

MATCH_EVENT_MAP = {
    "over": "OVER_COMPLETE",
    "maiden over": "MAIDEN_OVER",
    "wicket maiden over": "WICKET_MAIDEN_OVER",
    "end of over": "OVER_COMPLETE",
    "free hit": "FREE_HIT",
    "retired out": "WICKET_RETIRED_OUT",
    "appeal":"APPEAL",
    "review lost":"REVIEW_LOST",
    "boundary check":"BOUNDARY_CHECK",
    "review retained ":"REVIEW_RETAINDE"
}

# Pattern-based detection (for complex strings)
PATTERN_MAP = [
    # Wicket patterns
    (r'(?:bowled|castled|clean bowled)', "WICKET_BOWLED"),
    (r'caught (?:out|at|by)', "WICKET_CAUGHT"),
    (r'run[- ]?out', "WICKET_RUN_OUT"),
    (r'stumped', "WICKET_STUMPED"),
    (r'lbw', "WICKET_LBW"),
    (r'hit[- ]?wicket', "WICKET_HIT_WICKET"),
    
    # Run patterns
    (r'\b(?:dot|no run)\b', "DOT"),
    (r'\b1\b|\bone\b|single', "SINGLE"),
    (r'\b2\b|\btwo\b|double', "DOUBLE"),
    (r'\b3\b|\bthree\b|triple', "TRIPLE"),
    (r'\b4\b|\bfour\b|boundary', "FOUR"),
    (r'\b6\b|\bsix\b|maximum', "SIX"),
    
    # Extra patterns
    (r'wide', "WIDE"),
    (r'no[- ]?ball', "NO_BALL"),
    (r'bye(?!.*leg)', "BYE"),
    (r'leg[- ]?bye', "LEG_BYE"),
    
    # Match event patterns
    (r'over(?:\s+\d+)?(?:\s+complete)?', "OVER_COMPLETE"),
    (r'innings[- ]?break', "INNINGS_BREAK"),
    (r'strategic[- ]?timeout', "STRATEGIC_TIMEOUT"),
    (r'drinks[- ]?break', "DRINKS_BREAK"),
    (r'rain[- ]?(?:break|delay)', "RAIN_DELAY"),
]


# ==================== INTELLIGENT EVENT DETECTION ====================

def detect_event(event):

    # normalize input (helps avoid mismatch like "wide " or "WIDE")
    if event is None:
        return "UNKNOWN_EVENT"

    key = str(event).strip()

    # priority order: RUN → EXTRA → BREAK
    return (
        RUN_EVENT_MAP.get(key)
        or EXTRA_EVENT_MAP.get(key)
        or MATCH_EVENT_MAP.get(key)
        or WICKET_EVENT_MAP.get(key)
        or "UNKNOWN_EVENT"
    )

def detect_event2(event):
    """
    Intelligently detects cricket events from various input formats.
    
    Args:
        event: Input string, number, or None
    
    Returns:
        str: Detected event key (e.g., "SINGLE", "WICKET_CAUGHT", "WIDE", etc.)
    """
    
    # Handle None or empty input
    if event is None:
        return "UNKNOWN_EVENT"
    
    # Convert to string and clean
    event_str = str(event).strip()
    if not event_str:
        return "UNKNOWN_EVENT"
    
    # Normalize: lowercase, remove extra spaces
    event_lower = event_str.lower()
    event_normalized = re.sub(r'\s+', ' ', event_lower).strip()
    
    # ========== STEP 1: Direct lookup in RUN_EVENT_MAP ==========
    if event_normalized in RUN_EVENT_MAP:
        return RUN_EVENT_MAP[event_normalized]
    
    # Check numeric values (e.g., "0", "1", "2", etc.)
    if event_normalized.isdigit():
        return RUN_EVENT_MAP.get(event_normalized, "UNKNOWN_EVENT")
    
    # ========== STEP 2: Direct lookup in EXTRA_EVENT_MAP ==========
    for key, value in EXTRA_EVENT_MAP.items():
        if key in event_normalized:
            return value
    
    # ========== STEP 3: Wicket detection (priority) ==========
    # Check if it's a wicket event
    is_wicket = False
    for key, value in WICKET_EVENT_MAP.items():
        if key in event_normalized:
            is_wicket = True
            if event_normalized == key or event_normalized.startswith(key):
                return value
            # For caught-type events, check for specific type
            if 'caught' in event_normalized:
                return "WICKET_CAUGHT"
            if 'bowled' in event_normalized:
                return "WICKET_BOWLED"
            if 'run out' in event_normalized or 'runout' in event_normalized:
                return "WICKET_RUN_OUT"
            # Default wicket
            return "WICKET"
    
    # ========== STEP 4: Pattern matching ==========
    for pattern, event_key in PATTERN_MAP:
        if re.search(pattern, event_normalized):
            return event_key
    
    # ========== STEP 5: Match event lookup ==========
    for key, value in MATCH_EVENT_MAP.items():
        if key in event_normalized:
            return value
    
    # ========== STEP 6: Context-based detection ==========
    # Check for wicket based on common phrases
    wicket_indicators = ['wicket', 'out', 'dismissed', 'caught', 'bowled', 'stumped', 'lbw']
    if any(indicator in event_normalized for indicator in wicket_indicators):
        return "WICKET"
    
    # Check for run scoring
    if any(word in event_normalized for word in ['run', 'runs', 'score']):
        # Try to extract number
        numbers = re.findall(r'\b(\d+)\b', event_normalized)
        if numbers:
            num = numbers[0]
            if num in RUN_EVENT_MAP:
                return RUN_EVENT_MAP[num]
    
    # ========== STEP 7: Fallback ==========
    return "UNKNOWN_EVENT"


# ==================== ADVANCED DETECTION WITH CONTEXT ====================
def detect_event_advanced(event_text, context=None):
    """
    Advanced event detection that returns only the event type.
    
    Args:
        event_text: The event description
        context: Optional context (not used, kept for compatibility)
    
    Returns:
        str: Detected event type
    """
    
    if not event_text:
        return "UNKNOWN_EVENT"
    
    # Try basic detection first
    event_type = detect_event(event_text)
    
    if event_type == "UNKNOWN_EVENT":
        event_lower = str(event_text).lower()
        
        # Check for runs (0-6)
        """run_match = re.search(r'\b([0-6])\b', event_lower)
        if run_match:
            runs = int(run_match.group(1))
            run_map = {0: "DOT", 1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "FOUR", 6: "SIX"}
            return run_map.get(runs, "UNKNOWN_EVENT")"""
        
        # Check for wickets
        extra_words =['win','won', 'by','beat']
        if not any(keyword in event_lower for keyword in extra_words):
            if any(word in event_lower for word in ['wicket', 'out', 'dismissed', 'caught', 'bowled', 'stumped', 'lbw']):
                if 'caught' in event_lower:
                    return "WICKET_CAUGHT"
                elif 'bowled' in event_lower:
                    return "WICKET_BOWLED"
                elif 'run out' in event_lower or 'runout' in event_lower:
                    return "WICKET_RUN_OUT"
                elif 'stumped' in event_lower:
                    return "WICKET_STUMPED"
                elif 'lbw' in event_lower:
                    return "WICKET_LBW"
                else:
                    return "WICKET"
        
        # Check for extras
        extra_map = {
            'wide': 'WIDE',
            'no ball': 'NO_BALL',
            'bye': 'BYE',
            'leg bye': 'LEG_BYE',
            'Overthrow':'OVERTHROW'
        }
        for keyword, extra_type in extra_map.items():
            if keyword in event_lower:
                return extra_type
    
    return event_type
    
def detect_event_advanced2(event_text, context=None):
    """
    Advanced event detection with contextual information.
    
    Args:
        event_text: The event description
        context: Optional context dict with keys like 'ball_number', 'over_number', 'batsman', 'bowler'
    
    Returns:
        dict: Detailed event information
    """
    
    result = {
        'event_type': detect_event(event_text),
        'runs': None,
        'is_wicket': False,
        'is_extra': False,
        'confidence': 0.0,
        'details': {}
    }
    
    if not event_text:
        return result
    
    event_lower = str(event_text).lower()
    
    # Detect runs
    run_patterns = [
        (r'(?:scored|takes|taken)?\s*(\d+)\s*(?:run|runs)', 'runs'),
        (r'\b([0-6])\s*(?:runs?)?\s*(?:off|from)', 'runs'),
        (r'(\d+)\s*(?:runs?)?\s*$', 'runs'),
    ]
    
    for pattern, _ in run_patterns:
        match = re.search(pattern, event_lower)
        if match:
            runs = int(match.group(1))
            result['runs'] = runs
            if runs in [0, 1, 2, 3, 4, 6]:
                result['details']['runs_scored'] = runs
            break
    
    # Detect wicket
    wicket_keywords = ['wicket', 'out', 'dismissed', 'caught', 'bowled', 'stumped', 'lbw', 'run out']
    if any(keyword in event_lower for keyword in wicket_keywords):
        result['is_wicket'] = True
        result['confidence'] += 0.4
        
        # Determine wicket type
        if 'caught' in event_lower:
            result['details']['wicket_type'] = 'caught'
            result['confidence'] += 0.3
        elif 'bowled' in event_lower:
            result['details']['wicket_type'] = 'bowled'
            result['confidence'] += 0.3
        elif 'run out' in event_lower:
            result['details']['wicket_type'] = 'run_out'
            result['confidence'] += 0.3
        elif 'stumped' in event_lower:
            result['details']['wicket_type'] = 'stumped'
            result['confidence'] += 0.3
        elif 'lbw' in event_lower:
            result['details']['wicket_type'] = 'lbw'
            result['confidence'] += 0.3
    
    # Detect extras
    extra_keywords = ['wide', 'no ball', 'bye', 'leg bye']
    for extra in extra_keywords:
        if extra in event_lower:
            result['is_extra'] = True
            result['details']['extra_type'] = extra.replace(' ', '_').upper()
            result['confidence'] += 0.4
            break
    
    # Set confidence default if not set
    if result['confidence'] == 0.0 and result['event_type'] != "UNKNOWN_EVENT":
        result['confidence'] = 0.7
    
    return result


# ==================== BALL-BY-BALL EVENT PARSER ====================

def parse_ball_event(commentary):
    """
    Parses ball-by-ball commentary to extract events.
    
    Args:
        commentary: String containing ball commentary
    
    Returns:
        dict: Parsed events for the ball
    """
    
    if not commentary:
        return {}
    
    commentary_lower = commentary.lower()
    result = {
        'raw_commentary': commentary,
        'events': [],
        'runs': 0,
        'wicket': False,
        'extras': None
    }
    
    # Extract runs
    run_match = re.search(r'(\d+)\s*(?:run|runs)?', commentary_lower)
    if run_match:
        runs = int(run_match.group(1))
        if runs <= 6:
            result['runs'] = runs
            result['events'].append(RUN_EVENT_MAP.get(str(runs), "RUNS"))
    
    # Check for wicket
    if any(word in commentary_lower for word in ['wicket', 'out', 'dismissed', 'caught', 'bowled']):
        result['wicket'] = True
        result['events'].append("WICKET")
        
        # Specific wicket type
        if 'caught' in commentary_lower:
            result['events'].append("CAUGHT")
        elif 'bowled' in commentary_lower:
            result['events'].append("BOWLED")
        elif 'run out' in commentary_lower:
            result['events'].append("RUN_OUT")
    
    # Check for extras
    for extra in ['wide', 'no ball', 'bye', 'leg bye']:
        if extra in commentary_lower:
            result['extras'] = extra.upper().replace(' ', '_')
            result['events'].append(result['extras'])
            if extra in ['wide', 'no ball']:
                result['runs'] += 1
    
    return result


# ==================== USAGE EXAMPLES ====================
def process_event(res):    
    event_key=""
    result = res.lower()
    event = detect_event(result)
    print("Res", result)       
    if event == "UNKNOWN_EVENT":
        event = detect_event_advanced(result)        
        print("Adv", event)
        if event == "UNKNOWN_EVENT":
           event_key = detect_match_event(result)  
           print("Match Adv", event)                 
           return event_key
        return event    
    else:
        return event

  
if __name__ == "__main__":
   
    print(process_event("ball"))
