#settings
import os
from dotenv import load_dotenv

load_dotenv()

# ── API Keys ─────────────────────────────────────────────────
PINECONE_API_KEY     = os.getenv("PINECONE_API_KEY")
HUGGINGFACEHUB_TOKEN = os.getenv("HUGGINGFACEHUB_API_TOKEN")
GROQ_API_KEY         = os.getenv("GROQ_API_KEY")

# ── Data Paths ───────────────────────────────────────────────
DATA_DIR        = "./data"
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