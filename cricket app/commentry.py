import random
import re
from commentry_dic import COMMENTARY, WINNING_COMMENTARY_TEMPLATES
from utill import number_to_bangla_words
# -----------------------------
# Number → Bangla Words
# -----------------------------
BN_NUMBERS = {
    0: "শূন্য", 1: "এক", 2: "দুই", 3: "তিন", 4: "চার",
    5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আট", 9: "নয়",
    10: "দশ", 11: "এগারো", 12: "বারো", 13: "তেরো",
    14: "চৌদ্দ", 15: "পনেরো", 16: "ষোল", 17: "সতেরো",
    18: "আঠারো", 19: "উনিশ", 20: "বিশ"
}

def num_to_bn(n):
    """Convert small numbers to Bangla words, fallback to string"""
    return BN_NUMBERS.get(n, str(n))


# -----------------------------
# MAIN FUNCTION
# -----------------------------

def generate_event_commentary2(events):
    """
    Generate rich, natural Bangla commentary for a given list of cricket events
    events: list of strings (SIX, FOUR, DOUBLE, SINGLE, DOT, WIDE, NO_BALL)
    """
    parts = []

    # Primary scoring events (only one of these per ball)
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

    # Extras can be combined with scoring
    if "WIDE" in events:
        parts.append(random.choice(COMMENTARY["WIDE"]))

    if "NO_BALL" in events:
        parts.append(random.choice(COMMENTARY["NO_BALL"]))

    # Combine all parts into one natural paragraph
    commentary_text = " ".join(parts)
    return commentary_text
    

def get_match_situation(current_score, target, wickets_left, balls_left, is_batting_first):
    """Generate match situation commentary based on current match state"""
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
        # Defending logic
        return {"type": "DEFENDING_TENSE", "data": {"runs_to_defend": runs_to_defend, "wickets": wickets_left}}

def generate_wicket_commentary(runs, wickets, over, batsman=None, wicket_type=None):
    """
    Long, natural Bangla wicket commentary
    - No symbols like '/'
    - Human-like flow (2–3 sentences)
    - Context-aware (normal / pressure / collapse)
    """

    runs_bn = number_to_bangla_words(runs)
    wickets_bn = number_to_bangla_words(wickets)
    over_bn = str(over)

    name_part = f"{batsman} ফিরে যাচ্ছেন। " if batsman else ""

    # 🎯 Normal commentary (long)
    templates = [
        f"আউট! {name_part}এটা ছিল খুবই গুরুত্বপূর্ণ একটি উইকেট। {over_bn} ওভারে দলের রান এখন {runs_bn}, আর উইকেট {wickets_bn}টি। এই মুহূর্তে ম্যাচে কিছুটা ভারসাম্য ফিরে এসেছে।",
        
        f"উইকেট পড়ে গেছে! {name_part}দারুণ একটি ব্রেকথ্রু পেয়েছে বোলিং দল। {runs_bn} রান তুলতে গিয়ে {wickets_bn} উইকেট হারিয়েছে দলটি, এবং এখন ম্যাচের গতিপথ বদলে যেতে পারে।",
        
        f"এবং আউট! {name_part}খুব গুরুত্বপূর্ণ সময় এই উইকেটের পতন। {over_bn} ওভারে স্কোর এখন {runs_bn} রান, {wickets_bn} উইকেট, ফলে ব্যাটিং দল এখন কিছুটা চাপে পড়ে গেল।",
        
        f"বড় উইকেট! {name_part}এই উইকেটটি ম্যাচে বড় প্রভাব ফেলতে পারে। দল এখন {runs_bn} রানে {wickets_bn} উইকেট হারিয়েছে, এবং এখান থেকে ঘুরে দাঁড়ানোটা সহজ হবে না।",
    ]

    # 🔥 Pressure commentary (long)
    pressure_templates = [
        f"বড় ধাক্কা! {name_part}ঠিক এই সময়েই উইকেট হারানোটা দলের জন্য সমস্যা তৈরি করতে পারে। {runs_bn} রানে {wickets_bn} উইকেট, এবং এখন ম্যাচে চাপ স্পষ্টভাবে দেখা যাচ্ছে।",
        
        f"গুরুত্বপূর্ণ উইকেট! {name_part}বোলার ঠিক সময়েই সাফল্য এনে দিলেন। {over_bn} ওভারে {runs_bn} রান, {wickets_bn} উইকেট — ব্যাটিং দল এখন চাপের মধ্যে।",
        
        f"এই উইকেট ম্যাচের মোড় ঘুরিয়ে দিতে পারে! {name_part}দল এখন {runs_bn} রানে {wickets_bn} উইকেট হারিয়েছে, এবং এখান থেকে রান তোলা সহজ হবে না।",
    ]

    # 🚨 Collapse commentary (long)
    collapse_templates = [
        f"একের পর এক উইকেট! {name_part}দল পুরোপুরি চাপে পড়ে গেছে। {runs_bn} রানে {wickets_bn} উইকেট, এবং ব্যাটিং লাইনআপ এখন ভেঙে পড়ার মুখে।",
        
        f"ব্যাটিং ধস! {name_part}এই উইকেটের পর পরিস্থিতি আরও কঠিন হয়ে গেল। {runs_bn} রান, {wickets_bn} উইকেট — এখন ম্যাচ পুরোপুরি প্রতিপক্ষের নিয়ন্ত্রণে চলে যাচ্ছে।",
        
        f"চাপ বাড়ছেই! {name_part}দল এখন দিশেহারা অবস্থায়। {runs_bn} রানে {wickets_bn} উইকেট পড়ে গেছে, এবং এখান থেকে ঘুরে দাঁড়ানো বেশ কঠিন।",
    ]

    # 🎲 Smart logic
    if wickets >= 6:
        return random.choice(collapse_templates)

    if wickets >= 4 and random.random() > 0.5:
        return random.choice(pressure_templates)

    return random.choice(templates)
