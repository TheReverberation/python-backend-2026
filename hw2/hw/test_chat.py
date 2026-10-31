from importlib import import_module
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from shop_api.main import app

chat_module = import_module("shop_api.routers.chat_router")


@pytest.fixture
def chat_client():
    with TestClient(app) as client:
        yield client
    assert chat_module.rooms == {}


@pytest.mark.parametrize("message", ["hello", "Привет 👋", "", "one :: two\nthree"])
def test_broadcast_and_no_echo(chat_client, message):
    room = uuid4().hex
    with (
        chat_client.websocket_connect(f"/chat/{room}") as first,
        chat_client.websocket_connect(f"/chat/{room}") as second,
        chat_client.websocket_connect(f"/chat/{room}") as third,
    ):
        third.send_text("ready")
        first.receive_text()
        second.receive_text()
        first.send_text(message)
        received = second.receive_text()
        assert third.receive_text() == received
        username, separator, body = received.partition(" :: ")
        assert separator == " :: "
        assert body == message
        assert UUID(username.removeprefix("user_")).version == 4

        second.send_text("reply")
        reply = first.receive_text()
        assert reply.endswith(" :: reply") 
        assert third.receive_text() == reply
        assert reply.partition(" :: ")[0] != username

        first.send_text("again")
        assert second.receive_text() == f"{username} :: again"
        assert third.receive_text() == f"{username} :: again"


def test_rooms_are_isolated(chat_client):
    with (
        chat_client.websocket_connect("/chat/alpha") as alpha1,
        chat_client.websocket_connect("/chat/alpha") as alpha2,
        chat_client.websocket_connect("/chat/beta") as beta1,
        chat_client.websocket_connect("/chat/beta") as beta2,
    ):
        alpha2.send_text("alpha-ready")
        assert alpha1.receive_text().endswith(" :: alpha-ready")
        beta2.send_text("beta-ready")
        assert beta1.receive_text().endswith(" :: beta-ready")

        alpha1.send_text("alpha-secret")
        assert alpha2.receive_text().endswith(" :: alpha-secret")
        beta1.send_text("beta-secret")
        assert beta2.receive_text().endswith(" :: beta-secret")
        beta2.send_text("beta-reply")
        assert beta1.receive_text().endswith(" :: beta-reply")
        alpha2.send_text("alpha-reply")
        assert alpha1.receive_text().endswith(" :: alpha-reply")


def test_disconnect_and_reconnect(chat_client):
    path = "/chat/reconnect"
    with chat_client.websocket_connect(path) as first:
        with chat_client.websocket_connect(path) as second:
            second.send_text("before")
            old_name = first.receive_text().partition(" :: ")[0]
        with chat_client.websocket_connect(path) as replacement:
            replacement.send_text("after")
            message = first.receive_text()
            assert message.endswith(" :: after")
            assert message.partition(" :: ")[0] != old_name
            first.send_text("welcome")
            assert replacement.receive_text().endswith(" :: welcome")
    assert "reconnect" not in chat_module.rooms
    with chat_client.websocket_connect(path) as first:
        with chat_client.websocket_connect(path) as second:
            second.send_text("new room")
            assert first.receive_text().endswith(" :: new room")


def test_binary_message_is_rejected(chat_client):
    with chat_client.websocket_connect("/chat/binary") as websocket:
        websocket.send_bytes(b"not text")
        with pytest.raises(WebSocketDisconnect) as error:
            websocket.receive_text()
        assert error.value.code == 1003


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [WebSocketDisconnect(), RuntimeError("Already closed")])
async def test_disconnected_recipient_does_not_interrupt_broadcast(error):
    sender, disconnected, receiver = AsyncMock(), AsyncMock(), AsyncMock()
    sender.receive.side_effect = [
        {"type": "websocket.receive", "text": "hello"},
        {"type": "websocket.disconnect"},
    ]
    disconnected.send_text.side_effect = error
    room = {disconnected, receiver}
    chat_module.rooms["failed-send"] = room
    try:
        await chat_module.chat(sender, "failed-send")
        receiver.send_text.assert_awaited_once()
        assert receiver.send_text.call_args.args[0].endswith(" :: hello")
        assert room == {receiver}
    finally:
        chat_module.rooms.pop("failed-send", None)
