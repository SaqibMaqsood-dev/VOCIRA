"""
Support tickets - a parent fills in the form, an Issue appears in
ERPNext.

The Support page used to be a dead form: `type="button"`, no onClick,
no fetch. Typing something and pressing Submit did nothing at all.

These endpoints now sit behind it. The ticket is created in ERPNext's
Issue doctype - where the school's own Support module already
provides the full UI (localhost:8081/app/issue).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
    optional_current_user,
)

from backend.microservices.auth_services.models.user_model import Users

from backend.microservices.livekit_Rag_services.services.erp_services.support_service import (
    SupportService,
)


router = APIRouter(
    prefix="/support",
    tags=["Support"],
)

support_service = SupportService()


class TicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=140)
    message: str = Field(default="", max_length=5000)

    # Required for a guest, redundant for a logged-in parent.
    # The endpoint decides which case applies - the schema serves
    # both.
    email: EmailStr | None = None


class TicketResponse(BaseModel):
    ticket_id: str | None = None
    subject: str | None = None
    status: str | None = None
    priority: str | None = None
    opening_date: str | None = None


async def _caller_email(db: AsyncSession, user) -> tuple[str | None, str | None]:
    """
    Ticket kis ke naam par bane.

    In the token username = email, but that alone is not trusted -
    the DB confirms the user really exists.

    Returns (email, name) - the name goes into the ticket too, or the
    school sees nothing but an email address.
    """

    row = (
        await db.execute(
            select(Users).where(Users.user_id == user.user_id)
        )
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return row.email or user.username, row.name


# =========================================================
# NAYA TICKET
# =========================================================

@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    request: TicketRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(optional_current_user),
):
    """
    Ticket banayein - login ke sath ya us ke baghair.

    Logged in     : the email comes from the account
    Not logged in : the email must be filled into the form

    IMPORTANT: when logged in, the email in the request is ignored
    DELIBERATELY. Otherwise anyone could send someone else's email
    with their own token and open a ticket in that person's name -
    and it would then show up in that person's ticket list.
    """

    if user is not None:
        email, name = await _caller_email(db=db, user=user)

    else:
        name = None
        if not request.email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Please provide your email address, "
                    "or log in to submit a ticket."
                ),
            )

        email = str(request.email).strip().lower()

    try:
        result = await support_service.create_ticket(
            subject=request.subject,
            message=request.message,
            raised_by=email,
            raised_by_name=name,
        )

    except HTTPException:
        # ERPClient has already produced a meaningful error
        raise

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        )

    if not result.get("ticket_id"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Ticket could not be created in the school system",
        )

    print(
        f"[Support] ticket bana: {result['ticket_id']}  "
        f"({email}, {'login' if user else 'guest'})"
    )

    return result


# =========================================================
# MERE TICKETS
# =========================================================

@router.get("/tickets")
async def my_tickets(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    email, _ = await _caller_email(db=db, user=user)

    # The filter is applied inside the service - a parent cannot
    # ask for anyone else's tickets.
    return await support_service.list_tickets(
        raised_by=email,
        limit=min(limit, 50),
    )
