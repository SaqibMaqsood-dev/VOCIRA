"""
What a records provider is, for the catalogue (registry.py).

    mode    live         read on each question through its adapter (ERPNext, Open School MIS)
            sync         copied into Vocira's canonical records by the sync engine
            native       kept in Vocira itself - Native Records
            unavailable  no official integration Vocira can use yet
    setup   how it is connected on the panel:
            connection   address + credentials, tested (ERPNext, Open School MIS)
            links        a Google Sheet / online CSV link per table
            upload       an Excel / CSV file per table
            rest         an approved REST API: address, auth, an endpoint per table
            database     a read-only database account: a SELECT per table
            native       nothing to connect - records are typed in on the panel
            official     needs the provider's official integration first
    status  available | demo (optional, for trying Vocira out) | official_integration_required
"""

from dataclasses import dataclass, field
from typing import Awaitable, Callable

from backend.microservices.livekit_Rag_services.services.erp_services.records_base import CAPABILITIES

ALL_CAPABILITIES = ("profile", "attendance", "results", "fees", "marks", "timetable")


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"              # text | url | email | secret | select | number
    required: bool = True
    placeholder: str = ""
    help: str = ""
    options: tuple = ()             # for select: (value, label) pairs


@dataclass(frozen=True)
class Provider:
    kind: str
    label: str
    description: str
    category: str                   # provider | generic | native
    mode: str
    setup: str
    status: str = "available"
    fields: tuple = ()
    capabilities: tuple = ALL_CAPABILITIES
    tables: tuple = ()              # the canonical tables it can fill (copied sources)
    test: Callable[..., Awaitable[dict]] | None = None
    build: Callable | None = None   # a live provider's adapter: build(school, connection, default_service)
    sync: Callable[..., Awaitable[dict]] | None = None  # a copied source: sync(school, connection) -> per-table counts
    vendor_url: str | None = None
    notes: str = ""
    instead: tuple = ()             # what to use while it is unavailable
    extra: dict = field(default_factory=dict)

    def public(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "mode": self.mode,
            "setup": self.setup,
            "status": self.status,
            "fields": [{**f.__dict__, "options": [list(o) for o in f.options]} for f in self.fields],
            "capabilities": [{"key": c, "label": CAPABILITIES[c]["label"]} for c in self.capabilities],
            "tables": list(self.tables),
            "vendor_url": self.vendor_url,
            "notes": self.notes,
            "instead": list(self.instead),
            **self.extra,
        }


class SourceError(Exception):
    """A copied source could not be read - its message is shown (scrubbed) on the panel."""

    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        # a timeout or a dropped connection: worth trying again in a moment
        self.transient = transient
