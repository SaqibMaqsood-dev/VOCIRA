from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.helper_functions.database.base import (
    Base,
)


class SchoolConnection(Base):
    """
    How a school's records system is reached - set on the Schools page
    (services/erp_services/connectors.py). The non-secret settings are
    plain JSON; the secrets (keys, passwords) are encrypted with
    RECORDS_SECRETS_KEY and never sent back to the panel.
    """

    __tablename__ = "school_connections"

    school_id              : Mapped[str]             = mapped_column(String(40), primary_key=True)
    kind                   : Mapped[str]             = mapped_column(String(30))
    settings_json          : Mapped[str]             = mapped_column(Text, default="{}")
    secrets_enc            : Mapped[str | None]      = mapped_column(Text, nullable=True)
    capabilities_json      : Mapped[str]             = mapped_column(Text, default="[]")
    allow_private_network  : Mapped[bool]            = mapped_column(Boolean, default=False)
    last_test_at           : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_ok           : Mapped[bool | None]     = mapped_column(Boolean, nullable=True)
    last_test_summary      : Mapped[str | None]      = mapped_column(Text, nullable=True)
    updated_by             : Mapped[str | None]      = mapped_column(String(120), nullable=True)
    updated_at             : Mapped[datetime]        = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ConnectionAudit(Base):
    """Who connected, changed, tested or disconnected a school's records system, and when."""

    __tablename__ = "connection_audit"

    id         : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id  : Mapped[str]      = mapped_column(String(40), index=True)
    action     : Mapped[str]      = mapped_column(String(30))
    kind       : Mapped[str | None] = mapped_column(String(30), nullable=True)
    actor      : Mapped[str | None] = mapped_column(String(120), nullable=True)
    detail     : Mapped[str | None] = mapped_column(Text, nullable=True)
    at         : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
