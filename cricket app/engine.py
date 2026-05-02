import asyncio
import random
from state import MATCH
from ws_manager import push

def play_ball():
    return random.choice(["0", "1", "2", "4", "6", "W"])

async def engine():
    while True:
        if not MATCH["running"]:
            await asyncio.sleep(1)
            continue

        ball = play_ball()

        runs, wickets = map(int, MATCH["score"].split("/"))

        if ball == "W":
            wickets += 1
        else:
            runs += int(ball)

        MATCH["score"] = f"{runs}/{wickets}"

        over, b = map(int, MATCH["overs"].split("."))
        b += 1
        if b == 6:
            over += 1
            b = 0

        MATCH["overs"] = f"{over}.{b}"

        MATCH["this_over"].append(ball)
        if len(MATCH["this_over"]) > 6:
            MATCH["this_over"].pop(0)

        await push(MATCH)

        await asyncio.sleep(1.5)