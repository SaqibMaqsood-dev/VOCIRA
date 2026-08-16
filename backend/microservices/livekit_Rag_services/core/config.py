from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BASE_DIR / ".env"

class Settings(BaseSettings):
    DB_USER: str
    DB_PORT: int
    DB_HOST: str
    DB_NAME: str
    DB_PASSWORD: str

    GROQ_API_KEY: str
    HF_TOKEN: str

    POSTGRESQL: str

    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    LIVEKIT_URL: str
    LIVEKIT_API_KEY: str
    LIVEKIT_API_SECRET: str

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"{self.POSTGRESQL}://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def returning_groq_api(self) -> str:
        return self.GROQ_API_KEY

    @property
    def return_HF_token(self):
        return self.HF_TOKEN


settings = Settings()
