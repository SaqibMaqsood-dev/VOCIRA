"""
Endpoints restricted to admins.

Why this was needed: the escalations list carried only
`current_user`, meaning ANY logged-in parent could see every
escalation - including other families' questions. The role now comes
from the JWT (verify_tokken.py), so this check costs no trip to the
database.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)


ADMIN_ROLES = {"admin"}


async def require_admin(
    user: Annotated[object, Depends(current_user)],
):
    """Caller admin na ho to 403."""

    role = (getattr(user, "role", None) or "").strip().lower()

    if role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This area is for administrators only",
        )

    return user
