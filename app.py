import queue

import anyio
import anyio.streams
import json

from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from mdclient import MdClient
from tdclient import TdClient


html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            var ws = new WebSocket(`ws://192.168.0.188:8000/ws/${client_id}`);
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)


class MdService:
    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._queue = queue.Queue()
        self._client = MdClient()
        self._connection_manager: ConnectionManager = connection_manager
        self._running = False

    def on_tick_data(self, data: dict[str, any]) -> None:
        self._queue.put_nowait(data)

    async def start(self) -> None:
        self._client.registerDepthMarketDataCallback(self.on_tick_data)
        await anyio.to_thread.run_sync(self._client.connect)
        while not self._client.ready:
            await anyio.sleep(1.0)

        await anyio.to_thread.run_sync(self._client.subscribe, [b"ag2306"])
        self._running = True
        while self._running:
            try:
                data = await anyio.to_thread.run_sync(self._queue.get, True, 1)
                if data:
                    await self._connection_manager.broadcast(json.dumps(data))
            except queue.Empty:
                pass
    
    async def stop(self) -> None:
        print("stop the md service")
        self._running = False
        await anyio.to_thread.run_sync(self._client.disconnect)


class TdService:
    def __init__(self, connection_manager: ConnectionManager) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._client: TdClient = TdClient()
        self._connection_manager: ConnectionManager = connection_manager
        self._running: bool = False
    
    def on_order(self, data: dict[str, any]) -> None:
        self._queue.put_nowait(data)
    
    def on_trade(self, data: dict[str, any]) -> None:
        self._queue.put_nowait(data)
    
    async def start(self, userConfig) -> None:
        self._client.registerOrderCallback(self.on_order)
        self._client.registerTrdeCallback(self.on_trade)
        self._client.setUserConfig(userConfig)

        await anyio.to_thread.run_sync(self._client.connect)
        while not self._client.ready and not self._client.error:
            await anyio.sleep(1.0)
        
        if self._client.error:
            print("td login error, return")
            return None
        
        self._running = True
        while self._running:
            print(f"td running = {self._running}")
            try:
                data = await anyio.to_thread.run_sync(self._queue.get, True, 3)
                if data:
                    await self._connection_manager.broadcast(json.dumps(data))
            except queue.Empty:
                pass
    
    async def stop(self) -> None:
        print("stop the td service")
        self._running = False
        await anyio.to_thread.run_sync(self._client.disconnect)


manager = ConnectionManager()
md_service = MdService(manager)
td_service = TdService(manager)

# @asynccontextmanager
# async def lifespan(_app: FastAPI):
#     print("called before yield")
#     yield
#     print("called after yield")
#     await md_service.stop()
# 
# app = FastAPI(lifespan=lifespan)
app = FastAPI()

@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: int):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"You wrote: {data}", websocket)
            await manager.broadcast(f"Client #{client_id} says: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        await manager.broadcast(f"Client #{client_id} left the chat")
