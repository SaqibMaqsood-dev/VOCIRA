"""
Named school-management systems. Each folder is one provider: what it is,
how it is connected, and - for a live system - its adapter.

A provider whose official API Vocira can use is "available" (or "demo");
one without a documented API it can call is "official_integration_required"
and points the school to Excel/CSV, Google Sheets or the Generic REST API
until the vendor provides one. No endpoint here is guessed.
"""
