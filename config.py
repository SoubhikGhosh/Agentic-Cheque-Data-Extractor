# ==============================================================================
# File: config.py
# ==============================================================================

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    REDIS_URL = "redis://redis:6379/0"
    UPLOADS_DIR = "uploads"
    PROCESSED_DIR = "processed"
    CROPPED_DIR = "cropped"
    RESULTS_DIR = "results" 

    # Format: (left_percentage, top_percentage, right_percentage, bottom_percentage)
    FIELD_COORDINATES = {
        # The date agent will look in the top-right quadrant.
        "date": (0.5, 0.0, 1.0, 0.5),

        # The amount_numeric agent will look in the entire right half.
        "amount_numeric": (0.5, 0.0, 1.0, 1.0)
    }

settings = Settings()

os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
os.makedirs(settings.CROPPED_DIR, exist_ok=True)
os.makedirs(settings.RESULTS_DIR, exist_ok=True)
