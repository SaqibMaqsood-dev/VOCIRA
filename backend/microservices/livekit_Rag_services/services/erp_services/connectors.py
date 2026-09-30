"""
Records connectors - one door to any school's records system.

The agent asks a school's records only two things: which children a
guardian has, and one resource (attendance, fees, results, ...) for
them. Every records system - ERPNext today; Odoo, a school's own
portal or an uploaded spreadsheet later - answers those two through
an adapter behind the same interface, so the agent never changes when
a school with a different system joins.

Which adapter a school uses, and where its credentials come from, is
its setting in services/tenants.py.

Authorization does not move into the adapters' hands: the guardian is
always the one the auth service vouched for (never anything said on
the call), and each adapter must return only that guardian's
children's records - ERPNext does it by filtering on the guardian.
"""

import os

from backend.microservices.livekit_Rag_services.services.erp_services.ERP_client import (
    ERPClient,
)
from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)


class RecordsUnavailable(Exception):
    """This school has no records system connected."""


class RecordsConnector:
    """What the agent needs from a school's records system."""

    kind = "none"
    available = False

    async def children_of(self, guardian_id: str) -> list[dict]:
        """The guardian's children: [{"id": ..., "name": ...}]."""
        return []

    async def fetch(
        self,
        resource: str,
        guardian_id: str,
        student_name: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        """One resource for the guardian's children - or one child, by name."""
        raise RecordsUnavailable(self.kind)


class NoRecordsConnector(RecordsConnector):
    """A school with no records system: general questions only."""


class ERPNextConnector(RecordsConnector):
    """A school on ERPNext's Education module."""

    kind = "erpnext"
    available = True

    def __init__(self, service: ERPService):
        self._service = service

    async def children_of(self, guardian_id: str) -> list[dict]:
        if not guardian_id:
            return []
        students = await self._service.get_parent_students(erp_parent_id=guardian_id)
        return [
            {"id": s["name"], "name": s["student_name"].strip()}
            for s in students
            if isinstance(s, dict) and s.get("name") and s.get("student_name")
        ]

    async def fetch(
        self,
        resource: str,
        guardian_id: str,
        student_name: str | None = None,
        session_id: str | None = None,
    ) -> dict:
        return await self._service.fetch(
            resource=resource,
            erp_parent_id=guardian_id,
            student_name=student_name,
            session_id=session_id,
        )


def _erpnext_for(school, default_service: ERPService | None) -> ERPNextConnector:
    prefix = school.records_env_prefix
    if not prefix:
        return ERPNextConnector(default_service or ERPService())
    client = ERPClient(
        base_url=os.getenv(f"{prefix}_BASE_URL"),
        api_key=os.getenv(f"{prefix}_API_KEY"),
        api_secret=os.getenv(f"{prefix}_API_SECRET"),
    )
    return ERPNextConnector(ERPService(client=client))


# kind -> how to build that adapter for a school. A new records system
# is one more entry here and one more adapter class above.
_ADAPTERS = {
    "erpnext": _erpnext_for,
}

# Keyed by the school AND its records setting, so a school whose
# records system was changed in the admin panel gets a fresh connector.
_connectors: dict[tuple, RecordsConnector] = {}


def connector_for(school, default_service: ERPService | None = None) -> RecordsConnector:
    """
    The records connector for a school - built once, then reused.

    default_service is the ERPNext service to use for a school that
    keeps the service's own ERP settings (the first school).
    """
    key = (school.id, school.records, school.records_env_prefix)
    found = _connectors.get(key)
    if found is None:
        build = _ADAPTERS.get(school.records or "")
        found = build(school, default_service) if build else NoRecordsConnector()
        _connectors[key] = found
    return found
