"""
VOCIRA ka ER diagram - SVG bana kar PNG mein badalne ke liye.

Schema haath se nahi likhi: SQLAlchemy metadata se aati hai, is liye
diagram wahi dikhata hai jo DB mein waqai hai.

Ek baat jo diagram mein khaas tor par dikhayi gayi hai: teen tables
(sessions, messages, escalations) users ki UUID rakhti hain magar un
par FOREIGN KEY hai hi nahi. Wo rishtay asli hain aur code un par
chalta hai, magar DB unhein nafiz nahi karta - is liye wo lakeerein
tooti hui (dashed) hain, solid nahi. Ek ER diagram jo dono ko ek
jaisa dikhaye wo jhoot bolta hai.
"""

import html
import os
import subprocess

OUT_DIR = r"D:\college_vocira_project"
SVG = os.path.join(OUT_DIR, "vocira-er-diagram.svg")
PNG = os.path.join(OUT_DIR, "vocira-er-diagram.png")

W, H = 1780, 1080

# Group ke rang - header fill; sab par safaid text parhne laayak hai
C_RBAC = "#6d28d9"
C_ID = "#1d4ed8"
C_CONV = "#0f766e"
C_EXT = "#c2410c"

INK = "#0f172a"
MUTED = "#64748b"
LINE = "#94a3b8"
SURFACE = "#ffffff"
BG = "#f1f5f9"

ROW_H = 24
HEAD_H = 38
PAD_B = 12


def esc(s):
    return html.escape(str(s))


class Table:
    def __init__(self, name, x, y, w, color, cols, note=None):
        self.name, self.x, self.y, self.w = name, x, y, w
        self.color, self.cols, self.note = color, cols, note
        self.h = HEAD_H + len(cols) * ROW_H + PAD_B

    def row_y(self, field):
        """Us field ki lakeer kis oonchai par lagni chahiye."""
        for i, (n, *_rest) in enumerate(self.cols):
            if n == field:
                return self.y + HEAD_H + i * ROW_H + ROW_H / 2
        return self.y + self.h / 2

    @property
    def cx(self):
        return self.x + self.w / 2

    def svg(self):
        p = []
        p.append(
            f'<rect x="{self.x}" y="{self.y}" width="{self.w}" height="{self.h}" '
            f'rx="10" fill="{SURFACE}" stroke="#cbd5e1" stroke-width="1.5" '
            f'filter="url(#shadow)"/>'
        )
        # header
        p.append(
            f'<path d="M {self.x} {self.y + 10} a 10 10 0 0 1 10 -10 '
            f'h {self.w - 20} a 10 10 0 0 1 10 10 v {HEAD_H - 10} '
            f'h -{self.w} z" fill="{self.color}"/>'
        )
        p.append(
            f'<text x="{self.x + 14}" y="{self.y + 25}" font-size="15" '
            f'font-weight="700" fill="#ffffff" '
            f'font-family="Consolas,Menlo,monospace">{esc(self.name)}</text>'
        )

        for i, (n, typ, kind) in enumerate(self.cols):
            ry = self.y + HEAD_H + i * ROW_H + 16
            if i % 2 == 1:
                p.append(
                    f'<rect x="{self.x + 1}" y="{ry - 16}" width="{self.w - 2}" '
                    f'height="{ROW_H}" fill="#f8fafc"/>'
                )

            badge, bold, fill = "", "400", INK
            if kind == "pk":
                badge, bold, fill = "PK", "700", INK
            elif kind == "fk":
                badge, fill = "FK", "#1d4ed8"
            elif kind == "soft":
                badge, fill = "→", "#b45309"

            if badge:
                p.append(
                    f'<text x="{self.x + 13}" y="{ry}" font-size="9.5" '
                    f'font-weight="700" fill="{fill}" opacity="0.85" '
                    f'font-family="system-ui,sans-serif">{esc(badge)}</text>'
                )
            p.append(
                f'<text x="{self.x + 38}" y="{ry}" font-size="12.5" '
                f'font-weight="{bold}" fill="{fill}" '
                f'font-family="Consolas,Menlo,monospace">{esc(n)}</text>'
            )
            p.append(
                f'<text x="{self.x + self.w - 13}" y="{ry}" font-size="11" '
                f'text-anchor="end" fill="{MUTED}" '
                f'font-family="Consolas,Menlo,monospace">{esc(typ)}</text>'
            )
        return "\n".join(p)


# ============================================================
# SCHEMA  (SQLAlchemy metadata se nikala hua)
# ============================================================

permissions = Table("permissions", 60, 150, 300, C_RBAC, [
    ("permission_id", "varchar(100)", "pk"),
    ("name", "varchar(100)", ""),
])

role = Table("role", 60, 316, 300, C_RBAC, [
    ("role_id", "varchar", "pk"),
    ("name", "text", ""),
])

