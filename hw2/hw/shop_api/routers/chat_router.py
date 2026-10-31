from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
rooms: dict[str, set[WebSocket]] = {}


@router.websocket("/chat/{chat_name}")
async def chat(websocket: WebSocket, chat_name: str) -> None:
    await websocket.accept()
    username = f"user_{uuid4().hex}"
    room = rooms.setdefault(chat_name, set())
    room.add(websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") is None:
                await websocket.close(code=1003, reason="Only text messages are supported")
                break
            text = f"{username} :: {message['text']}"
            for member in tuple(room):
                if member is websocket:
                    continue
                try:
                    await member.send_text(text)
                except (WebSocketDisconnect, RuntimeError):
                    room.discard(member)
    finally:
        room.discard(websocket)
        if not room and rooms.get(chat_name) is room:
            del rooms[chat_name]
