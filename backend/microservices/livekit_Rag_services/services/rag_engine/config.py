"""
RAG engine settings.

NOTE: this file reads the same env vars as groq.py, so the provider
is switched from one place. GROQ_MODEL used to be hardcoded here
separately - when gpt-oss-20b ran out of quota, ERP questions kept
working while RAG ones answered "assistant is currently busy".

ENV LOADING ORDER MATTERS:

There are two .env files - the service's
(livekit_Rag_services/.env) and an older one here (rag_engine/.env).
load_dotenv does NOT override variables that are already set, so
whichever file loads FIRST wins. Only the local file was loaded here
before, so depending on import order the service setting sometimes
applied and sometimes the local one did. The result: LLM_BASE_URL
pointed at Groq in the service .env while RAG still went to
OpenRouter and got a 402.

The service file now loads FIRST (it is the real source), and the
local file is left for keys the service .env does not carry (such as
HUGGINGFACEHUB_API_TOKEN).
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# service ki .env - livekit_Rag_services/.env  (asal source)
SERVICE_ENV_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "..", "..", ".env")
)
load_dotenv(dotenv_path=SERVICE_ENV_PATH)

# local file sirf fallback ke tor par
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_PATH)

# ── API Keys ─────────────────────────────────────────────────
PINECONE_API_KEY     = os.getenv("PINECONE_API_KEY")
HUGGINGFACEHUB_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY       = os.getenv("GEMINI_API_KEY")

# ── Data Paths ───────────────────────────────────────────────
DATA_DIR        = os.path.join(BASE_DIR, "data")
PDF_PATH        = os.path.join(DATA_DIR, "pdf")
TEXT_FILES_PATH = os.path.join(DATA_DIR, "text_files")
URLS_FILE_PATH  = os.path.join(DATA_DIR, "urls.txt")

# ── Embeddings ───────────────────────────────────────────────
#
# "local"  -> BAAI/bge-small-en-v1.5, 384 dims
#             needs sentence-transformers + torch (~4 GB)
# "gemini" -> gemini-embedding-001, 768 dims
#             an HTTP call only, no heavy packages
#
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()

LOCAL_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
LOCAL_EMBEDDING_DIM   = 384

GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_EMBEDDING_DIM   = int(os.getenv("GEMINI_EMBEDDING_DIM", "768"))

if EMBEDDING_PROVIDER == "gemini":
    EMBEDDING_MODEL = GEMINI_EMBEDDING_MODEL
    EMBEDDING_DIM   = GEMINI_EMBEDDING_DIM
    _DEFAULT_INDEX  = "school-bot-gemini"
else:
    EMBEDDING_MODEL = LOCAL_EMBEDDING_MODEL
    EMBEDDING_DIM   = LOCAL_EMBEDDING_DIM
    _DEFAULT_INDEX  = "school-bot-index"

# ── Pinecone ─────────────────────────────────────────────────
#
# The index name changes with the provider because the dimensions
# differ (384 vs 768). One index cannot serve both - and keeping them
# separate means you can switch provider and switch straight back.
#
INDEX_NAME         = os.getenv("PINECONE_INDEX", _DEFAULT_INDEX)
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "school-general")

# ── RAG ──────────────────────────────────────────────────────
MAX_CONTEXT_CHARS = 4000

# Fetching 10 chunks pushed the context past MAX_CONTEXT_CHARS
# (~6300 chars) and it was then truncated - so the last chunks were
# embedded, fetched and thrown away. The prompt still came to ~1380
# tokens, which is heavy against Groq's 8000/min limit. 5 chunks
# still fill MAX_CONTEXT_CHARS.
TOP_K             = int(os.getenv("RAG_TOP_K", "5"))

# The same LLM model the rest of the system uses (services/groq/groq.py)
GROQ_MODEL = os.getenv("LLM_SMART_MODEL") or os.getenv(
    "GROQ_SMART_MODEL", "openai/gpt-oss-120b"
)