# ---------------------------------------

def generate_winning_commentary2(team, margin, win_type):
    """
    Advanced natural Bangla winning commentary
    - More expressive & emotional
    - Broadcast-style flow
    - Context-aware variations
    """

    if not team:
        return None

    # Normalize win type
    type_bn = "উইকেটে" if win_type == "wickets" else "রানে"

    # 🎯 Standard balanced win
    templates = [
        f"ম্যাচ শেষ, এবং জয় পেয়েছে {team}! {margin} {type_bn} দুর্দান্ত পারফরম্যান্সে তারা ম্যাচটি নিজেদের করে নিয়েছে। পুরো ম্যাচ জুড়েই ছিল নিয়ন্ত্রণ, এবং শেষ পর্যন্ত সেই ধারাবাহিকতাই এনে দিল এই জয়।",

        f"খেলা শেষ! {team} {margin} {type_bn} একটি দারুণ জয় তুলে নিল। শুরু থেকে শেষ পর্যন্ত পরিকল্পিত ক্রিকেট খেলেছে তারা, এবং প্রতিপক্ষকে খুব একটা সুযোগ দেয়নি ঘুরে দাঁড়ানোর।",

        f"জয় {team}-এর! {margin} {type_bn} তারা আজকের ম্যাচে অসাধারণ পারফরম্যান্স দেখিয়েছে। ব্যাটিং, বোলিং—সব বিভাগেই ছিল চমৎকার সমন্বয়।",

        f"এবং শেষ পর্যন্ত {team} জিতে গেল! {margin} {type_bn} এই জয় তাদের আত্মবিশ্বাস আরও বাড়াবে। পুরো ম্যাচে তারা ছিল অনেক বেশি সংগঠিত ও আত্মবিশ্বাসী।",
    ]

    # 🔥 Dominating performance
    dominant_templates = [
        f"একতরফা লড়াই বলা যায়! {team} {margin} {type_bn} বিশাল জয় তুলে নিয়েছে। শুরু থেকেই ম্যাচের নিয়ন্ত্রণ ছিল তাদের হাতে, এবং প্রতিপক্ষকে একেবারেই খেলায় ফিরতে দেয়নি।",

        f"সম্পূর্ণ আধিপত্য {team}-এর! {margin} {type_bn} এই বড় জয় প্রমাণ করে আজ তারা কতটা শক্তিশালী পারফরম্যান্স দিয়েছে। প্রতিটি বিভাগেই ছিল শ্রেষ্ঠত্ব।",

        f"দাপুটে জয়! {team} {margin} {type_bn} ব্যবধানে ম্যাচ জিতে নিয়েছে। এমন পারফরম্যান্সে তারা প্রতিপক্ষকে পুরোপুরি চাপে ফেলে দেয় এবং ম্যাচটা একদম নিজেদের মতো করে খেলেছে।",
    ]

    # 🎉 Close thriller finish
    close_templates = [
        f"কি রোমাঞ্চকর ম্যাচ! শেষ মুহূর্ত পর্যন্ত উত্তেজনা ছিল, কিন্তু শেষ হাসি হাসলো {team}। {margin} {type_bn} এই জয় সত্যিই স্মরণীয় হয়ে থাকবে।",

        f"হৃদয় কাঁপানো লড়াইয়ের পর {team} জিতে গেল! মাত্র {margin} {type_bn} এই জয় এসেছে, এবং ম্যাচটি শেষ বল পর্যন্ত জমে ছিল।",

        f"অবিশ্বাস্য সমাপ্তি! {team} শেষ মুহূর্তে ম্যাচ ছিনিয়ে নিল {margin} {type_bn} ব্যবধানে। এমন ম্যাচ ক্রিকেটপ্রেমীদের অনেকদিন মনে থাকবে।",
    ]

    # ⚡ Chase victory (wickets win special tone)
    chase_templates = [
        f"টার্গেট তাড়া করে জয়! {team} দারুণভাবে রান তাড়া করে {margin} {type_bn} জয় তুলে নিয়েছে। ব্যাটসম্যানদের আত্মবিশ্বাসী পারফরম্যান্স ছিল চোখে পড়ার মতো।",

        f"চমৎকার রান চেজ! {team} সহজভাবেই লক্ষ্য ছুঁয়ে ফেলেছে এবং {margin} {type_bn} জয় পেয়েছে। শেষ দিকে ছিল সম্পূর্ণ নিয়ন্ত্রণ।",
    ]

    # 🎲 Smart selection logic
    if win_type == "runs" and margin >= 50:
        return random.choice(dominant_templates)

    if win_type == "wickets" and margin >= 7:
        return random.choice(dominant_templates)

    if margin <= 2:
        return random.choice(close_templates)

    if win_type == "wickets" and margin >= 4:
        return random.choice(chase_templates)

    return random.choice(templates)
    
