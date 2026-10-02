"""
Vocira's canonical records - one shape for every school's student records,
whatever they came from (services/integrations/).

A school's records reach these tables from an Excel/CSV upload, its live
Google Sheets, an approved REST API, a read-only database, or Vocira's own
Native Records (typed in on the admin panel). A school on a live system
(ERPNext, Open School MIS) is read through its adapter instead and keeps
nothing here.

Every row carries its school. Nothing reads these tables without one:
services/integrations/store.py filters every query by school_id, and the
tests in tests/test_integrations_tenancy.py check that one school never
sees another's rows.

Dates are kept as ISO text (2026-10-02), the way every source gives them.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.helper_functions.database.base import (
    Base,
)


class _RecordRow:
    """What every canonical row has: its school, where it came from, and any extra columns."""

    id         : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id  : Mapped[str]      = mapped_column(String(40), index=True)
    # native | excel | sheets | rest-api | database
    source     : Mapped[str]      = mapped_column(String(30), default="native")
    # columns the source had beyond the canonical ones - read out like any other
    extra_json : Mapped[str]      = mapped_column(Text, default="{}")
    updated_at : Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RecGuardian(_RecordRow, Base):
    __tablename__ = "rec_guardians"
    __table_args__ = (UniqueConstraint("school_id", "guardian_id", name="uq_rec_guardian"),)

    guardian_id : Mapped[str]        = mapped_column(String(80))
    name        : Mapped[str]        = mapped_column(String(160))
    email       : Mapped[str | None] = mapped_column(String(200), nullable=True)
    mobile      : Mapped[str | None] = mapped_column(String(40), nullable=True)
    relation    : Mapped[str | None] = mapped_column(String(40), nullable=True)


class RecStudent(_RecordRow, Base):
    __tablename__ = "rec_students"
    __table_args__ = (UniqueConstraint("school_id", "student_id", name="uq_rec_student"),)

    student_id    : Mapped[str]        = mapped_column(String(80))
    name          : Mapped[str]        = mapped_column(String(160))
    class_name    : Mapped[str | None] = mapped_column(String(80), nullable=True)
    section       : Mapped[str | None] = mapped_column(String(40), nullable=True)
    roll_no       : Mapped[str | None] = mapped_column(String(40), nullable=True)
    gender        : Mapped[str | None] = mapped_column(String(20), nullable=True)
    date_of_birth : Mapped[str | None] = mapped_column(String(20), nullable=True)


class RecStudentGuardian(_RecordRow, Base):
    """Which guardian a student belongs to - a child can have more than one."""

    __tablename__ = "rec_student_guardians"
    __table_args__ = (UniqueConstraint("school_id", "student_id", "guardian_id", name="uq_rec_student_guardian"),)

    student_id  : Mapped[str] = mapped_column(String(80))
    guardian_id : Mapped[str] = mapped_column(String(80))


class RecClass(_RecordRow, Base):
    __tablename__ = "rec_classes"
    __table_args__ = (UniqueConstraint("school_id", "class_id", name="uq_rec_class"),)

    class_id      : Mapped[str]        = mapped_column(String(80))
    name          : Mapped[str]        = mapped_column(String(80))
    section       : Mapped[str | None] = mapped_column(String(40), nullable=True)
    class_teacher : Mapped[str | None] = mapped_column(String(160), nullable=True)


class RecTeacher(_RecordRow, Base):
    __tablename__ = "rec_teachers"
    __table_args__ = (UniqueConstraint("school_id", "teacher_id", name="uq_rec_teacher"),)

    teacher_id : Mapped[str]        = mapped_column(String(80))
    name       : Mapped[str]        = mapped_column(String(160))
    email      : Mapped[str | None] = mapped_column(String(200), nullable=True)
    mobile     : Mapped[str | None] = mapped_column(String(40), nullable=True)
    subject    : Mapped[str | None] = mapped_column(String(120), nullable=True)


class RecAttendance(_RecordRow, Base):
    __tablename__ = "rec_attendance"
    __table_args__ = (Index("ix_rec_attendance_student", "school_id", "student_id"),)

    student_id : Mapped[str]        = mapped_column(String(80))
    date       : Mapped[str]        = mapped_column(String(20))
    status     : Mapped[str]        = mapped_column(String(20))
    remarks    : Mapped[str | None] = mapped_column(Text, nullable=True)


class RecFee(_RecordRow, Base):
    __tablename__ = "rec_fees"
    __table_args__ = (Index("ix_rec_fees_student", "school_id", "student_id"),)

    student_id  : Mapped[str]          = mapped_column(String(80))
    description : Mapped[str | None]   = mapped_column(String(160), nullable=True)
    amount      : Mapped[float | None] = mapped_column(Float, nullable=True)
    paid        : Mapped[float | None] = mapped_column(Float, nullable=True)
    outstanding : Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date    : Mapped[str | None]   = mapped_column(String(20), nullable=True)
    status      : Mapped[str | None]   = mapped_column(String(30), nullable=True)


class RecResult(_RecordRow, Base):
    __tablename__ = "rec_results"
    __table_args__ = (Index("ix_rec_results_student", "school_id", "student_id"),)

    student_id : Mapped[str]          = mapped_column(String(80))
    subject    : Mapped[str]          = mapped_column(String(120))
    marks      : Mapped[float | None] = mapped_column(Float, nullable=True)
    total      : Mapped[float | None] = mapped_column(Float, nullable=True)
    grade      : Mapped[str | None]   = mapped_column(String(20), nullable=True)
    exam       : Mapped[str | None]   = mapped_column(String(120), nullable=True)
    year       : Mapped[str | None]   = mapped_column(String(20), nullable=True)


class RecTimetable(_RecordRow, Base):
    __tablename__ = "rec_timetable"
    __table_args__ = (Index("ix_rec_timetable_class", "school_id", "class_name"),)

    class_name : Mapped[str]        = mapped_column(String(80))
    day        : Mapped[str]        = mapped_column(String(20))
    subject    : Mapped[str]        = mapped_column(String(120))
    start_time : Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_time   : Mapped[str | None] = mapped_column(String(10), nullable=True)
    teacher    : Mapped[str | None] = mapped_column(String(160), nullable=True)
    room       : Mapped[str | None] = mapped_column(String(40), nullable=True)


class RecAnnouncement(_RecordRow, Base):
    __tablename__ = "rec_announcements"

    title     : Mapped[str]        = mapped_column(String(200))
    message   : Mapped[str]        = mapped_column(Text)
    # "all", or one class's name
    audience  : Mapped[str]        = mapped_column(String(80), default="all")
    date      : Mapped[str | None] = mapped_column(String(20), nullable=True)
    expires   : Mapped[str | None] = mapped_column(String(20), nullable=True)


class IntegrationSyncRun(Base):
    """One sync of a school's records: what started it, how it went, how many rows each table got."""

    __tablename__ = "integration_sync_runs"

    id          : Mapped[int]             = mapped_column(Integer, primary_key=True, autoincrement=True)
    school_id   : Mapped[str]             = mapped_column(String(40), index=True)
    kind        : Mapped[str]             = mapped_column(String(30))
    # initial | manual | scheduled | upload | retry
    trigger     : Mapped[str]             = mapped_column(String(20))
    # running | success | partial | failed
    status      : Mapped[str]             = mapped_column(String(20), default="running")
    attempts    : Mapped[int]             = mapped_column(Integer, default=1)
    counts_json : Mapped[str]             = mapped_column(Text, default="{}")
    summary     : Mapped[str | None]      = mapped_column(Text, nullable=True)
    # never a credential: services/integrations/security.py scrubs it first
    error       : Mapped[str | None]      = mapped_column(Text, nullable=True)
    actor       : Mapped[str | None]      = mapped_column(String(120), nullable=True)
    started_at  : Mapped[datetime]        = mapped_column(DateTime, server_default=func.now())
    finished_at : Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
