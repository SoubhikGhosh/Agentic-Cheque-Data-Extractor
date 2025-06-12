# ==============================================================================
# File: api.py
# ==============================================================================
# The FastAPI server.

import os
import uuid
import zipfile
import io
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from celery.result import AsyncResult
from config import settings
from tasks import extract_cheque_data

app = FastAPI(title="Cheque Extraction API", version="2.0")

@app.post("/extract-zip/", status_code=202)
async def upload_zip_and_extract(file: UploadFile = File(...)):
    """
    Endpoint to upload a ZIP file containing multiple cheque images.
    It extracts images from the ZIP, creates a background task for each one,
    and returns a list of task IDs for the client to monitor.
    This endpoint is designed to be called by the Agent Control Panel (ACP).
    """
    if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP file.")

    task_ids = []
    
    try:
        # Read the zip file content into memory
        zip_content = await file.read()
        
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            # Get a list of all files in the zip
            file_list = z.namelist()
            
            for filename in file_list:
                # Check for valid image files and ignore macOS metadata files
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')) and not filename.startswith('__MACOSX'):
                    
                    # Extract the single image file into memory
                    image_data = z.read(filename)
                    
                    # Generate a unique path for this image to avoid collisions
                    unique_id = str(uuid.uuid4())
                    temp_image_path = os.path.join(settings.UPLOADS_DIR, f"{unique_id}_{os.path.basename(filename)}")
                    
                    # Write the image from memory to the uploads directory
                    with open(temp_image_path, "wb") as buffer:
                        buffer.write(image_data)
                    
                    # Dispatch the extraction task to the worker
                    task = extract_cheque_data.delay(temp_image_path)
                    task_ids.append(task.id)

        if not task_ids:
            raise HTTPException(status_code=400, detail="No valid image files found in the ZIP archive.")
            
        return JSONResponse({
            "message": f"Processing started for {len(task_ids)} images.",
            "task_ids": task_ids
        })

    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="The uploaded file is not a valid ZIP archive.")
    except Exception as e:
        # Log the exception for debugging
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process ZIP file: {e}")


@app.get("/results/{task_id}")
def get_task_result(task_id: str):
    """
    Endpoint to check the status and get the result of a single task.
    The ACP would call this endpoint for each task ID it receives.
    """
    task_result = AsyncResult(task_id, app=extract_cheque_data.app)

    if not task_result:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task_result.ready():
        if task_result.successful():
            return JSONResponse({"status": "SUCCESS", "data": task_result.get()})
        else:
            return JSONResponse({"status": "FAILURE", "error": str(task_result.info)})
    else:
        return JSONResponse({"status": "PENDING"})
