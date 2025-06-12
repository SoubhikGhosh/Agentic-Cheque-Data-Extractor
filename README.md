# Agentic-Cheque-Data-Extractor
 Running Locally without Docker (For Development)
Install Dependencies:

Install Redis for your operating system.

Create a Python virtual environment and install the requirements:

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

Update Config: Open config.py and change the REDIS_URL to point to your local machine:

# Change this line in config.py
REDIS_URL = "redis://localhost:6379/0"

Start Services: Open three separate terminal windows in your project directory.

Terminal 1 (Start Redis): redis-server

Terminal 2 (Start Worker): celery -A tasks worker --loglevel=info (ensure venv is active)

Terminal 3 (Start API): uvicorn api:app --reload (ensure venv is active)

Step 3: How to Use the API
Prepare your data: Create a .zip file (e.g., cheques_batch.zip) containing one or more cheque images. Place it in your project folder.

Submit the ZIP file: Open a new terminal and run the following command to send your file to the API for processing:

curl -X POST -F "file=@cheques_batch.zip" http://127.0.0.1:8000/extract-zip/

Receive Task IDs: The API will immediately respond with a JSON object containing the task_ids for each image found in the zip:

{
  "message": "Processing started for 2 images.",
  "task_ids": [
    "a1b2c3d4-e5f6-a7b8-c9d0-e1f2a3b4c5d6",
    "f1a2b3c4-d5e6-f7a8-b9c0-d1e2f3a4b5c6"
  ]
}

Check the Results: Wait a few moments for the background worker to process the images. Then, use one of the task_ids to check its status.

# Replace YOUR_TASK_ID_HERE with an actual ID from the previous step
curl http://127.0.0.1:8000/results/YOUR_TASK_ID_HERE

The final, successful result will be a JSON object containing the extracted data.