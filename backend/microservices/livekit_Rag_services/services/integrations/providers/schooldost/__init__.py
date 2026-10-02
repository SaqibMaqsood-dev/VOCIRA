"""
SchoolDost.Cloud - a school-management system used in Pakistan.

Status: official integration required. SchoolDost lists API access as a feature, but its API is not publicly documented.
Vocira does not guess endpoints for it. Ask SchoolDost for the API documentation and a read-only key, then connect it as a Generic REST API. Until then, use its Excel/CSV exports or a Google Sheet.
"""

from backend.microservices.livekit_Rag_services.services.integrations.base import Provider

PROVIDER = Provider(
    kind='schooldost',
    label='SchoolDost.Cloud',
    description="SchoolDost.Cloud - connected through the vendor's official integration once it is available.",
    category="provider",
    mode="unavailable",
    setup="official",
    status="official_integration_required",
    vendor_url='https://schooldost.cloud/',
    notes='SchoolDost lists API access as a feature, but its API is not publicly documented. Ask SchoolDost for the API documentation and a read-only key, then connect it as a Generic REST API. Until then, use its Excel/CSV exports or a Google Sheet.',
    instead=("excel", "spreadsheet", "rest-api"),
)
