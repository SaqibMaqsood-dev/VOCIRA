"""
Support tickets - a parent fills in the Support form, and the ticket goes
to their own school's admin (the panel's Tickets page, admin_route.py).

Which school:
    a guardian   their account's school - never the page's word for it
    a guest      the school whose address the form was sent from

These used to become Issues in the first school's ERPNext, whatever school
the parent was from: another school saw a parent's name, email and message,
and the parent's own school - on a spreadsheet, or the MIS - never did.
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.helper_functions.database.session import get_db

from backend.helper_functions.token_service.access_tokken.get_current_user import (
    current_user,
    optional_current_user,
)

from backend.microservices.auth_services.models.user_model import Users
from backend.microservices.livekit_Rag_services.models.support_ticket_model import (
    RESOLVED_VISIBLE_DAYS,
    SupportTicket,
)
from backend.microservices.livekit_Rag_services.services import tenants


router = APIRouter(
    prefix="/support",
    tags=["Support"],
)

# how a ticket's state reads on the parent's side
STATUS_LABEL = {"open": "Open", "in_progress": "In progress", "resolved": "Resolved"}


class TicketRequest(BaseModel):
    subject: str = Field(min_length=3, max_length=140)
    message: str = Field(default="", max_length=5000)

    # Required for a guest, redundant for a logged-in parent.
    # The endpoint decides which case applies - the schema serves
    # both.
    email: EmailStr | None = None

    # The school whose address the form was sent from - a guest's school.
    # A guardian's comes from their account instead.
    school: str | None = Field(default=None, max_length=60)


class TicketResponse(BaseModel):
    ticket_id: str | None = None
    subject: str | None = None
    status: str | None = None
    priority: str | None = None
    opening_date: str | None = None


async def _caller(db: AsyncSession, user) -> Users:
    """
    The account the ticket is from.

    In the token username = email, but that alone is not trusted -
    the DB confirms the user really exists.
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

    return row


def _date(when: datetime | None) -> str | None:
    return when.strftime("%Y-%m-%d") if when else None


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

    Logged in     : the email and the school come from the account
    Not logged in : the email must be filled into the form, and the
                    school is the one whose address the form is on

    IMPORTANT: when logged in, the email in the request is ignored
    DELIBERATELY. Otherwise anyone could send someone else's email
    with their own token and open a ticket in that person's name -
    and it would then show up in that person's ticket list.
    """

    await tenants.refresh()

    if user is not None:
        account = await _caller(db=db, user=user)
        email, name, user_id = account.email or user.username, account.name, account.user_id
        school = tenants.get_school(account.school_id or tenants.default_school_id())

    else:
        if not request.email:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Please provide your email address, "
                    "or log in to submit a ticket."
                ),
            )
        email, name, user_id = str(request.email).strip().lower(), None, None
        school = tenants.find_by_address(request.school)
        if school is None:
            # never a default school: the ticket would reach the wrong one
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Open the Support page from your school's own address to send it to your school.",
            )

    subject = request.subject.strip()
    if len(subject) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Subject must be at least 3 characters.",
        )

    ticket = SupportTicket(
        school_id=school.id,
        user_id=user_id,
        name=name,
        email=email,
        subject=subject,
        message=request.message.strip(),
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    print(
        f"[Support] ticket {ticket.reference} for {school.id} "
        f"({email}, {'login' if user else 'guest'})"
    )

    return TicketResponse(
        ticket_id=ticket.reference,
        subject=ticket.subject,
        status=STATUS_LABEL.get(ticket.status, ticket.status),
        opening_date=_date(ticket.created_at),
    )


# =========================================================
# MERE TICKETS
# =========================================================

@router.get("/tickets")
async def my_tickets(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user=Depends(current_user),
):
    """
    The caller's own tickets, with the school's reply: the ones still open
    first, then the resolved ones - each newest first. A ticket resolved
    more than RESOLVED_VISIBLE_DAYS ago is marked "older": the page keeps
    it behind "Show older tickets" (nothing is deleted).
    """
    account = await _caller(db=db, user=user)

    older = (
        SupportTicket.resolved_at < func.now() - timedelta(days=RESOLVED_VISIBLE_DAYS)
    ).label("older")
    rows = (
        await db.execute(
            select(SupportTicket, older)
            .where(SupportTicket.user_id == account.user_id)
            .order_by(
                case((SupportTicket.status == "resolved", 1), else_=0),
                SupportTicket.created_at.desc(),
            )
            .limit(min(max(limit, 1), 50))
        )
    ).all()

    return [
        {
            "name": t.reference,
            "subject": t.subject,
            "status": STATUS_LABEL.get(t.status, t.status),
            "opening_date": _date(t.created_at),
            "resolved_date": _date(t.resolved_at),
            "reply": t.reply,
            "older": bool(is_older),
        }
        for t, is_older in rows
    ]
