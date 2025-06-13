# ==============================================================================
# File: tasks.py
# ==============================================================================

import os
import base64
import requests
import json
import time
from celery import Celery, group
from PIL import Image, ImageEnhance
from config import settings
from prompts import get_extraction_from_crop_prompt

celery_app = Celery("tasks", broker=settings.REDIS_URL, backend=settings.REDIS_URL)

celery_app.conf.update(task_acks_late=True, worker_prefetch_multiplier=1)

class ImageProcessor:
    """Handles image pre-processing and cropping."""
    def process_full_image(self, image_path, task_id):
        processed_path = os.path.join(settings.PROCESSED_DIR, f"{task_id}.jpg")
        with Image.open(image_path) as img:
            img = img.convert('L')
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0)
            img.save(processed_path, "JPEG")
            return processed_path

    def crop_image_by_percentage(self, image_path, field_name, task_id, percentages):
        """Crops an image based on percentage coordinates."""
        cropped_path = os.path.join(settings.CROPPED_DIR, f"{task_id}_{field_name}.jpg")
        with Image.open(image_path) as img:
            width, height = img.size
            left = int(width * percentages[0])
            top = int(height * percentages[1])
            right = int(width * percentages[2])
            bottom = int(height * percentages[3])
            
            cropped_img = img.crop((left, top, right, bottom))
            cropped_img.save(cropped_path, "JPEG")
            return cropped_path

class GeminiAgent:
    """A generic agent to call Gemini API with retry logic."""
    def __init__(self, api_key, max_retries=5, base_delay=1):
        self.api_key = api_key
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.api_key}"
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def extract_field(self, cropped_image_path, field_name):
        """Extracts data from a single pre-cropped image."""
        base64_image = self._encode_image(cropped_image_path)
        prompt = get_extraction_from_crop_prompt(field_name)
        payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}]}], "generationConfig": {"response_mime_type": "application/json"}}
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.api_url, json=payload, headers={"Content-Type": "application/json"}, timeout=90)
                response.raise_for_status()
                result_json_str = response.json()['candidates'][0]['content']['parts'][0]['text']
                return json.loads(result_json_str)
            except requests.exceptions.RequestException as e:
                if attempt >= self.max_retries - 1: raise
                delay = self.base_delay * (2 ** attempt)
                time.sleep(delay)
        raise Exception(f"API call for {field_name} failed after all retries.")

def _run_single_field_extraction(image_path, field_name, parent_task_id):
    """Generic helper function for a single field extraction task."""
    image_processor = ImageProcessor()
    gemini_agent = GeminiAgent(api_key=settings.GEMINI_API_KEY)
    
    files_to_cleanup = []
    try:
        percentages = settings.FIELD_COORDINATES[field_name]
        cropped_path = image_processor.crop_image_by_percentage(image_path, field_name, parent_task_id, percentages)
        files_to_cleanup.append(cropped_path)
        
        extraction_result = gemini_agent.extract_field(cropped_path, field_name)
        
        return {"field_name": field_name, **extraction_result}
    finally:
        for f_path in files_to_cleanup:
            if os.path.exists(f_path): os.remove(f_path)

@celery_app.task
def extract_date_task(processed_image_path, parent_task_id):
    return _run_single_field_extraction(processed_image_path, "date", parent_task_id)

@celery_app.task
def extract_amount_numeric_task(processed_image_path, parent_task_id):
    return _run_single_field_extraction(processed_image_path, "amount_numeric", parent_task_id)

@celery_app.task(bind=True, name='tasks.process_cheque_workflow')
def process_cheque_workflow(self, original_image_path):
    """This is the main Coordinator Agent task."""
    task_id = self.request.id
    print(f"Coordinator task {task_id} received for image: {original_image_path}")
    
    image_processor = ImageProcessor()
    files_to_cleanup = [original_image_path]
    
    try:
        # Pre-process the image ONCE
        processed_path = image_processor.process_full_image(original_image_path, task_id)
        files_to_cleanup.append(processed_path)
        
        # Define the parallel jobs for our specialized agents
        # This creates a group of tasks that will run in parallel.
        specialist_tasks = group(
            extract_date_task.s(processed_path, task_id),
            extract_amount_numeric_task.s(processed_path, task_id)
        )
        
        # Execute the group and wait for all results
        result_group = specialist_tasks.apply_async()
        results = result_group.get(disable_sync_subtasks=False) # Wait for completion
        
        # Aggregate the results
        final_data = {"extracted_fields": results}
        
        print(f"Coordinator task {task_id} completed successfully.")
        return {'status': 'SUCCESS', 'result': final_data}
        
    except Exception as e:
        print(f"Coordinator task {task_id} failed: {e}")
        # Celery's built-in retry mechanism for broader task failures
        self.retry(exc=e)
        return {'status': 'FAILED', 'error': str(e)}

    finally:
        # Clean up the main original and processed files
        print(f"Coordinator cleaning up files for task {task_id}...")
        for f_path in files_to_cleanup:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except OSError as e:
                    print(f"Error removing file {f_path}: {e}")
                    