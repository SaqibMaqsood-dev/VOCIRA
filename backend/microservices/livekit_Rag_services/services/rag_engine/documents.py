"""
Knowledge base ke documents - list, upload, note, delete.

Pehle naya data daalne ka sirf ek tareeqa tha: file server par
manually rakho (rag_engine/data/pdf ya text_files mein), phir sync
dabao. Admin panel se kuch nahi ho sakta tha - na upload, na ye
dekhna ke index kis kis cheez se bana hai.

Ye module wahi kaam panel ke liye khol deta hai. Files wahin jati
hain jahan ingestion.py unhein dhoondti hai - koi naya raasta nahi
banaya, warna do jagah rakhi files ka masla shuru ho jata.
"""

import os
import re
import unicodedata
from datetime import datetime

from backend.microservices.livekit_Rag_services.services.rag_engine.config import (
    PDF_PATH,
    TEXT_FILES_PATH,
)


# Wahi qismein jo ingestion.py parh sakti hai - is se zyada qubool
# karna jhoot hoga: file rakhi jayegi magar index mein kabhi na aati.
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

    AHEM: user ka bheja hua naam kabhi seedha path mein nahi jata.
    "../../.env" jaisa naam data folder se bahar likh sakta hai.
    Yahan sirf basename liya jata hai aur us mein se bhi khatarnaak
    harf nikal diye jate hain.
    """

    name = os.path.basename(name or "").strip()

    # Unicode ki chaalein (fullwidth solidus waghera) normalize karein
    name = unicodedata.normalize("NFKC", name)

    # sirf harf, ginti, space, dash, underscore, dot
    name = re.sub(r"[^\w\s.\-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    # aage peeche ke dots - ".." aur chhupi hui files rok dein
    name = name.strip(". ")

    if not name:
        raise DocumentError("File name is not usable")

    return name[:120]


def _resolve(kind_dir: str, filename: str) -> str:
    """
    Poora path banayein aur tasdeeq karein ke wo folder ke ANDAR hai.

    safe_filename ke baad bhi ye doosri chhanni lagti hai - path se
    juri baatein ek check par nahi chhorni chahiyein.
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

    chunks_by_source aakhri sync se aata hai (source -> kitne chunks).
    Jo file sync ke baad rakhi gayi ho us ka count None hota hai -
    yani "abhi index mein nahi".
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
    """Uploaded file ko usi folder mein rakhein jahan ingestion dhoondti hai."""

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
# NOTE  (chhoti baaton ke liye - PDF banane ki zaroorat nahi)
# =========================================================

def save_note(title: str, text: str) -> dict:
    """
    Ek chhota note .txt ki soorat mein.

    "School ka timing badal gaya" jaisi baat ke liye PDF edit karna
    bewaqoofi hai. Note wahi text_files folder mein jata hai, is
    liye ingestion ke liye ye aur kisi file mein koi farq nahi.
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

    # Title bhi file mein likhte hain - RAG ke chunks mein wo
    # context banata hai ("School timings" wala hissa).
    body = f"{title}\n\n{text}\n"

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(body)

    return {"name": name, "kind": "text", "size": len(body.encode("utf-8"))}


# =========================================================
# DELETE
# =========================================================

def delete_document(name: str) -> bool:
    """File hatayein. Index se wo agli sync par nikalti hai."""

    name = safe_filename(name)
    _, folder = _kind_for(name)
    path = _resolve(folder, name)

    if not os.path.isfile(path):
        return False

    os.remove(path)
    return True
