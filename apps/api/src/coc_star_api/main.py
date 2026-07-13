from fastapi import FastAPI, WebSocket

app = FastAPI(title="coc-star API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "coc-star-api"}


@app.websocket("/ws/rooms/{room_id}")
async def room_socket(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "room.connected", "room_id": room_id})
    await websocket.close()

