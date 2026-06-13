import re
from typing import Optional, Dict, List, Tuple
from functools import lru_cache
from dataclasses import dataclass
from enum import Enum
from commentry_dic import COMMENTARY
import re
from typing import Optional, Dict, List, Tuple
from functools import lru_cache
from dataclasses import dataclass
from enum import Enum

# ==================== ENUMS FOR BETTER TYPE SAFETY ====================
class EventPriority(Enum):
    TERMINAL = 1      # Match ending events (highest priority)
    RESULT = 2        # Win/loss results
    WICKET = 3        # Dismissals
    RUN = 4           # Run scoring
    EXTRA = 5         # Extras
    SITUATION = 6     # Toss, breaks, rain
    STATUS = 7        # Live, scheduled (lowest priority)

@dataclass
class EventRule:
    pattern: str
    event_key: str
    priority: EventPriority
    requires_context: bool = False
    negative_patterns: List[str] = None
    exact_match: bool = False  # For single character/digit matches
    
    def __post_init__(self):
        if self.exact_match:
            self.compiled_pattern = re.compile(f'^{self.pattern}$', re.IGNORECASE)
        else:
            self.compiled_pattern = re.compile(self.pattern, re.IGNORECASE)
        self.negative_compiled = [re.compile(p, re.IGNORECASE) for p in (self.negative_patterns or [])]

# ==================== CONSOLIDATED EVENT RULES ====================
EVENT_RULES: List[EventRule] = [
    # TERMINAL EVENTS (Highest Priority)
    EventRule(r'\b(abandoned|called off|cancelled)\b', "MATCH_ABANDONED", EventPriority.TERMINAL),
    EventRule(r'\b(suspended|postponed)\b', "SUSPENDED", EventPriority.TERMINAL),
    
    # WICKET EVENTS (High Priority)
    EventRule(r'bowled|castled|clean bowled', "WICKET_BOWLED", EventPriority.WICKET),
    EventRule(r'caught (?:out|at|by)', "WICKET_CAUGHT", EventPriority.WICKET),
    EventRule(r'run[- ]?out|runout', "WICKET_RUN_OUT", EventPriority.WICKET),
    EventRule(r'stumped', "WICKET_STUMPED", EventPriority.WICKET),
    EventRule(r'lbw', "WICKET_LBW", EventPriority.WICKET),
    EventRule(r'hit[- ]?wicket', "WICKET_HIT_WICKET", EventPriority.WICKET),
    EventRule(r'obstructing the field', "WICKET_OBSTRUCTING", EventPriority.WICKET),
    EventRule(r'retired out', "WICKET_RETIRED_OUT", EventPriority.WICKET),
    EventRule(r'timed out', "WICKET_TIMED_OUT", EventPriority.WICKET),
    EventRule(r'\bwicket\b', "WICKET", EventPriority.WICKET),
    
    # RESULT EVENTS
    EventRule(r'won by \d+ runs?', "COMPLETED_WITH_RESULT", EventPriority.RESULT),
    EventRule(r'won by \d+ wickets?', "COMPLETED_WITH_RESULT", EventPriority.RESULT),
    EventRule(r'beat .+? by \d+ runs?', "COMPLETED_WITH_RESULT", EventPriority.RESULT),
    EventRule(r'match tied', "COMPLETED_WITH_RESULT", EventPriority.RESULT),
    
    # TOSS EVENTS
    EventRule(r'opt\s+to\s+bat|elect(?:ed)?\s+to\s+bat', "TOSS_WON_BAT_FIRST", EventPriority.SITUATION),
    EventRule(r'opt\s+to\s+(?:field|bowl)|elect(?:ed)?\s+to\s+(?:field|bowl)', "TOSS_WON_BOWL_FIRST", EventPriority.SITUATION),
    EventRule(r'won the toss', "TOSS_COMPLETED", EventPriority.SITUATION),
    
    # BOWLER RUNUP (must come before run detection)
    EventRule(r'\b(?:ball|delivery|bowler\s+run[s]?[\s-]?up|run[s]?[\s-]?up)\b', "BOWLER_RUNUP", EventPriority.EXTRA),
    
    # EXTRA EVENTS
    EventRule(r'\bwide\b', "WIDE", EventPriority.EXTRA),
    EventRule(r'no[- ]?ball|noball', "NO_BALL", EventPriority.EXTRA),
    EventRule(r'\bbye\b(?!.*leg)', "BYE", EventPriority.EXTRA),
    EventRule(r'leg[- ]?bye', "LEG_BYE", EventPriority.EXTRA),
    EventRule(r'penalty', "PENALTY", EventPriority.EXTRA),
    EventRule(r'free hit', "FREE_HIT", EventPriority.SITUATION),
    EventRule(r'catch drop|drop(ped)? catch', "DROP_CATCH", EventPriority.EXTRA),
    EventRule(r'overthrow', "OVERTHROW", EventPriority.EXTRA),
    EventRule(r'appeal', "APPEAL", EventPriority.EXTRA),
    EventRule(r'review lost', "REVIEW_LOST", EventPriority.EXTRA),
    EventRule(r'boundary check', "BOUNDARY_CHECK", EventPriority.EXTRA),
    EventRule(r'ball in air', "BALL_IN_AIR", EventPriority.EXTRA),
    
    # RUN EVENTS (including exact single-digit matches)
    EventRule(r'0|dot|no run', "DOT", EventPriority.RUN, exact_match=False),
    EventRule(r'1|one|single', "SINGLE", EventPriority.RUN, exact_match=False),
    EventRule(r'2|two|double', "DOUBLE", EventPriority.RUN, exact_match=False),
    EventRule(r'3|three|triple', "TRIPLE", EventPriority.RUN, exact_match=False),
    EventRule(r'4|four|boundary', "FOUR", EventPriority.RUN, exact_match=False),
    EventRule(r'6|six|maximum', "SIX", EventPriority.RUN, exact_match=False),
    
    # SITUATION EVENTS
    EventRule(r'over\s+(?:complete|end)|end of over', "OVER_COMPLETE", EventPriority.SITUATION),
    EventRule(r'maiden over(?!.*wicket)', "MAIDEN_OVER", EventPriority.SITUATION),
    EventRule(r'wicket maiden over', "WICKET_MAIDEN_OVER", EventPriority.SITUATION),
    EventRule(r'strategic timeout', "STRATEGIC_TIMEOUT", EventPriority.SITUATION),
    EventRule(r'innings break|end of innings', "INNINGS_BREAK", EventPriority.SITUATION),
    EventRule(r'drinks break', "DRINKS_BREAK", EventPriority.SITUATION),
    EventRule(r'rain (?:delay|stoppage|interruption)', "RAIN_DELAY", EventPriority.SITUATION),
    EventRule(r'match stopped due to rain', "MATCH_STOPPED_RAIN", EventPriority.SITUATION),
    
    # STATUS EVENTS (Lowest Priority)
    EventRule(r'\blive\b', "LIVE", EventPriority.STATUS),
    EventRule(r'yet to start|hasn\'?t started', "YET_TO_START", EventPriority.STATUS),
]

