"""
Regression tests for two real bugs this project hit while seeding 500
students: a parent's OWN two children sharing a first name silently
mixed both children's data together, and speech-to-text mangling a
child's name past recognition made the assistant refuse outright.

These run against the actual dev ERPNext + Redis (no mocking layer
exists in this codebase for ERPClient) - the same guardians used
throughout manual testing this session:

    EDU-GRD-2026-00356  Ali Naqvi + Ali Baig       (same first name)
    EDU-GRD-2026-00484  Arham Bilal + Bushra Bilal (distinct names)

Run with: uv run --project backend/microservices/livekit_Rag_services pytest backend/microservices/livekit_Rag_services/tests -v
"""
import uuid

import pytest

from backend.microservices.livekit_Rag_services.services.erp_services.erp_service import (
    ERPService,
)

SAME_FIRST_NAME_GUARDIAN = "EDU-GRD-2026-00356"  # Ali Naqvi, Ali Baig
DISTINCT_NAME_GUARDIAN = "EDU-GRD-2026-00484"  # Arham Bilal, Bushra Bilal


def _session_id() -> str:
    """A fresh, unused session id per test - tests must not share
    Redis-backed "last mentioned child" state with each other."""
    return f"pytest-{uuid.uuid4().hex[:12]}"


@pytest.fixture
def erp():
    return ERPService()


async def test_shared_first_name_is_ambiguous_not_merged(erp):
    """
    Two of the SAME parent's children share a first name. Asking for
    just "Ali" must not return either child's data (which risks
    handing back the wrong one) - it must ask which one, naming both.
    """
    result = await erp.fetch(
        resource="attendance",
        erp_parent_id=SAME_FIRST_NAME_GUARDIAN,
        student_name="Ali",
        session_id=_session_id(),
    )

    assert result["data"] == []
    assert "Ali Naqvi" in result["_note"]
    assert "Ali Baig" in result["_note"]


async def test_full_name_resolves_to_exactly_one_child(erp):
    """The same ambiguous pair, asked for by full name, must return
    ONLY that child - never both."""
    result = await erp.fetch(
        resource="attendance",
        erp_parent_id=SAME_FIRST_NAME_GUARDIAN,
        student_name="Ali Naqvi",
        session_id=_session_id(),
    )

    assert len(result["data"]) == 1
    assert result["data"][0]["student_name"] == "Ali Naqvi"


async def test_garbled_name_falls_back_to_last_child_same_session(erp):
    """
    STT sometimes mangles a name past any string-similarity match
    ("Arham" heard as "Khosaera"). Within the SAME session, right
    after that child was already discussed, the follow-up must still
    resolve to them instead of refusing.
    """
    session_id = _session_id()

    first = await erp.fetch(
        resource="assessment",
        erp_parent_id=DISTINCT_NAME_GUARDIAN,
        student_name="Arham Bilal",
        session_id=session_id,
    )
    assert len(first["data"]) == 1
    assert first["data"][0]["student_name"] == "Arham Bilal"

    followup = await erp.fetch(
        resource="assessment",
        erp_parent_id=DISTINCT_NAME_GUARDIAN,
        student_name="Khosaera Arham",  # unrecognisable STT mangling
        session_id=session_id,
    )
    assert len(followup["data"]) == 1
    assert followup["data"][0]["student_name"] == "Arham Bilal"


async def test_garbled_name_with_no_prior_context_is_honest(erp):
    """
    The same unrecognisable name, but a session that never discussed
    either child - there is nothing to fall back to, so the honest
    "not found" (not a guess) is the correct answer.
    """
    result = await erp.fetch(
        resource="assessment",
        erp_parent_id=DISTINCT_NAME_GUARDIAN,
        student_name="Khosaera Arham",
        session_id=_session_id(),
    )

    assert result["data"] == []
    assert "not" in result["_note"].lower() or "misheard" in result["_note"].lower()


async def test_fallback_never_crosses_into_a_different_guardian(erp):
    """
    The last-mentioned-child memory is looked up by session_id alone -
    it must only ever be offered back to fetch() calls that pass the
    authorized student_ids of the SAME guardian who set it. A
    completely unmatched name for an unrelated guardian, sharing no
    session with the first guardian, must not somehow resolve.
    """
    result = await erp.fetch(
        resource="assessment",
        erp_parent_id=SAME_FIRST_NAME_GUARDIAN,
        student_name="Khosaera Arham",  # not a name in EITHER family
        session_id=_session_id(),
    )

    assert result["data"] == []
