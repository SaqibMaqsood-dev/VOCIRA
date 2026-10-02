"""
ERPNext (Education module) - a live provider, now optional.

Its adapter is the one Vocira always had (erp_services/connectors.py,
erp_service.py): read live through ERPNext's REST API with a read-only API
key. The ERPNext that runs on the development machine is a demo copy for
trying Vocira out, not something Vocira needs.
"""

from backend.microservices.livekit_Rag_services.services.erp_services import connectors as legacy
from backend.microservices.livekit_Rag_services.services.integrations.base import Field, Provider

PROVIDER = Provider(
    kind="erpnext",
    label="ERPNext (Education)",
    description="ERPNext with the Education module, read live through its official REST API.",
    category="provider",
    mode="live",
    setup="connection",
    status="demo",
    fields=(
        Field("base_url", "ERPNext address", "url", placeholder="https://school.erpnext.com"),
        Field("api_key", "API key", "secret", help="ERPNext: User > API Access > Generate Keys - for a read-only user."),
        Field("api_secret", "API secret", "secret"),
    ),
    capabilities=("profile", "attendance", "results", "fees", "marks", "timetable"),
    test=legacy._test_erpnext,
    build=legacy._erpnext_for,
    vendor_url="https://frappe.io/erpnext",
    notes="Optional. Read live on each question with a read-only API key; nothing is copied into Vocira.",
)
