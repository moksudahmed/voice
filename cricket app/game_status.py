import time
import sys
import re
from commentry import generate_break_commentary

def parse_match_result(text: str):
    pattern = r"(.+?)\s+won\s+by\s+(\d+)\s+(runs|wickets)"
    match = re.search(pattern, text, re.IGNORECASE)

    if not match:
        return None

    return {
        "winner": match.group(1).strip(),
        "margin": int(match.group(2)),
        "type": match.group(3).lower()
    }

def detect_game_status(data):
    """
    Detect cricket match status with proper priority handling.
    """

    text = " ".join(str(item) for item in data if item)
    text_lower = text.lower()

    # =========================================================
    # 1. MATCH ABANDONED
    # =========================================================
    if re.search(r"match\s+abandoned", text_lower):
        return "ABANDONED"

    # =========================================================
    # 2. SUSPENDED / DEFERRED
    # =========================================================
    if re.search(r"\bsuspended\b", text_lower):
        return "SUSPENDED"

    if re.search(r"\bdeferred\b", text_lower):
        return "DEFERRED"

    # =========================================================
    # 3. COMPLETED MATCH
    # =========================================================
    win_patterns = [
        r'won by \d+ runs?',
        r'won by \d+ wickets?',
        r'beat .+ by \d+ runs?',
        r'beat .+ by \d+ wickets?',
        r'match tied',
        r'tie match',
        r'super over',
        r'result:.*won'
    ]

    for pattern in win_patterns:
        if re.search(pattern, text_lower):

            win_match = re.search(
                r'([A-Za-z0-9 .&_-]+(?:won by \d+ runs?|won by \d+ wickets?|beat [A-Za-z0-9 .&_-]+ by \d+ runs?|beat [A-Za-z0-9 .&_-]+ by \d+ wickets?))',
                text,
                re.IGNORECASE
            )

            if win_match:
                return f"Completed - {win_match.group(1).strip()}"

            return "COMPLETED_WITH_RESULT"

    if "🏆" in text and ("won" in text_lower or "champion" in text_lower):
        return "COMPLETED_WITH_RESULT"

    # =========================================================
    # 4. WEATHER / DELAY STATUS
    # =========================================================

    # Toss delayed
    if re.search(r'toss\s+delayed', text_lower):

        if re.search(r'wet\s+outfield', text_lower):
            return "TOSS_DELAYED_WET_OUTFIELD"

        if re.search(r'rain', text_lower):
            return "RAIN_DELAY"

        return "TOSS_DELAYED"

    # Start delayed
    if re.search(r'start\s+delayed', text_lower):

        if re.search(r'rain', text_lower):
            return "RAIN_DELAY"

        return "START_DELAYED"

    # Match dealyed
    if re.search(r'match\s+delayed', text_lower):

        if re.search(r'rain', text_lower):
            return "RAIN_DELAY"

        return "START_DELAYED"

    # Match stopped
    if re.search(r'match\s+stopped.*rain', text_lower):
        return "MATCH_STOPPED_RAIN"

    # Rain break
    if re.search(r'rain\s+break', text_lower):
        return "RAIN_BREAK"

    # Rain delay
    if re.search(r'rain\s+delay', text_lower):
        return "RAIN_DELAY"

    # Wet outfield
    if re.search(r'wet\s+outfield', text_lower):
        return "RAIN_DELAY"

    # =========================================================
    # 5. BREAKS
    # =========================================================
    if re.search(r'drinks\s+break', text_lower):
        return "DRINKS_BREAK"

    if re.search(r'innings\s+(break|interval)', text_lower):
        return "INNINGS_BREAK"

    if re.search(r'tea\s+break', text_lower):
        return "TEA_BREAK"

    if re.search(r'lunch\s+break', text_lower):
        return "LUNCH_BREAK"

    # =========================================================
    # 6. YET TO START
    # =========================================================
    yet_to_start_patterns = [
        r"match hasn't started yet",
        r"match has not started yet",
        r"we'?ll be live once the toss begins",
        r"awaiting toss",
        r"toss yet to take place",
        r"yet to start"
    ]

    for pattern in yet_to_start_patterns:
        if re.search(pattern, text_lower):
            return "YET_TO_START"

    # =========================================================
    # 7. LIVE MATCH
    # =========================================================
    if (
        "live" in text_lower
        and "match abandoned" not in text_lower
        and "yet to start" not in text_lower
    ):
        return "LIVE"

    # =========================================================
    # 8. TOMORROW
    # =========================================================
    if any(str(item).strip().lower() == "tomorrow" for item in data):
        return "TOMORROW"

    # =========================================================
    # 9. TODAY
    # =========================================================
    for i, item in enumerate(data):

        if str(item).strip().lower() == "today":

            if i + 1 < len(data):
                time_val = str(data[i + 1])

                if re.search(r'\d{1,2}:\d{2}', time_val):
                    return f"Today at {time_val}"

            return "Today"

    # =========================================================
    # 10. SCHEDULED MATCH
    # =========================================================
    weekdays = {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }

    for i, item in enumerate(data):

        item_str = str(item)

        if re.search(r'\d{1,2}:\d{2}\s*(am|pm)?', item_str, re.I):

            if i > 0:

                prev = str(data[i - 1]).lower()

                if prev in weekdays:
                    return f"{data[i - 1]} at {item_str}"

            return f"Scheduled at {item_str}"

    # =========================================================
    # 11. LEGACY WIN DETECTION
    # =========================================================
    if "match info" in text_lower:

        for item in data:

            if isinstance(item, str) and "won" in item.lower():

                if "head to head" not in text_lower:
                    winner = item.replace("Won", "").replace("won", "").strip()

                    if winner:
                        return f"Completed - {winner} Won"

    # =========================================================
    # 12. COUNTDOWN TIMER
    # =========================================================
    for item in data:

        if not isinstance(item, str):
            continue

        if re.search(r'\d+m.*\d+s', item.lower()):
            return "LIVE_COUNTDOWN"

    # =========================================================
    # 13. FALLBACK
    # =========================================================
    if "match info" in text_lower:
        return "YET_TO_START" #"Scheduled (Yet to Start)"

    return "UNKNOWN_EVENT"

