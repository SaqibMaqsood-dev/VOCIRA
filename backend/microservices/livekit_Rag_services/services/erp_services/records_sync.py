"""
Keeping a spreadsheet school's records live.

Each of the school's tables has a link - a Google Sheet tab or any
online CSV / Excel file. The service re-reads every link on its own
timer (RECORDS_SYNC_MINUTES, 5 by default) - nobody has to press
anything - and also on demand ("Sync now"), checks
the copy exactly as spreadsheet.parse checks any sheet, and only then
replaces the copy the agent reads. A link that fails - down, no longer
shared, a broken column - leaves the last good copy in place and the
reason on the Schools page, so the agent never loses a school's records
because of one bad edit.

The links are the super admin's, but the server is what fetches them,
so a link may only reach the public internet: every host it leads to
(redirects included) must resolve to a public address - never this
machine or its local network.
"""

import asyncio
import hashlib
import ipaddress
import os
import re
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx

from backend.microservices.livekit_Rag_services.services.erp_services import spreadsheet

SYNC_MINUTES = max(1, int(os.getenv("RECORDS_SYNC_MINUTES", "5") or 5))

# When the timer last went round and goes round next (UTC, as stored) -
# shown on the Schools page so it is plain that syncing is automatic.
last_round_at: str | None = None
next_round_at: str | None = None
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_MAX_REDIRECTS = 5

# docs.google.com/spreadsheets/d/<id>/edit?...#gid=<tab>
_GOOGLE_SHEET = re.compile(r"^/spreadsheets/d/([A-Za-z0-9_-]{20,})(?:/|$)")


class LinkError(ValueError):
    """The link could not give a sheet - shown to the super admin as the reason."""


def normalize(url: str) -> str:
    """
    The link to fetch. A Google Sheets link as copied from the browser
    or the Share box becomes its CSV export, of the same tab (gid); a
    "published to the web" link is asked for CSV. Anything else is
    fetched as given.
    """
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise LinkError("Paste a full link that starts with https://")
    if len(url) > 2000:
        raise LinkError("That link is too long.")

    if parsed.hostname == "docs.google.com":
        query = parse_qs(parsed.query)
        if parsed.path.startswith("/spreadsheets/d/e/"):
            # published to the web: .../pubhtml or .../pub?output=html
            path = re.sub(r"/pubhtml$", "/pub", parsed.path)
            query["output"] = ["csv"]
            return urlunparse(parsed._replace(path=path, query=urlencode(query, doseq=True), fragment=""))
        match = _GOOGLE_SHEET.match(parsed.path)
        if match:
            gid = (query.get("gid") or re.findall(r"gid=(\d+)", parsed.fragment) or [None])[0]
            export = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=csv"
            return export + (f"&gid={gid}" if gid else "")
    return url


async def _check_public(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise LinkError("The link must start with https://")
    try:
        infos = await asyncio.to_thread(
            socket.getaddrinfo, parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        )
    except socket.gaierror:
        raise LinkError(f"{parsed.hostname} could not be found - check the link.")
    for info in infos:
        address = ipaddress.ip_address(info[4][0].split("%")[0])
        if not address.is_global:
            raise LinkError("That link points inside the server's own network - only public links are allowed.")


async def fetch(url: str) -> tuple[bytes, str]:
    """The link's content and type, following redirects one checked hop at a time."""
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False,
                                 headers={"User-Agent": "Vocira-records-sync/1.0"}) as client:
        for _ in range(_MAX_REDIRECTS + 1):
            await _check_public(url)
            async with client.stream("GET", url) as response:
                if response.is_redirect and response.headers.get("location"):
                    url = urljoin(url, response.headers["location"])
                    continue
                if response.status_code in (401, 403):
                    raise LinkError("The link needs a login. Share the sheet as 'Anyone with the link - Viewer'.")
                if response.status_code == 404:
                    raise LinkError("Nothing was found at that link (404).")
                if response.status_code >= 400:
                    raise LinkError(f"The link answered with an error (HTTP {response.status_code}).")
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > spreadsheet.MAX_BYTES:
                        raise LinkError("The sheet is larger than 5 MB.")
                    chunks.append(chunk)
                return b"".join(chunks), response.headers.get("content-type", "")
    raise LinkError("The link redirects too many times.")


def _as_file(content: bytes, content_type: str) -> str:
    """Which kind of sheet came back - or the reason it is not one."""
    if content[:2] == b"PK":
        return "link.xlsx"
    head = content[:600].lstrip().lower()
    if head.startswith((b"<!doctype html", b"<html")) or "text/html" in content_type:
        raise LinkError(
            "The link opened a web page, not a sheet. For Google Sheets: Share -> 'Anyone with the link' "
            "-> Viewer, then copy the link of the tab. Otherwise use a direct link to a .csv or .xlsx file."
        )
    return "link.csv"


