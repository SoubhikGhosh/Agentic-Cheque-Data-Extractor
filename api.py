# ==============================================================================
# File: api.py
# ==============================================================================

import os
import uuid
import zipfile
import io
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from config import settings
# Import the new main workflow task
from tasks import process_cheque_workflow

app = FastAPI(title="Cheque Extraction API", version="4.0") 

@app.post("/extract-zip/", status_code=202)
async def upload_zip_and_extract(file: UploadFile = File(...)):
    """Endpoint to upload a ZIP file. It calls the main coordinator task for each image."""
    if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP file.")
    task_ids = []
    try:
        zip_content = await file.read()
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            file_list = z.namelist()
            for filename in file_list:
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')) and not filename.startswith('__MACOSX'):
                    image_data = z.read(filename)
                    unique_id = str(uuid.uuid4())
                    temp_image_path = os.path.join(settings.UPLOADS_DIR, f"{unique_id}_{os.path.basename(filename)}")
                    with open(temp_image_path, "wb") as buffer:
                        buffer.write(image_data)
                    
                    # *** CHANGE: Call the main workflow task, not the old one ***
                    task = process_cheque_workflow.delay(temp_image_path)
                    task_ids.append(task.id)
        if not task_ids:
            raise HTTPException(status_code=400, detail="No valid image files found.")
        return JSONResponse({"message": f"Processing started for {len(task_ids)} images.", "task_ids": task_ids})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process ZIP file: {e}")

@app.get("/results/{task_id}")
def get_task_result(task_id: str):
    """Endpoint to check the status and get the result of a single task."""
    task_result = AsyncResult(task_id, app=process_cheque_workflow.app)
    if not task_result:
        raise HTTPException(status_code=404, detail="Task not found.")
    if task_result.ready():
        if task_result.successful():
            return JSONResponse({"status": "SUCCESS", "data": task_result.get()})
        else:
            return JSONResponse({"status": "FAILURE", "error": str(task_result.info)})
    else:
        return JSONResponse({"status": "PENDING"})