role_permissions = Table("role_permissions", 60, 482, 300, C_RBAC, [
    ("role_id", "varchar", "fk"),
    ("permission_id", "varchar(100)", "fk"),
])

erpnext = Table("ERPNext · Guardian", 60, 700, 300, C_EXT, [
    ("name", "EDU-GRD-...", "pk"),
    ("guardian_name", "data", ""),
    ("email_address", "data", ""),
], note="separate system (MariaDB)")

users = Table("users", 520, 150, 340, C_ID, [
    ("user_id", "uuid", "pk"),
    ("parent_id", "varchar(100)", "soft"),
    ("name", "varchar(100)", ""),
    ("role_id", "varchar", "fk"),
    ("email", "varchar(200)", ""),
    ("password_hashed", "text", ""),
    ("phone_number", "varchar(20)", ""),
    ("location", "text", ""),
    ("address", "text", ""),
    ("date_birth", "date", ""),
    ("created_at", "datetime", ""),
    ("updated_at", "datetime", ""),
])

refresh_tokken = Table("refresh_tokken", 520, 700, 340, C_ID, [
    ("id", "uuid", "pk"),
    ("user_id", "uuid", "fk"),
    ("token_hash", "text", ""),
    ("is_revoked", "boolean", ""),
    ("created_at", "datetime", ""),
    ("expires_at", "datetime", ""),
])

sessions = Table("sessions", 1080, 150, 330, C_CONV, [
    ("id", "uuid", "pk"),
    ("user_id", "uuid", "soft"),
    ("start_at", "datetime", ""),
    ("end_at", "datetime", ""),
    ("title", "text", ""),
    ("status", "active | closed", ""),
])

messages = Table("messages", 1080, 400, 330, C_CONV, [
    ("id", "uuid", "pk"),
    ("session_id", "uuid", "fk"),
    ("user_id", "uuid", "soft"),
    ("sender_type", "user|ai|guest", ""),
    ("content", "text", ""),
    ("intent", "text", ""),
    ("source_type", "rag|erp|...", ""),
    ("created_at", "datetime", ""),
])

escalations = Table("escalations", 1080, 700, 330, C_CONV, [
    ("id", "uuid", "pk"),
    ("message_id", "uuid", "fk"),
    ("user_id", "uuid", "soft"),
    ("status", "pending|open|...", ""),
    ("created_at", "datetime", ""),
])

TABLES = [permissions, role, role_permissions, erpnext, users,
          refresh_tokken, sessions, messages, escalations]


# ============================================================
# LAKEEREIN
# ============================================================

def elbow(x1, y1, x2, y2, mid=None):
    m = mid if mid is not None else (x1 + x2) / 2
    return f"M {x1} {y1} H {m} V {y2} H {x2}"


def link(a, af, b, bf, *, solid=True, label="", mid=None,
         from_right=True, to_left=True):
    x1 = (a.x + a.w) if from_right else a.x
    y1 = a.row_y(af)
    x2 = b.x if to_left else (b.x + b.w)
    y2 = b.row_y(bf)

    dash = "" if solid else ' stroke-dasharray="7 5"'
    color = "#475569" if solid else "#b45309"
    marker = "url(#arrow)" if solid else "url(#arrow-soft)"

    parts = [
        f'<path d="{elbow(x1, y1, x2, y2, mid)}" fill="none" '
        f'stroke="{color}" stroke-width="1.8"{dash} marker-end="{marker}"/>'
    ]
    if label:
        lx = mid if mid is not None else (x1 + x2) / 2
        ly = (y1 + y2) / 2
        wdt = len(label) * 6.4 + 12
        parts.append(
            f'<rect x="{lx - wdt/2}" y="{ly - 9}" width="{wdt}" height="18" '
            f'rx="9" fill="{BG}" stroke="#e2e8f0"/>'
        )
        parts.append(
            f'<text x="{lx}" y="{ly + 4}" font-size="10.5" text-anchor="middle" '
            f'fill="{MUTED}" font-family="system-ui,sans-serif">{esc(label)}</text>'
        )
    return "\n".join(parts)


def group(x, y, w, h, title, color):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" '
        f'fill="{color}" fill-opacity="0.045" stroke="{color}" '
        f'stroke-opacity="0.22" stroke-width="1.5" stroke-dasharray="4 4"/>'
        f'<text x="{x + 18}" y="{y + 26}" font-size="12" font-weight="700" '
        f'letter-spacing="1.6" fill="{color}" fill-opacity="0.75" '
        f'font-family="system-ui,sans-serif">{esc(title)}</text>'
    )


