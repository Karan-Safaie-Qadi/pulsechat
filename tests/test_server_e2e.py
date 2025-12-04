"""End-to-end test: real TCP connections against a running server."""

import asyncio
import json

import pytest

from pulsechat.config import Settings
from pulsechat.server import ChatServer


class Client:
    """Tiny test client speaking the wire protocol."""

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

    async def send(self, payload):
        self.writer.write((json.dumps(payload) + "\n").encode())
        await self.writer.drain()

    async def recv(self, timeout=3.0):
        line = await asyncio.wait_for(self.reader.readline(), timeout)
        if not line:
            return None
        return json.loads(line)

    async def collect_until(self, wanted_type, timeout=3.0, max_frames=50):
        """Read frames until one of `wanted_type` arrives; return the list."""
        seen = []
        for _ in range(max_frames):
            frame = await self.recv(timeout)
            if frame is None:
                break
            seen.append(frame)
            if frame.get("type") == wanted_type:
                return seen
        return seen


async def _run_scenario(tmp_path):
    settings = Settings(
        host="127.0.0.1",
        port=0,  # OS picks a free port
        data_dir=tmp_path / "transcripts",
    )
    server = ChatServer(settings)
    await server.start()
    port = server._server.sockets[0].getsockname()[1]

    async def chat():
        a_reader, a_writer = await asyncio.open_connection("127.0.0.1", port)
        b_reader, b_writer = await asyncio.open_connection("127.0.0.1", port)
        a = Client(a_reader, a_writer)
        b = Client(b_reader, b_writer)

        await a.send({"type": "register", "name": "ali"})
        await a.recv()
        await b.send({"type": "register", "name": "sara"})
        await b.recv()

        await a.send({"type": "join", "room": "general"})
        await a.recv()
        await b.send({"type": "join", "room": "general"})
        await b.recv()
        await a.collect_until("presence")  # b's join announcement

        await a.send({"type": "msg", "room": "general", "text": "salam sara"})
        # the echo of our own message may arrive before the ack
        first = await a.recv()
        if first["type"] == "msg":
            first = await a.recv()
        assert first["type"] == "ok", first
        delivered = await b.recv()
        assert delivered["type"] == "msg", delivered
        assert delivered["from"] == "ali"
        assert delivered["text"] == "salam sara"

        await a.send({"type": "priv", "to": "sara", "text": "psst"})
        await a.recv()
        priv = await b.recv()
        assert priv["type"] == "priv", priv
        assert priv["text"] == "psst"

        await a.send({"type": "who", "room": "general"})
        roster = await a.recv()
        assert sorted(roster["members"]) == ["ali", "sara"]

        # error path: unknown user
        await a.send({"type": "priv", "to": "ghost", "text": "?"})
        err = await a.recv()
        assert err["type"] == "error"
        assert err["code"] == "no_such_user"

        # bad json gets a clean error, connection survives
        a.writer.write(b"{oops\n")
        await a.writer.drain()
        err2 = await a.recv()
        assert err2["type"] == "error"
        assert err2["code"] == "bad_json"

        await a.send({"type": "ping"})
        pong = await a.recv()
        assert pong["type"] == "pong"

        a_writer.close()
        b_writer.close()
        return True

    try:
        return await asyncio.wait_for(chat(), timeout=15)
    finally:
        await server.stop()


def test_two_clients_chat(tmp_path):
    assert asyncio.run(_run_scenario(tmp_path))


def test_transcript_written(tmp_path):
    asyncio.run(_run_scenario(tmp_path))
    files = list((tmp_path / "transcripts").rglob("*.jsonl"))
    assert files, "expected a transcript file"


def test_bot_population_runs(tmp_path):
    async def scenario():
        settings = Settings(host="127.0.0.1", port=0, data_dir=tmp_path / "t2")
        server = ChatServer(settings)
        await server.start(with_bots=4)
        port = server._server.sockets[0].getsockname()[1]
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        c = Client(reader, writer)
        await c.send({"type": "register", "name": "observer"})
        await c.recv()
        await c.send({"type": "join", "room": "general"})
        await c.recv()
        # bots are active; within a while we should overhear at least one msg
        seen = await c.collect_until("msg", timeout=12.0)
        await server.stop()
        return any(f.get("type") == "msg" for f in seen)

    assert asyncio.run(scenario())





















































