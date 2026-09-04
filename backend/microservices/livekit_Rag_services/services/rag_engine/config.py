"""
RAG engine settings.

NOTE: ye file wahi env vars padhti hai jo groq.py padhta hai, taake
provider ek hi jagah se badle. Pehle yahan GROQ_MODEL alag hardcoded
tha - jab gpt-oss-20b ka quota khatam hua to ERP sawal chalte rahe
magar RAG wale "assistant is currently busy" dete rahe.

ENV LOADING KA TARTEEB AHEM HAI:

Do .env files hain - service ki (livekit_Rag_services/.env) aur ek
purani yahan (rag_engine/.env). load_dotenv pehle se set variables
ko override NAHI karta, is liye jo file PEHLE load ho wahi jeetti
hai. Pehle yahan sirf local file load hoti thi, to import order ke
mutabiq kabhi service ki setting chalti thi aur kabhi local wali.
Natija: LLM_BASE_URL service .env mein Groq par hota tha magar RAG
phir bhi OpenRouter ko jata tha aur 402 khata tha.

Ab service wali PEHLE load hoti hai (wahi asal source hai), aur
local file sirf un keys ke liye rehti hai jo service .env mein
nahi hain (jaise HUGGINGFACEHUB_API_TOKEN).
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
#             sentence-transformers + torch chahiye (~4 GB)
# "gemini" -> gemini-embedding-001, 768 dims
#             sirf HTTP call, koi bhaari package nahi
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
# Index ka naam provider ke saath badalta hai kyunke dimensions alag
# hain (384 vs 768). Ek hi index dono ke liye use nahi ho sakti -
# aur dono alag rehne se provider badal kar foran wapis aa sakte hain.
#
INDEX_NAME         = os.getenv("PINECONE_INDEX", _DEFAULT_INDEX)
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "school-general")

# ── RAG ──────────────────────────────────────────────────────
MAX_CONTEXT_CHARS = 4000
TOP_K             = int(os.getenv("RAG_TOP_K", "10"))

# LLM ka model wahi jo baqi system use karta hai (services/groq/groq.py)
GROQ_MODEL = os.getenv("LLM_SMART_MODEL") or os.getenv(
    "GROQ_SMART_MODEL", "openai/gpt-oss-120b"
)
