"""
eSchools (AQS Soft) - a school-management system used in Pakistan.

Status: official integration required. No public developer API documentation was found for eSchools.
Vocira does not guess endpoints for it. Ask AQS Soft for official read-only API access and its documentation, then connect it as a Generic REST API. Until then, use its Excel/CSV exports or a Google Sheet.
"""

from backend.microservices.livekit_Rag_services.services.integrations.base import Provider

PROVIDER = Provider(
    kind='eschools',
    label='eSchools (AQS Soft)',
    description="eSchools (AQS Soft) - connected through the vendor's official integration once it is available.",
    category="provider",
    mode="unavailable",
    setup="official",
    status="official_integration_required",
    vendor_url='https://new.eschools.cloud/',
    notes='No public developer API documentation was found for eSchools. Ask AQS Soft for official read-only API access and its documentation, then connect it as a Generic REST API. Until then, use its Excel/CSV exports or a Google Sheet.',
    instead=("excel", "spreadsheet", "rest-api"),
)
