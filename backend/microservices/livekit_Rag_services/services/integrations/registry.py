"""
The catalogue of records providers, and each school's adapter.

    catalogue()            what the panels offer - every provider, available or not
    get(kind)              one provider
    connector_for(school)  the adapter the agent's tools read a school's records through

A live provider (ERPNext, Open School MIS) gets its own adapter; every
copied or native source gets the canonical adapter over the school's
canonical records. Either way it is wrapped so it answers only about what
the school allowed Vocira to read.
"""

from backend.microservices.livekit_Rag_services.services.erp_services import connections
from backend.microservices.livekit_Rag_services.services.erp_services.records_base import (
    NoRecordsConnector,
    OnlyAllowed,
    RecordsConnector,
)
from backend.microservices.livekit_Rag_services.services.integrations import native
from backend.microservices.livekit_Rag_services.services.integrations.base import Provider
from backend.microservices.livekit_Rag_services.services.integrations.canonical_adapter import CanonicalConnector
from backend.microservices.livekit_Rag_services.services.integrations.generic import (
    database,
    excel,
    google_sheets,
    rest_api,
)
from backend.microservices.livekit_Rag_services.services.integrations.providers import (
    erpnext,
    eschools,
    open_school_mis,
    schooldost,
    skoo,
    skoolee,
)

PROVIDERS: dict[str, Provider] = {p.kind: p for p in (
    native.PROVIDER,
    excel.PROVIDER,
    google_sheets.PROVIDER,
    rest_api.PROVIDER,
    database.PROVIDER,
    erpnext.PROVIDER,
    open_school_mis.PROVIDER,
    skoo.PROVIDER,
    eschools.PROVIDER,
    schooldost.PROVIDER,
    skoolee.PROVIDER,
)}

# Not offered for now (2026-10-05): kept in the code, but left out of the
# catalogue and never choosable. To bring one back, take it out of here and
# put it back in tenants.RECORDS_KINDS.
HIDDEN = frozenset({"rest-api", "database"})

# What a school's records can be set to - a provider Vocira can actually use
USABLE = tuple(kind for kind, p in PROVIDERS.items() if p.mode != "unavailable" and kind not in HIDDEN)


def catalogue() -> list[dict]:
    return [p.public() for kind, p in PROVIDERS.items() if kind not in HIDDEN]


def get(kind: str | None) -> Provider | None:
    return PROVIDERS.get(kind or "")


# Keyed by the school, its records setting and its connection's version,
# so a school whose system was changed gets a fresh adapter.
_connectors: dict[tuple, RecordsConnector] = {}


def connector_for(school, default_service=None) -> RecordsConnector:
    """
    The records adapter for a school - built once, then reused.

    default_service is the ERPNext service for a school that keeps the
    service's own ERP settings (the first school, before its keys moved
    into its connection).
    """
    connection = connections.get(school.id)
    if connection is not None and connection.kind != school.records:
        connection = None
    key = (school.id, school.records, school.records_env_prefix, connection.version if connection else None)
    found = _connectors.get(key)
    if found is not None:
        return found

    provider = get(school.records)
    if provider is None or provider.mode == "unavailable":
        found = NoRecordsConnector()
    elif provider.mode == "live":
        found = provider.build(school, connection, default_service)
    else:
        found = CanonicalConnector(school, provider.kind)

    # only what the school allowed Vocira to read
    if connection is not None and connection.capabilities and found.available:
        found = OnlyAllowed(found, set(connection.capabilities))
    _connectors[key] = found
    return found
