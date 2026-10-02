"""
Generic REST API - a copied source, for a school whose software gives it
official API access (SchoolDost, Skoolee and others, once the vendor hands
over their documentation and a read-only key).

Nothing about any vendor is assumed. The admin types in what the vendor's
documentation says:

    settings  base_url, auth_type (none | bearer | header | basic),
              auth_header (for "header"), username (for "basic"),
              endpoints: {table: {"path": "/students",
                                  "list_path": "data.items",   where the list is in the JSON
                                  "next_path": "links.next"}}  optional: the next page's link
    secrets   token - the bearer token, API key, or basic-auth password

Each endpoint is read with GET only, its JSON list mapped (mapping step)
into the canonical fields, and the school's copy of that table replaced.
"""

from urllib.parse import urljoin, urlparse

import httpx

from backend.microservices.livekit_Rag_services.services.integrations import normalizer, security, store
from backend.microservices.livekit_Rag_services.services.integrations.base import Field, Provider, SourceError

SOURCE = "rest-api"
MAX_PAGES = 50
MAX_BYTES = 10 * 1024 * 1024
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
TABLES = ("students", "guardians", "attendance", "fees", "results", "timetable", "announcements", "classes", "teachers")


def _dig(body, path: str):
    """'data.items' -> body["data"]["items"]; '' -> body itself."""
    value = body
    for part in [p for p in (path or "").split(".") if p]:
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def _flatten(record: dict, prefix: str = "", depth: int = 0) -> dict:
    """{"guardian": {"name": "X"}} -> {"guardian.name": "X"} - two levels deep; lists are left out."""
    out = {}
    for key, value in record.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict) and depth < 2:
            out.update(_flatten(value, f"{name}.", depth + 1))
        elif not isinstance(value, (list, dict)):
            out[name] = value
    return out


def _headers_and_auth(settings: dict, secrets: dict):
    headers = {"Accept": "application/json", "User-Agent": "Vocira-records/1.0"}
    auth = None
    kind = settings.get("auth_type") or "none"
    token = secrets.get("token") or ""
    if kind == "bearer":
        headers["Authorization"] = f"Bearer {token}"
    elif kind == "header":
        headers[(settings.get("auth_header") or "X-API-Key").strip()] = token
    elif kind == "basic":
        auth = (settings.get("username") or "", token)
    return headers, auth


async def _get_json(client: httpx.AsyncClient, url: str, settings: dict, secrets: dict, allow_private: bool):
    headers, auth = _headers_and_auth(settings, secrets)
    for _ in range(6):  # a redirect is followed only after its own address is checked
        try:
            await security.check_url(url, allow_private)
        except security.AddressError as error:
            raise SourceError(str(error))
        try:
            response = await client.get(url, headers=headers, auth=auth)
        except httpx.TimeoutException:
            raise SourceError("The API took too long to answer.", transient=True)
        except httpx.HTTPError as error:
            raise SourceError(f"The API could not be reached ({type(error).__name__}).", transient=True)
        if response.is_redirect and response.headers.get("location"):
            url = urljoin(url, response.headers["location"])
            continue
        if response.status_code in (401, 403):
            raise SourceError(f"The API refused the credentials (HTTP {response.status_code}) - check the token and its access.")
        if response.status_code == 404:
            raise SourceError(f"Nothing was found at {urlparse(url).path} (404) - check the endpoint path.")
        if response.status_code == 429 or response.status_code >= 500:
            raise SourceError(f"The API is busy or failing (HTTP {response.status_code}).", transient=True)
        if response.status_code >= 400:
            raise SourceError(f"The API answered with an error (HTTP {response.status_code}).")
        if len(response.content) > MAX_BYTES:
            raise SourceError("The API's answer is larger than 10 MB - ask for a smaller page size.")
        try:
            return response.json(), url
        except ValueError:
            raise SourceError("The endpoint did not answer with JSON.")
    raise SourceError("The API redirects too many times.")


async def fetch_table(settings: dict, secrets: dict, allow_private: bool, table: str, limit_pages: int = MAX_PAGES) -> list[dict]:
    """One table's records from its endpoint, every page followed - flattened dicts."""
    endpoint = (settings.get("endpoints") or {}).get(table) or {}
    base = (settings.get("base_url") or "").rstrip("/") + "/"
    if not endpoint.get("path"):
        raise SourceError(f"No endpoint is set for {table}.")
    url = urljoin(base, endpoint["path"].lstrip("/"))
    origin = urlparse(base).netloc
    records = []
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=False) as client:
        for _ in range(limit_pages):
            body, url = await _get_json(client, url, settings, secrets, allow_private)
            found = _dig(body, endpoint.get("list_path") or "")
            if not isinstance(found, list):
                where = endpoint.get("list_path") or "the top of the answer"
                raise SourceError(f"No list was found at '{where}' in the answer - check the list path.")
            records.extend(_flatten(r) for r in found if isinstance(r, dict))
            if len(records) > normalizer.MAX_ROWS:
                raise SourceError(f"More than {normalizer.MAX_ROWS} records.")
            following = _dig(body, endpoint.get("next_path") or "") if endpoint.get("next_path") else None
            if not following or not isinstance(following, str):
                break
            url = urljoin(url, following)
            if urlparse(url).netloc != origin:
                raise SourceError("The next page points to another server - it was not followed.")
    return records