def detect_game_status_old(data):
    """
    Detect cricket match status with proper priority handling.
    """

    text = " ".join(str(item) for item in data if item)
    text_lower = text.lower()

    # =========================================================
    # 1. MATCH ABANDONED
    # =========================================================
    if re.search(r"match\s+abandoned", text_lower):
        return "Match Abandoned"

    # =========================================================
    # 2. SUSPENDED / DEFERRED
    # =========================================================
    if re.search(r"\bsuspended\b", text_lower):
        return "Suspended"

    if re.search(r"\bdeferred\b", text_lower):
        return "Deferred"

    # =========================================================
    # 3. COMPLETED MATCH
    # =========================================================
    win_patterns = [
        r'won by \d+ runs?',
        r'won by \d+ wickets?',
        r'beat .+ by \d+ runs?',
        r'beat .+ by \d+ wickets?',
        r'match tied',
        r'tie match',
        r'super over',
        r'result:.*won'
    ]

    for pattern in win_patterns:
        if re.search(pattern, text_lower):

            win_match = re.search(
                r'([A-Za-z0-9 .&_-]+(?:won by \d+ runs?|won by \d+ wickets?|beat [A-Za-z0-9 .&_-]+ by \d+ runs?|beat [A-Za-z0-9 .&_-]+ by \d+ wickets?))',
                text,
                re.IGNORECASE
            )

            if win_match:
                return f"Completed - {win_match.group(1).strip()}"

            return "Completed - Match Finished"

    if "🏆" in text and ("won" in text_lower or "champion" in text_lower):
        return "Completed - Match Finished"

    # =========================================================
    # 4. WEATHER / DELAY STATUS
    # =========================================================

    # Toss delayed
    if re.search(r'toss\s+delayed', text_lower):

        if re.search(r'wet\s+outfield', text_lower):
            return "Toss Delayed (Wet Outfield)"

        if re.search(r'rain', text_lower):
            return "Toss Delayed (Rain)"

        return "Toss Delayed"

    # Start delayed
    if re.search(r'start\s+delayed', text_lower):

        if re.search(r'rain', text_lower):
            return "Start Delayed (Rain)"

        return "Start Delayed"

    # Match delayed
    if re.search(r'match\s+delayed', text_lower):

        if re.search(r'rain', text_lower):
            return "Match Delayed (Rain)"

        return "Match Delayed"

    # Match stopped
    if re.search(r'match\s+stopped.*rain', text_lower):
        return "Match Stopped (Rain)"

    # Rain break
    if re.search(r'rain\s+break', text_lower):
        return "Rain Break"

    # Rain delay
    if re.search(r'rain\s+delay', text_lower):
        return "Rain Delay"

    # Wet outfield
    if re.search(r'wet\s+outfield', text_lower):
        return "Delayed (Wet Outfield)"

    # =========================================================
    # 5. BREAKS
    # =========================================================
    if re.search(r'drinks\s+break', text_lower):
        return "Drinks Break"

    if re.search(r'innings\s+(break|interval)', text_lower):
        return "Innings Break"

    if re.search(r'tea\s+break', text_lower):
        return "Tea Break"

    if re.search(r'lunch\s+break', text_lower):
        return "Lunch Break"

    # =========================================================
    # 6. YET TO START
    # =========================================================
    yet_to_start_patterns = [
        r"match hasn't started yet",
        r"match has not started yet",
        r"we'?ll be live once the toss begins",
        r"awaiting toss",
        r"toss yet to take place",
        r"yet to start"
    ]

    for pattern in yet_to_start_patterns:
        if re.search(pattern, text_lower):
            return "Yet to Start"

    # =========================================================
    # 7. LIVE MATCH
    # =========================================================
    if (
        "live" in text_lower
        and "match abandoned" not in text_lower
        and "yet to start" not in text_lower
    ):
        return "Live"

    # =========================================================
    # 8. TOMORROW
    # =========================================================
    if any(str(item).strip().lower() == "tomorrow" for item in data):
        return "Tomorrow"

    # =========================================================
    # 9. TODAY
    # =========================================================
    for i, item in enumerate(data):

        if str(item).strip().lower() == "today":

            if i + 1 < len(data):
                time_val = str(data[i + 1])

                if re.search(r'\d{1,2}:\d{2}', time_val):
                    return f"Today at {time_val}"

            return "Today"

    # =========================================================
    # 10. SCHEDULED MATCH
    # =========================================================
    weekdays = {
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    }

    for i, item in enumerate(data):

        item_str = str(item)

        if re.search(r'\d{1,2}:\d{2}\s*(am|pm)?', item_str, re.I):

            if i > 0:

                prev = str(data[i - 1]).lower()

                if prev in weekdays:
                    return f"{data[i - 1]} at {item_str}"

            return f"Scheduled at {item_str}"

    # =========================================================
    # 11. LEGACY WIN DETECTION
    # =========================================================
    if "match info" in text_lower:

        for item in data:

            if isinstance(item, str) and "won" in item.lower():

                if "head to head" not in text_lower:
                    winner = item.replace("Won", "").replace("won", "").strip()

                    if winner:
                        return f"Completed - {winner} Won"

    # =========================================================
    # 12. COUNTDOWN TIMER
    # =========================================================
    for item in data:

        if not isinstance(item, str):
            continue

        if re.search(r'\d+m.*\d+s', item.lower()):
            return "Live (Countdown Active)"

    # =========================================================
    # 13. FALLBACK
    # =========================================================
    if "match info" in text_lower:
        return "Scheduled (Yet to Start)"

    return "Unknown Status"



