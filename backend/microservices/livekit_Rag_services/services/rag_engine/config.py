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
GROQ_MODEL        = "llama-3.1-8b-instant"
TOP_K             = 10

# ── Pinecone Namespace ───────────────────────────────────────
PINECONE_NAMESPACE = "school-general"