from playwright.sync_api import sync_playwright
import re
import json
import time
import random
import asyncio
import edge_tts
import os
import time
import sys
import re
from datetime import datetime
import threading
from queue import Queue
from commentry import generate_wicket_commentary, generate_winning_commentary, generate_event_commentary,generate_toss_commentary, demonstrate_toss_scenarios, pre_game_scenario_commentary, generate_break_commentary
from voice import speak
from game_status import detect_game_status, handle_break_period
# ---------------------------------------
# CONFIG
# ---------------------------------------
CREX_URL = "https://crex.com/cricket-live-score/nz-a-vs-sl-a-2nd-odi-new-zealand-a-tour-of-sri-lanka-2026-match-updates-110G"
OUTPUT_FILE = "C:/cricket_voices/score.json"

REFRESH_INTERVAL = 1  # seconds

# ---------------------------------------
# COMMENTARY
# ---------------------------------------

COMMENTARY = {

    "DOT": [
        "ডট বল, কোনো রান নেই।",
        "চমৎকার ডেলিভারি, ব্যাটসম্যান রান নিতে পারলেন না।",
        "দারুণ লাইন-লেন্থ, ব্যাটসম্যান চাপে।",
        "বলটা ভালোভাবে সামলেছেন, কিন্তু রান নেই।",
        "ডট বল, বোলারের দারুণ নিয়ন্ত্রণ দেখা যাচ্ছে।"
    ],

    "SINGLE": [
        "এক রান নেওয়া হয়েছে।",
        "সহজেই একটি রান সংগ্রহ করলেন।",
        "স্ট্রাইক ঘুরিয়ে দিলেন, এক রান।",
        "হালকা ট্যাপ করে একটি রান।",
        "দৌড়ে একটি রান সম্পন্ন।"
    ],

    "DOUBLE": [
        "দুই রান সম্পন্ন।",
        "দারুণ দৌড়ে দুই রান নিলেন।",
        "গ্যাপ খুঁজে বের করে দুই রান সংগ্রহ।",
        "ফিল্ডারের ফাঁক দিয়ে দুই রান।",
        "চমৎকার রানিং বিটুইন দ্য উইকেটস, দুই রান।"
    ],

    "TRIPLE": [
        "তিন রান নেওয়া হয়েছে।",
        "দারুণ দৌড়ে তিন রান সম্পন্ন।",
        "বড় শট না হলেও তিন রান পেলেন।",
        "ফিল্ডারদের ফাঁকি দিয়ে তিন রান।"
    ],

    "FOUR": [
        "চার! অসাধারণ শট!",
        "দারুণ টাইমিং, বল সোজা বাউন্ডারির বাইরে!",
        "চমৎকার কভার ড্রাইভ, চার রান!",
        "গ্যাপ খুঁজে নিয়েছেন, বল গড়িয়ে বাউন্ডারি!",
        "এটা থামানো সম্ভব ছিল না—চার!"
    ],

    "SIX": [
        "ছক্কা! বিশাল শট!",
        "বলটা সরাসরি গ্যালারিতে!",
        "কি দারুণ পাওয়ার, ছয় রান!",
        "দর্শকরা উপভোগ করছেন, দুর্দান্ত ছক্কা!",
        "একেবারে মাঠের বাইরে পাঠিয়ে দিলেন!"
    ],

    "WICKET": [
        "আউট! বড় উইকেট পড়েছে!",
        "বোলারের দারুণ সাফল্য, ব্যাটসম্যান ফিরে যাচ্ছেন।",
        "ক্যাচ! এবং আউট!",
        "এলবিডব্লিউ! আম্পায়ার আউট দিয়েছেন!",
        "ম্যাচে বড় টার্নিং পয়েন্ট!"
    ],

    "OVER_COMPLETE": [
        "ওভার শেষ হয়েছে।",
        "এই ওভার শেষে কিছুটা চাপ তৈরি হয়েছে।",
        "ওভার সমাপ্ত, এখন স্ট্র্যাটেজি বদলাতে পারে দল।",
        "ভালো একটি ওভার শেষ করলেন বোলার।"
    ],

    "WIDE": [
        "ওয়াইড বল, অতিরিক্ত এক রান।",
        "লাইন মিস করেছেন, ওয়াইড।",
        "খুব বাইরে বল, আম্পায়ারের ইশারা—ওয়াইড।"
    ],

    "NO_BALL": [
        "নো বল! ফ্রি হিট আসছে।",
        "ওভারস্টেপ করেছেন বোলার, নো বল।",
        "এটা নো বল, ব্যাটসম্যান পেলেন সুযোগ।"
    ],

    "FREE_HIT": [
        "এটি ফ্রি হিট!",
        "ব্যাটসম্যানের জন্য বড় সুযোগ, ফ্রি হিট বল।",
        "এই বলে আউট হওয়ার ভয় নেই, ফ্রি হিট।"
    ],

    "BYE": [
        "বাই রান নেওয়া হয়েছে।",
        "উইকেটকিপার মিস করেছেন, বাই রান।",
        "ব্যাটে লাগেনি, কিন্তু রান এসেছে।"
    ],

    "LEG_BYE": [
        "লেগ বাই, একটি রান।",
        "পায়ে লেগে বল সরে গেছে, রান নেওয়া হয়েছে।",
        "ব্যাটে লাগেনি, লেগ বাই হিসেবে গণনা।"
    ],

    "WELCOME": 
        ["""কি দারুণ একটা রোমাঞ্চকর ম্যাচই না দেখলাম আমরা! 🔥
শেষ পর্যন্ত শ্বাসরুদ্ধকর লড়াইয়ের পর রাজস্থান রয়্যালস জয় তুলে নিয়েছে ৬ রানে! 🎉🏏
পুরো ম্যাচ জুড়েই ছিল টানটান উত্তেজনা।
শেষ ওভার পর্যন্ত ম্যাচের ফল অনিশ্চিত ছিল, আর সেখানেই স্নায়ুচাপ সামলে অসাধারণ পারফরম্যান্স দেখিয়েছে রাজস্থান রয়্যালস।
ব্যাটিংয়ে ভালো সংগ্রহ গড়ার পর বোলাররাও দারুণভাবে দায়িত্ব পালন করেছে।
বিশেষ করে শেষ মুহূর্তে নিয়ন্ত্রিত বোলিং — সেটাই আজ জয়ের মূল চাবিকাঠি হয়ে দাঁড়িয়েছে 👏
অন্যদিকে গুজরাট টাইটান্সও হাল ছাড়েনি।
শেষ পর্যন্ত লড়াই চালিয়ে গেছে, কিন্তু শেষ মুহূর্তে এসে মাত্র ৬ রানের জন্য থেমে যেতে হয়েছে তাদের।
আজকের এই জয় রাজস্থান রয়্যালসের আত্মবিশ্বাসকে অনেকটাই বাড়িয়ে দেবে 💪
প্রিয় দর্শক, এমন হাই-ভোল্টেজ ম্যাচ উপভোগ করার জন্য আপনাদের সবাইকে অসংখ্য ধন্যবাদ ❤️
আরও লাইভ আপডেট, কমেন্ট্রি ও বিশ্লেষণের জন্য আমাদের সাথেই থাকুন।
আবার দেখা হবে পরবর্তী ম্যাচে… ততক্ষণ পর্যন্ত ভালো থাকুন এবং ক্রিকেট উপভোগ করুন! 🏏🔥

 """,


"""কি দারুণ একটা রোমাঞ্চকর ম্যাচই না দেখলাম আমরা! 🔥
শেষ পর্যন্ত শ্বাসরুদ্ধকর লড়াইয়ের পর রাজস্থান রয়্যালস জয় তুলে নিয়েছে ৬ রানে! 🎉🏏
পুরো ম্যাচ জুড়েই ছিল টানটান উত্তেজনা।
শেষ ওভার পর্যন্ত ম্যাচের ফল অনিশ্চিত ছিল, আর সেখানেই স্নায়ুচাপ সামলে অসাধারণ পারফরম্যান্স দেখিয়েছে রাজস্থান রয়্যালস।
ব্যাটিংয়ে ভালো সংগ্রহ গড়ার পর বোলাররাও দারুণভাবে দায়িত্ব পালন করেছে।
বিশেষ করে শেষ মুহূর্তে নিয়ন্ত্রিত বোলিং — সেটাই আজ জয়ের মূল চাবিকাঠি হয়ে দাঁড়িয়েছে 👏
অন্যদিকে গুজরাট টাইটান্সও হাল ছাড়েনি।
শেষ পর্যন্ত লড়াই চালিয়ে গেছে, কিন্তু শেষ মুহূর্তে এসে মাত্র ৬ রানের জন্য থেমে যেতে হয়েছে তাদের।
আজকের এই জয় রাজস্থান রয়্যালসের আত্মবিশ্বাসকে অনেকটাই বাড়িয়ে দেবে 💪
প্রিয় দর্শক, এমন হাই-ভোল্টেজ ম্যাচ উপভোগ করার জন্য আপনাদের সবাইকে অসংখ্য ধন্যবাদ ❤️
আরও লাইভ আপডেট, কমেন্ট্রি ও বিশ্লেষণের জন্য আমাদের সাথেই থাকুন।
আবার দেখা হবে পরবর্তী ম্যাচে… ততক্ষণ পর্যন্ত ভালো থাকুন এবং ক্রিকেট উপভোগ করুন! 🏏🔥

"""
],

    "MATCH_RESULT": [
        "ম্যাচ শেষ! কি দারুণ লড়াই!",
        "খেলা শেষ, এক অসাধারণ ম্যাচের সমাপ্তি!",
        "শেষ পর্যন্ত দারুণ প্রতিদ্বন্দ্বিতা দেখলাম!",
        "এই ম্যাচটি ক্রিকেটপ্রেমীদের মনে থাকবে দীর্ঘদিন!"
    ]
}

