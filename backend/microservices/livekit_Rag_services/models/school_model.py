from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.helper_functions.database.base import (
    Base,
)


class SchoolRecord(Base):
    """
    A school added from the admin panel (services/tenants.py).

    The first schools are defined in code; everything added later
    lives here, so both the API and the voice worker - separate
    processes - see the same list.
    """

    __tablename__ = "schools"

    id                 : Mapped[str]         = mapped_column(String(40), primary_key=True)
    name               : Mapped[str]         = mapped_column(String(80))
    name_ur            : Mapped[str]         = mapped_column(String(80))
    helpline           : Mapped[str]         = mapped_column(String(30))
    records            : Mapped[str | None]  = mapped_column(String(20), nullable=True)
    records_env_prefix : Mapped[str | None]  = mapped_column(String(40), nullable=True)
    created_at         : Mapped[datetime]    = mapped_column(DateTime, server_default=func.now())
