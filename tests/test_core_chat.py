"""Tests for core OpenClaw chat client."""

from __future__ import annotations

import asyncio
import json

import pytest

from clawrium.core.chat import (
    ChatAuthenticationError,
    OpenClawChatClient,
)


class FakeWebSocket:
    """Deterministic fake websocket for request/response testing."""

    def __init__(self, frames: list[dict]):
        self._frames = [json.dumps(frame) for frame in frames]
        self.sent: list[dict] = []
        self.closed = False

    async def recv(self) -> str:
        if not self._frames:
            raise RuntimeError("No more frames")
        return self._frames.pop(0)

    async def send(self, data: str) -> None:
        self.sent.append(json.loads(data))

    async def close(self) -> None:
        self.closed = True


def test_connect_success(monkeypatch):
    frames = [
        {
            "type": "event",
            "event": "connect.challenge",
            "payload": {"nonce": "abc123", "ts": 1234},
        },
        {
            "type": "res",
            "id": "1",
            "ok": True,
            "payload": {"type": "hello-ok", "protocol": 3},
        },
    ]
    fake_ws = FakeWebSocket(frames)

    async def fake_connect(*args, **kwargs):
        return fake_ws

    monkeypatch.setattr("clawrium.core.chat.websockets.connect", fake_connect)

    client = OpenClawChatClient("ws://test-host:40123", "secret-token")
    asyncio.run(client.connect())

    assert len(fake_ws.sent) == 1
    req = fake_ws.sent[0]
    assert req["method"] == "connect"
    assert req["params"]["auth"]["token"] == "secret-token"


def test_send_message_streams_and_returns_final(monkeypatch):
    frames = [
        {
            "type": "event",
            "event": "connect.challenge",
            "payload": {"nonce": "abc123", "ts": 1234},
        },
        {
            "type": "res",
            "id": "1",
            "ok": True,
            "payload": {"type": "hello-ok", "protocol": 3},
        },
        {"type": "res", "id": "2", "ok": True, "payload": {"runId": "run-42"}},
        {
            "type": "event",
            "event": "chat",
            "payload": {"runId": "run-42", "state": "delta", "delta": "Hello"},
        },
        {
            "type": "event",
            "event": "chat",
            "payload": {
                "runId": "run-42",
                "state": "final",
                "message": {"content": "Hello from assistant"},
            },
        },
    ]
    fake_ws = FakeWebSocket(frames)

    async def fake_connect(*args, **kwargs):
        return fake_ws

    monkeypatch.setattr("clawrium.core.chat.websockets.connect", fake_connect)

    client = OpenClawChatClient("ws://test-host:40123", "secret-token")
    asyncio.run(client.connect())

    chunks: list[str] = []
    result = asyncio.run(client.send_message("hello", "main", on_delta=chunks.append))

    assert "Hello" in chunks
    assert result == "Hello from assistant"
    assert fake_ws.sent[1]["method"] == "chat.send"
    assert fake_ws.sent[1]["params"]["message"] == "hello"


def test_connect_raises_auth_error(monkeypatch):
    frames = [
        {
            "type": "event",
            "event": "connect.challenge",
            "payload": {"nonce": "abc123", "ts": 1234},
        },
        {
            "type": "res",
            "id": "1",
            "ok": False,
            "error": {"message": "unauthorized"},
        },
    ]
    fake_ws = FakeWebSocket(frames)

    async def fake_connect(*args, **kwargs):
        return fake_ws

    monkeypatch.setattr("clawrium.core.chat.websockets.connect", fake_connect)

    client = OpenClawChatClient("ws://test-host:40123", "bad-token")
    with pytest.raises(ChatAuthenticationError):
        asyncio.run(client.connect())