# ---------------------------------------
# STATE
# ---------------------------------------
last_runs = None
last_wickets = None
last_over = None
last_ball = None
welcome_played = False

def parse_winning_info(text):
    """
    Extract winning result from raw text
    Example:
    'RCB won by 6 wickets'
    'India won by 25 runs'
    """

    text = text.lower()

    result = {
        "team": None,
        "type": None,   # "wickets" or "runs"
        "margin": None
    }

    # Pattern: Team won by X wickets/runs
    match = re.search(r'([a-z\s]+?) won by (\d+) (wickets|runs)', text)

    if match:
        result["team"] = match.group(1).strip().title()
        result["margin"] = int(match.group(2))
        result["type"] = match.group(3)

    return result


def generate_continuous_commentary2(events, batsmen, runs, wickets, over):
    parts = []

    # Priority events
    if "WICKET" in events:        
        line = generate_wicket_commentary(runs, wickets, over, batsmen)
        parts.append(line)

    if "SIX" in events:
        line = generate_event_commentary(events)    
        parts.append(line)

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

    # ---------------------------------------
    # BATSMAN STATUS
    # ---------------------------------------
    if batsmen and len(batsmen) >= 2:
        b1 = batsmen[0]
        b2 = batsmen[1]

        parts.append(
            f"{b1['name']} খেলছেন {b1['runs']} রান, {b2['name']} করছেন {b2['runs']} রান।"
        )

    # ---------------------------------------
    # OVER COMPLETE
    # ---------------------------------------
    if "OVER_COMPLETE" in events:
        parts.append(
            f"ওভার শেষ। স্কোর এখন {runs}-{wickets}, {over} ওভার শেষে।"
        )

    return " ".join(parts)

