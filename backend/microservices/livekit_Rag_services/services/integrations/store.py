"""
The canonical records store - Postgres (models/canonical_records_model.py).

Every function takes the school first, and every query filters by it: a
row is only ever read, changed or deleted together with its school_id.
That is the whole of tenant isolation here, so nothing in this file may
query a records table without it (tests/test_integrations_tenancy.py).

A copied source replaces a table wholesale on each sync (replace_table);
Native Records change one row at a time (create_row, update_row, ...).
"""

import json
import re
from datetime import date

from sqlalchemy import String, delete, func, insert, or_, select

from backend.helper_functions.database.session import SessionLocal
from backend.microservices.livekit_Rag_services.models import canonical_records_model as m
from backend.microservices.livekit_Rag_services.services.integrations import canonical


def _school(school_id: str) -> str:
    school_id = (school_id or "").strip().lower()
    if not school_id:
        raise ValueError("A school is needed for every records query.")
    return school_id


def _limit(model, column: str, value):
    """A value cut to its column's length - a long cell must not fail the whole import."""
    if isinstance(value, str):
        length = getattr(model.__table__.c[column].type, "length", None)
        if length and len(value) > length:
            return value[:length]
    return value


def _to_model(table: str, row: dict, school_id: str, source: str) -> dict:
    t = canonical.spec(table)
    out = {"school_id": school_id, "source": source}
    for name, column in t["columns"].items():
        if name in row:
            out[column] = _limit(t["model"], column, row[name])
    extra = row.get("_extra") or {}
    out["extra_json"] = json.dumps(extra, ensure_ascii=False) if extra else "{}"
    return out


def _from_model(table: str, obj) -> dict:
    t = canonical.spec(table)
    out = {"id": obj.id, "source": obj.source}
    for name, column in t["columns"].items():
        out[name] = getattr(obj, column)
    try:
        extra = json.loads(obj.extra_json or "{}")
    except ValueError:
        extra = {}
    if extra:
        out["_extra"] = extra
    return out


def _key(value) -> str:
    return str(value or "").strip().lower()


# =========================================================
# A copied source: one table at a time, replaced wholesale
# =========================================================

async def replace_table(school_id: str, table: str, rows: list[dict], source: str) -> int:
    """The school's copy of one table becomes `rows` (canonical rows, from the normalizer)."""
    school_id = _school(school_id)
    t = canonical.spec(table)
    model = t["model"]
    async with SessionLocal() as db:
        if table == "students":
            await _replace_students(db, school_id, rows, source)
        else:
            await db.execute(delete(model).where(model.school_id == school_id))
            key = t["key"]
            if key:
                # one row per id - a repeated id is the same record listed twice
                rows = list({_key(r.get(key)): r for r in rows if r.get(key)}.values())
            if rows:
                await db.execute(insert(model), [_to_model(table, r, school_id, source) for r in rows])
        await db.commit()
    return len(rows)


async def _replace_students(db, school_id: str, rows: list[dict], source: str) -> None:
    await db.execute(delete(m.RecStudentGuardian).where(m.RecStudentGuardian.school_id == school_id))
    await db.execute(delete(m.RecStudent).where(m.RecStudent.school_id == school_id))

    students, links, named = {}, {}, {}
    for r in rows:
        sid = r["student_id"]
        students.setdefault(_key(sid), r)
        gid = r.get("guardian_id")
        if not gid:
            continue
        links[(_key(sid), _key(gid))] = (students[_key(sid)]["student_id"], gid)
        g = named.setdefault(_key(gid), {"guardian_id": gid})
        for field_name in ("guardian_name", "guardian_email", "guardian_mobile"):
            if r.get(field_name) and not g.get(field_name):
                g[field_name] = r[field_name]

    if students:
        await db.execute(insert(m.RecStudent), [_to_model("students", r, school_id, source) for r in students.values()])
    if links:
        await db.execute(insert(m.RecStudentGuardian), [
            {"school_id": school_id, "source": source, "student_id": sid, "guardian_id": gid, "extra_json": "{}"}
            for sid, gid in links.values()
        ])

    # the parents the students name: added, or brought up to date
    existing = {_key(g.guardian_id): g for g in (await db.execute(
        select(m.RecGuardian).where(m.RecGuardian.school_id == school_id))).scalars()}
    fresh = []
    for key, g in named.items():
        found = existing.get(key)
        if found is None:
            fresh.append(_to_model("guardians", {**g, "guardian_name": g.get("guardian_name") or g["guardian_id"]},
                                   school_id, source))
            continue
        for field_name, column in (("guardian_name", "name"), ("guardian_email", "email"), ("guardian_mobile", "mobile")):
            if g.get(field_name):
                setattr(found, column, _limit(m.RecGuardian, column, g[field_name]))
    if fresh:
        await db.execute(insert(m.RecGuardian), fresh)
    # parents an earlier copy of this same source brought, whom no student names any more
    stale = [g.id for key, g in existing.items() if g.source == source and key not in named]
    if stale:
        await db.execute(delete(m.RecGuardian).where(m.RecGuardian.school_id == school_id, m.RecGuardian.id.in_(stale)))


