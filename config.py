# ==============================================================================
# File: config.py
# ==============================================================================
# Centralized configuration for the application.

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    REDIS_URL = "redis://redis:6379/0"
    UPLOADS_DIR = "uploads"
    PROCESSED_DIR = "processed"

settings = Settings()

os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
os.makedirs(settings.PROCESSED_DIR, exist_ok=True)