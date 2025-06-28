from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Charger les variables d'environnement avant l'initialisation de Settings
load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str
    GEMINI_API_KEY: Optional[str] = None
    
    # Configuration SharePoint/Microsoft Graph
    TENANT_ID: Optional[str] = None
    CLIENT_ID: Optional[str] = None
    CLIENT_SECRET: Optional[str] = None
    GRAPH_DRIVE_ID: Optional[str] = None
    GRAPH_DPFG_FOLDER: Optional[str] = "Documents"
    DPGF_UPLOAD_DIR: Optional[str] = "/var/lib/dpgf"

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