def num_to_bn(n):
    """Convert number to Bangla words for TTS-friendly commentary"""
    # Simple example, can be extended
    bn_digits = {
        0: "শূন্য", 1: "এক", 2: "দুই", 3: "তিন", 4: "চার",
        5: "পাঁচ", 6: "ছয়", 7: "সাত", 8: "আট", 9: "নয়", 10: "দশ"
    }
    if n in bn_digits:
        return bn_digits[n]
    return str(n)  # fallback
    
def generate_continuous_commentary2(events, batsmen, runs, wickets, over):
    """
    Generate a smooth, human-like cricket commentary for a sequence of events
    - events: list of strings (SIX, FOUR, WICKET, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, OVER_COMPLETE)
    - batsmen: list of dicts [{'name':str,'runs':int}, ...]
    - runs: total runs
    - wickets: total wickets
    - over: current over (float)
    """

    parts = []

    # 1️⃣ WICKET has highest priority
    if "WICKET" in events:
        parts.append(generate_wicket_commentary(runs, wickets, over, batsmen[0]['name'] if batsmen else None))

    # 2️⃣ Scoring events (SIX, FOUR, DOUBLE, SINGLE, DOT)
    scoring_priority = ["SIX", "FOUR", "DOUBLE", "SINGLE", "DOT"]
    for event in scoring_priority:
        if event in events:
            parts.append(generate_event_commentary([event]))
            break  # Only one scoring commentary per ball

    # 3️⃣ Extras
    for extra in ["WIDE", "NO_BALL"]:
        if extra in events:
            parts.append(generate_event_commentary([extra]))

    # 4️⃣ Batsman status
    if batsmen and len(batsmen) >= 2:
        b1 = batsmen[0]
        b2 = batsmen[1]
        parts.append(
            f"{b1['name']} এখন {num_to_bn(b1['runs'])} রান করছে, {b2['name']} করছে {num_to_bn(b2['runs'])} রান।"
        )
    elif batsmen and len(batsmen) == 1:
        b1 = batsmen[0]
        parts.append(f"{b1['name']} এখন {num_to_bn(b1['runs'])} রান করছে।")

    # 5️⃣ Over complete summary
    if "OVER_COMPLETE" in events:
        parts.append(
            f"{num_to_bn(over)} ওভার শেষ। স্কোর এখন {num_to_bn(runs)} রান, {num_to_bn(wickets)} উইকেট।"
        )

    # Combine all commentary parts naturally
    return " ".join(parts)

import random

def generate_continuous_commentary(events, batsmen, runs, wickets, over, team1=None, team2=None, context=None):
    """
    Generate a smooth, human-like cricket commentary for a sequence of events
    - events: list of strings (SIX, FOUR, WICKET, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, OVER_COMPLETE)
    - batsmen: list of dicts [{'name':str,'runs':int}, ...]
    - runs: total runs
    - wickets: total wickets
    - over: current over (float)
    - team1, team2: optional team names for updates
    """

    parts = []

    # 1️⃣ WICKET has highest priority
    if "WICKET" in events:
        parts.append(generate_wicket_commentary(runs, wickets, over, batsmen[0]['name'] if batsmen else None))

    # 2️⃣ Scoring events (SIX, FOUR, DOUBLE, SINGLE, DOT)
    scoring_priority = ["SIX", "FOUR", "DOUBLE", "SINGLE", "DOT"]
    for event in scoring_priority:
        if event in events:        
            parts.append(generate_event_commentary([event]))            
            break  # Only one scoring commentary per ball

    # 3️⃣ Extras
    for extra in ["WIDE", "NO_BALL"]:
        if extra in events:
            parts.append(generate_event_commentary([extra]))

    # 4️⃣ Batsman status
    if batsmen and len(batsmen) >= 2:
        b1 = batsmen[0]
        b2 = batsmen[1]
        parts.append(
            f"{b1['name']} এখন {num_to_bn(b1['runs'])} রান করছে, {b2['name']} করছে {num_to_bn(b2['runs'])} রান।"
        )
    elif batsmen and len(batsmen) == 1:
        b1 = batsmen[0]
        parts.append(f"{b1['name']} এখন {num_to_bn(b1['runs'])} রান করছে।")

    # 5️⃣ Over complete summary
    if "OVER_COMPLETE" in events:
        over_comment = f"{num_to_bn(over)} ওভার শেষ। স্কোর এখন {num_to_bn(runs)} রান, {num_to_bn(wickets)} উইকেট।"
        parts.append(over_comment)

        # 6️⃣ Welcome message and quick update for new viewers
        if team1 and team2:
            welcome_msg = (
                f"যারা নতুন যুক্ত হয়েছেন, স্বাগতম! "
                f"এই সময় {team1} বনাম {team2} ম্যাচে স্কোর {num_to_bn(runs)} রানে {num_to_bn(wickets)} উইকেট। "
                f"{over} ওভার শেষ হয়েছে, দলের সংগ্রহ ভালোভাবে এগুচ্ছে। ম্যাচে উত্তেজনা অব্যাহত!"
            )
            parts.append(welcome_msg)

    # Combine all commentary parts naturally
    return " ".join(parts)
    