def generate_winning_commentary(team, margin, win_type):
    """
    Ultra-natural Bangla winning commentary
    - Long, emotional, TV-style narration
    - Smooth storytelling flow
    - Context-aware variations
    """

    if not team:
        return None

    type_bn = "উইকেটে" if win_type == "wickets" else "রানে"

    # 🎯 Balanced win
    templates = [
        f"ম্যাচ শেষ, এবং দারুণ এক জয়ের সাক্ষী থাকলো আজকের এই লড়াই। {team} {margin} {type_bn} ম্যাচটি জিতে নিয়েছে অসাধারণ পারফরম্যান্সের মাধ্যমে। শুরু থেকেই তারা ছিল বেশ আত্মবিশ্বাসী, পরিকল্পনা অনুযায়ী খেলেছে, এবং প্রতিটি বিভাগে নিজেদের শ্রেষ্ঠত্ব দেখিয়েছে। শেষ পর্যন্ত সেই ধারাবাহিকতাই এনে দিল এই গুরুত্বপূর্ণ জয়।",

        f"খেলা শেষ! {team} {margin} {type_bn} একটি চমৎকার জয় তুলে নিল আজ। পুরো ম্যাচ জুড়ে তারা ছিল অনেক বেশি সংগঠিত এবং নিয়ন্ত্রিত। ব্যাটিং হোক বা বোলিং—সব জায়গাতেই ছিল স্পষ্ট পরিকল্পনা, আর সেটার ফলই এই জয়।",

        f"জয় {team}-এর! {margin} {type_bn} তারা আজকের ম্যাচে সত্যিই পরিপূর্ণ ক্রিকেট খেলেছে। প্রতিটি মুহূর্তে ছিল আত্মবিশ্বাস, ছিল নিয়ন্ত্রণ, আর সেই কারণেই শেষ পর্যন্ত তারা ম্যাচটা নিজেদের করে নিতে পেরেছে।",
    ]

    # 🔥 Dominating performance
    dominant_templates = [
        f"একতরফা লড়াই বলা যায় আজকের ম্যাচটি! {team} {margin} {type_bn} বিশাল ব্যবধানে জয় তুলে নিয়েছে। শুরু থেকেই ম্যাচের নিয়ন্ত্রণ ছিল তাদের হাতে, এবং প্রতিপক্ষকে এক মুহূর্তের জন্যও ঘুরে দাঁড়ানোর সুযোগ দেয়নি। এমন পারফরম্যান্স নিঃসন্দেহে তাদের আত্মবিশ্বাস অনেক বাড়িয়ে দেবে।",

        f"সম্পূর্ণ আধিপত্য দেখাল {team}! {margin} {type_bn} এই বড় জয় প্রমাণ করে তারা আজ কতটা প্রস্তুত ছিল। ব্যাটিং, বোলিং, ফিল্ডিং—সব জায়গাতেই ছিল নিখুঁত পারফরম্যান্স, এবং প্রতিপক্ষকে পুরোপুরি চাপে ফেলে দিয়েছে।",

        f"দাপুটে জয়! {team} {margin} {type_bn} ব্যবধানে ম্যাচ জিতে একেবারে আধিপত্য বিস্তার করেছে। শুরু থেকেই তারা ম্যাচটা নিজেদের নিয়ন্ত্রণে নিয়ে নেয় এবং শেষ পর্যন্ত সেই নিয়ন্ত্রণ আর হারায়নি।",
    ]

    # 🎉 Close thriller
    close_templates = [
        f"কি অসাধারণ রোমাঞ্চকর ম্যাচ দেখলাম আমরা! শেষ মুহূর্ত পর্যন্ত উত্তেজনা ছিল তুঙ্গে, কিন্তু শেষ হাসি হাসলো {team}। মাত্র {margin} {type_bn} এই জয় সত্যিই স্মরণীয় হয়ে থাকবে।",

        f"হৃদয় কাঁপানো লড়াইয়ের পর অবশেষে জয় পেল {team}! ম্যাচটা শেষ বল পর্যন্ত গড়িয়েছিল, আর শেষ মুহূর্তে {margin} {type_bn} ব্যবধানে জয় নিশ্চিত করে তারা।",

        f"অবিশ্বাস্য সমাপ্তি! শেষ মুহূর্তে নাটকীয়ভাবে ম্যাচ জিতে নিল {team}, {margin} {type_bn} ব্যবধানে। এমন ম্যাচ ক্রিকেটপ্রেমীরা অনেকদিন মনে রাখবে।",
    ]

    # ⚡ Chase win (wickets)
    chase_templates = [
        f"টার্গেট তাড়া করে দুর্দান্ত জয়! {team} অসাধারণ ব্যাটিং করে {margin} {type_bn} জয় তুলে নিয়েছে। শুরুটা হয়তো কিছুটা সতর্ক ছিল, কিন্তু সময়ের সঙ্গে সঙ্গে তারা পুরো নিয়ন্ত্রণ নিয়ে নেয় এবং খুব আত্মবিশ্বাসের সঙ্গে ম্যাচ শেষ করে।",

        f"চমৎকার রান চেজ! {team} দারুণভাবে লক্ষ্য ছুঁয়ে ফেলেছে এবং {margin} {type_bn} জয় পেয়েছে। শেষ দিকে তাদের ব্যাটিং ছিল একেবারে নিখুঁত, কোনো ভুল করেনি।",

        f"দারুণভাবে লক্ষ্য তাড়া করে জয় পেল {team}! {margin} {type_bn} এই জয় এসেছে পরিপক্ক ব্যাটিং এবং সঠিক পরিকল্পনার মাধ্যমে।",
    ]

    # 🏆 Historic / special tone
    special_templates = [
        f"এই জয় শুধুমাত্র একটি জয় নয়, এটি একটি বার্তা! {team} {margin} {type_bn} ব্যবধানে ম্যাচ জিতে দেখিয়ে দিল তারা কতটা শক্তিশালী দল। পুরো ম্যাচ জুড়ে ছিল আত্মবিশ্বাস, নিয়ন্ত্রণ, এবং জয়ের তীব্র ইচ্ছা।",

        f"স্মরণীয় এক জয়! {team} {margin} {type_bn} ব্যবধানে ম্যাচ জিতে আজকের দিনটিকে বিশেষ করে রাখলো। এমন পারফরম্যান্স দলটির জন্য অনেক বড় অনুপ্রেরণা হয়ে থাকবে।",
    ]

    # 🎲 Smart selection logic
    if win_type == "runs" and margin >= 60:
        return random.choice(dominant_templates + special_templates)

    if win_type == "wickets" and margin >= 8:
        return random.choice(dominant_templates)

    if margin <= 2:
        return random.choice(close_templates)

    if win_type == "wickets" and margin >= 4:
        return random.choice(chase_templates)

    if margin >= 30:
        return random.choice(dominant_templates)

    # default balanced
    return random.choice(templates)

