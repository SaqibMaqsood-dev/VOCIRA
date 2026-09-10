"""
Generates deploy/.env.prod.

What it does:

  1. generates strong new secrets (JWT, DB, RabbitMQ, LiveKit,
     internal service key)
  2. carries the API keys (Groq, Pinecone, HF, Gemini, ERP) over
     from your existing .env files
  3. writes it all into deploy/.env.prod

How to run it (from the repo root):

    python deploy/gen-secrets.py

Run again and it will not overwrite the existing file - that needs
--force. The reason: once deployed, changing the JWT secret logs
every user out, and changing the DB password cuts the services off
from the database.

This script never prints the value of any secret to the screen.
"""

import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
TARGET = DEPLOY / ".env.prod"

# Where the existing API keys are read from
SOURCES = [
    ROOT / "backend" / "microservices" / "livekit_Rag_services" / ".env",
    ROOT / "backend" / "microservices" / "auth_services" / ".env",
]

# These carry over from your existing .env
CARRY_OVER = [
    "GROQ_API_KEY",
    "HF_TOKEN",
    "PINECONE_API_KEY",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_FAST_MODEL",
    "LLM_SMART_MODEL",
    "EMBEDDING_PROVIDER",
    "GEMINI_API_KEY",
    "GEMINI_EMBEDDING_MODEL",
    "GEMINI_EMBEDDING_DIM",
    "ERP_API_KEY",
    "ERP_API_SECRET",
]


def read_env(path: Path) -> dict:
    """A simple KEY=VALUE parser - it skips comments and blank lines."""
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if re.fullmatch(r"[A-Z0-9_]+", key):
            values[key] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    force = "--force" in sys.argv

    if TARGET.exists() and not force:
        print(f"{TARGET.relative_to(ROOT)} already exists.")
        print()
        print("Regenerating would change the JWT secret and the DB password -")
        print("logging every user out, and cutting the services off from the")
        print("database (unless the old volume is removed).")
        print()
        print("If you really mean to:  python deploy/gen-secrets.py --force")
        return 1

    existing = {}
    for source in SOURCES:
        existing.update(read_env(source))

    found = [k for k in CARRY_OVER if existing.get(k)]
    missing = [k for k in CARRY_OVER if not existing.get(k)]

    template = (DEPLOY / ".env.example").read_text(encoding="utf-8")

    # ---- naye secrets ----
    generated = {
        # token_urlsafe(48) ~ 64 characters. A JWT needs at least
        # 32 bytes - this is comfortably more.
        "JWT_SECRET_KEY": secrets.token_urlsafe(48),
        "INTERNAL_SERVICE_KEY": secrets.token_urlsafe(32),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(24),
        "RABBITMQ_PASSWORD": secrets.token_urlsafe(24),
        # LiveKit's own convention: the key starts with "API"
        "LIVEKIT_API_KEY": "API" + secrets.token_hex(8),
        "LIVEKIT_API_SECRET": secrets.token_urlsafe(32),
    }

    replacements = dict(generated)
    for key in CARRY_OVER:
        if existing.get(key):
            replacements[key] = existing[key]

    out_lines = []
    for line in template.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in replacements:
                out_lines.append(f"{key}={replacements[key]}")
                continue
        out_lines.append(line)

    TARGET.write_text("\n".join(out_lines) + "\n", encoding="utf-8")

    # File permissions do not mean the same thing on Windows as on
    # Linux, but on the VM (Linux) this matters
    try:
        TARGET.chmod(0o600)
    except Exception:
        pass

    print(f"Ban gayi: {TARGET.relative_to(ROOT)}")
    print()
    print("Naye secrets (values jaan boojh kar nahi dikhayi ja rahin):")
    for key in generated:
        print(f"   {key}")
    print()
    if found:
        print("Purani .env se utha li gayin:")
        for key in found:
            print(f"   {key}")
        print()
    if missing:
        print("These were not found - they will have to be filled in by hand:")
        for key in missing:
            print(f"   {key}")
        print()
    print("Now fill in these four by hand (they do not exist yet):")
    print("   DOMAIN            your domain / DuckDNS subdomain")
    print("   ACME_EMAIL        for Let's Encrypt notices")
    print("   CORS_ORIGINS      the URL of the frontend on Vercel")
    print("   ERP_BASE_URL      on the same VM, http://erpnext:8080 is right")
    print()
    print("This file is in .gitignore - it will not be committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