def detect_live_status_old(data):
    """
    Detects the game status including breaks, completed matches with results
    """
    text = ' '.join(str(item) for item in data)
    text_lower = text.lower()
    #print("Hello", data)
    # 1. Highest priority: Match Abandoned
    if "Match Abandoned" in data or "match abandoned" in text_lower:
        return "Match Abandoned"
    
    # 2. Suspended / Deferred
    if "Suspended" in text or "suspended" in text_lower:
        return "Suspended"
    if "Deferred" in text or "deferred" in text_lower:
        return "Deferred"
    
    # 3. COMPLETED MATCH WITH RESULT (Check before breaks)
    # Pattern: "Team X won by X runs/wickets" or "Team X won by X runs 🏆"
    win_patterns = [
        r'won by \d+ runs?',
        r'won by \d+ wickets?',
        r'won by \d+ runs?\s*🏆',
        r'won by \d+ wickets?\s*🏆',
        r'beat .+ by \d+ runs?',
        r'beat .+ by \d+ wickets?',
        r'match tied',
        r'tie match',
        r'super over',
        r'result: .+ won'
    ]
    
    for pattern in win_patterns:
        if re.search(pattern, text_lower):
            # Extract the winning message
            win_match = re.search(r'[A-Za-z0-9\s]+(?:won by \d+ runs?|won by \d+ wickets?|beat [A-Za-z0-9\s]+ by \d+ runs?)', text)
            if win_match:
                return f"Completed - {win_match.group(0).strip()}"
            return "Completed - Match Finished"
    
    # Also check for emoji trophy 🏆 which indicates completion
    if "🏆" in text and ("won" in text_lower or "champion" in text_lower):
        return "Completed - Match Finished"
    
    # 4. BREAKS
    if "Drinks Break" in text or "drinks break" in text_lower:
        return "Drinks Break"
    if "Innings Break" in text or "innings break" in text_lower or "Innings Interval" in text:
        print("Check Data", data)
        return "Innings Break"
    if "Tea Break" in text or "tea break" in text_lower:
        return "Tea Break"
    if "Lunch Break" in text or "lunch break" in text_lower:
        return "Lunch Break"
    if "Rain Break" in text or "rain break" in text_lower or "Rain Delay" in text:
        return "Rain Break (Delayed)"
    
    # 5. Yet to start (toss pending)
    if "Match hasn't started yet" in text or "We'll be live once the toss begins" in text:
        return "Yet to Start"
    
    if "Toss delayed due to wet outfield" in text or "We'll be live once the toss begins" in text:
        return "Yet to Start"
    
    if "Match stopped due to rain" in text or "We'll be live once the toss begins" in text:
        return "Match Stoped"
    
    
    # 6. Live match
    if "Live" in data and "Match Abandoned" not in data:
        if "Match hasn't started yet" not in text:
            return "Live"
    
    
    # 10. Completed match (legacy detection without result message)
    match_info_index = -1
    if "Match info" in data:
        match_info_index = data.index("Match info")
    
    if match_info_index != -1:
        for i in range(match_info_index, min(match_info_index + 20, len(data))):
            if i + 1 < len(data) and isinstance(data[i], str) and "Won" in data[i]:
                head_to_head_index = text_lower.find("head to head")
                current_pos = text_lower.find(data[i].lower())
                if head_to_head_index == -1 or current_pos < head_to_head_index:
                    # Extract which team won
                    winner = data[i].replace("Won", "").strip()
                    return f"Completed - {winner} Won"
    
    # 11. Check for final score pattern (both innings completed)
    innings_complete = False
    score_pattern = r'\d{1,3}/\d{1,2}'
    scores_found = re.findall(score_pattern, text)
    if len(scores_found) >= 2:  # At least 2 innings scores
        # Check if "overs" appears after scores (suggests completion)
        if "overs" in text_lower and "won" not in text_lower:
            # Might be completed but result not explicitly stated
            pass
    
    # 12. Live countdown timer
    for item in data:
        if isinstance(item, str) and "m" in item and "s" in item and ":" in item:
            if any(c.isdigit() for c in item) and "(" not in item:
                return "Live (Countdown active)"
    
    # 13. Default fallback
    if "Match info" in data:
        return "Scheduled (Yet to Start)"
    
    return "Unknow Event"

