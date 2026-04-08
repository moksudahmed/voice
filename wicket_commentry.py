import random

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
def generate_wicket_commentary2(runs, wickets, over, batsman=None):
    """
    Smart Bangla wicket commentary
    - Avoids symbols like '/'
    - Converts numbers to words
    - More natural speech flow
    """

    runs_bn = num_to_bn(runs)
    wickets_bn = num_to_bn(wickets)
    over_bn = str(over)  # keep decimal natural (TTS reads better)

    name_part = f"{batsman} ফিরে যাচ্ছেন। " if batsman else ""

    # 🎯 Normal commentary
    templates = [
        f"আউট! {name_part}দলের রান এখন {runs_bn}, উইকেট {wickets_bn}টি, {over_bn} ওভারে বড় ধাক্কা।",
        f"উইকেট পড়ে গেছে! {name_part}{over_bn} ওভারে দল করেছে {runs_bn} রান, হারিয়েছে {wickets_bn} উইকেট।",
        f"এবং আউট! {name_part}স্কোর এখন {runs_bn} রান, {wickets_bn} উইকেট, ম্যাচে নতুন মোড়।",
        f"বড় উইকেট! {name_part}{runs_bn} রানে {wickets_bn} উইকেট, চাপ বাড়ছে।",
        f"উইকেট! {name_part}এই মুহূর্তে দলের সংগ্রহ {runs_bn} রান, {wickets_bn} উইকেট।",
    ]

    # 🔥 Pressure situation
    pressure_templates = [
        f"বড় ধাক্কা! {name_part}{runs_bn} রানে {wickets_bn} উইকেট, দল কিছুটা চাপে।",
        f"গুরুত্বপূর্ণ উইকেট! {name_part}{over_bn} ওভারে {runs_bn} রান, {wickets_bn} উইকেট — ম্যাচ জমে উঠছে।",
        f"এই উইকেট ম্যাচের মোড় ঘুরিয়ে দিতে পারে! {runs_bn} রান, {wickets_bn} উইকেট।",
    ]

    # 🚨 Collapse situation
    collapse_templates = [
        f"একের পর এক উইকেট! {runs_bn} রানে {wickets_bn} উইকেট, দল বিপদে।",
        f"ব্যাটিং ধস! {runs_bn} রান, {wickets_bn} উইকেট — পরিস্থিতি কঠিন হয়ে যাচ্ছে।",
        f"চাপ বাড়ছেই! {runs_bn} রানে {wickets_bn} উইকেট পড়ে গেছে।",
    ]

    # 🎲 Smart selection logic
    if wickets >= 6:
        return random.choice(collapse_templates)

    if wickets >= 4 and random.random() > 0.5:
        return random.choice(pressure_templates)

    return random.choice(templates)
    
def generate_wicket_commentary(runs, wickets, over, batsman=None):
    """
    Long, natural Bangla wicket commentary
    - No symbols like '/'
    - Human-like flow (2–3 sentences)
    - Context-aware (normal / pressure / collapse)
    """

    runs_bn = num_to_bn(runs)
    wickets_bn = num_to_bn(wickets)
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
