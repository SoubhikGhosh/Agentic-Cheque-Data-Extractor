# ==============================================================================
# File: tasks.py
# ==============================================================================
# This file defines the background tasks that our worker will execute.

import os
import base64
import requests
import json
from celery import Celery
from PIL import Image, ImageEnhance
from config import settings
from prompts import get_prompt_for_fields

celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

class ImageProcessor:
    """Handles image pre-processing logic."""
    def process(self, image_path, task_id):
        processed_path = os.path.join(settings.PROCESSED_DIR, f"{task_id}.jpg")
        print(f"Processing image: {image_path}")
        try:
            with Image.open(image_path) as img:
                img = img.convert('L')
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
                img.save(processed_path, "JPEG")
                return processed_path
        except Exception as e:
            print(f"Error processing image {image_path}: {e}")
            raise

class GeminiExtractor:
    """Handles communication with the Gemini API."""
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.api_key}"

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def extract(self, image_path, fields_to_extract):
        print(f"Starting extraction for: {fields_to_extract} from {image_path}")
        base64_image = self._encode_image(image_path)
        prompt = get_prompt_for_fields(fields_to_extract)
        payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}]}], "generationConfig": {"response_mime_type": "application/json"}}
        response = requests.post(self.api_url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        result_json_str = response.json()['candidates'][0]['content']['parts'][0]['text']
        return json.loads(result_json_str)

@celery_app.task(bind=True, name='tasks.extract_cheque_data', max_retries=3, default_retry_delay=60)
def extract_cheque_data(self, image_path):
    """
    Celery task to run the full extraction workflow for a single image.
    This function will be executed by a background worker.
    """
    task_id = self.request.id
    print(f"Worker received task {task_id} for image {image_path}")
    try:
        image_processor = ImageProcessor()
        processed_image_path = image_processor.process(image_path, task_id)
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set.")
        extractor = GeminiExtractor(api_key=settings.GEMINI_API_KEY)
        fields_to_extract = ["date", "amount_numeric"]
        extracted_data = extractor.extract(processed_image_path, fields_to_extract)
        os.remove(image_path)
        os.remove(processed_image_path)
        print(f"Task {task_id} completed successfully.")
        return {'status': 'SUCCESS', 'result': extracted_data}
    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        self.retry(exc=e)
        return {'status': 'FAILED', 'error': str(e)}

