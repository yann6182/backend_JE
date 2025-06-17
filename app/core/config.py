from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    GEMINI_API_KEY: Optional[str] = None

    class Config:
        env_file = '.env'

def get_settings() -> Settings:
    return Settings()

settings = get_settings()