async def read(url: str, table: str, mapping: dict | None = None) -> tuple[list[str], list[dict], list[str], str]:
    """Fetch and check one table: (columns, rows, warnings, digest) - or LinkError / SpreadsheetError."""
    try:
        content, content_type = await fetch(url)
    except httpx.TimeoutException:
        raise LinkError("The link took too long to answer.")
    except httpx.HTTPError as error:
        raise LinkError(f"The link could not be reached ({type(error).__name__}).")
    columns, rows, warnings = spreadsheet.parse(table, _as_file(content, content_type), content, mapping)
    # the mapping is part of what was read: a changed mapping is a changed copy
    digest = hashlib.sha256(content + repr(sorted((mapping or {}).items())).encode()).hexdigest()
    return columns, rows, warnings, digest


async def connect(records_dir: str, table: str, url: str, mapping: dict | None = None) -> dict:
    """A new link for a table: kept only if it gives a usable sheet now."""
    source = normalize(url)
    columns, rows, warnings, digest = await read(source, table, mapping)
    return spreadsheet.save(records_dir, table, source, columns, rows, warnings, digest)


async def sync_table(records_dir: str, table: str, mapping: dict | None = None) -> dict:
    """Re-read one table's link. A failure keeps the copy in use and records why."""
    meta = spreadsheet.read_meta(records_dir, table)
    if not meta or not meta.get("source_url"):
        return {"table": table, "ok": False, "skipped": True}
    try:
        columns, rows, warnings, digest = await read(meta["source_url"], table, mapping)
    except (LinkError, spreadsheet.SpreadsheetError) as error:
        spreadsheet.update_meta(records_dir, table, last_attempt=spreadsheet.now(), last_error=str(error))
        print(f"[Records sync] {table}: kept the {meta.get('synced_at')} copy - {error}")
        return {"table": table, "ok": False, "error": str(error)}

    if digest == meta.get("digest") and spreadsheet.has_table(records_dir, table):
        # unchanged - no rewrite, so the agent's cached copy stays warm
        stamp = spreadsheet.now()
        spreadsheet.update_meta(records_dir, table, synced_at=stamp, last_attempt=stamp, last_error=None)
        return {"table": table, "ok": True, "changed": False, "rows": meta.get("rows")}

    saved = spreadsheet.save(records_dir, table, meta["source_url"], columns, rows, warnings, digest)
    print(f"[Records sync] {table}: {saved['rows']} rows (changed)")
    return {"table": table, "ok": True, "changed": True, "rows": saved["rows"]}


_locks: dict[str, asyncio.Lock] = {}


async def sync_school(school_id: str, records_dir: str, mappings: dict | None = None) -> list[dict]:
    """Every linked table of one school - one sync of a school at a time."""
    lock = _locks.setdefault(school_id, asyncio.Lock())
    async with lock:
        return [await sync_table(records_dir, table, (mappings or {}).get(table)) for table in spreadsheet.TABLES]


async def sync_all() -> None:
    from backend.microservices.livekit_Rag_services.services import tenants

    await tenants.refresh(force=True)
    checked = changed = failed = 0
    for school_id in list(tenants.all_schools()):
        school = tenants.get_school(school_id)
        if school.records == "spreadsheet":
            try:
                results = [r for r in await sync_school(school.id, tenants.records_dir(school.id)) if not r.get("skipped")]
            except Exception as error:  # one school's trouble never stops the others
                print(f"[Records sync] {school.id}: {type(error).__name__}: {error}")
                continue
            checked += len(results)
            changed += sum(1 for r in results if r.get("changed"))
            failed += sum(1 for r in results if not r["ok"])
    if checked:
        print(f"[Records sync] automatic round: {checked} link(s) checked, {changed} changed, {failed} failed")


def _in(seconds: float) -> str:
    moment = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return moment.replace(tzinfo=None).isoformat(timespec="seconds")


async def run_forever() -> None:
    """The timer: shortly after start, then every SYNC_MINUTES - on its own."""
    global last_round_at, next_round_at
    next_round_at = _in(30)
    await asyncio.sleep(30)
    while True:
        last_round_at = spreadsheet.now()
        try:
            # every copied source that is due - Google Sheets every SYNC_MINUTES as
            # before, a REST API or database by its own schedule (integrations/sync.py)
            from backend.microservices.livekit_Rag_services.services.integrations import sync as hub_sync

            await hub_sync.scheduled_round()
        except Exception as error:
            print(f"[Records sync] round failed: {type(error).__name__}: {error}")
        next_round_at = _in(SYNC_MINUTES * 60)
        await asyncio.sleep(SYNC_MINUTES * 60)
