from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"



class Settings(BaseSettings):
    APP_NAME: str
    APP_ENV: str

    HOST: str
    PORT: int

    DATABASE_URL: str
    DB_ECHO: bool = False

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15 
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    PASSWORD_HASH_ALGORITHM: str = "bcrypt"

    # /users/internal/{id} sirf doosri services ke liye hai, end users
    # ke liye nahi. Wo call bina JWT ke aati hai, is liye user auth ke
    # bajaye ye shared secret use hota hai.
    INTERNAL_SERVICE_KEY: str = "vocira-internal-dev-key-change-me"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        extra="ignore",
    )


settings = Settings()