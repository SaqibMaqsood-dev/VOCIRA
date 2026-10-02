"""
Skoolee - a school-management system used in Pakistan.

Status: official integration required. Skoolee is listed as having an API, but no public documentation for it was found.
Vocira does not guess endpoints for it. Ask the vendor for the API documentation and a read-only key, then connect it as a Generic REST API. Until then, use Excel/CSV exports or a Google Sheet.
"""

from backend.microservices.livekit_Rag_services.services.integrations.base import Provider

PROVIDER = Provider(
    kind='skoolee',
    label='Skoolee',
    description="Skoolee - connected through the vendor's official integration once it is available.",
    category="provider",
    mode="unavailable",
    setup="official",
    status="official_integration_required",
    vendor_url='https://sourceforge.net/software/product/Skoolee/',
    notes='Skoolee is listed as having an API, but no public documentation for it was found. Ask the vendor for the API documentation and a read-only key, then connect it as a Generic REST API. Until then, use Excel/CSV exports or a Google Sheet.',
    instead=("excel", "spreadsheet", "rest-api"),
)
