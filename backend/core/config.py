from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    postgresql                  : str 
    user                        : str
    password                    : str
    host                        : str
    port                        : int
    db_name                     : str
    SECRET_KEY                  : str
    ALGORITHM                   : str
    ACCESS_TOKEN_EXPIRE_MINUTES : int 
    groq_api_key                : str
    HF_TOKEN                    : str
    API_KEY                     : str
    API_SECRET                  : str
    LIVEKIT_URL                 : str

    class Config:
        env_file = ".env"
        case_sensitive = False 
    
    @property
    def Database_URL(self) -> str:
        return f"{self.postgresql}://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
    
    @property
    def returning_groq_api(self) -> str:
        return f"{self.groq_api_key}"

    @property
    def return_HF_tokken(self):
        return f"{self.HF_TOKEN}"


settings = Settings()