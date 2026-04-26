import time
import sys
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
from commentry import generate_wicket_commentary, generate_winning_commentary, generate_event_commentary,generate_toss_commentary, demonstrate_toss_scenarios, pre_game_scenario_commentary, generate_break_commentary
from voice import speak

def detect_game_status(data):
    """
    Detects the game status including breaks, completed matches with results
    """
    text = ' '.join(str(item) for item in data)
    text_lower = text.lower()
    
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
    
    # 6. Live match
    if "Live" in data and "Match Abandoned" not in data:
        if "Match hasn't started yet" not in text:
            return "Live"
    
    # 7. Tomorrow
    if "Tomorrow" in data:
        return "Tomorrow"
    
    # 8. Today with time
    today_index = -1
    if "Today" in data:
        today_index = data.index("Today") if "Today" in data else -1
        if today_index != -1 and today_index + 1 < len(data):
            time_val = data[today_index + 1]
            if ":" in time_val or "PM" in time_val or "AM" in time_val:
                return f"Today at {time_val}"
        return "Today"
    
    # 9. Scheduled match with time
    for i, item in enumerate(data):
        if isinstance(item, str) and (":" in item and ("PM" in item or "AM" in item)):
            if i > 0 and data[i-1] == "Today":
                return f"Today at {item}"
            elif i > 0 and data[i-1] in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]:
                return f"{data[i-1]} at {item}"
            else:
                if "Match info" in data and not any(win in text_lower for win in ['won', 'beat', 'tie']):
                    return f"Scheduled at {item}"
    
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
    
    return "Unknown Status"

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
                    speak("TEA_BREAK", line)
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