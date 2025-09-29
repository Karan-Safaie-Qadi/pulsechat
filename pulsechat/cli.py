"""Command-line entrypoint.

Examples:
    python -m pulsechat --demo --port 7788
    python -m pulsechat --bots 12 --bot-rate fast
    PULSECHAT_HOST=0.0.0.0 python -m pulsechat
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

from pulsechat import __version__
from pulsechat.config import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pulsechat",
        description="Async TCP chat server with a bot engine for load simulation.",
    )
    parser.add_argument("--host", default=None, help="bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default 7788)")
    parser.add_argument("--bots", type=int, default=0, metavar="N", help="number of bots to run")
    parser.add_argument(
        "--bot-rate",
        choices=("fast", "normal", "slow"),
        default=None,
        help="how chatty the bots are",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        metavar="DIR",
        help="where transcripts are written (default data/transcripts)",
    )
    parser.add_argument("--demo", action="store_true", help="shorthand for --bots 8 --bot-rate fast")
    parser.add_argument("--verbose", "-v", action="store_true", help="debug logging")
    parser.add_argument("--version", action="version", version=f"pulsechat {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()

    if args.host is not None:
        settings = replace(settings, host=args.host)
    if args.port is not None:
        settings = replace(settings, port=args.port)
    if args.bot_rate is not None:
        settings = replace(settings, bot_rate=args.bot_rate)
    if args.data_dir is not None:
        from pathlib import Path

        settings = replace(settings, data_dir=Path(args.data_dir))
    if args.demo and args.bots == 0:
        args.bots = 8
        if args.bot_rate is None:
            settings = replace(settings, bot_rate="fast")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    from pulsechat.server import ChatServer

    async def run() -> int:
        server = ChatServer(settings)
        await server.start(with_bots=args.bots)
        try:
            await server.serve_forever()
        except asyncio.CancelledError:
            pass
        finally:
            await server.stop()
        return 0

    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        print("\nshutting down.", file=sys.stderr)
        return 0


def replace(settings, **changes):
    """Tiny dataclasses.replace shim so cli stays readable."""
    import dataclasses

    return dataclasses.replace(settings, **changes)


if __name__ == "__main__":
    raise SystemExit(main())










