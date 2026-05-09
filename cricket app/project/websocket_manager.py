from fastapi import WebSocket

class ConnectionManager:

    def __init__(self):
        self.clients = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.clients.append(websocket)

    def disconnect(self, websocket):
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def broadcast(self, data):
        dead = []

        for ws in self.clients:
            try:
                await ws.send_json(data)
            except:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()