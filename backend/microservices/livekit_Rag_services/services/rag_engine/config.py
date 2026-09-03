#settings
import os
from dotenv import load_dotenv

# Explicitly load rag_engine/.env — no matter where the worker is run from (whether from
# backend/ or from rag_engine/ itself), this will always find the correct .env.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_PATH)

# ── API Keys ─────────────────────────────────────────────────
PINECONE_API_KEY     = os.getenv("PINECONE_API_KEY")
HUGGINGFACEHUB_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY")

# ── Data Paths ───────────────────────────────────────────────
DATA_DIR        = os.path.join(BASE_DIR, "data")
PDF_PATH        = os.path.join(DATA_DIR, "pdf")
TEXT_FILES_PATH = os.path.join(DATA_DIR, "text_files")
URLS_FILE_PATH  = os.path.join(DATA_DIR, "urls.txt")

# ── Pinecone ─────────────────────────────────────────────────
INDEX_NAME      = "school-bot-index"
TEMP_INDEX_NAME = f"{INDEX_NAME}-temp"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM   = 384

# ── RAG ──────────────────────────────────────────────────────
MAX_CONTEXT_CHARS = 4000

# NOTE: Ye pehle "openai/gpt-oss-20b" par hardcoded tha, jabke baqi
# system services/groq/groq.py ka model use karta hai. Natija: jab
# gpt-oss-20b ka daily quota khatam hua to ERP sawal to chalte rahe
# magar RAG wale har baar "assistant is currently busy" dete rahe.
#
# Ab wahi env var aur wahi default jo groq.py mein hai, taake dono
# hamesha ek hi model par rahein.
GROQ_MODEL = os.getenv(
    "GROQ_SMART_MODEL",
    "openai/gpt-oss-120b",
)

TOP_K             = 10

# ── Pinecone Namespace ───────────────────────────────────────
PINECONE_NAMESPACE = "school-general"