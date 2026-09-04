"""
Sirf admin ke liye endpoints.

Kyun zaroori tha: escalations ki list par pehle sirf `current_user`
laga hua tha, yaani KOI BHI logged-in parent saari escalations
dekh sakta tha - doosre khandaan ke sawal bhi. Role ab JWT se
milta hai (verify_tokken.py), is liye is check par koi DB ka
chakkar nahi lagta.
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