# ==================== FAST LOOKUP FOR SINGLE CHARACTERS ====================
FAST_RUN_MAP = {
    '0': "DOT",
    '1': "SINGLE", 
    '2': "DOUBLE",
    '3': "TRIPLE",
    '4': "FOUR",
    '5': "FIVE",  # Rare but possible
    '6': "SIX",
    '7': "SEVEN",  # Very rare
}

FAST_WORD_MAP = {
    'dot': "DOT",
    'single': "SINGLE",
    'double': "DOUBLE", 
    'triple': "TRIPLE",
    'four': "FOUR",
    'six': "SIX",
    'ball': "BOWLER_RUNUP",
    'delivery': "BOWLER_RUNUP",
    'wide': "WIDE",
    'wicket': "WICKET",
}

# ==================== MERGED DETECTION ENGINE ====================
class CricketEventDetector:
    """Unified, efficient event detector with caching and context awareness"""
    
    def __init__(self):
        self._cache: Dict[str, str] = {}
        self._compiled_rules = EVENT_RULES
    
    @lru_cache(maxsize=500)
    def detect(self, text: str, context: Optional[Dict] = None) -> Tuple[str, float]:
        """
        Detect event with confidence score.
        
        Returns:
            Tuple of (event_key, confidence_score)
        """
        if not text or not isinstance(text, str):
            return "UNKNOWN_EVENT", 0.0
        
        text_clean = text.strip().lower()
        if not text_clean:
            return "UNKNOWN_EVENT", 0.0
        
        # Check cache first
        if text_clean in self._cache:
            return self._cache[text_clean], 1.0
        
        # FAST PATH: Single character or simple word lookup
        if len(text_clean) == 1 and text_clean in FAST_RUN_MAP:
            result = FAST_RUN_MAP[text_clean]
            self._cache[text_clean] = result
            return result, 1.0
        
        if text_clean in FAST_WORD_MAP:
            result = FAST_WORD_MAP[text_clean]
            self._cache[text_clean] = result
            return result, 1.0
        
        # Sort rules by priority
        sorted_rules = sorted(self._compiled_rules, key=lambda x: x.priority.value)
        
        best_match = None
        best_confidence = 0.0
        
        for rule in sorted_rules:
            # For exact match patterns, check if text equals pattern
            if rule.exact_match and len(text_clean) == 1:
                if text_clean == rule.pattern.lower():
                    confidence = 1.0
                    best_match = rule.event_key
                    best_confidence = confidence
                    break
                continue
            
            # Check positive pattern
            if not rule.compiled_pattern.search(text_clean):
                continue
            
            # Check negative patterns
            if rule.negative_patterns:
                skip = False
                for neg_pattern in rule.negative_compiled:
                    if neg_pattern.search(text_clean):
                        skip = True
                        break
                if skip:
                    continue
            
            # Calculate confidence
            confidence = self._calculate_confidence(text_clean, rule)
            
            if confidence > best_confidence:
                best_match = rule.event_key
                best_confidence = confidence
                # Early exit for high confidence matches
                if confidence >= 0.95:
                    break
        
        result = best_match if best_match else "UNKNOWN_EVENT"
        self._cache[text_clean] = result
        return result, best_confidence
    
    def _calculate_confidence(self, text: str, rule: EventRule) -> float:
        """Calculate confidence score for a match"""
        confidence = 0.7  # Base confidence
        
        # Exact match boost
        if rule.pattern.lower() == text:
            confidence += 0.25
        
        # Word boundary match boost (more precise)
        if re.search(rf'\b{re.escape(rule.pattern)}\b', text, re.IGNORECASE):
            confidence += 0.15
        
        # Exact single character boost
        if len(text) == 1 and text == rule.pattern:
            confidence += 0.3
        
        # Penalty for very short text (less context)
        if len(text) < 5 and rule.priority in [EventPriority.RUN, EventPriority.EXTRA]:
            confidence -= 0.1
        
        # Boost for exact word matches
        if text in FAST_WORD_MAP and FAST_WORD_MAP[text] == rule.event_key:
            confidence += 0.2
        
        return min(confidence, 1.0)

