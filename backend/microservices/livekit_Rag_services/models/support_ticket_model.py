from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Identity, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.helper_functions.database.base import (
    Base,
)

# a ticket's states, as the school's admin moves it along
TICKET_STATUSES = ("open", "in_progress", "resolved")

# A resolved ticket stays among a parent's tickets this long after it was
# resolved, then moves under "older tickets" - nothing is deleted.
RESOLVED_VISIBLE_DAYS = 30


class SupportTicket(Base):
    """
    A message from the Support page - a guest's or a guardian's - for their
    own school's admin (the panel's Tickets page).

    These went to the first school's ERPNext before, whichever school the
    parent was from: another school then saw a parent's name, email and
    message, and their own school never did.
    """

    __tablename__ = "support_tickets"

    id         : Mapped[UUID]         = mapped_column(SQLUUID(as_uuid=True), default=uuid4, primary_key=True)
    # the reference a parent is given: T-0007
    number     : Mapped[int]          = mapped_column(Integer, Identity(), unique=True)
    school_id  : Mapped[str]          = mapped_column(String(40), index=True)
    # a guardian's account; None for a guest
    user_id    : Mapped[UUID | None]  = mapped_column(SQLUUID(as_uuid=True), nullable=True, index=True)
    name       : Mapped[str | None]   = mapped_column(String(100), nullable=True)
    email      : Mapped[str]          = mapped_column(String(200))
    subject    : Mapped[str]          = mapped_column(String(140))
    message    : Mapped[str]          = mapped_column(Text, default="")
    status     : Mapped[str]          = mapped_column(String(20), default="open", server_default="open")
    # the school's answer - shown to a guardian on their Support page
    reply      : Mapped[str | None]   = mapped_column(Text, nullable=True)
    created_at : Mapped[datetime]     = mapped_column(DateTime, server_default=func.now())
    updated_at : Mapped[datetime]     = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    # when it was resolved - not updated_at, which moves with every edit of
    # the reply; cleared when the ticket is opened again
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    @property
    def reference(self) -> str:
        return f"T-{self.number:04d}" if self.number else "T-?"
