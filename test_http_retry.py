# -*- coding: utf-8 -*-
"""Proves the retry policy against a server that fails on purpose.

Each case asserts both halves of the behaviour: that a blip is
retried and recovered from, and - just as important - that a real
answer like 403 is NOT retried, because retrying it would only add
silence to a live call.
"""
import asyncio
import time

import httpx
from fastapi import FastAPI, Response
from uvicorn import Config, Server

from backend.microservices.livekit_Rag_services.services.http_retry import (
    request_with_retry,
)

app = FastAPI()
hits: dict[str, int] = {}


def _count(name: str) -> int:
    hits[name] = hits.get(name, 0) + 1
    return hits[name]


@app.get("/flaky-503")
async def flaky_503():
    """Fails twice with 503, then succeeds."""
    return Response(status_code=200 if _count("503") > 2 else 503)


@app.get("/always-403")
async def always_403():
    """A real answer - must never be retried."""
    _count("403")
    return Response(status_code=403)


@app.get("/always-500")
async def always_500():
    _count("500")
    return Response(status_code=500)


@app.get("/slow")
async def slow():
    """Stalls on the first call, answers instantly after."""
    if _count("slow") == 1:
        await asyncio.sleep(5)
    return Response(status_code=200)


@app.get("/ok")
async def ok():
    _count("ok")
    return Response(status_code=200)


async def main() -> None:
    server = Server(Config(app, host="127.0.0.1", port=8099, log_level="error"))
    task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.05)

    base = "http://127.0.0.1:8099"
    failures = 0

    def check(name: str, passed: bool, detail: str) -> None:
        nonlocal failures
        if not passed:
            failures += 1
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    # 1. a blip is retried and recovered
    hits.clear()
    started = time.monotonic()
    r = await request_with_retry("GET", f"{base}/flaky-503", label="flaky")
    check(
        "503 twice then OK",
        r.status_code == 200 and hits["503"] == 3,
        f"status={r.status_code} attempts={hits['503']} "
        f"took={time.monotonic() - started:.1f}s",
    )

    # 2. a real answer is NOT retried
    hits.clear()
    r = await request_with_retry("GET", f"{base}/always-403", label="403")
    check(
        "403 not retried",
        r.status_code == 403 and hits["403"] == 1,
        f"status={r.status_code} attempts={hits['403']}",
    )

    # 3. a persistent 5xx gives up after the limit, returns the response
    hits.clear()
    r = await request_with_retry("GET", f"{base}/always-500", label="500")
    check(
        "500 tried 3x then returned",
        r.status_code == 500 and hits["500"] == 3,
        f"status={r.status_code} attempts={hits['500']}",
    )

    # 4. a timeout is retried, and the retry succeeds
    hits.clear()
    started = time.monotonic()
    r = await request_with_retry(
        "GET", f"{base}/slow", timeout=1.0, label="slow"
    )
    check(
        "timeout retried then OK",
        r.status_code == 200 and hits["slow"] == 2,
        f"status={r.status_code} attempts={hits['slow']} "
        f"took={time.monotonic() - started:.1f}s",
    )

    # 5. a healthy call is not slowed down
    hits.clear()
    started = time.monotonic()
    r = await request_with_retry("GET", f"{base}/ok", label="ok")
    elapsed = time.monotonic() - started
    check(
        "healthy call adds no delay",
        r.status_code == 200 and hits["ok"] == 1 and elapsed < 0.5,
        f"attempts={hits['ok']} took={elapsed:.3f}s",
    )

    # 6. an unreachable host raises rather than hanging
    hits.clear()
    started = time.monotonic()
    try:
        await request_with_retry(
            "GET", "http://127.0.0.1:9", timeout=1.0, label="dead"
        )
        check("unreachable host raises", False, "no exception")
    except httpx.TransportError as error:
        check(
            "unreachable host raises",
            True,
            f"{type(error).__name__} after "
            f"{time.monotonic() - started:.1f}s",
        )

    print(f"\n==== {failures} failure(s)")

    server.should_exit = True
    await task


if __name__ == "__main__":
    asyncio.run(main())