def generate_event_commentary(events, context=None):
    """
    Generate rich, natural Bangla commentary for cricket events
    
    Args:
        events: list of strings (SIX, FOUR, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, 
                               WICKET, BOWLED, CATCH, BATTER_INJURED, BATTER_RETURNS,
                               RETIRE_HURT, TIME_OUT, DRINKS_BREAK, REVIEW_TAKEN,
                               REVIEW_LOST, REVIEW_SUCCESSFUL, POWERPLAY, STRATEGIC_TIMEOUT,
                               RAIN_DELAY, TOSS_WIN_BAT, TOSS_WIN_BOWL, TOSS_LOSS,
                               PLAYING_XI, IMPACT_PLAYER)
        context: dict containing match context (team, decision, players, etc.)
    """
    parts = []
   
    # Check for toss and team selection events first
    toss_events = ["TOSS_WIN_BAT", "TOSS_WIN_BOWL", "TOSS_LOSS", "PLAYING_XI", "IMPACT_PLAYER"]
    
    for event in events:
        if event in toss_events and event in COMMENTARY:
            if context and 'team' in context:
                commentary_text = random.choice(COMMENTARY[event])
                if '{team}' in commentary_text:
                    commentary_text = commentary_text.format(team=context['team'])
                if '{decision}' in commentary_text:
                    commentary_text = commentary_text.format(decision=context.get('decision', 'ব্যাটিং'))
                if '{players}' in commentary_text:
                    commentary_text = commentary_text.format(players=context.get('players', 'নতুন মুখ'))
                if '{changes}' in commentary_text:
                    commentary_text = commentary_text.format(changes=context.get('changes', 'কেউ নেই'))
                if '{player}' in commentary_text:
                    commentary_text = commentary_text.format(player=context.get('player', 'নতুন খেলোয়াড়'))
                if '{key_players}' in commentary_text:
                    commentary_text = commentary_text.format(key_players=context.get('key_players', 'অভিজ্ঞ খেলোয়াড়রা'))
                if '{bowlers}' in commentary_text:
                    commentary_text = commentary_text.format(bowlers=context.get('bowlers', 'মূল বোলাররা'))
                if '{surprise_player}' in commentary_text:
                    commentary_text = commentary_text.format(surprise_player=context.get('surprise_player', 'চমকের নাম'))
                parts.append(commentary_text)
            else:
                parts.append(random.choice(COMMENTARY[event]))
    
    # Check for special event types
    special_events = ["BATTER_INJURED", "BATTER_RETURNS", "RETIRE_HURT", "TIME_OUT", 
                      "DRINKS_BREAK", "REVIEW_TAKEN", "REVIEW_LOST", "REVIEW_SUCCESSFUL",
                      "POWERPLAY", "STRATEGIC_TIMEOUT", "RAIN_DELAY"]
    
    for event in events:
        if event in special_events and event in COMMENTARY:
            parts.append(random.choice(COMMENTARY[event]))
    
    # Primary scoring events (only one of these per ball)
    scoring_events = ["BOWLED", "CATCH", "WICKET", "SIX", "FOUR", "DOUBLE", "SINGLE", "DOT"]
    for event in scoring_events:
        if event in events and event in COMMENTARY:
            parts.append(random.choice(COMMENTARY[event]))
            break  # Only add one scoring event per ball
    
    # Extras can be combined with scoring
    extras = ["WIDE", "NO_BALL"]
    for extra in extras:
        if extra in events and extra in COMMENTARY:
            parts.append(random.choice(COMMENTARY[extra]))
    
    # Add milestone commentary if provided
    if context and 'milestone' in context:
        milestone_type = context['milestone']
        if milestone_type in COMMENTARY["MILESTONE"]:
            parts.append(COMMENTARY["MILESTONE"][milestone_type])
    
    # Add over summary if provided
    if context and 'over_info' in context:
        over_info = context['over_info']
        summary = random.choice(COMMENTARY["OVER_SUMMARY"])
        summary = summary.format(runs=over_info.get('runs', 0), wickets=over_info.get('wickets', 0))
        parts.append("\n" + summary)
    
    # Add match situation if provided
    if context and 'match_situation' in context:
        situation_type = context['match_situation']['type']
        situation_data = context['match_situation']['data']
        if situation_type in COMMENTARY["MATCH_SITUATION"]:
            situation = COMMENTARY["MATCH_SITUATION"][situation_type].format(**situation_data)
            parts.append("\n" + situation)
    
    # Combine all parts
    commentary_text = " ".join(parts)
    return commentary_text