def generate_continuous_commentary_eng(events, batsmen, runs, wickets, over, team1=None, team2=None, context=None):
    """
    Generate a smooth, human-like cricket commentary for a sequence of events
    - events: list of strings (SIX, FOUR, WICKET, DOUBLE, SINGLE, DOT, WIDE, NO_BALL, OVER_COMPLETE)
    - batsmen: list of dicts [{'name':str,'runs':int}, ...]
    - runs: total runs
    - wickets: total wickets
    - over: current over (float)
    - team1, team2: optional team names for updates
    """

    parts = []

    # 1️⃣ WICKET has highest priority
    if "WICKET" in events:
        parts.append(generate_wicket_commentary(runs, wickets, over, batsmen[0]['name'] if batsmen else None))

    # 2️⃣ Scoring events (SIX, FOUR, DOUBLE, SINGLE, DOT)
    scoring_priority = ["SIX", "FOUR", "DOUBLE", "SINGLE", "DOT"]
    for event in scoring_priority:
        if event in events:        
            parts.append(generate_event_commentary([event]))            
            break  # Only one scoring commentary per ball

    # 3️⃣ Extras
    for extra in ["WIDE", "NO_BALL"]:
        if extra in events:
            parts.append(generate_event_commentary([extra]))

    # 4️⃣ Batsman status
    if batsmen and len(batsmen) >= 2:
        b1 = batsmen[0]
        b2 = batsmen[1]
        parts.append(
            f"{b1['name']} is on {b1['runs']} runs, {b2['name']} is on {b2['runs']} runs."
        )
    elif batsmen and len(batsmen) == 1:
        b1 = batsmen[0]
        parts.append(f"{b1['name']} is on {b1['runs']} runs.")

    # 5️⃣ Over complete summary
    if "OVER_COMPLETE" in events:
        over_comment = f"End of over {over}. The score is {runs} runs for {wickets} wickets."
        parts.append(over_comment)

        # 6️⃣ Welcome message and quick update for new viewers
        if team1 and team2:
            welcome_msg = (
                f"Welcome to everyone who just joined! "
                f"In this {team1} vs {team2} match, the score is {runs} runs for {wickets} wickets. "
                f"{over} overs have been completed, the team is progressing well. The excitement continues!"
            )
            parts.append(welcome_msg)

    # Combine all commentary parts naturally
    return " ".join(parts)
# ---------------------------------------
# PARSE SCORE (ROBUST)
# ---------------------------------------

def parse_score(text):
    """
    CREX format: '47-05.1'
    Means: runs=47, wickets=0, over=5, ball=1
    Pattern: {runs}-{wickets}{over}.{ball}
    """
    match = re.search(r'(\d+)-(\d)(\d+)\.([0-5])', text)
    if not match:
        return None

    runs    = int(match.group(1))
    wickets = int(match.group(2))  # single digit: 0-9
    over    = int(match.group(3))  # remaining digits after wicket
    ball    = int(match.group(4))  # decimal part, always 0-5

    return runs, wickets, over, ball


def clean_name(name):
    """
    Remove unwanted text before actual player name
    """
    # Keep only last 2–3 words (typical cricket name)
    words = name.strip().split()
    return " ".join(words[-2:])

def remove_first_part(name):
    parts = name.split(" ", 1)
    return parts[1] if len(parts) > 1 else name
    
def parse_batsmen(text):
    """
    Extract exactly 2 batsmen (clean & accurate)
    """

    # Normalize
    text = text.replace("\r", "").strip()

    # 🔥 Remove unwanted UI text before parsing
    remove_words = [
        "Match info", "Live", "Scorecard",
        "Commentary", "Over", "Projected Score"
    ]

    for word in remove_words:
        text = text.replace(word, "")

    # 👉 Core pattern (with + separator)
    pattern = r'''
        ([A-Z][a-zA-Z\s\.]+?)\s+
        (\d+)\s+\((\d+)\)\s*
        \+\s*
        ([A-Z][a-zA-Z\s\.]+?)\s+
        (\d+)\s+\((\d+)\)
    '''

    match = re.search(pattern, text, re.VERBOSE)

    if match:
        return [
            {
                "name": remove_first_part(clean_name(match.group(1))),
                "runs": int(match.group(2)),
                "balls": int(match.group(3)),
            },
            {
                "name": remove_first_part(clean_name(match.group(4))),
                "runs": int(match.group(5)),
                "balls": int(match.group(6)),
            }
        ]

    return []