def handle_break_period(status, page, browser, team=None, runs= None, wickets=None):
    """
    Handle different types of breaks intelligently
    """
    break_durations = {
        "Drinks Break": 5,
        "Tea Break": 20,
        "Lunch Break": 40,
        "Innings Break": 15,
        "Rain Break (Delayed)": None
    }
    
    duration = break_durations.get(status, None)
    
    if status == "Rain Break (Delayed)":
        print(f"☔ {status} detected. Waiting indefinitely until match resumes...")
        print("   Will check every 2 minutes for updates")
        
        wait_time = 120
        check_count = 0
        
        while True:
            time.sleep(wait_time)
            page.reload()
            page.wait_for_timeout(2000)
            text = page.inner_text("body")
            lines = text.splitlines()
            new_status = detect_game_status(lines)
            print(new_status)
            check_count += 1
            print(f"   [{check_count * 2} min] Checking status: {new_status}")
            
            if "Live" in new_status:
                print(f"✅ Match resumed! Now {new_status}")
                return new_status
            elif "Completed" in new_status or "Abandoned" in new_status:
                print(f"🏆 Match {new_status}. Exiting.")
                browser.close()
                sys.exit(0)
    
    elif duration:
        print(f"⏸️ {status} detected. Duration: ~{duration} minutes")
        print(f"   Waiting {duration} minutes for play to resume...")       
                                    
        for remaining in range(duration * 60, 0, -30):
            mins = remaining // 60
            secs = remaining % 60
            print(f"   ⏳ Resuming in {mins:02d}:{secs:02d}", end='\r')
            line = generate_break_commentary(status, team, runs, wickets)  
            
            if line:
                    print("🎙 FINAL:", line)
                    # Save last main event
                    #write_json(runs, wickets, over, ball, event)
                    #print(event)
                    # Speak once (IMPORTANT FIX ✅)
                   #speak("TEA_BREAK", line)
            time.sleep(30)
        
        print(f"\n   🔄 Checking if match has resumed...")
        page.reload()
        page.wait_for_timeout(2000)
        text = page.inner_text("body")
        lines = text.splitlines()
        new_status = detect_game_status(lines)
        
        if "Live" in new_status:
            print(f"✅ Match resumed! Now {new_status}")
            return new_status
        else:
            print(f"⚠️ Match status after break: {new_status}")
            return new_status
    
    else:
        print(f"⚠️ Unknown break duration for {status}. Will check every minute.")
        check_count = 0
        while True:
            time.sleep(60)
            page.reload()
            page.wait_for_timeout(2000)
            text = page.inner_text("body")
            lines = text.splitlines()
            new_status = detect_game_status(lines)
            check_count += 1
            
            print(f"   [{check_count} min] Checking: {new_status}")
            
            if "Live" in new_status:
                print(f"✅ Match resumed!")
                return new_status
            elif "Completed" in new_status or "Abandoned" in new_status:
                print(f"🏆 Match {new_status}. Exiting.")
                browser.close()
                sys.exit(0)

"""
if __name__ == "__main__":
    
    print(detect_game_status(["Toss delayed due to wet outfield"]))
    # Toss Delayed (Wet Outfield)

    print(detect_game_status(["Toss delayed due to rain"]))
    # Toss Delayed (Rain)

    print(detect_game_status(["Start Delayed Due to rain"]))
    # Start Delayed (Rain)

    print(detect_game_status(["Match stopped due to rain"]))
    # Match Stopped (Rain)

    print(detect_game_status(["Rain Break"]))
    # Rain Break

    print(detect_game_status(["Rain Delay"]))
    # Rain Delay"""