def generate_toss_commentary(team, decision, is_win=True):
    """
    Generate commentary for toss and team selection
    
    Args:
        team: Team name (e.g., "LSG", "MI", "CSK")
        decision: "bat" or "bowl"
        is_win: True if team won the toss, False if lost
    """
    events = []
    context = {'team': team}
    
    if is_win:
        if decision == "bat":
            events.append("TOSS_WIN_BAT")
            context['decision'] = "ব্যাটিং"
        else:
            events.append("TOSS_WIN_BOWL")
            context['decision'] = "বোলিং"
    else:
        events.append("TOSS_LOSS")
        if decision == "bat":
            context['decision'] = "ব্যাটিং"
        else:
            context['decision'] = "বোলিং"
    
    return generate_event_commentary(events, context)


def generate_break_commentary(status, team=None, runs=None, wickets=None):
    """
    Generate commentary for match breaks safely with error handling
    """

    try:
        
        if status == "Drinks Break":
            templates = COMMENTARY.get("DRINKS_BREAK", [])
        elif status == "Innings Break":
            templates = COMMENTARY.get("INNINGS_BREAK", [])
        elif status == "Tea Break":
            templates = COMMENTARY.get("TEA_BREAK", [])
        elif status == "Lunch Break":
            templates = COMMENTARY.get("LUNCH_BREAK", [])
        elif status == "Rain Break (Delayed)":
            templates = COMMENTARY.get("RAIN_DELAY", [])
        else:
            return "এই মুহূর্তে ম্যাচ সংক্রান্ত কোনো আপডেট পাওয়া যাচ্ছে না।"
       
        # Safe random selection
        if not templates:
            return "এই মুহূর্তে ম্যাচে বিরতি চলছে। আমাদের সাথেই থাকুন, লাইক ও কমেন্ট করে আপনার মতামত জানাতে ভুলবেন না!"

        template = random.choice(templates)

        # Safe formatting (avoid crash if missing placeholders)
        return template.format(
            team=team or "",
            runs=runs or "",
            wickets=wickets or ""
        )

    except KeyError as e:
        return f"কমেন্টারি ডেটা অনুপস্থিত: {str(e)}"

    except IndexError:
        return "কমেন্টারি লিস্ট খালি আছে।"

    except Exception as e:
        return f"কমেন্টারি জেনারেট করতে সমস্যা হয়েছে: {str(e)}"
        
