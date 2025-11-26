"""The asyncio TCP server that ties everything together.

One task per client connection. Each connection reads newline-delimited JSON
frames, validates them through the protocol module, dispatches through
ChatHandlers, and writes replies/events back. The bot engine runs on the same
loop so bots and humans share one room registry.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from pulsechat import protocol
from pulsechat.bots import BotEngine
from pulsechat.config import Settings, load_settings
from pulsechat.handlers import ChatHandlers
from pulsechat.protocol import (
    ProtocolError,
    encode_frame,
    parse_frame,
    server_event,
)
from pulsechat.rooms import RoomRegistry
from pulsechat.sessions import Session, SessionRegistry
from pulsechat.storage import TranscriptStore

log = logging.getLogger("pulsechat.server")


class ChatServer:
    """Wire everything together and own the accept loop."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or load_settings()
        self.sessions = SessionRegistry()
        self.rooms = RoomRegistry(history_limit=self.settings.history_limit)
        self.store = TranscriptStore(Path(self.settings.data_dir))
        self.handlers = ChatHandlers(
            sessions=self.sessions,
            rooms=self.rooms,
            store=self.store,
            history_limit=self.settings.history_limit,
        )
        self.bot_engine: BotEngine | None = None
        self._server: asyncio.Server | None = None

    async def start(self, with_bots: int = 0) -> None:
        """Bind the listener and optionally raise a bot population."""
        self._server = await asyncio.start_server(
            self._handle_client, self.settings.host, self.settings.port
        )
        if with_bots > 0:
            self.bot_engine = BotEngine(
                self.handlers, count=with_bots, rate=self.settings.bot_rate
            )
            await self.bot_engine.start()
        addrs = ", ".join(str(sock.getsockname()) for sock in self._server.sockets or ())
        log.info("pulsechat listening on %s", addrs)

    async def serve_forever(self) -> None:
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def stop(self) -> None:
        if self.bot_engine is not None:
            await self.bot_engine.stop()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
        self.store.close()

    # -- per-connection ------------------------------------------------------

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        log.debug("connection from %s", peer)
        session = Session(sid=protocol.make_id(), name=f"anon-{protocol.make_id()[:6]}", writer=writer)
        try:
            while True:
                try:
                    line = await asyncio.wait_for(
                        reader.readline(), timeout=self.settings.read_timeout
                    )
                except asyncio.TimeoutError:
                    writer.write(encode_frame(server_event("system", message="idle timeout, bye")))
                    await writer.drain()
                    break
                if not line:
                    break  # client hung up
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                try:
                    frame = parse_frame(decoded, max_text=self.settings.max_message_len)
                    reply = self.handlers.dispatch(session, frame)
                except ProtocolError as exc:
                    reply = server_event("error", code=exc.code, message=exc.message)
                except Exception:  # noqa: BLE001
                    log.exception("handler crashed on frame: %r", decoded[:120])
                    reply = server_event("error", code="internal", message="internal error")
                if reply is not None:
                    # echo the client's seq (if any) so SDKs can match replies
                    try:
                        sent = json.loads(decoded)
                        if isinstance(sent.get("seq"), int):
                            reply["reply_seq"] = sent["seq"]
                    except json.JSONDecodeError:
                        pass
                    writer.write(encode_frame(reply))
                    await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            log.debug("connection dropped: %s", peer)
        finally:
            await self._drop_session(session, writer)

    async def _drop_session(self, session: Session, writer: asyncio.StreamWriter) -> None:
        """Remove a session and announce its departure to joined rooms."""
        removed = self.sessions.remove(session.sid)
        for room_name in list(session.rooms):
            room = self.rooms.get(room_name)
            if room is not None:
                room.remove_member(session.sid)
                self.rooms.drop_if_empty(room_name)
                self._fanout_room(
                    room_name,
                    server_event("presence", event="leave", room=room_name, who=session.name),
                )
        if removed is not None:
            log.info("session %s (%s) disconnected", session.name, session.sid)
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass

    def _fanout_room(self, room_name: str, event: dict) -> None:
        self.handlers._fanout_room(room_name, event)












