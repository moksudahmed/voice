last_version = -1

async def broadcaster():

    global last_version

    while True:

        if STATE["version"] != last_version:

            last_version = STATE["version"]

            await manager.broadcast(STATE)

        await asyncio.sleep(0.05)