async def clear(school_id: str) -> None:
    """Every canonical record of a school - when it is removed from the platform."""
    school_id = _school(school_id)
    async with SessionLocal() as db:
        for t in canonical.TABLES.values():
            await db.execute(delete(t["model"]).where(t["model"].school_id == school_id))
        await db.execute(delete(m.RecStudentGuardian).where(m.RecStudentGuardian.school_id == school_id))
        await db.commit()


# =========================================================
# Reading - what the agent's tools and the admin panel ask
# =========================================================

async def counts(school_id: str) -> dict[str, int]:
    school_id = _school(school_id)
    out = {}
    async with SessionLocal() as db:
        for name, t in canonical.TABLES.items():
            model = t["model"]
            out[name] = (await db.execute(
                select(func.count()).select_from(model).where(model.school_id == school_id))).scalar() or 0
    return out


async def has_rows(school_id: str, table: str) -> bool:
    school_id = _school(school_id)
    model = canonical.spec(table)["model"]
    async with SessionLocal() as db:
        found = (await db.execute(select(model.id).where(model.school_id == school_id).limit(1))).first()
    return found is not None


async def has_students(school_id: str) -> bool:
    school_id = _school(school_id)
    async with SessionLocal() as db:
        found = (await db.execute(
            select(m.RecStudent.id).where(m.RecStudent.school_id == school_id).limit(1))).first()
    return found is not None


async def children_of(school_id: str, guardian_id: str) -> list[dict]:
    """A guardian's own children - by the link, never by anything said on a call."""
    school_id = _school(school_id)
    if not guardian_id:
        return []
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(m.RecStudent)
            .join(m.RecStudentGuardian, (m.RecStudentGuardian.school_id == m.RecStudent.school_id)
                  & (func.lower(m.RecStudentGuardian.student_id) == func.lower(m.RecStudent.student_id)))
            .where(m.RecStudent.school_id == school_id,
                   func.lower(m.RecStudentGuardian.guardian_id) == _key(guardian_id))
            .order_by(m.RecStudent.name)
        )).scalars().all()
    seen, out = set(), []
    for s in rows:
        if _key(s.student_id) in seen:
            continue
        seen.add(_key(s.student_id))
        out.append({"id": s.student_id, "name": s.name, "class": s.class_name, "section": s.section})
    return out


async def guardians(school_id: str) -> list[dict]:
    """Every parent in the school's records, for the Accounts page: id, name, email, mobile, children."""
    school_id = _school(school_id)
    async with SessionLocal() as db:
        parents = (await db.execute(
            select(m.RecGuardian).where(m.RecGuardian.school_id == school_id))).scalars().all()
        links = (await db.execute(
            select(m.RecStudentGuardian.guardian_id, func.count())
            .where(m.RecStudentGuardian.school_id == school_id)
            .group_by(m.RecStudentGuardian.guardian_id))).all()
    children = {}
    for gid, n in links:
        children[_key(gid)] = children.get(_key(gid), 0) + n
    out = [
        {"id": g.guardian_id, "name": g.name or g.guardian_id, "email": g.email, "mobile": g.mobile,
         "students": children.get(_key(g.guardian_id), 0)}
        for g in parents
    ]
    return sorted(out, key=lambda g: (g["name"] or "").lower())


