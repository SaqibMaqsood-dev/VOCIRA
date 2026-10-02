"""
Authorized database connection - a copied source, for a school (or its
vendor) that gives Vocira a READ-ONLY account on the records database.

    settings  engine (postgresql), host, port, database, username, sslmode,
              queries: {table: "SELECT ... FROM ..."}
    secrets   password

Reading only, three times over:
    1. each query must be one SELECT (or WITH ... SELECT) - nothing that writes
    2. the session is opened with default_transaction_read_only = on, and every
       query runs inside a READ ONLY transaction - the database itself refuses
       a write
    3. a statement timeout (15 s) and a row cap (20,000)
The school should still give an account that can only read, on only the
tables Vocira needs.

PostgreSQL only: the server has no MySQL / SQL Server driver installed.
"""

import re

from backend.microservices.livekit_Rag_services.services.integrations import normalizer, security, store
from backend.microservices.livekit_Rag_services.services.integrations.base import Field, Provider, SourceError

SOURCE = "database"
TABLES = ("students", "guardians", "attendance", "fees", "results", "timetable", "announcements", "classes", "teachers")
STATEMENT_TIMEOUT_MS = 15000

# Words that make a SELECT write, lock or reach outside its rows. Ordinary column
# names (comment, status, date ...) are fine - the read-only transaction is the
# real guard; this only says early, in plain words, why a query is refused.
_WRITES = re.compile(
    r"\b(insert|update|delete|merge|drop|alter|create|truncate|grant|revoke|copy|call|execute|into|"
    r"pg_sleep|pg_read_file|pg_read_binary_file|pg_ls_dir|pg_terminate_backend|pg_cancel_backend|"
    r"lo_import|lo_export|dblink|set_config)\b",
    re.IGNORECASE,
)


def check_query(sql: str) -> str:
    """The query, if it only reads - else SourceError saying why."""
    query = (sql or "").strip().rstrip(";").strip()
    if not query:
        raise SourceError("The query is empty.")
    # what is inside quotes and comments is not SQL to check
    bare = re.sub(r"'(?:[^']|'')*'", "''", query)
    bare = re.sub(r'"(?:[^"]|"")*"', '""', bare)
    bare = re.sub(r"--[^\n]*", " ", bare)
    bare = re.sub(r"/\*.*?\*/", " ", bare, flags=re.DOTALL)
    if ";" in bare:
        raise SourceError("One query only - no ';' in the middle.")
    if not re.match(r"(?is)^\s*(select|with)\b", bare):
        raise SourceError("Only SELECT queries are allowed.")
    found = _WRITES.search(bare)
    if found:
        raise SourceError(f"Vocira only reads - the query uses '{found.group(1).upper()}'.")
    return query


async def _connect(settings: dict, secrets: dict, allow_private: bool):
    if (settings.get("engine") or "postgresql") != "postgresql":
        raise SourceError("Only PostgreSQL is supported on this server - a MySQL or SQL Server driver is not installed.")
    host = (settings.get("host") or "").strip()
    try:
        port = int(settings.get("port") or 5432)
    except ValueError:
        raise SourceError("The port must be a number.")
    try:
        await security.check_host(host, port, allow_private)
    except security.AddressError as error:
        raise SourceError(str(error))

    import asyncpg

    ssl = {"disable": False, "require": "require", "prefer": "prefer"}.get(settings.get("sslmode") or "prefer", "prefer")
    try:
        return await asyncpg.connect(
            host=host, port=port, database=settings.get("database") or None, user=settings.get("username") or None,
            password=secrets.get("password") or None, ssl=ssl, timeout=10,
            server_settings={"default_transaction_read_only": "on", "statement_timeout": str(STATEMENT_TIMEOUT_MS),
                             "application_name": "vocira-records"},
        )
    except asyncpg.InvalidPasswordError:
        raise SourceError("The database refused the username or password.")
    except asyncpg.InvalidCatalogNameError:
        raise SourceError("That database does not exist on the server.")
    except (OSError, TimeoutError) as error:
        raise SourceError(f"The database could not be reached ({type(error).__name__}).", transient=True)
    except asyncpg.PostgresError as error:
        raise SourceError(f"The database refused the connection: {error}")


async def _run(conn, sql: str, limit: int) -> tuple[list[str], list[dict]]:
    import asyncpg

    query = check_query(sql)
    wrapped = f"SELECT * FROM ({query}) AS vocira_source LIMIT {int(limit)}"
    try:
        async with conn.transaction(readonly=True):
            statement = await conn.prepare(wrapped)
            columns = [a.name for a in statement.get_attributes()]
            rows = [dict(r) for r in await statement.fetch()]
    except asyncpg.ReadOnlySQLTransactionError:
        raise SourceError("That query tries to change data - Vocira only reads.")
    except asyncpg.QueryCanceledError:
        raise SourceError(f"The query took longer than {STATEMENT_TIMEOUT_MS // 1000} seconds.", transient=True)
    except asyncpg.PostgresError as error:
        raise SourceError(f"The query failed: {error}")
    return columns, rows


