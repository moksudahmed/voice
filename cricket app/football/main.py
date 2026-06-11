from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import requests

app = FastAPI()

API_TOKEN = "0f9ae9ea357046c788ad0c4c54499754"
URL = "https://api.football-data.org/v4/matches"

app.mount("/static", StaticFiles(directory="static"), name="static")


def fetch_match():
    try:
        headers = {"X-Auth-Token": API_TOKEN}
        res = requests.get(URL, headers=headers, timeout=10)

        # ---------------------------
        # 1. CHECK HTTP STATUS
        # ---------------------------
        if res.status_code != 200:
            return {
                "error": True,
                "message": "API request failed",
                "status_code": res.status_code,
                "raw": res.text
            }

        data = res.json()

        # ---------------------------
        # 2. SAFE MATCH CHECK
        # ---------------------------
        matches = data.get("matches", [])

        if not matches:
            return {
                "error": True,
                "message": "No matches available",
                "data": data
            }

        match = matches[0]

        # ---------------------------
        # 3. SAFE SCORE HANDLING
        # ---------------------------
        score = match.get("score", {}).get("fullTime", {})

        return {
            "error": False,

            "competition": match["competition"]["name"],
            "group": match.get("group"),
            "status": match["status"],

            "home": match["homeTeam"]["tla"],
            "away": match["awayTeam"]["tla"],

            "home_name": match["homeTeam"]["name"],
            "away_name": match["awayTeam"]["name"],

            "home_score": score.get("home") or 0,
            "away_score": score.get("away") or 0,

            "utcDate": match["utcDate"]
        }

    except Exception as e:
        return {
            "error": True,
            "message": str(e)
        }


@app.get("/api/match")
def get_match():
    return fetch_match()


@app.get("/api/match-status")
def match_status():
    return fetch_match()


@app.get("/api/matches")
def matches():
    return {"matches": [fetch_match()]}