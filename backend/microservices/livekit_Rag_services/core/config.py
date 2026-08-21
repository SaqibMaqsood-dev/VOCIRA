from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# Paths
# ============================================================

# config.py
#   ↓ parent
# core/
#   ↓ parent
# livekit_Rag_services/
#
# Therefore:
# parents[1] = livekit_Rag_services

BASE_DIR = Path(__file__).resolve().parents[1]

ENV_FILE = BASE_DIR / ".env"

# Explicitly load the .env from livekit_Rag_services/
load_dotenv(ENV_FILE)


# ============================================================
# Settings
# ============================================================

class Settings(BaseSettings):

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    DB_USER: str
    DB_PORT: int
    DB_HOST: str
    DB_NAME: str
    DB_PASSWORD: str

    POSTGRESQL: str

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    GROQ_API_KEY: str
    HF_TOKEN: str
    PINECONE_API_KEY: str

    # --------------------------------------------------------
    # Authentication
    # --------------------------------------------------------

    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    # --------------------------------------------------------
    # LiveKit
    # --------------------------------------------------------

    LIVEKIT_URL: str
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    # --------------------------------------------------------
    # ERP
    # --------------------------------------------------------

    ERP_BASE_URL: str
    ERP_API_KEY: str
    ERP_API_SECRET: str

    # --------------------------------------------------------
    # Auth Microservice
    # --------------------------------------------------------

    AUTH_SERVICE_URL: str = "http://127.0.0.1:8000"

    # --------------------------------------------------------
    # Pydantic Settings
    # --------------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================
    # Properties
    # ========================================================

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"{self.POSTGRESQL}://"
            f"{self.DB_USER}:"
            f"{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:"
            f"{self.DB_PORT}/"
            f"{self.DB_NAME}"
        )

    @property
    def returning_groq_api(self) -> str:
        return self.GROQ_API_KEY

    @property
    def return_HF_token(self) -> str:
        return self.HF_TOKEN


# ============================================================
# Create settings
# ============================================================

settings = Settings()


# ============================================================
# RAG Constants
# ============================================================

INDEX_NAME = "school-bot-index"
TEMP_INDEX_NAME = f"{INDEX_NAME}-temp"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

MAX_CONTEXT_CHARS = 4000
GROQ_MODEL = "llama-3.1-8b-instant"
TOP_K = 10

PINECONE_NAMESPACE = "school-general"


# ============================================================
# RAG Data Paths
# ============================================================

DATA_DIR = BASE_DIR / "data"

PDF_PATH = DATA_DIR / "pdf"
TEXT_FILES_PATH = DATA_DIR / "text_files"
URLS_FILE_PATH = DATA_DIR / "urls.txt"


# ============================================================
# Debug
# ============================================================

print(f"📁 [RAG Config] BASE_DIR: {BASE_DIR}")
print(f"📄 [RAG Config] ENV_FILE: {ENV_FILE}")
print(f"📄 [RAG Config] ENV_EXISTS: {ENV_FILE.exists()}")

print(
    f"🔑 [RAG Config] PINECONE_API_KEY loaded: "
    f"{bool(settings.PINECONE_API_KEY)}"
)

print(
    f"🔑 [RAG Config] GROQ_API_KEY loaded: "
    f"{bool(settings.GROQ_API_KEY)}"
)

print(
    f"🔑 [RAG Config] HF_TOKEN loaded: "
    f"{bool(settings.HF_TOKEN)}"
)