async def read_table(settings: dict, secrets: dict, allow_private: bool, table: str, limit: int | None = None):
    query = (settings.get("queries") or {}).get(table)
    if not query:
        raise SourceError(f"No query is set for {table}.")
    conn = await _connect(settings, secrets, allow_private)
    try:
        return await _run(conn, query, (limit or normalizer.MAX_ROWS) + 1)
    finally:
        await conn.close()


async def test(settings: dict, secrets: dict, allow_private_network: bool) -> dict:
    """Sign in and run each query (its first rows): columns and a suggested mapping for each."""
    steps, counts, columns, suggested = [], {}, {}, {}
    queries = settings.get("queries") or {}
    for table, sql in queries.items():
        if sql:
            try:
                check_query(sql)
            except SourceError as error:
                steps.append({"name": f"{table.title()} query", "ok": False, "detail": str(error)})
    if steps:
        return {"ok": False, "steps": steps, "capabilities": [], "counts": {}}
    try:
        conn = await _connect(settings, secrets, allow_private_network)
    except SourceError as error:
        steps.append({"name": "Sign in", "ok": False, "detail": security.scrub(error, secrets)})
        return {"ok": False, "steps": steps, "capabilities": [], "counts": {}}
    steps.append({"name": "Signed in", "ok": True, "detail": "read-only session"})
    try:
        for table in TABLES:
            if not queries.get(table):
                continue
            try:
                cols, rows = await _run(conn, queries[table], 50)
            except SourceError as error:
                steps.append({"name": table.title(), "ok": False, "detail": security.scrub(error, secrets)})
                continue
            counts[table] = len(rows)
            columns[table] = cols
            suggested[table] = normalizer.suggest_mapping(table, cols)
            steps.append({"name": table.title(), "ok": True, "detail": f"{len(cols)} columns, rows readable"})
    finally:
        await conn.close()
    if "students" not in queries or not queries.get("students"):
        steps.append({"name": "Students query", "ok": False, "detail": "Set the Students query - it ties parents to their children."})
    ok = "students" in counts and all(s["ok"] for s in steps)
    capabilities = ["profile"] if "students" in counts else []
    capabilities += [c for t, c in (("attendance", "attendance"), ("fees", "fees"), ("results", "results"),
                                    ("results", "marks"), ("timetable", "timetable")) if t in counts]
    return {"ok": ok, "steps": steps, "capabilities": capabilities, "counts": counts,
            "columns": columns, "suggested": suggested}


async def sync(school, connection, force: bool = False) -> dict:
    settings, secrets = connection.settings, connection.secrets
    queries = {t: q for t, q in (settings.get("queries") or {}).items() if q and t in TABLES}
    if not queries:
        raise SourceError("No queries are set - add at least the Students query.")
    counts, errors, warnings = {}, {}, {}
    conn = await _connect(settings, secrets, connection.allow_private_network)
    try:
        for table in TABLES:
            if table not in queries:
                continue
            try:
                columns, rows = await _run(conn, queries[table], normalizer.MAX_ROWS + 1)
                result = normalizer.normalize(table, columns, rows, (connection.mapping or {}).get(table))
            except SourceError as error:
                errors[table] = security.scrub(error, secrets)
                continue
            except normalizer.NormalizeError as error:
                errors[table] = str(error)
                continue
            counts[table] = await store.replace_table(school.id, table, result.rows, SOURCE)
            if result.warnings:
                warnings[table] = result.warnings
    finally:
        await conn.close()
    if errors and not counts:
        raise SourceError("; ".join(f"{t}: {e}" for t, e in errors.items()))
    return {"counts": counts, "errors": errors, "warnings": warnings, "changed": True}


PROVIDER = Provider(
    kind="database",
    label="Database (read-only)",
    description="A read-only account on the school's records database (PostgreSQL), with one SELECT query per table.",
    category="generic",
    mode="sync",
    setup="database",
    fields=(
        Field("engine", "Database", "select", options=(("postgresql", "PostgreSQL"),)),
        Field("host", "Host", placeholder="db.school.edu.pk"),
        Field("port", "Port", "number", required=False, placeholder="5432"),
        Field("database", "Database name"),
        Field("username", "Read-only username"),
        Field("password", "Password", "secret"),
        Field("sslmode", "Encryption", "select", required=False,
              options=(("prefer", "Use it when offered"), ("require", "Required"), ("disable", "Off"))),
    ),
    tables=TABLES,
    test=test,
    sync=sync,
    notes="Give Vocira an account that can only read. Queries run in a read-only transaction with a 15-second limit.",
    extra={"sync_minutes": 60},
)