def pre_game_scenario_commentary(text: str) -> str:
    if not text:
        return "এই মুহূর্তে ম্যাচ সংক্রান্ত কোনো আপডেট পাওয়া যাচ্ছে না।"

    text_lower = text.lower()

    # Delay scenarios
    if "delayed" in text_lower:
        if "rain" in text_lower:
            return "বৃষ্টি বাধায় ম্যাচ শুরুতে দেরি হচ্ছে, সবাই অপেক্ষায় আছেন খেলা শুরুর জন্য।"
        elif "wet" in text_lower:
            return "আউটফিল্ড ভেজা থাকার কারণে ম্যাচ শুরুতে দেরি হচ্ছে। মাঠ প্রস্তুত হলেই খেলা শুরু হবে।"
        else:
            return "কিছু অনির্দিষ্ট কারণে টস দেরিতে হচ্ছে, আপডেটের জন্য সাথে থাকুন।"

    # Toss auto-detect (e.g., "CNQ-W opt to Bat")
    toss_match = re.search(r'([A-Za-z\-]+)\s+opt to\s+(bat|bowl)', text, re.IGNORECASE)
    if toss_match:
        team = toss_match.group(1)
        decision = toss_match.group(2).lower()

        if decision == "bat":
            return f"টস জিতে {team} ব্যাটিং করার সিদ্ধান্ত নিয়েছে। আজ তারা শুরুটা করতে চায় শক্তভাবে!"
        else:
            return f"টস জিতে {team} বোলিং করার সিদ্ধান্ত নিয়েছে। শুরুতেই প্রতিপক্ষকে চাপে ফেলতে চাইবে তারা।"

    # Players entering
    if "entering" in text_lower or "players" in text_lower:
        return "খেলোয়াড়রা এখন মাঠে প্রবেশ করছেন, আর কিছুক্ষণের মধ্যেই ম্যাচ শুরু হতে যাচ্ছে!"

    return "ম্যাচের বর্তমান অবস্থা সম্পর্কে পরিষ্কার কোনো তথ্য পাওয়া যায়নি।"
    