# ==================== SMART EXTRACTOR ====================
class SmartEventExtractor:
    """Extracts events from unstructured commentary text"""
    
    def __init__(self):
        self.detector = CricketEventDetector()
    
    def extract_events(self, commentary: str) -> List[Dict]:
        """Extract multiple events from a commentary string"""
        if not commentary:
            return []
        
        events = []
        
        # Try to split into sentences for better detection
        sentences = re.split(r'[.!?]\s+', commentary)
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            event_key, confidence = self.detector.detect(sentence)
            
            if event_key != "UNKNOWN_EVENT" and confidence > 0.5:
                events.append({
                    "event": event_key,
                    "confidence": confidence,
                    "text": sentence
                })
        
        # Remove duplicates (keep highest confidence)
        seen = set()
        unique_events = []
        for event in events:
            if event["event"] not in seen:
                seen.add(event["event"])
                unique_events.append(event)
        
        return unique_events
    
    def get_primary_event(self, commentary: str) -> str:
        """Get the most important event from commentary"""
        events = self.extract_events(commentary)
        
        # Priority order for importance
        importance = {
            "WICKET": 10, "WICKET_BOWLED": 10, "WICKET_CAUGHT": 10,
            "WICKET_RUN_OUT": 10, "WICKET_STUMPED": 10, "WICKET_LBW": 10,
            "SIX": 8, "FOUR": 7, 
            "TOSS_COMPLETED": 9, "TOSS_WON_BAT_FIRST": 9, "TOSS_WON_BOWL_FIRST": 9,
            "INNINGS_BREAK": 9, "COMPLETED_WITH_RESULT": 10,
            "MAIDEN_OVER": 6, "OVER_COMPLETE": 5,
            "WIDE": 4, "NO_BALL": 4,
            "SINGLE": 3, "DOUBLE": 3, "TRIPLE": 3,
            "DOT": 2, "BOWLER_RUNUP": 1
        }
        
        if not events:
            return "UNKNOWN_EVENT"
        
        # Sort by importance, then confidence
        events.sort(key=lambda e: (
            importance.get(e["event"], 0),
            e["confidence"]
        ), reverse=True)
        
        return events[0]["event"]

# ==================== UNIFIED DETECTION FUNCTION ====================
def detect_cricket_event(text: str, advanced: bool = True) -> str:
    """Unified event detection - single function for all cases"""
    detector = SmartEventExtractor()
    
    if advanced and len(text.split()) > 5:  # Longer text, likely commentary
        return detector.get_primary_event(text)
    else:
        return detector.detector.detect(text)[0]

def process_event_efficient(res: str) -> str:
    """Efficient single-pass event processing"""
    if not res:
        return "UNKNOWN_EVENT"
    
    result_lower = res.lower().strip()
    
    # Fast path for common short events
    if result_lower in FAST_RUN_MAP:
        return FAST_RUN_MAP[result_lower]
    
    if result_lower in FAST_WORD_MAP:
        return FAST_WORD_MAP[result_lower]
    
    # Use unified detector
    event = detect_cricket_event(res, advanced=False)  # Force simple detection for short strings
    
    # Special cases
    if "catch drop" in result_lower or "dropped catch" in result_lower:
        return "DROP_CATCH"
    
    return event

# ==================== TEST ====================
if __name__ == "__main__":
    detector = SmartEventExtractor()
    
    test_cases = [
        "Maiden over from Bumrah",
        "3",
        "ball",
        "4",  # Should be FOUR
        "wicket",  # Should be WICKET
        "wide",  # Should be WIDE
        "1",  # Should be SINGLE
        "6",  # Should be SIX
        "dot",  # Should be DOT
        "runout",  # Should be WICKET_RUN_OUT
        "No ball",  # Should be NO_BALL
        "Caught at long on",  # Should be WICKET_CAUGHT
        "run out",
        "not out",
        "catch drop",
        "Murshidabad Kings won by 28 runs (DLS METHOD) 🏆",
        "abandoned",
        "suspended",
        "rain stopped"

    ]
    
    for test in test_cases:
        event = process_event_efficient(test)
        print(f"Input: '{test:30}' -> Event: {event}")