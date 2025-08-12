PulseChat
=========

PulseChat is an async TCP chat server that carries load for testing clients:
rooms, private messages, presence, reconnects, and a population of bots that
type, chat, and idle like human users.

Quick start
-----------

    python -m pulsechat --demo --port 7788

Connect with netcat:

    nc 127.0.0.1 7788
    {"type": "register", "name": "parisa"}

Then join a room:

    {"type": "join", "room": "general"}
    {"type": "msg", "room": "general", "text": "salam everyone"}

Protocol
--------

One JSON object per line (newline-delimited JSON over TCP).

Client -> server:

    {"type": "register", "name": "sara"}
    {"type": "join", "room": "general"}
    {"type": "leave", "room": "general"}
    {"type": "msg", "room": "general", "text": "hello"}
    {"type": "priv", "to": "sara", "text": "psst"}
    {"type": "who", "room": "general"}
    {"type": "history", "room": "general", "limit": 20}
    {"type": "ping"}

Server -> client:

    {"type": "ok", "reply_to": <seq>, ...}
    {"type": "error", "code": "...", "message": "..."}
    {"type": "msg", "room": "...", "from": "...", "text": "...", "seq": 3}
    {"type": "priv", "from": "...", "text": "..."}
    {"type": "presence", "event": "join", "room": "...", "who": "..."}
    {"type": "roster", "room": "...", "members": [...]}
    {"type": "history", "room": "...", "messages": [...]}
    {"type": "typing", "room": "...", "who": "..."}
    {"type": "pong"}
    {"type": "system", "message": "..."}

Bot engine
----------

    python -m pulsechat --bots 12 --demo

Each bot picks a persona (the chatty one, the lurker, the greeter, the
questioner), joins rooms, types with human-ish delay, reacts to others, and
goes idle. Tune density with `--bot-rate fast|normal|slow`.

Configuration
-------------

Every knob has an environment variable twin (host, port, data dir, log level,
bot rate, message limit) so the server drops into containers cleanly.

Layout
------

    pulsechat/
      config.py      env-driven settings
      protocol.py    message validation + framing
      rooms.py       thread-safe room registry
      sessions.py    per-connection session store
      handlers.py    request dispatch
      server.py      asyncio socket server
      bots.py        persona-driven bot engine
      storage.py     JSONL transcripts
      cli.py         argparse entrypoint
    tests/           pytest suite

License: MIT.








































