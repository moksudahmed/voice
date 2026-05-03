import time

CACHE = {
    "data": None,
    "ts": 0
}

CACHE_TTL = 2  # seconds


def fetch_live_score():
    """
    Stable fake/live hybrid data source.
    Replace later with real API.
    """

    # simple cache (prevents spam + crashes)
    if time.time() - CACHE["ts"] < CACHE_TTL:
        return CACHE["data"]

    data = {
        "team_a": "BAN",
        "team_b": "NZ",
        "score": "156/5",
        "overs": "17.2",
        "status": "LIVE",
        "run_rate": 9.1
    }

    CACHE["data"] = data
    CACHE["ts"] = time.time()

    return data