import requests
from bs4 import BeautifulSoup
import re

def scrape_match_data(url: str):
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        text = soup.get_text(" ", strip=True)

        score = "0/0"
        match = re.search(r"\d{1,3}[/\-]\d{1,2}", text)
        if match:
            score = match.group(0).replace("-", "/")

        overs = "0.0"
        over_match = re.search(r"\d{1,2}\.\d", text)
        if over_match:
            overs = over_match.group(0)

        ball = "0"
        boxes = soup.find_all("div", class_="result-box")
        if boxes:
            last = boxes[-1]
            span = last.find("span", class_="font1")
            if span:
                ball = span.text.strip()

        return {"score": score, "overs": overs, "ball": ball}

    except Exception as e:
        print("SCRAPE ERROR:", e)
        return None