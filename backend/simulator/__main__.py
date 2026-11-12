"""CLI: python -m simulator {backfill,live} --url http://localhost:8000"""

import argparse
import heapq
import itertools
import logging
import random
import time
from datetime import UTC, datetime, timedelta

import httpx

from simulator.generator import Profile, build_session, iter_backfill, poisson

log = logging.getLogger("simulator")
BATCH_SIZE = 500


def _serialise(event: dict) -> dict:
    return {**event, "ts": event["ts"].isoformat()}


def post_batch(client: httpx.Client, url: str, events: list[dict], retries: int = 3) -> None:
    payload = {"events": [_serialise(e) for e in events]}
    for attempt in range(1, retries + 1):
        try:
            response = client.post(f"{url}/v1/events", json=payload, timeout=10)
            response.raise_for_status()
            return
        except httpx.HTTPError as exc:
            if attempt == retries:
                raise
            log.warning("post failed (%s); retry %d/%d", exc, attempt, retries)
            time.sleep(attempt)


def _flush(client: httpx.Client, url: str, events: list[dict]) -> int:
    for i in range(0, len(events), BATCH_SIZE):
        post_batch(client, url, events[i : i + BATCH_SIZE])
    return len(events)


def run_backfill(args: argparse.Namespace, client: httpx.Client) -> None:
    rng = random.Random(args.seed)
    now = datetime.now(UTC)
    profile = _profile(args, now)
    events = list(iter_backfill(rng, now, args.minutes, args.rate, profile))
    sent = _flush(client, args.url, events)
    log.info("backfilled %d events covering the last %d minutes", sent, args.minutes)


def run_live(args: argparse.Namespace, client: httpx.Client) -> None:
    """Start ~`rate` sessions per second; release each event when its timestamp is reached."""
    rng = random.Random(args.seed)
    started = datetime.now(UTC)
    profile = _profile(args, started)
    pending: list[tuple[datetime, int, dict]] = []
    counter = itertools.count()
    deadline = started + timedelta(seconds=args.duration) if args.duration else None
    sent = 0
    while True:
        now = datetime.now(UTC)
        for _ in range(poisson(rng, args.rate)):
            for event in build_session(rng, now, profile):
                heapq.heappush(pending, (event["ts"], next(counter), event))
        due = []
        while pending and pending[0][0] <= now:
            due.append(heapq.heappop(pending)[2])
        if due:
            sent += _flush(client, args.url, due)
            log.info("sent %d events (total %d, %d scheduled)", len(due), sent, len(pending))
        if deadline and now >= deadline:
            return
        time.sleep(1)


def _profile(args: argparse.Namespace, now: datetime) -> Profile:
    start = now + timedelta(seconds=args.incident_after) if args.incident_cdn else None
    if args.incident_cdn and args.command == "backfill":
        start = now - timedelta(minutes=min(15, args.minutes))
    return Profile(incident_cdn=args.incident_cdn, incident_start=start)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="simulator", description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--incident-cdn", default=None, help="degrade this CDN (e.g. fastly)")
    parser.add_argument(
        "--incident-after", type=int, default=120, help="seconds until the live incident starts"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    backfill = sub.add_parser("backfill", help="load historical traffic")
    backfill.add_argument("--minutes", type=int, default=60)
    backfill.add_argument("--rate", type=float, default=2.0, help="sessions per second")

    live = sub.add_parser("live", help="stream traffic in real time")
    live.add_argument("--rate", type=float, default=5.0, help="new sessions per second")
    live.add_argument("--duration", type=int, default=0, help="seconds to run (0 = forever)")
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    args = build_parser().parse_args(argv)
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    with httpx.Client(headers=headers) as client:
        {"backfill": run_backfill, "live": run_live}[args.command](args, client)


if __name__ == "__main__":
    main()