def build():
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="system-ui,sans-serif">',
        '<defs>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">'
        '<feDropShadow dx="0" dy="2" stdDeviation="4" '
        'flood-color="#0f172a" flood-opacity="0.10"/></filter>',
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#475569"/></marker>',
        '<marker id="arrow-soft" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="#b45309"/></marker>',
        '</defs>',
        f'<rect width="{W}" height="{H}" fill="{BG}"/>',
    ]

    # ---- sar-nama ----
    p.append(
        f'<text x="60" y="58" font-size="27" font-weight="750" fill="{INK}">'
        'VOCIRA — Database Schema</text>'
    )
    p.append(
        f'<text x="60" y="84" font-size="13.5" fill="{MUTED}">'
        'PostgreSQL · 8 tables · generated from the running SQLAlchemy models'
        '</text>'
    )

    # ---- groups ----
    p.append(group(36, 112, 348, 700, "AUTH & ROLES", C_RBAC))
    p.append(group(496, 112, 388, 800, "IDENTITY", C_ID))
    p.append(group(1056, 112, 378, 800, "CONVERSATION", C_CONV))

    # ---- lakeerein (tables se pehle, taake peeche rahen) ----
    # RBAC ke andar ke rishtay daayein corridor se - baayein wo canvas
    # ke kinare tak jate thay aur "1 : N" ka label kat jata tha.
    # Paanchon lakeerein 392..492 ke corridor mein, 24px ke faasle par.
    p.append(link(permissions, "permission_id", role_permissions,
                  "permission_id", mid=392, to_left=False, label="1 : N"))
    p.append(link(role, "role_id", role_permissions, "role_id",
                  mid=416, to_left=False, label="1 : N"))
    p.append(link(role, "role_id", users, "role_id", mid=444, label="1 : N"))
    p.append(link(users, "user_id", refresh_tokken, "user_id",
                  from_right=False, to_left=False, mid=492, label="1 : N"))
    p.append(link(sessions, "id", messages, "session_id",
                  from_right=False, to_left=False, mid=1040, label="1 : N"))
    p.append(link(messages, "id", escalations, "message_id",
                  from_right=False, to_left=False, mid=1040, label="1 : N"))

    # nafiz na hone wale rishtay
    p.append(link(users, "user_id", sessions, "user_id", solid=False, mid=970))
    p.append(link(users, "user_id", messages, "user_id", solid=False, mid=950))
    p.append(link(users, "user_id", escalations, "user_id",
                  solid=False, mid=930))
    p.append(link(erpnext, "name", users, "parent_id", solid=False, mid=468))

    for t in TABLES:
        p.append(t.svg())
        if t.note:
            p.append(
                f'<text x="{t.x + 14}" y="{t.y + t.h + 17}" font-size="10.5" '
                f'fill="{MUTED}" font-style="italic">{esc(t.note)}</text>'
            )

    # ---- legend ----
    ly = 950
    p.append(
        f'<rect x="36" y="{ly - 26}" width="1400" height="86" rx="14" '
        f'fill="{SURFACE}" stroke="#e2e8f0"/>'
    )
    p.append(
        f'<text x="60" y="{ly - 4}" font-size="11.5" font-weight="700" '
        f'letter-spacing="1.4" fill="{MUTED}">LEGEND</text>'
    )

    p.append(f'<path d="M 62 {ly + 22} h 46" stroke="#475569" stroke-width="1.8" '
             f'marker-end="url(#arrow)"/>')
    p.append(f'<text x="120" y="{ly + 26}" font-size="12.5" fill="{INK}">'
             'Foreign key — enforced by the database</text>')

    p.append(f'<path d="M 470 {ly + 22} h 46" stroke="#b45309" stroke-width="1.8" '
             f'stroke-dasharray="7 5" marker-end="url(#arrow-soft)"/>')
    p.append(f'<text x="528" y="{ly + 26}" font-size="12.5" fill="{INK}">'
             'Logical link only — <tspan font-weight="700">no FK constraint</tspan>; '
             'the code relies on it, the database does not enforce it</text>')

    p.append(
        f'<text x="62" y="{ly + 48}" font-size="11.5" fill="{MUTED}" '
        f'xml:space="preserve">'
        'PK = primary key     FK = foreign key     '
        '&#8594; = column points outside its own table'
        '</text>'
    )

    p.append('</svg>')
    return "\n".join(p)


os.makedirs(OUT_DIR, exist_ok=True)
with open(SVG, "w", encoding="utf-8") as fh:
    fh.write(build())
print(f"  SVG : {SVG}")

# ---- PNG (sharp frontend ke node_modules mein hai) ----
node = f"""
const sharp = require({os.path.join(os.getcwd(), 'frontend', 'node_modules', 'sharp').replace(os.sep, '/')!r});
sharp({SVG.replace(os.sep, '/')!r}, {{ density: 200 }})
  .png({{ compressionLevel: 9 }})
  .toFile({PNG.replace(os.sep, '/')!r})
  .then(i => console.log('  PNG :', {PNG!r}, i.width + 'x' + i.height))
  .catch(e => {{ console.error('  PNG fail:', e.message); process.exit(1); }});
"""
subprocess.run(["node", "-e", node], check=True)