def generate_playing_xi_commentary(team, players_list=None, changes=None, key_players=None):
    """
    Generate commentary for playing XI announcement
    
    Args:
        team: Team name
        players_list: List of players in the XI
        changes: Changes from previous match
        key_players: Key players to highlight
    """
    events = ["PLAYING_XI"]
    context = {
        'team': team,
        'players': players_list if players_list else ["নতুন মুখ"],
        'changes': changes if changes else "কেউ নেই",
        'key_players': key_players if key_players else ["অভিজ্ঞ খেলোয়াড়রা"]
    }
    
    return generate_event_commentary(events, context)


def generate_impact_player_commentary(team, player, reason=None):
    """
    Generate commentary for impact player announcement
    
    Args:
        team: Team name
        player: Impact player name
        reason: Reason for bringing impact player
    """
    events = ["IMPACT_PLAYER"]
    context = {
        'team': team,
        'player': player
    }
    
    return generate_event_commentary(events, context)


# Example usage with LSG opt to bat scenario
def demonstrate_toss_scenarios():
    """Demonstrate toss and team selection scenarios"""
    
    print("="*80)
    print("TOSS AND TEAM SELECTION COMMENTARY DEMONSTRATION")
    print("="*80)
    
    # Scenario 1: LSG wins toss and opts to bat
    print("\n1. LSG WINS TOSS AND OPTS TO BAT:")
    commentary = generate_toss_commentary("LSG", "bat", is_win=True)
    print(f"   {commentary}")
    
    # Scenario 2: LSG wins toss and opts to bowl
    print("\n2. LSG WINS TOSS AND OPTS TO BOWL:")
    commentary = generate_toss_commentary("LSG", "bowl", is_win=True)
    print(f"   {commentary}")
    
    # Scenario 3: LSG loses toss, opponent chooses to bat
    print("\n3. LSG LOSES TOSS, OPPONENT CHOOSES TO BAT:")
    commentary = generate_toss_commentary("LSG", "bat", is_win=False)
    print(f"   {commentary}")
    
    # Scenario 4: Playing XI announcement
    print("\n4. PLAYING XI ANNOUNCEMENT:")
    commentary = generate_playing_xi_commentary(
        team="LSG",
        players_list="রাহুল, মায়ার্স, স্টইনিস, পুরাণ, বদৌনি, ক্রুনাল, মোহসীন, অভিষেক, রবি, বিশ্নোই, আভেশ",
        changes="ফিরেছেন মায়ার্স, বাদ পড়েছেন ডি কক",
        key_players="রাহুল ও স্টইনিস"
    )
    print(f"   {commentary}")
    
    # Scenario 5: Impact player introduction
    print("\n5. IMPACT PLAYER INTRODUCTION:")
    commentary = generate_impact_player_commentary(
        team="LSG",
        player="অ্যাঞ্জেলো ম্যাথিউজ",
        reason="বোলিং আক্রমণে বৈচিত্র্য আনতে"
    )
    print(f"   {commentary}")
    
    # Scenario 6: Complete match start scenario
    print("\n6. COMPLETE MATCH START SCENARIO (LSG opts to bat):")
    toss_commentary = generate_toss_commentary("LSG", "bat", is_win=True)
    xi_commentary = generate_playing_xi_commentary(
        team="LSG",
        players_list="কে এল রাহুল (অধিনায়ক), কাইল মায়ার্স, মার্কাস স্টইনিস, নিকোলাস পুরাণ (উইকেটরক্ষক), আয়ুশ বদৌনি, ক্রুনাল পাণ্ড্য, মোহসীন খান, অভিষেক শর্মা, রবি বিষ্ণোই, যশ ঠাকুর, আভেশ খান",
        changes="মায়ার্স ফিরেছেন ইনজুরি থেকে, আভেশ খান পেস আক্রমণে"
    )
    
    print(f"   TOSS: {toss_commentary}")
    print(f"   TEAM: {xi_commentary}")
    print("\n   এবং ম্যাচ শুরু হতে যাচ্ছে... উত্তেজনা চরমে!")

