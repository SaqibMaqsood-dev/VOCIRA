"""
The Records Integration Hub - how a school's student records reach Vocira,
whatever system the school runs (or none).

    Third-party system      ERPNext, Open School MIS, a REST API, a database,
            |               Google Sheets, an Excel/CSV upload - or nothing
    Provider adapter        providers/, generic/, native/
            |
    Data normalizer         normalizer.py - columns mapped to Vocira's fields
            |
    Canonical records       canonical.py (the shape), store.py (Postgres)
            |
    AI tools                tools.py - get_student, get_fee_status,
                            get_attendance, get_results, get_timetable,
                            get_announcements

The agent never talks to a provider. It asks the tools, and the tools ask
the school's adapter (registry.connector_for). A live system (ERPNext,
Open School MIS) is read through its adapter on each question; every other
source is copied into the canonical tables by the sync engine (sync.py)
and read from there.

Every record belongs to one school, and every read and write names it.
"""