def _columns(records: list[dict]) -> list[str]:
    seen = {}
    for r in records:
        for key in r:
            seen.setdefault(key, None)
    return list(seen)


async def test(settings: dict, secrets: dict, allow_private_network: bool) -> dict:
    """Read each configured endpoint (first page) - counts, columns and a suggested mapping for each."""
    steps, counts, columns, suggested = [], {}, {}, {}
    try:
        await security.check_url(settings.get("base_url", ""), allow_private_network)
    except security.AddressError as error:
        steps.append({"name": "Address", "ok": False, "detail": str(error)})
        return {"ok": False, "steps": steps, "capabilities": [], "counts": {}}
    endpoints = settings.get("endpoints") or {}
    if not endpoints.get("students"):
        steps.append({"name": "Students endpoint", "ok": False, "detail": "Set the Students endpoint - it ties parents to their children."})
    for table in TABLES:
        if not (endpoints.get(table) or {}).get("path"):
            continue
        try:
            records = await fetch_table(settings, secrets, allow_private_network, table, limit_pages=1)
        except SourceError as error:
            steps.append({"name": table.title(), "ok": False, "detail": security.scrub(error, secrets)})
            continue
        counts[table] = len(records)
        columns[table] = _columns(records)
        suggested[table] = normalizer.suggest_mapping(table, columns[table])
        steps.append({"name": table.title(), "ok": True, "detail": f"{len(records)} record(s) on the first page"})
    ok = bool(counts.get("students")) and all(s["ok"] for s in steps)
    capabilities = ["profile"] if counts.get("students") is not None else []
    capabilities += [c for t, c in (("attendance", "attendance"), ("fees", "fees"), ("results", "results"),
                                    ("results", "marks"), ("timetable", "timetable")) if t in counts]
    return {"ok": ok, "steps": steps, "capabilities": capabilities, "counts": counts,
            "columns": columns, "suggested": suggested}


async def sync(school, connection, force: bool = False) -> dict:
    """Every configured endpoint, read and mapped; the school's copy of each table replaced."""
    settings, secrets = connection.settings, connection.secrets
    counts, errors, warnings, transient = {}, {}, {}, []
    endpoints = settings.get("endpoints") or {}
    tables = [t for t in TABLES if (endpoints.get(t) or {}).get("path")]
    if not tables:
        raise SourceError("No endpoints are set - add at least the Students endpoint.")
    for table in tables:
        try:
            records = await fetch_table(settings, secrets, connection.allow_private_network, table)
            result = normalizer.normalize(table, _columns(records), records, (connection.mapping or {}).get(table))
        except SourceError as error:
            errors[table] = security.scrub(error, secrets)
            transient.append(error.transient)
            continue
        except normalizer.NormalizeError as error:
            errors[table] = str(error)
            continue
        counts[table] = await store.replace_table(school.id, table, result.rows, SOURCE)
        if result.warnings:
            warnings[table] = result.warnings
    if errors and not counts:
        # nothing could be read: worth another try only if every failure was a passing one
        raise SourceError("; ".join(f"{t}: {e}" for t, e in errors.items()),
                          transient=bool(transient) and all(transient))
    return {"counts": counts, "errors": errors, "warnings": warnings, "changed": True}


PROVIDER = Provider(
    kind="rest-api",
    label="Generic REST API",
    description="Any school software that gives official, read-only API access - set up from the vendor's documentation.",
    category="generic",
    mode="sync",
    setup="rest",
    fields=(
        Field("base_url", "API address", "url", placeholder="https://api.yourschoolsoftware.com/v1"),
        Field("auth_type", "How it signs in", "select", options=(("none", "No sign-in"), ("bearer", "Bearer token"),
                                                                  ("header", "API key in a header"), ("basic", "Username and password"))),
        Field("auth_header", "Header name (for an API key)", required=False, placeholder="X-API-Key"),
        Field("username", "Username (for username and password)", required=False),
        Field("token", "Token, API key or password", "secret", required=False,
              help="Ask the vendor for a read-only key made for Vocira."),
    ),
    tables=TABLES,
    test=test,
    sync=sync,
    notes="GET requests only. Re-read every hour by default.",
    extra={"sync_minutes": 60},
)