# ---------------------------------------
# GET SCORE TEXT
# ---------------------------------------
def get_score_text(page):
    """
    Try multiple selectors to get full score (runs-wickets + overs)
    """
    selectors = [
        "div[class*='innings'] span[class*='score']",  # main score element
        "div[class*='score']",                         # fallback
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        except:
            continue
    # final fallback
    try:
        return page.inner_text("body")
    except:
        return ""

# ---------------------------------------
# GET COMMENTARY
# ---------------------------------------
def get_commentary(page):
    try:
        el = page.query_selector("div[class*='commentary']")
        if el:
            return el.inner_text().lower()
    except:
        pass
    return ""

# ---------------------------------------
# DETECT EVENT
# ---------------------------------------

  
def detect_run(run_diff):
    """
    Return run-based event
    """
    if run_diff == 0:
        return "DOT"
    elif run_diff == 1:
        return "SINGLE"
    elif run_diff == 2:
        return "DOUBLE"
    elif run_diff == 3:
        return "TRIPLE"
    elif run_diff == 4:
        return "FOUR"
    elif run_diff >= 6:
        return "SIX"
    return None

def detect_wicket_advanced(text):
    if not text:
        return None

    t = text.lower()

    if "caught out" in t or "c " in t:
        return "CAUGHT"
    if "lbw" in t:
        return "LBW"
    if "bowled" in t or "b " in t:
        return "BOWLED"
    if "stumped" in t or "st " in t:
        return "STUMPED"
    if "run out" in t:
        return "RUN_OUT"
    if "hit wicket" in t:
        return "HIT_WICKET"
    if "timed out" in t:
        return "TIMED_OUT"
    if "\nw\n" in t or " out" in t:
        return "WICKET"

    return None
def detect_ball_status(runs, wickets, over, ball, commentary_text=""):
    """
    MULTI-EVENT DETECTOR (FIXED)

    Returns:
        list → ["DOUBLE", "OVER_COMPLETE"]
    """
    global last_runs, last_wickets, last_over, last_ball

    # First call
    if last_runs is None:
        last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball
        return []

    run_diff = runs - last_runs
    events = []

    same_ball = (over == last_over and ball == last_ball)
    new_ball = (over == last_over and ball != last_ball)
    over_changed = (last_over is not None and over > last_over)

    commentary_text = commentary_text.lower()

    # ---------------------------------------
    # ✅ EXTRAS FIRST (WIDE / NO BALL)
    # ---------------------------------------
    if same_ball and run_diff > 0:
        if "No ball" in commentary_text:
            events.append("NO_BALL")
        else:
            events.append("WIDE")
            

    # ---------------------------------------
    # ✅ WICKET
    # ---------------------------------------
    if wickets > last_wickets:
        detect_wicket_advanced(commentary_text)
        events.append("WICKET")

    # ---------------------------------------
    # ✅ RUN EVENT (for real ball OR last ball of over)
    # ---------------------------------------
    
    if runs > 0:
        run_event = detect_run(runs)
        if run_event:
            # avoid duplicate if already wide/no ball
            if run_event not in events:
                events.append(run_event)

    elif runs == 0 and new_ball:
        events.append("DOT")

    # ---------------------------------------
    # ✅ OVER COMPLETE (ALWAYS ADD SEPARATELY)
    # ---------------------------------------
    if over_changed:
        events.append("OVER_COMPLETE")

    # ---------------------------------------
    # UPDATE STATE
    # ---------------------------------------
    last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball

    return events
    
def detect_event(runs, wickets, over, ball, commentary_text=""):
    global last_runs, last_wickets, last_over, last_ball

    if last_runs is None:
        last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball
        return []

    events = []
    text = commentary_text.lower()

    run_diff = runs - last_runs
    wicket_diff = wickets - last_wickets

    same_ball = (over == last_over and ball == last_ball)
    new_ball = not same_ball
    over_changed = (last_over is not None and over > last_over)

    # -----------------------------
    # TEXT FLAGS
    # -----------------------------
    is_wide = "wide" in text
    is_no_ball = "no ball" in text or "no-ball" in text
    # -----------------------------
    # 🔵 OVER COMPLETE
    # -----------------------------
    if over_changed:
        events.append("OVER_COMPLETE")
        
    # -----------------------------
    # 🟥 WICKET
    # -----------------------------
    if wicket_diff > 0:
        events.append("WICKET")
    
    else:
        # -----------------------------
        # 🟡 EXTRAS (FIXED LOGIC)
        # -----------------------------
        if same_ball and run_diff > 0:

            extra_type = None

            # Priority 1: Text detection
            if is_no_ball:
                extra_type = "NO_BALL"
            elif is_wide:
                extra_type = "WIDE"

            # Priority 2: Smart fallback (🔥 NEW)
            elif run_diff >= 2:
                # Assume at least 1 extra happened
                extra_type = "WIDE"

            if extra_type:
                events.append(extra_type)
                extra_runs = run_diff - 1
            else:
                extra_runs = run_diff

            # Bat runs after extra
            if extra_runs > 0:
                run_event = detect_run(extra_runs)
                if run_event:
                    events.append(run_event)

        # -----------------------------
        # 🟢 NORMAL BALL
        # -----------------------------
        elif new_ball:
            if run_diff > 0:
                run_event = detect_run(run_diff)
                if run_event:
                    events.append(run_event)
            else:
                events.append("DOT")

    

    # remove duplicates
    events = list(dict.fromkeys(events))

    # update state
    last_runs, last_wickets, last_over, last_ball = runs, wickets, over, ball

    return events
    

    
# ---------------------------------------
# WRITE JSON
# ---------------------------------------
def write_json(runs, wickets, over, ball, event):
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "runs": runs,
                "wickets": wickets,
                "over": over,
                "ball": ball,
                "event": event,
                event: ""
            }, f, indent=4)
    except Exception as e:
        print("JSON Error:", e)


    
def batsman_commentary(batsmen):
    if len(batsmen) == 2:
        b1, b2 = batsmen
        return f"{b1['name']} {b1['runs']} রানে খেলছেন, আর {b2['name']} করেছেন {b2['runs']} রান।"
        
