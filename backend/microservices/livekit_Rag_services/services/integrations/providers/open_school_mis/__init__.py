"""
Globussoft Open School MIS - a live provider, now optional.

Its adapter (erp_services/open_school_mis.py) signs in with a service
account and reads the MIS REST API. The MIS running on the development
machine (Medicaps' demo) is a demo copy, not something Vocira needs.
"""

from backend.microservices.livekit_Rag_services.services.erp_services import connectors as legacy
from backend.microservices.livekit_Rag_services.services.erp_services import open_school_mis
from backend.microservices.livekit_Rag_services.services.integrations.base import Field, Provider

PROVIDER = Provider(
    kind="open-school-mis",
    label="Open School MIS",
    description="Globussoft Open School MIS (MIS-ILSMS), read live through its REST API with a service account.",
    category="provider",
    mode="live",
    setup="connection",
    status="demo",
    fields=(
        Field("base_url", "MIS API address", "url", placeholder="https://mis.school.edu/api/v1",
              help="The address of the MIS API, ending in /api/v1."),
        Field("email", "Service account email", "email", placeholder="vocira@school.edu",
              help="An MIS account made for Vocira - not a person's own login."),
        Field("password", "Service account password", "secret"),
    ),
    capabilities=("profile", "attendance", "results", "fees", "marks"),
    test=open_school_mis.test,
    build=legacy._mis_for,
    vendor_url="https://github.com/sumitglobussoft/globussoft-school-mis",
    notes="Optional. Read live on each question; nothing is copied into Vocira.",
)