async def guardian(school_id: str, guardian_id: str) -> dict | None:
    school_id = _school(school_id)
    async with SessionLocal() as db:
        g = (await db.execute(select(m.RecGuardian).where(
            m.RecGuardian.school_id == school_id, func.lower(m.RecGuardian.guardian_id) == _key(guardian_id)))).scalar()
    return _from_model("guardians", g) if g else None


async def records_for(school_id: str, table: str, student_ids: list[str]) -> list[dict]:
    """A table's rows for these students only (students, attendance, fees, results)."""
    school_id = _school(school_id)
    model = canonical.spec(table)["model"]
    wanted = [_key(s) for s in student_ids if s]
    if not wanted:
        return []
    # attendance newest first; everything else in the order the source listed it
    order = [model.date.desc()] if table == "attendance" else [model.id]
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(model).where(model.school_id == school_id, func.lower(model.student_id).in_(wanted)).order_by(*order)
        )).scalars().all()
    return [_from_model(table, r) for r in rows]


async def timetable_for(school_id: str, class_names: list[str]) -> list[dict]:
    school_id = _school(school_id)
    wanted = [_key(c) for c in class_names if c]
    if not wanted:
        return []
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(m.RecTimetable).where(m.RecTimetable.school_id == school_id,
                                         func.lower(m.RecTimetable.class_name).in_(wanted))
            .order_by(m.RecTimetable.class_name, m.RecTimetable.id)
        )).scalars().all()
    return [_from_model("timetable", r) for r in rows]


async def announcements(school_id: str, class_names: list[str] | None = None, today: str | None = None) -> list[dict]:
    """The notices showing today: for everyone, or for one of these classes."""
    school_id = _school(school_id)
    today = today or date.today().isoformat()
    audiences = ["all", ""] + [_key(c) for c in (class_names or []) if c]
    async with SessionLocal() as db:
        rows = (await db.execute(
            select(m.RecAnnouncement).where(
                m.RecAnnouncement.school_id == school_id,
                func.lower(func.coalesce(m.RecAnnouncement.audience, "all")).in_(audiences),
                or_(m.RecAnnouncement.date.is_(None), m.RecAnnouncement.date <= today),
                or_(m.RecAnnouncement.expires.is_(None), m.RecAnnouncement.expires == "",
                    m.RecAnnouncement.expires >= today),
            ).order_by(m.RecAnnouncement.date.desc().nullslast(), m.RecAnnouncement.id.desc()).limit(10)
        )).scalars().all()
    return [_from_model("announcements", r) for r in rows]


# =========================================================
# Native Records - one row at a time, from the admin panel
# =========================================================

_PREFIX = {"students": "S", "guardians": "P", "teachers": "T", "classes": "C"}


async def _next_id(db, school_id: str, table: str, hint: str | None = None) -> str:
    t = canonical.spec(table)
    model, column = t["model"], t["columns"][t["key"]]
    taken = {_key(v) for v in (await db.execute(
        select(getattr(model, column)).where(model.school_id == school_id))).scalars()}
    if table == "classes" and hint:
        base = re.sub(r"[^a-z0-9]+", "-", hint.lower()).strip("-") or "class"
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}-{n}", n + 1
        return candidate
    n = len(taken) + 1
    while f"{_PREFIX[table]}-{n:04d}".lower() in taken:
        n += 1
    return f"{_PREFIX[table]}-{n:04d}"


def _search(table: str, q: str):
    t = canonical.spec(table)
    model = t["model"]
    like = f"%{q.strip()}%"
    columns = [getattr(model, c) for c in t["columns"].values() if isinstance(model.__table__.c[c].type, String)]
    return or_(*[c.ilike(like) for c in columns])


