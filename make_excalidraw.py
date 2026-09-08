"""
VOCIRA - User Layer ka Excalidraw scene banata hai.

Output file .excalidraw hai - Excalidraw (web ya desktop) mein
seedha "Open" se ya canvas par drag-drop kar ke khul jati hai.
Har box aur arrow alag se editable rehta hai, is liye aap chahen
to hath se aage badha ya rang badal sakte hain.

Structure: 4 category-boxes (Pages, Shared Components,
Layout/Chrome, PWA Layer), har ek ke neeche us ke asal
sub-components, ek zanjeer (chain) ki tarah joRe hue.
"""

import json
import random

SEED = lambda: random.randint(1, 2_000_000_000)
NOW = 1_700_000_000_000

FONT_HAND = 1  # Excalifont - Excalidraw ka apna hand-drawn font


def rect(id_, x, y, w, h, stroke, bg, rough=1, sw=2):
    return {
        "id": id_, "type": "rectangle",
        "x": x, "y": y, "width": w, "height": h, "angle": 0,
        "strokeColor": stroke, "backgroundColor": bg,
        "fillStyle": "hachure", "strokeWidth": sw, "strokeStyle": "solid",
        "roughness": rough, "opacity": 100,
        "groupIds": [], "frameId": None,
        "roundness": {"type": 3}, "seed": SEED(),
        "version": 1, "versionNonce": SEED(), "isDeleted": False,
        "boundElements": None, "updated": NOW, "link": None, "locked": False,
    }


def text(id_, x, y, w, h, s, color, size=18, align="center"):
    return {
        "id": id_, "type": "text",
        "x": x, "y": y, "width": w, "height": h, "angle": 0,
        "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": 2, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100,
        "groupIds": [], "frameId": None, "roundness": None, "seed": SEED(),
        "version": 1, "versionNonce": SEED(), "isDeleted": False,
        "boundElements": None, "updated": NOW, "link": None, "locked": False,
        "text": s, "fontSize": size, "fontFamily": FONT_HAND,
        "textAlign": align, "verticalAlign": "middle",
        "containerId": None, "originalText": s, "lineHeight": 1.25,
    }


def arrow(id_, x1, y1, x2, y2, color, sw=1.5):
    x = min(x1, x2)
    y = min(y1, y2)
    return {
        "id": id_, "type": "arrow",
        "x": x1, "y": y1, "width": abs(x2 - x1) or 1, "height": abs(y2 - y1) or 1,
        "angle": 0,
        "strokeColor": color, "backgroundColor": "transparent",
        "fillStyle": "hachure", "strokeWidth": sw, "strokeStyle": "solid",
        "roughness": 1, "opacity": 100,
        "groupIds": [], "frameId": None,
        "roundness": {"type": 2}, "seed": SEED(),
        "version": 1, "versionNonce": SEED(), "isDeleted": False,
        "boundElements": None, "updated": NOW, "link": None, "locked": False,
        "points": [[0, 0], [x2 - x1, y2 - y1]],
        "lastCommittedPoint": None,
        "startBinding": None, "endBinding": None,
        "startArrowhead": None, "endArrowhead": "arrow",
    }


# =========================================================
# CONTENT - asal codebase se, koi andaza nahi
# =========================================================

CATEGORIES = [
    {
        "id": "pages", "title": "PAGES",
        "stroke": "#1971c2", "bg": "#a5d8ff",
        "items": [
            "/   (Home)",
            "/assistant",
            "/dashboard",
            "/support",
            "/login",
            "/features",
            "404 (not-found)",
        ],
    },
    {
        "id": "components", "title": "SHARED COMPONENTS",
        "stroke": "#2f9e44", "bg": "#b2f2bb",
        "items": [
            ("HomeHero", None),
            ("VoiceOrb", "used inside HomeHero"),
            ("AgentVisualizer", "used on /assistant"),
            ("CallTable", "used on /dashboard"),
            ("StatsCard", "used on /dashboard"),
            ("FeatureCard", "used on /features"),
            ("AuthForm", "also used on /admin/signup"),
        ],
    },
    {
        "id": "layout", "title": "LAYOUT / CHROME",
        "stroke": "#6741d9", "bg": "#d0bfff",
        "items": [
            ("AppChrome", "picks user vs admin chrome"),
            ("Navbar", None),
            ("BrandLogo", "also used in Admin Sidebar"),
            ("Footer", None),
            ("BackgroundGradient", "GradFlow animated bg"),
            ("providers", "React context wrapper"),
        ],
    },
    {
        "id": "pwa", "title": "PWA LAYER",
        "stroke": "#f08c00", "bg": "#ffec99",
        "items": [
            "manifest.js",
            "sw.js  (service worker)",
            "offline.html",
            "InstallPrompt",
            "ServiceWorker",
        ],
    },
]

COL_W = 340
GAP_X = 40
X0 = 60
CAT_Y = 140
CAT_H = 64
SUB_H = 46
SUB_GAP = 14
SUB_STEP = SUB_H + SUB_GAP
SUB_START_Y = CAT_Y + CAT_H + 50

elements = []

# ---- title ----
elements.append(text(
    "title", X0, 30, 900, 46,
    "VOCIRA — User Layer  (components & sub-components)",
    "#1e1e1e", size=28, align="left",
))
elements.append(text(
    "subtitle", X0, 78, 1100, 30,
    "Every page a parent can open, and every piece that builds it — grouped by role.",
    "#868e96", size=16, align="left",
))

for col, cat in enumerate(CATEGORIES):
    x = X0 + col * (COL_W + GAP_X)

    # ---- category header box ----
    cat_rect_id = f"rect-{cat['id']}"
    elements.append(rect(cat_rect_id, x, CAT_Y, COL_W, CAT_H, cat["stroke"], cat["bg"], sw=2.5))
    elements.append(text(
        f"text-{cat['id']}", x, CAT_Y, COL_W, CAT_H,
        cat["title"], "#1e1e1e", size=20,
    ))

    # ---- chain of sub-items ----
    prev_bottom = CAT_Y + CAT_H
    prev_center_x = x + COL_W / 2

    for i, item in enumerate(cat["items"]):
        if isinstance(item, tuple):
            label, note = item
        else:
            label, note = item, None

        sy = SUB_START_Y + i * SUB_STEP
        rid = f"rect-{cat['id']}-{i}"
        elements.append(rect(rid, x, sy, COL_W, SUB_H, cat["stroke"], "transparent", sw=1.5))
        elements.append(text(
            f"text-{cat['id']}-{i}", x, sy, COL_W, SUB_H,
            label, "#1e1e1e", size=16,
        ))

        # connector from previous box down into this one
        elements.append(arrow(
            f"arrow-{cat['id']}-{i}",
            prev_center_x, prev_bottom,
            x + COL_W / 2, sy,
            cat["stroke"],
        ))

        # small side-note for items that live in more than one place
        if note:
            elements.append(text(
                f"note-{cat['id']}-{i}", x + COL_W + 14, sy + 6, 260, 34,
                f"↳ {note}", "#868e96", size=13, align="left",
            ))

        prev_bottom = sy + SUB_H
        prev_center_x = x + COL_W / 2

scene = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://excalidraw.com",
    "elements": elements,
    "appState": {
        "gridSize": None,
        "viewBackgroundColor": "#ffffff",
    },
    "files": {},
}

OUT = "vocira-user-layer.excalidraw"
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(scene, f, indent=2)

print(f"  {len(elements)} elements -> {OUT}")