import re
import random

# ================================
# 🧹 TEXT CLEANER (CREX-PROOF)
# ================================
def clean_crex_text(raw_text: str) -> str:
    text = re.sub(r"[^\w\s\.\-:/]", " ", raw_text)  # keep useful chars
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ================================
# 🏏 TEAM EXTRACTION
# ================================
def extract_teams(match_title: str):
    if not match_title:
        return None, None

    parts = re.split(r"\s+vs\s+", match_title, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()

    return None, None


# ================================
# 🧠 RESULT PARSER (ROBUST)
# ================================
def parse_result(text: str):
    clean_text = clean_crex_text(text).lower()

    winning_team = None
    result_type = "UNKNOWN"
    runs = None
    wickets = None

    # Winning team
    win_match = re.search(r"([a-z\s]+?) won by", clean_text)
    if win_match:
        winning_team = win_match.group(1).strip().title()

    # Wickets
    w_match = re.search(r"won by (\d+)\s*wicket", clean_text)
    if w_match:
        wickets = int(w_match.group(1))
        result_type = "WON_BY_WICKETS"

    # Runs
    r_match = re.search(r"won by (\d+)\s*run", clean_text)
    if r_match:
        runs = int(r_match.group(1))
        result_type = "WON_BY_RUNS"

    # Super Over / Tie
    if "super over" in clean_text or "tied" in clean_text:
        result_type = "SUPER_OVER"

    return {
        "winning_team": winning_team,
        "result_type": result_type,
        "runs": runs,
        "wickets": wickets
    }


# ================================
# 🎯 LOSING TEAM DETECTOR
# ================================
def detect_losing_team(winning_team, match_title):
    team1, team2 = extract_teams(match_title)

    if not winning_team or not team1 or not team2:
        return None

    if winning_team.lower() in team1.lower():
        return team2
    else:
        return team1


# ================================
# 🏆 PLAYER EXTRACTION (SMART)
# ================================
def extract_key_players(text: str):
    clean_text = clean_crex_text(text).lower()

    players = []

    # Batting (e.g., "kohli 82")
    batters = re.findall(r"([a-z]+(?:\s[a-z]+)?)\s(\d{2,3})", clean_text)

    # Bowling (e.g., "rashid 3/25")
    bowlers = re.findall(r"([a-z]+(?:\s[a-z]+)?)\s(\d{1,2})/(\d{1,3})", clean_text)

    # Add top batters
    for name, runs in batters[:2]:
        players.append(f"{name.title()} {runs} রান")

    # Add top bowlers
    for name, wk, _ in bowlers[:2]:
        players.append(f"{name.title()} {wk} উইকেট")

    return players[:3]




# ================================
# 🎙️ COMMENTARY GENERATOR
# ================================
def generate_commentary(parsed, losing_team, players):

    winning_team = parsed["winning_team"] or "দল"
    result_type = parsed["result_type"]
    runs = parsed["runs"]
    wickets = parsed["wickets"]

    templates = WINNING_COMMENTARY_TEMPLATES.get(result_type, WINNING_COMMENTARY_TEMPLATES["DEFAULT"])
    template = random.choice(templates)

    players_line = ""
    if players:
        players_line = f"আজকের নায়ক: {', '.join(players)} 💥"
    else:
        players_line = "দলগত পারফরম্যান্স ছিল দুর্দান্ত 💥"

    return template.format(
        winning_team=winning_team,
        losing_team=losing_team or "প্রতিপক্ষ দল",
        runs=runs,
        wickets=wickets,
        players_line=players_line
    )


# ================================
# 🚀 FULL PIPELINE FUNCTION
# ================================
def generate_full_commentary(raw_text, match_title=None):

    # Step 1: Parse result
    parsed = parse_result(raw_text)

    # Step 2: Detect losing team
    losing_team = detect_losing_team(parsed["winning_team"], match_title)

    # Step 3: Extract players
    players = extract_key_players(raw_text)

    # Step 4: Generate commentary
    commentary = generate_commentary(parsed, losing_team, players)

    return commentary


