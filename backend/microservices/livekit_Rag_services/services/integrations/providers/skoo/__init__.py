"""
eSkooly (Skoo) - a school-management system used in Pakistan.

Status: official integration required. eSkooly does not publish a developer API - its site lists SMS and WhatsApp integrations only.
Vocira does not guess endpoints for it. Export the school's student list, attendance, results and fees to Excel/CSV (or a Google Sheet) and use that. If eSkooly gives the school official API access, connect it as a Generic REST API from their documentation.
"""

from backend.microservices.livekit_Rag_services.services.integrations.base import Provider

PROVIDER = Provider(
    kind='skoo',
    label='eSkooly (Skoo)',
    description="eSkooly (Skoo) - connected through the vendor's official integration once it is available.",
    category="provider",
    mode="unavailable",
    setup="official",
    status="official_integration_required",
    vendor_url='https://www.eskooly.com/',
    notes="eSkooly does not publish a developer API - its site lists SMS and WhatsApp integrations only. Export the school's student list, attendance, results and fees to Excel/CSV (or a Google Sheet) and use that. If eSkooly gives the school official API access, connect it as a Generic REST API from their documentation.",
    instead=("excel", "spreadsheet", "rest-api"),
)
