clients = set()

async def push(data):
    dead = set()

    for ws in clients.copy():
        try:
            await ws.send_json(data)
        except:
            dead.add(ws)

    for d in dead:
        clients.discard(d)