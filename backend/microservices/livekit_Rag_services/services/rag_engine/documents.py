"""
Knowledge base documents - list, upload, note, delete.

There used to be exactly one way to add new data: put the file on the
server by hand (into rag_engine/data/pdf or text_files), then press
sync. Nothing could be done from the admin panel - no upload, and no
way to see what the index had been built from.

This module opens that up to the panel. Files go exactly where
ingestion.py looks for them - no new location was introduced, or
files would start living in two places.
"""

import os
import re
import unicodedata
from datetime import datetime

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    PDF_PATH,
    TEXT_FILES_PATH,
)


# Only the types ingestion.py can read - accepting more than this
# would be a lie: the file would be stored but never reach the index.
KINDS = {
    ".pdf": ("pdf", PDF_PATH),
    ".txt": ("text", TEXT_FILES_PATH),
}

MAX_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_NOTE_CHARS = 20000


class DocumentError(ValueError):
    """Caller ki ghalti - HTTP 4xx banane ke liye."""


def safe_filename(name: str) -> str:
    """
    Naam ko mehfooz banayein.

    IMPORTANT: a name sent by the user never goes straight into a
    path. A name like "../../.env" could write outside the data
    folder. Only the basename is taken here, and dangerous characters
    are stripped out of that too.
    """

    name = os.path.basename(name or "").strip()

    # Normalise Unicode tricks (a fullwidth solidus and the like)
    name = unicodedata.normalize("NFKC", name)

    # letters, digits, space, dash, underscore and dot only
    name = re.sub(r"[^\w\s.\-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    # leading and trailing dots - blocks ".." and hidden files
    name = name.strip(". ")

    if not name:
        raise DocumentError("File name is not usable")

    return name[:120]


def _resolve(kind_dir: str, filename: str) -> str:
    """
    Build the full path and confirm it stays INSIDE the folder.

    This second sieve runs even after safe_filename - anything to do
    with paths should never rest on a single check.
    """

    full = os.path.realpath(os.path.join(kind_dir, filename))
    root = os.path.realpath(kind_dir)

    if not full.startswith(root + os.sep):
        raise DocumentError("Invalid file path")

    return full


def _kind_for(filename: str):
    ext = os.path.splitext(filename)[1].lower()

    if ext not in KINDS:
        allowed = ", ".join(sorted(KINDS))
        raise DocumentError(f"Only {allowed} files are supported")

    return KINDS[ext]


# =========================================================
# LIST
# =========================================================

def list_documents(chunks_by_source: dict | None = None) -> list[dict]:
    """
    Disk par jo documents hain, un ki list.

    chunks_by_source comes from the last sync (source -> chunk
    count). A file added after that sync has a count of None -
    meaning "not in the index yet".
    """

    chunks_by_source = chunks_by_source or {}
    out = []

    for ext, (kind, folder) in KINDS.items():
        if not os.path.isdir(folder):
            continue

        for entry in sorted(os.listdir(folder)):
            if not entry.lower().endswith(ext):
                continue

            path = os.path.join(folder, entry)

            try:
                stat = os.stat(path)
            except OSError:
                continue

            # ingestion source ko poore path se likhti hai
            chunks = chunks_by_source.get(os.path.realpath(path))

            out.append(
                {
                    "name": entry,
                    "kind": kind,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(
                        stat.st_mtime
                    ).isoformat(timespec="seconds"),
                    "chunks": chunks,
                    "indexed": chunks is not None,
                }
            )

    out.sort(key=lambda d: d["modified"], reverse=True)
    return out


# =========================================================
# UPLOAD
# =========================================================

def save_upload(filename: str, content: bytes) -> dict:
    """Store an uploaded file where ingestion looks for it."""

    if not content:
        raise DocumentError("File is empty")

    if len(content) > MAX_BYTES:
        raise DocumentError(
            f"File is larger than {MAX_BYTES // (1024 * 1024)} MB"
        )

    name = safe_filename(filename)
    kind, folder = _kind_for(name)

    os.makedirs(folder, exist_ok=True)
    path = _resolve(folder, name)

    with open(path, "wb") as handle:
        handle.write(content)

    return {"name": name, "kind": kind, "size": len(content)}


# =========================================================
# NOTE  (for small things - no need to produce a PDF)
# =========================================================

def save_note(title: str, text: str) -> dict:
    """
    Ek chhota note .txt ki soorat mein.

    Editing a PDF for something like "the school timings changed"
    is absurd. The note goes into the same text_files folder, so as
    far as ingestion is concerned it is no different from any other
    file.
    """

    title = (title or "").strip()
    text = (text or "").strip()

    if len(title) < 3:
        raise DocumentError("Title must be at least 3 characters")

    if len(text) < 10:
        raise DocumentError("Note must be at least 10 characters")

    if len(text) > MAX_NOTE_CHARS:
        raise DocumentError(
            f"Note is longer than {MAX_NOTE_CHARS} characters"
        )

    name = safe_filename(title)
    if not name.lower().endswith(".txt"):
        name = f"{name}.txt"

    os.makedirs(TEXT_FILES_PATH, exist_ok=True)
    path = _resolve(TEXT_FILES_PATH, name)

    # The title is written into the file as well - it gives the
    # RAG chunks context (the "School timings" part).
    body = f"{title}\n\n{text}\n"

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)

    return {"name": name, "kind": "text", "size": len(body.encode("utf-8"))}


# =========================================================
# DELETE
# =========================================================

def delete_document(name: str) -> bool:
    """Delete a file. It leaves the index on the next sync."""

    name = safe_filename(name)
    _, folder = _kind_for(name)
    path = _resolve(folder, name)

    if not os.path.isfile(path):
        return False

    os.remove(path)
    return True
