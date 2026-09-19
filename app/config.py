import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RECORDS_DIR = BASE_DIR / "records"
UPLOADS_DIR = BASE_DIR / "uploads"

# Ensure runtime directories exist
DATA_DIR.mkdir(exist_ok=True)
RECORDS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

class Settings(BaseSettings):
    APP_NAME: str = "AI Resume Screening Agent"
    APP_VERSION: str = "1.0.0"
    
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = DATA_DIR
    RECORDS_DIR: Path = RECORDS_DIR
    UPLOADS_DIR: Path = UPLOADS_DIR

    # Storage Paths
    DB_PATH: str = str(DATA_DIR / "screening.db")
    EXCEL_PATH: str = str(RECORDS_DIR / "screened_candidates.xlsx")
    CSV_PATH: str = str(RECORDS_DIR / "screened_candidates.csv")
    
    # AI Provider Settings (Google Gemini free tier / Groq / Fallback)
    AI_PROVIDER: str = "gemini"  # "gemini", "groq", "heuristic"
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.6-flash"
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    
    # Email / Notification Automation Settings
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@example.com"
    ENABLE_REAL_EMAIL: bool = False

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
