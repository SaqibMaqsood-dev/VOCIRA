"""
Which school a call belongs to, and what that school has.

One voice agent serves every school. What differs is per school and
lives here: its name and helpline, where its documents are, the
Pinecone namespace its knowledge is searched in, and whether it has a
records system (ERP) at all.

Adding a school is adding an entry below and uploading its documents
- the agent, the router and the prompts do not change.

The school of a call comes from the login or the link the caller
opened, never from anything said on the call: "I am from the other
school" must not open another school's knowledge or records.
"""

import os
from dataclasses import dataclass

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    DATA_DIR,
    PDF_PATH,
    PINECONE_NAMESPACE,
    TEXT_FILES_PATH,
    URLS_FILE_PATH,
)


@dataclass(frozen=True)
class School:
    id: str
    name: str            # as said in English
    name_ur: str         # as said in Urdu
    helpline: str        # digits as written, read out digit by digit
    namespace: str       # Pinecone namespace its knowledge is in
    pdf_dir: str
    text_dir: str
    urls_file: str
    records: str | None  # "erpnext", or None: general questions only
    # Where this school's records system credentials are read from:
    # <PREFIX>_BASE_URL / _API_KEY / _API_SECRET in the environment -
    # never in code. None = the service's own ERP_* settings.
    records_env_prefix: str | None = None

    def display_name(self, language: str | None) -> str:
        return self.name_ur if (language or "").lower() == "ur" else self.name


def _school_dir(school_id: str) -> str:
    return os.path.join(DATA_DIR, "schools", school_id)


# The first school keeps the folders and namespace it always had, so
# its knowledge base stays exactly as it was - nothing to re-index.
EDUCATORS = School(
    id="educators",
    name="The Educators",
    name_ur="دی ایجوکیٹرز",
    helpline="042-111-777-800",
    namespace=PINECONE_NAMESPACE,
    pdf_dir=PDF_PATH,
    text_dir=TEXT_FILES_PATH,
    urls_file=URLS_FILE_PATH,
    records="erpnext",
)

# A made-up second school for the demo: general questions only, no
# records system connected.
DEMO_B = School(
    id="demo-b",
    name="Demo School B",
    name_ur="ڈیمو اسکول بی",
    helpline="021-111-000-222",
    namespace="school-demo-b",
    pdf_dir=os.path.join(_school_dir("demo-b"), "pdf"),
    text_dir=os.path.join(_school_dir("demo-b"), "text_files"),
    urls_file=os.path.join(_school_dir("demo-b"), "urls.txt"),
    records=None,
)

SCHOOLS: dict[str, School] = {s.id: s for s in (EDUCATORS, DEMO_B)}

DEFAULT_SCHOOL_ID = EDUCATORS.id


def get_school(school_id: str | None) -> School:
    """The school for an id - the default one for anything unknown."""
    return SCHOOLS.get((school_id or "").strip().lower(), SCHOOLS[DEFAULT_SCHOOL_ID])


def is_known(school_id: str | None) -> bool:
    return (school_id or "").strip().lower() in SCHOOLS


def public_list() -> list[dict]:
    """What the admin panel and the frontend may know about each school."""
    return [
        {
            "id": s.id,
            "name": s.name,
            "name_ur": s.name_ur,
            "helpline": s.helpline,
            "namespace": s.namespace,
            "records": s.records,
        }
        for s in SCHOOLS.values()
    ]
