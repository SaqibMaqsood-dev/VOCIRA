"""
RAG engine settings.

NOTE: ye file apni .env padhti hai (rag_engine/.env). Pehle yahan
GROQ_MODEL alag hardcoded tha jo baqi system se mel nahi khata tha -
jab gpt-oss-20b ka quota khatam hua to ERP sawal chalte rahe magar
RAG wale "assistant is currently busy" dete rahe. Ab wahi env var
padhta hai jo groq.py padhta hai.
"""

import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