def game_welcome(page):
    welcome_played = False
    last_toss_text = None

    while True:
        try:
            # ---------------------------------------
            # GET FULL PAGE TEXT
            # ---------------------------------------
            text = page.inner_text("body")
            
            # ---------------------------------------
            # PARSE SCORE
            # ---------------------------------------
            score = parse_score(text)
            print("PARSED:", score)

            runs, wickets, over, ball = score
            print(runs)
            # ---------------------------------------
            # MATCH NOT STARTED
            # ---------------------------------------
            if runs == 0 and over == 0 and ball == 0:

                # First time welcome message
                if not welcome_played:
                    line = random.choice(COMMENTARY["WELCOME"])
                    speak("WELCOME", line)
                    welcome_played = True
                    time.sleep(2)

                # Get latest status line (toss / delay / players entering)
                lines = text.split("\n")
                current_status = lines[16] if len(lines) > 16 else ""

                # If new update এসেছে (avoid repeat)
                if current_status and current_status != last_toss_text:
                    commentary = pre_game_scenario_commentary(current_status)
                    
                    # Add natural flow
                    final_line = commentary + " " + random.choice(COMMENTARY["WELCOME"])
                    
                    speak("TOSS", final_line)
                    last_toss_text = current_status
                    time.sleep(2)

                continue

            # ---------------------------------------
            # MATCH STARTED → EXIT
            # ---------------------------------------
            else:
                speak("INFO", "খেলা শুরু হয়ে গেছে, এখন সরাসরি লাইভ স্কোর আপডেটে চলে যাচ্ছি!")
                break

        except Exception as e:
            print("Error in game_welcome:", e)
            time.sleep(2)
# ---------------------------------------
# ---------------------------------------
# MAIN LOOP
# ---------------------------------------

       
def main2():
    global welcome_played

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(CREX_URL)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        print("🚀 SYSTEM STARTED...")
        line = ""
        event="WELCOME"
        # ✅ Welcome (only once)
        """if not welcome_played:
            line = random.choice(COMMENTARY["WELCOME"])
            speak(event, line)
            welcome_played = True
            time.sleep(2)"""
        game_welcome(page)
        while True:
            try:
                # ---------------------------------------
                # GET FULL PAGE TEXT
                # ---------------------------------------
                text = page.inner_text("body")
                
                # ---------------------------------------
                # PARSE SCORE
                # ---------------------------------------
                score = parse_score(text)
                print("PARSED:", score)
                #print("text:", text)
                
                # Method 1: Line number
                
                lines = text.splitlines()
                """if runs <10:
                    last_status_message = lines[18]
                else:
                    last_status_message = lines[17]
                if run ==0:
                    print("HELLO")"""                    
                
                #print(lines[16].find("Toss"))
                
                #last_status_message = lines[16]
                #$print("Status", last_status_message)
                #demonstrate_toss_scenarios()
                #for i, line in enumerate(lines, start=1):                    
                #    print(f"'Event' found at line {i}: {line}")

                # Method 2: Character index
                #index = text.find("Caught Out")
                #print(f"'Caught Out' starts at character index: {index}")
                last_status_message=""
                if not score:
                    time.sleep(REFRESH_INTERVAL)                    
                    info = parse_winning_info(last_status_message)

                    line = generate_winning_commentary(
                        info["team"],
                        info["margin"],
                        info["type"]
                    )
                    speak(event, line)
                    print(line)
                    continue
               
                runs, wickets, over, ball = score
                
                if runs == 0 and over == 0 and ball == 0:
                    last_status_message = lines[16]                    
                    line = pre_game_scenario_commentary(last_status_message) + random.choice(COMMENTARY["WELCOME"])
                    event ="TOSS"
                    time.sleep(2)
                else :
                    if "CRR" in lines[17]:                                                     
                        last_status_message = lines[16]
                    else : 
                        last_status_message = lines[17]
                    print(last_status_message)
                    
                    status = detect_game_status(last_status_message)
                    
                    print(f"Status: {status['status']}")
                    if status['details']:
                            print(f"📊 Details: {status['details']}")
                    print("-" * 70)
                    # ---------------------------------------
                    # PARSE BATSMEN
                    # ---------------------------------------
                    batsmen = parse_batsmen(text)

                    # Debug
                    """for b in batsmen:
                        print("Batsman:", b)"""

                    # ---------------------------------------
                    # DETECT EVENTS
                    # ---------------------------------------
                    events = detect_event(runs, wickets, over, ball, last_status_message)                
                    #commentary = generate_toss_commentary("LSG", "bat", is_win=True)
                    #print(commentary)
                    
                    if not events:
                        time.sleep(REFRESH_INTERVAL)
                        continue

                    print("EVENTS:", events)

                    # ---------------------------------------
                    # GENERATE NATURAL COMMENTARY
                    # ---------------------------------------
                    line = generate_continuous_commentary(
                        events,
                        batsmen,
                        runs,
                        wickets,
                        over,
                        "A",
                        "B",
                        last_status_message
                    )
                    event = events[0]                   
                    
                    
                    #    if status['details']:
                    #        print(f"Details: {status['details']}")
                    #    print("-" * 50)
                #print("🎙 FINAL:", line)
                # ---------------------------------------
                # OUTPUT
                # ---------------------------------------
                if line:
                    print("🎙 FINAL:", line)

                    # Save last main event
                    write_json(runs, wickets, over, ball, event)
                    print(event)
                    # Speak once (IMPORTANT FIX ✅)
                    speak(event, line)
                    

            except Exception as e:
                print("MAIN ERROR:", e)

            time.sleep(REFRESH_INTERVAL)
            
