"""
Endpoints restricted to admins.

Why this was needed: the escalations list carried only
`current_user`, meaning ANY logged-in parent could see every
escalation - including other families' questions. The role now comes
from the JWT (verify_tokken.py), so this check costs no trip to the
database.

Two kinds of administrator (one agent, many schools):

    super_admin  runs the platform - every school; adds and removes
                 schools. Their token carries no school.
    admin        runs ONE school - only that school's calls, knowledge,
                 escalations and accounts. Their token carries the
                 school; a token from before schools existed carries
                 none and means the first school.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)


SUPER_ADMIN_ROLE = "super_admin"
ADMIN_ROLES = {"admin", SUPER_ADMIN_ROLE}

# The first school - the one every account belonged to before schools
# existed. Kept here (not imported from the voice service) so the auth
# service can use it too.
DEFAULT_SCHOOL_ID = "educators"


def _role(user) -> str:
    return (getattr(user, "role", None) or "").strip().lower()


def is_super_admin(user) -> bool:
    return _role(user) == SUPER_ADMIN_ROLE


def caller_school(user) -> str | None:
    """
    The school an administrator is limited to: a school admin's own
    (the first school when their token has none), or None for a super
    admin - who is not limited to any.
    """
    if is_super_admin(user):
        return None
    return (getattr(user, "school_id", None) or DEFAULT_SCHOOL_ID).strip().lower()


async def require_admin(
    user: Annotated[object, Depends(current_user)],
):
    """Caller admin (or super admin) na ho to 403."""

    if _role(user) not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is for administrators only",
        )

    return user


async def require_super_admin(
    user: Annotated[object, Depends(current_user)],
):
    """Only the platform's super admin - not a school's admin."""

    if not is_super_admin(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the platform's super admin can do this",
        )

    return user
