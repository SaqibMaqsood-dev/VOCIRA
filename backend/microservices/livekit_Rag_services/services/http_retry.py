"""One retry policy for every outbound HTTP call.

On WiFi these calls effectively never fail, so a single attempt with
a flat timeout was enough. On a phone's connection it is not: a
one-second stall is normal there, and it used to surface to the
caller as a hard "could not reach the server" for something that
would have worked on the next try.

Only failures worth retrying are retried. A timeout, a dropped
connection or a 503 is the network having a bad moment. A 403 or a
404 is an answer - asking again just wastes the caller's time and,
during a voice call, their patience.
"""

import asyncio
import random
import time

import httpx


# Worth another go: the request never really got an answer, or the
# server said "not now".
TRANSIENT_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

# Three attempts, ~0.3s then ~0.8s apart. The ceiling matters: this
# runs inside a live call, where a caller is listening to silence
# while it happens, so the worst case adds about a second rather
# than the tens of seconds a general-purpose backoff would.
DEFAULT_ATTEMPTS = 3
BACKOFF_SECONDS = (0.3, 0.8)

# The hard ceiling, and the reason it exists: attempts alone do not
# bound the wait. Three tries at a 15s timeout is 45 seconds, and a
# caller on a live call hears every one of them as silence. Whatever
# the attempts are doing, the whole thing gives up at this point.
DEFAULT_BUDGET_SECONDS = 12.0


def _delay(attempt: int) -> float:
    base = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]

    # Jitter, so several callers retrying after the same blip do not
    # all come back at the same instant.
    return base + random.random() * 0.2


async def request_with_retry(
    method: str,
    url: str,
    *,
    timeout: float = 15.0,
    attempts: int = DEFAULT_ATTEMPTS,
    budget: float = DEFAULT_BUDGET_SECONDS,
    label: str = "",
    **kwargs,
) -> httpx.Response:
    """Make an HTTP request, retrying only what is worth retrying.

    Returns the final response - including a failing one, so the
    caller keeps its own error handling. Raises the last transport
    error if every attempt failed to get a response at all.

    `budget` bounds the whole thing, retries included: each attempt
    only gets whatever time is left, so a stalled network cannot
    stretch this past the ceiling.
    """

    last_error: Exception | None = None
    deadline = time.monotonic() + budget

    for attempt in range(attempts):

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            break

        try:
            async with httpx.AsyncClient(
                timeout=min(timeout, remaining)
            ) as client:
                response = await client.request(method, url, **kwargs)

            if (
                response.status_code in TRANSIENT_STATUSES
                and attempt < attempts - 1
                and time.monotonic() + _delay(attempt) < deadline
            ):
                print(
                    f"[HTTP Retry] {label or url} -> "
                    f"{response.status_code}, retrying "
                    f"({attempt + 1}/{attempts})"
                )
                await asyncio.sleep(_delay(attempt))
                continue

            return response

        except httpx.TransportError as error:
            # Timeouts, refused connections, DNS failures, a dropped
            # link mid-request - all the ways a phone's network gives
            # out.
            last_error = error

            if (
                attempt >= attempts - 1
                or time.monotonic() + _delay(attempt) >= deadline
            ):
                break

            print(
                f"[HTTP Retry] {label or url} -> "
                f"{type(error).__name__}, retrying "
                f"({attempt + 1}/{attempts})"
            )

            await asyncio.sleep(_delay(attempt))

    raise last_error