async def list_rows(school_id: str, table: str, q: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    school_id = _school(school_id)
    t = canonical.spec(table)
    model = t["model"]
    where = [model.school_id == school_id]
    if q and q.strip():
        where.append(_search(table, q))
    async with SessionLocal() as db:
        total = (await db.execute(select(func.count()).select_from(model).where(*where))).scalar() or 0
        if table == "attendance":
            order = [model.date.desc(), model.id.desc()]
        elif table in ("announcements", "fees", "results"):
            order = [model.id.desc()]
        else:  # by the table's first field - a student's id, a class's ...
            order = [getattr(model, next(iter(t["columns"].values())))]
        objs = (await db.execute(select(model).where(*where).order_by(*order).limit(limit).offset(offset))).scalars().all()
        rows = [_from_model(table, o) for o in objs]
        if table == "students" and rows:
            ids = [_key(r["student_id"]) for r in rows]
            links = (await db.execute(select(m.RecStudentGuardian).where(
                m.RecStudentGuardian.school_id == school_id,
                func.lower(m.RecStudentGuardian.student_id).in_(ids)))).scalars().all()
            first = {}
            for link in links:
                first.setdefault(_key(link.student_id), link.guardian_id)
            names = {_key(g.guardian_id): g for g in (await db.execute(select(m.RecGuardian).where(
                m.RecGuardian.school_id == school_id,
                func.lower(m.RecGuardian.guardian_id).in_([_key(v) for v in first.values()])))).scalars()}
            for r in rows:
                gid = first.get(_key(r["student_id"]))
                r["guardian_id"] = gid
                g = names.get(_key(gid)) if gid else None
                r["guardian_name"] = g.name if g else None
                r["guardian_email"] = g.email if g else None
                r["guardian_mobile"] = g.mobile if g else None
    return rows, total


async def _link_guardian(db, school_id: str, student_id: str, row: dict, source: str) -> None:
    """A student's parent, as typed on the Students form: linked, and added when new."""
    gid = row.get("guardian_id")
    await db.execute(delete(m.RecStudentGuardian).where(
        m.RecStudentGuardian.school_id == school_id, func.lower(m.RecStudentGuardian.student_id) == _key(student_id)))
    if not gid:
        return
    db.add(m.RecStudentGuardian(school_id=school_id, source=source, student_id=student_id, guardian_id=gid, extra_json="{}"))
    found = (await db.execute(select(m.RecGuardian).where(
        m.RecGuardian.school_id == school_id, func.lower(m.RecGuardian.guardian_id) == _key(gid)))).scalar()
    if found is None:
        db.add(m.RecGuardian(**_to_model("guardians", {
            "guardian_id": gid, "guardian_name": row.get("guardian_name") or gid,
            "guardian_email": row.get("guardian_email"), "guardian_mobile": row.get("guardian_mobile"),
        }, school_id, source)))
    else:
        for name, column in (("guardian_name", "name"), ("guardian_email", "email"), ("guardian_mobile", "mobile")):
            if row.get(name):
                setattr(found, column, _limit(m.RecGuardian, column, row[name]))


class DuplicateRecord(ValueError):
    """Another record of the school already has this id."""


async def _unique(db, school_id: str, table: str, row: dict, row_id: int | None = None) -> None:
    t = canonical.spec(table)
    if not t["key"] or not row.get(t["key"]):
        return
    model, column = t["model"], t["columns"][t["key"]]
    clash = (await db.execute(select(model.id).where(
        model.school_id == school_id, func.lower(getattr(model, column)) == _key(row[t["key"]]),
        *( [model.id != row_id] if row_id else [] )))).first()
    if clash:
        raise DuplicateRecord(f"Another record already has the ID '{row[t['key']]}'.")


async def create_row(school_id: str, table: str, row: dict, source: str = "native") -> dict:
    school_id = _school(school_id)
    t = canonical.spec(table)
    async with SessionLocal() as db:
        if t["key"] and not row.get(t["key"]):
            row = {**row, t["key"]: await _next_id(db, school_id, table, row.get("class_name"))}
        await _unique(db, school_id, table, row)
        obj = t["model"](**_to_model(table, row, school_id, source))
        db.add(obj)
        if table == "students":
            await _link_guardian(db, school_id, row["student_id"], row, source)
        await db.commit()
        await db.refresh(obj)
        return _from_model(table, obj)


async def update_row(school_id: str, table: str, row_id: int, row: dict) -> dict | None:
    school_id = _school(school_id)
    t = canonical.spec(table)
    async with SessionLocal() as db:
        obj = (await db.execute(select(t["model"]).where(
            t["model"].school_id == school_id, t["model"].id == row_id))).scalar()
        if obj is None:
            return None
        if t["key"] and not row.get(t["key"]):
            row = {**row, t["key"]: getattr(obj, t["columns"][t["key"]])}
        await _unique(db, school_id, table, row, row_id)
        old_key = getattr(obj, t["columns"][t["key"]]) if t["key"] else None
        for column, value in _to_model(table, row, school_id, obj.source).items():
            if column not in ("school_id", "source", "extra_json") or (column == "extra_json" and row.get("_extra")):
                setattr(obj, column, value)
        if table == "students":
            if old_key and _key(old_key) != _key(row["student_id"]):
                await db.execute(delete(m.RecStudentGuardian).where(
                    m.RecStudentGuardian.school_id == school_id,
                    func.lower(m.RecStudentGuardian.student_id) == _key(old_key)))
            await _link_guardian(db, school_id, row["student_id"], row, obj.source)
        await db.commit()
        await db.refresh(obj)
        return _from_model(table, obj)


async def delete_row(school_id: str, table: str, row_id: int) -> bool:
    school_id = _school(school_id)
    t = canonical.spec(table)
    async with SessionLocal() as db:
        obj = (await db.execute(select(t["model"]).where(
            t["model"].school_id == school_id, t["model"].id == row_id))).scalar()
        if obj is None:
            return False
        if table == "students":
            await db.execute(delete(m.RecStudentGuardian).where(
                m.RecStudentGuardian.school_id == school_id,
                func.lower(m.RecStudentGuardian.student_id) == _key(obj.student_id)))
        await db.delete(obj)
        await db.commit()
    return True


async def class_names(school_id: str) -> list[str]:
    """Every class the school's students and classes name - for the attendance register."""
    school_id = _school(school_id)
    async with SessionLocal() as db:
        named = set((await db.execute(select(m.RecStudent.class_name).where(
            m.RecStudent.school_id == school_id, m.RecStudent.class_name.is_not(None)))).scalars())
        named |= set((await db.execute(select(m.RecClass.name).where(m.RecClass.school_id == school_id))).scalars())
    return sorted({c for c in named if c}, key=str.lower)


async def register(school_id: str, class_name: str, day: str) -> list[dict]:
    """A class's students with what each was marked on a day - the attendance register."""
    school_id = _school(school_id)
    async with SessionLocal() as db:
        students = (await db.execute(select(m.RecStudent).where(
            m.RecStudent.school_id == school_id, func.lower(m.RecStudent.class_name) == _key(class_name))
            .order_by(m.RecStudent.roll_no, m.RecStudent.name))).scalars().all()
        marks = {_key(a.student_id): a for a in (await db.execute(select(m.RecAttendance).where(
            m.RecAttendance.school_id == school_id, m.RecAttendance.date == day,
            func.lower(m.RecAttendance.student_id).in_([_key(s.student_id) for s in students])))).scalars()}
    return [{"student_id": s.student_id, "student_name": s.name, "roll_no": s.roll_no,
             "status": marks[_key(s.student_id)].status if _key(s.student_id) in marks else None}
            for s in students]


async def mark_attendance(school_id: str, day: str, marks: dict[str, str], source: str = "native") -> int:
    """One day's register: student id -> Present / Absent / Leave / Late. Replaces that day's marks for them."""
    school_id = _school(school_id)
    marks = {_key(k): v for k, v in marks.items() if v}
    if not marks:
        return 0
    async with SessionLocal() as db:
        known = {_key(s): s for s in (await db.execute(select(m.RecStudent.student_id).where(
            m.RecStudent.school_id == school_id, func.lower(m.RecStudent.student_id).in_([_key(k) for k in marks])
        ))).scalars()}
        ids = [known[_key(k)] for k in marks if _key(k) in known]
        if not ids:
            return 0
        await db.execute(delete(m.RecAttendance).where(
            m.RecAttendance.school_id == school_id, m.RecAttendance.date == day,
            func.lower(m.RecAttendance.student_id).in_([_key(i) for i in ids])))
        await db.execute(insert(m.RecAttendance), [
            {"school_id": school_id, "source": source, "student_id": sid, "date": day,
             "status": marks[_key(sid)], "extra_json": "{}"}
            for sid in ids
        ])
        await db.commit()
    return len(ids)
