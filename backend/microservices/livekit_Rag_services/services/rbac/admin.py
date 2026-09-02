from fastapi import Depends, HTTPException, status

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
)


async def require_admin(
    user=Depends(current_user),
):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return user
