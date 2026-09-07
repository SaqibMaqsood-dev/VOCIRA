"""
Support tickets - parent form bhare, ERPNext mein Issue bane.

Support page pehle ek murda form tha: `type="button"`, koi onClick
nahi, koi fetch nahi. Likhne aur Submit dabane se kuch nahi hota tha.

Ab ye endpoints us ke peeche hain. Ticket ERPNext ke Issue doctype
mein banta hai - wahin jahan school ka apna Support module pehle se
poora UI rakhta hai (localhost:8081/app/issue).
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

    # Guest ke liye lazmi, logged-in parent ke liye faltu.
    # Kaun sa haal hai, wo endpoint tay karta hai - schema dono
    # sooraton mein chalta hai.
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

    Token mein username = email hota hai, magar us par akela bharosa
    nahi karte - DB se tasdeeq karte hain ke ye user waqai mojood hai.

    Returns (email, naam) - naam ticket mein bhi jata hai, warna
    school ko sirf email nazar aata hai.
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

    Login ho    : email account se aata hai
    Login na ho : email form mein bharna lazmi hai

    AHEM: logged-in surat mein request ka email JAAN BUJH KAR
    nazarandaz hota hai. Warna koi bhi apne token ke sath doosre ka
    email bhej kar us ke naam par ticket khol sakta - aur wo us ki
    ticket list mein nazar aane lagta.
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
        # ERPClient ne pehle se maani-khez ghalti banai hai
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
        f"🎫 [Support] ticket bana: {result['ticket_id']}  "
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

    # Filter service ke andar lagti hai - parent doosre ke tickets
    # maang hi nahi sakta.
    return await support_service.list_tickets(
        raised_by=email,
        limit=min(limit, 50),
    )