def get_match_status2(data_list):
    text = " ".join(str(item).lower() for item in data_list)

    # ✅ Detect score (MANDATORY for LIVE)
    score_pattern = re.search(r"\b\d{1,3}/\d{1,2}\b", text)
    over_pattern = re.search(r"\b\d{1,2}\.\d\b", text)

    # ✅ Detect future/scheduled signals
    if "tomorrow" in text:
        return "NOT_STARTED"

    if re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)\b", text) and not score_pattern:
        return "NOT_STARTED"

    # ✅ Explicit not started text
    if any(k in text for k in [
        "hasn't started", "yet to start", "starting soon"
    ]):
        return "NOT_STARTED"

    # ✅ Finished match
    if any(k in text for k in [
        "won by", "match ended", "result", "defeated"
    ]):
        return "FINISHED"

    # ✅ LIVE (STRICT CONDITION)
    if score_pattern and over_pattern:
        return "LIVE"

    # ✅ FALLBACK (IMPORTANT FIX)
    # If NO score at all → NOT_STARTED
    if not score_pattern:
        return "NOT_STARTED"

    return "UNKNOWN"



def main():
    global welcome_played

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(CREX_URL)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)

        print("🚀 SYSTEM STARTED...")
        text = page.inner_text("body")                
                
        lines = text.splitlines()        
        status = detect_game_status(lines)
        
        print(f"📊 Current Status: {status}")
        
        # ========== INTELLIGENT STATUS HANDLING ==========
        
        # 1. Match Abandoned - Exit immediately
        if "Abandoned" in status:
            print("❌ Match has been ABANDONED. Exiting...")
            browser.close()
            sys.exit(0)
        
        # 2. Suspended/Deferred - Exit with message
        if "Suspended" in status or "Deferred" in status:
            print(f"⏸️ Match is {status}. Exiting...")
            browser.close()
            sys.exit(0)
        
        # 3. Completed - Show result and exit
        if "Completed" in status:
            result_text = status.replace("Completed - ", "")
            print(f"🏆 MATCH FINISHED! {result_text}")
            print("✅ Exiting...")
            browser.close()
            sys.exit(0)
        
        # 4. Tomorrow - Exit with scheduling info
        if "Tomorrow" in status:
            print(f"📅 Match is scheduled for {status}. Script will exit. Run again tomorrow.")
            browser.close()
            sys.exit(0)
        
        # 5. Today at specific time
        if "Today at" in status:
            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:AM|PM))', status)
            if time_match:
                match_time_str = time_match.group(1)
                now = datetime.now()
                match_time = datetime.strptime(match_time_str, "%I:%M %p")
                match_time = now.replace(hour=match_time.hour, minute=match_time.minute, second=0, microsecond=0)
                
                if now > match_time:
                    print(f"⏰ Match scheduled at {match_time_str} should have started. Checking again...")
                    page.reload()
                    page.wait_for_timeout(2000)
                    text = page.inner_text("body")
                    lines = text.splitlines()
                    status = detect_game_status(lines)
                    print(f"📊 Updated Status: {status}")
                    
                    if "Live" in status:
                        print("🎯 Match is LIVE! Starting main loop...")
                    elif "Completed" in status:
                        result_text = status.replace("Completed - ", "")
                        print(f"🏆 Match already finished! {result_text}")
                        browser.close()
                        sys.exit(0)
                    else:
                        print(f"ℹ️ Match status is '{status}'. Exiting.")
                        browser.close()
                        sys.exit(0)
                else:
                    wait_seconds = (match_time - now).total_seconds()
                    if wait_seconds > 3600:
                        print(f"📅 Match starts at {match_time_str}. Script will exit. Run closer to match time.")
                        browser.close()
                        sys.exit(0)
                    else:
                        print(f"⏳ Match starts at {match_time_str}. Waiting {wait_seconds/60:.1f} minutes...")
                        time.sleep(wait_seconds)
                        page.reload()
                        page.wait_for_timeout(2000)
                        text = page.inner_text("body")
                        lines = text.splitlines()
                        status = detect_game_status(lines)
                        print(f"📊 Updated Status: {status}")
        
        # 6. "Today" without time or "Scheduled" - Exit
        if "Today" in status and "at" not in status:
            print("📅 Match is scheduled for today but no specific time found. Exiting. Run manually when match starts.")
            browser.close()
            sys.exit(0)
        
        if "Scheduled" in status:
            print("📅 Match is scheduled but not started yet. Exiting. Run closer to match time.")
            browser.close()
            sys.exit(0)
        
        # 7. "Yet to Start" - Wait for toss/live
        if "Yet to Start" in status:
            print("🟡 Match yet to start. Waiting for toss/live signal...")
            max_wait_time = 7200
            start_wait = time.time()
            
            while True:
                time.sleep(30)
                page.reload()
                page.wait_for_timeout(2000)
                text = page.inner_text("body")
                lines = text.splitlines()
                new_status = detect_game_status(lines)
                print(f"🔄 Re-check: {new_status}")
                
                if "Live" in new_status:
                    status = new_status
                    print("🎯 Match is now LIVE! Proceeding...")
                    break
                elif "Completed" in new_status:
                    result_text = new_status.replace("Completed - ", "")
                    print(f"🏆 Match already finished! {result_text}")
                    browser.close()
                    sys.exit(0)
                elif "Abandoned" in new_status or "Suspended" in new_status:
                    print(f"❌ Match {new_status}. Exiting.")
                    browser.close()
                    sys.exit(0)
                elif time.time() - start_wait > max_wait_time:
                    print("⏰ Max wait time exceeded. Match didn't start. Exiting.")
                    browser.close()
                    sys.exit(0)
        
        # 8. LIVE MATCH - Main continuous loop with break handling
        if "Live" in status or "Break" in status:
            print("🎬 MATCH IS LIVE! Starting continuous monitoring...")
            print("   Will detect and handle Drinks/Innings breaks automatically")
            print("   Will detect when match finishes with result")
            print("Press Ctrl+C to stop\n")
            
            refresh_interval = 15
            last_data_hash = None
            
            try:
                while True:
                    page.reload()
                    page.wait_for_timeout(2000)
                    text = page.inner_text("body")
                    lines = text.splitlines()
                    
                    current_status = detect_game_status(lines)
                    
                    # Check for completed match with result FIRST
                    if "Completed" in current_status:
                        result_text = current_status.replace("Completed - ", "")
                        print(f"\n{'='*60}")
                        print(f"🏆 MATCH FINISHED! {result_text}")
                        print(f"{'='*60}")
                        print("✅ Exiting...")
                        break
                    
                    # Handle breaks
                    elif "Break" in current_status:
                        print(f"\n{'='*50}")
                        print(f"⏸️ BREAK DETECTED: {current_status}")
                        print(f"{'='*50}")
                        
                        new_status = handle_break_period(current_status, page, browser)
                        
                        if new_status == "Live":
                            current_status = new_status
                            print(f"\n🎬 Match resumed! Continuing monitoring...\n")
                            continue
                        elif "Completed" in new_status:
                            result_text = new_status.replace("Completed - ", "")
                            print(f"\n🏆 MATCH FINISHED! {result_text}")
                            break
                        else:                            
                            if new_status ==  "Innings Break":                                
                                print(f"Match status after break: {new_status}")                                                            
                                
                            else:
                                print(f"Match status after break: {new_status}")                            
                            break
                    
                    # Check if match is no longer live
                    elif "Abandoned" in current_status:
                        print("\n❌ MATCH ABANDONED! Exiting...")
                        break
                    elif "Suspended" in current_status:
                        print("\n⏸️ MATCH SUSPENDED! Exiting...")
                        break
                    
                    # Extract match data for live matches
                    if "Live" in current_status:
                        #score_data = extract_match_data(lines)
                        score_data = parse_score(text)
                        print("PARSED:", score_data)
                        runs, wickets, over, ball = score_data
                        
                        # ---------------------------------------
                        # PARSE EACH BALL STATUS
                        # ---------------------------------------
                        last_status_message =""
                        if "CRR" in lines[17]:                                                     
                            last_status_message = lines[16]
                        else : 
                            last_status_message = lines[17]
                        print(last_status_message)
                        
                        # ---------------------------------------
                        # PARSE BATSMEN
                        # ---------------------------------------
                        batsmen = parse_batsmen(text)
                        
                        status = detect_game_status(last_status_message)
                        
                        # ---------------------------------------
                        # DETECT EVENTS
                        # ---------------------------------------
                        events = detect_event(runs, wickets, over, ball, last_status_message) 
                        
                        if not events:
                            #time.sleep(REFRESH_INTERVAL)
                            continue

                        print("EVENTS:", events)

                        # ---------------------------------------
                        # GENERATE NATURAL COMMENTARY
                        # ---------------------------------------
                        line = generate_continuous_commentary(
                            events,
                            batsmen,
                            runs,
                            wickets,
                            over,
                            "Sri Lanka",
                            "New Zealand",
                            last_status_message
                        )
                        event = events[0]
                        print(event)
                        print("🎙 FINAL:", line)
                        # ---------------------------------------
                        # OUTPUT
                        # ---------------------------------------
                        if line:
                            print("🎙 FINAL:", line)

                            # Save last main event
                            write_json(runs, wickets, over, ball, event)
                            print(event)
                            # Speak once (IMPORTANT FIX ✅)
                            speak(event, line)
                        import hashlib
                        data_hash = hashlib.md5(str(score_data).encode()).hexdigest()
                        if data_hash != last_data_hash:
                            prefix = "🏏"
                            print(f"{prefix} [{datetime.now().strftime('%H:%M:%S')}] {score_data}")
                            last_data_hash = data_hash
                        
                    time.sleep(refresh_interval)
                    
            except KeyboardInterrupt:
                print("\n👋 Manual stop requested. Exiting gracefully...")
        
        # 9. Unknown status
        if "Unknown" in status:
            print("⚠️ Could not determine match status. Exiting.")
            browser.close()
            sys.exit(0)
        
        browser.close()

def extract_match_data(lines):
    """
    Extract relevant match data from page lines.
    """
    score_info = []
    
    for i, line in enumerate(lines):
        if isinstance(line, str):
            # Check for score like "189/8" or "127-4"
            if re.search(r'\d{1,3}/\d{1,2}', line) or re.search(r'\d{1,3}-\d{1,2}', line):
                score_info.append(line)
            
            # Check for overs
            if re.search(r'\d{1,2}\.\d{1,2}\s*overs?', line.lower()):
                score_info.append(line)
            
            # Check for run rate
            if "run rate" in line.lower():
                score_info.append(line)
    
    if score_info:
        return ' | '.join(score_info[:3])
    
    return "Match in progress..."

if __name__ == "__main__":
    main()
    