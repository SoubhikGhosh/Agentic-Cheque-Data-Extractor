# ==============================================================================
# File: tasks.py
# ==============================================================================

import os
import base64
import requests
import json
import time
import uuid
import zipfile
import io
from celery import Celery, group, current_task
from celery.result import AsyncResult
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
        cropped_path = os.path.join(settings.CROPPED_DIR, f"{task_id}_{field_name}.jpg")
        with Image.open(image_path) as img:
            width, height = img.size
            left = int(width * percentages[0]); top = int(height * percentages[1])
            right = int(width * percentages[2]); bottom = int(height * percentages[3])
            img.crop((left, top, right, bottom)).save(cropped_path, "JPEG")
            return cropped_path

class GeminiAgent:
    """A generic agent to call Gemini API with retry logic."""
    def __init__(self, api_key, max_retries=5, base_delay=1):
        self.api_key = api_key
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.api_key}"
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _encode_image(self, image_path):
        with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')

    def extract_field(self, cropped_image_path, field_name):
        base64_image = self._encode_image(cropped_image_path)
        prompt = get_extraction_from_crop_prompt(field_name)
        payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}]}], "generationConfig": {"response_mime_type": "application/json"}}
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.api_url, json=payload, headers={"Content-Type": "application/json"}, timeout=90)
                response.raise_for_status()
                return json.loads(response.json()['candidates'][0]['content']['parts'][0]['text'])
            except requests.exceptions.RequestException as e:
                if attempt >= self.max_retries - 1: raise
                time.sleep(self.base_delay * (2 ** attempt))
        raise Exception(f"API call for {field_name} failed after all retries.")

def _run_single_field_extraction(image_path, field_name, parent_task_id):
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
def process_cheque_workflow(self, original_image_path, parent_job_id):
    task_id = self.request.id
    image_processor = ImageProcessor()
    files_to_cleanup = [original_image_path]
    try:
        processed_path = image_processor.process_full_image(original_image_path, task_id)
        files_to_cleanup.append(processed_path)
        specialist_tasks = group(extract_date_task.s(processed_path, task_id), extract_amount_numeric_task.s(processed_path, task_id))
        result_group = specialist_tasks.apply_async()
        results = result_group.get(disable_sync_subtasks=False)
        final_data = {"image_filename": os.path.basename(original_image_path), "extracted_fields": results}
        
        # *** NEW: Append result to the parent job's result file ***
        result_file_path = os.path.join(settings.RESULTS_DIR, f"{parent_job_id}.jsonl")
        with open(result_file_path, "a") as f:
            f.write(json.dumps(final_data) + "\n")
            
        return {'status': 'SUCCESS'}
    except Exception as e:
        return {'status': 'FAILED', 'error': str(e)}
    finally:
        for f_path in files_to_cleanup:
            if os.path.exists(f_path): os.remove(f_path)

@celery_app.task(bind=True, name='jobs.process_batch_job')
def process_batch_job(self, zip_file_content_b64, original_zip_filename):
    """The main Batch Job Agent. Orchestrates the entire ZIP file processing."""
    job_id = self.request.id
    print(f"Batch Job Agent {job_id} started for {original_zip_filename}")
    
    zip_content = base64.b64decode(zip_file_content_b64)
    image_paths = []
    
    # Unpack zip in memory and save images temporarily
    with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
        for filename in z.namelist():
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')) and not filename.startswith('__MACOSX'):
                image_data = z.read(filename)
                temp_image_path = os.path.join(settings.UPLOADS_DIR, f"{job_id}_{os.path.basename(filename)}")
                with open(temp_image_path, "wb") as buffer:
                    buffer.write(image_data)
                image_paths.append(temp_image_path)
    
    if not image_paths:
        self.update_state(state='FAILURE', meta={'error': 'No valid images in ZIP'})
        return {'status': 'FAILURE', 'error': 'No valid images in ZIP'}

    # Create a group of cheque-level coordinator tasks
    cheque_processing_group = group(
        process_cheque_workflow.s(path, parent_job_id=job_id) for path in image_paths
    )
    
    # Start the group of tasks and monitor progress
    result_group = cheque_processing_group.apply_async()
    
    total_tasks = len(image_paths)
    while not result_group.ready():
        completed_count = result_group.completed_count()
        self.update_state(state='PROGRESS', meta={'completed': completed_count, 'total': total_tasks})
        time.sleep(5)
        
    # The job is complete
    self.update_state(state='SUCCESS', meta={'completed': total_tasks, 'total': total_tasks})
    print(f"Batch Job {job_id} completed.")
    return {'status': 'SUCCESS', 'total_processed': total_tasks}
