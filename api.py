# ==============================================================================
# File: api.py
# ==============================================================================

import os
import base64
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from celery.result import AsyncResult
from config import settings
from tasks import process_batch_job

app = FastAPI(title="Cheque Extraction Batch API", version="5.0")

@app.post("/jobs/", status_code=202)
async def create_batch_job(file: UploadFile = File(...)):
    """
    Endpoint to upload a ZIP file. This creates a single Batch Job and
    returns a single job_id for the entire batch.
    """
    if file.content_type not in ["application/zip", "application/x-zip-compressed"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a ZIP file.")
    try:
        zip_content = await file.read()
        zip_content_b64 = base64.b64encode(zip_content).decode('utf-8')
        
        # Call the new top-level batch job task
        task = process_batch_job.delay(zip_content_b64, file.filename)
        
        return JSONResponse({
            "message": "Batch job created successfully. Processing has started.",
            "job_id": task.id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create job: {e}")

@app.get("/jobs/{job_id}/status")
def get_job_status(job_id: str):
    """Endpoint to check the status of a long-running batch job."""
    task_result = AsyncResult(job_id, app=process_batch_job.app)
    if not task_result:
        raise HTTPException(status_code=404, detail="Job not found.")
        
    response = {"job_id": job_id, "status": task_result.state}
    if task_result.info:
        response.update(task_result.info)
        
    return JSONResponse(response)

@app.get("/jobs/{job_id}/results")
def get_job_results(job_id: str):
    """
    Endpoint to download the final aggregated results for a completed job.
    This returns a JSON Lines file.
    """
    task_result = AsyncResult(job_id, app=process_batch_job.app)
    if not task_result or task_result.state != 'SUCCESS':
         raise HTTPException(status_code=404, detail="Job not found or not completed.")

    result_file_path = os.path.join(settings.RESULTS_DIR, f"{job_id}.jsonl")
    
    if not os.path.exists(result_file_path):
        raise HTTPException(status_code=404, detail="Result file not found.")

    return FileResponse(result_file_path, media_type="application/json-lines", filename=f"results_{job_id}.jsonl")
