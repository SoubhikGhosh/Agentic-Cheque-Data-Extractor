# ==============================================================================
# File: config.py
# ==============================================================================
# *** UPDATED: Added percentage-based coordinates for fields. ***
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    REDIS_URL = "redis://redis:6379/0"
    UPLOADS_DIR = "uploads"
    PROCESSED_DIR = "processed"
    CROPPED_DIR = "cropped"

    # *** NEW: Configuration-driven cropping coordinates ***
    # Format: (left_percentage, top_percentage, right_percentage, bottom_percentage)
    # These values define the bounding box for each field relative to the image size.
    FIELD_COORDINATES = {
        "date": (0.75, 0.05, 0.98, 0.15),          # Top-right area
        "amount_numeric": (0.7, 0.25, 0.98, 0.35)  # Middle-right area
        # Add coordinates for other fields like 'micr', 'payee_name' here
    }

settings = Settings()

os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
os.makedirs(settings.CROPPED_DIR, exist_ok=True)
