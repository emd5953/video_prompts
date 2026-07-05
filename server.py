"""
FastAPI server — web UI for uploading videos and generating apps.
Now with SSE streaming, spec review, and regeneration.
"""

import os
import json
import shutil
import uuid
import asyncio
from typing import AsyncGenerator

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse

import config
from video_analyzer import analyze_video
from code_generator import generate_project
from project_writer import write_project, zip_project

app = FastAPI(title="Video to App", description="Upload a video demo, get a working app.")

# In-memory store for specs (keyed by job_id)
specs_store: dict[str, dict] = {}
# Store video paths so we can re-analyze if needed
videos_store: dict[str, str] = {}


def sse_event(event: str, data: dict) -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.get("/", response_class=HTMLResponse)
async def index():
    with open(os.path.join(os.path.dirname(__file__), "templates", "index.html")) as f:
        return f.read()


@app.post("/api/upload")
async def upload_video(video: UploadFile = File(...)):
    """Upload a video and return a job_id."""
    allowed_types = [
        "video/mp4", "video/webm", "video/quicktime",
        "video/x-msvideo", "video/x-matroska",
    ]
    if video.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video type: {video.content_type}. Use MP4, WebM, MOV, AVI, or MKV.",
        )

    job_id = str(uuid.uuid4())[:8]
    ext = os.path.splitext(video.filename or "video.mp4")[1] or ".mp4"
    video_path = os.path.join(config.UPLOAD_DIR, f"{job_id}{ext}")

    with open(video_path, "wb") as f:
        shutil.copyfileobj(video.file, f)

    videos_store[job_id] = video_path
    return {"jobId": job_id}


@app.get("/api/analyze/{job_id}")
async def analyze(job_id: str):
    """Analyze the video with SSE streaming progress. Returns the app spec."""
    video_path = videos_store.get(job_id)
    if not video_path:
        raise HTTPException(status_code=404, detail="Job not found. Upload a video first.")

    async def stream() -> AsyncGenerator[str, None]:
        yield sse_event("step", {"step": 1, "message": "Uploading video to Gemini..."})
        await asyncio.sleep(0.1)

        try:
            # Run the blocking analysis in a thread
            yield sse_event("step", {"step": 2, "message": "Gemini is watching your video..."})
            loop = asyncio.get_event_loop()
            app_spec = await loop.run_in_executor(None, analyze_video, video_path)

            specs_store[job_id] = app_spec

            yield sse_event("spec", {
                "jobId": job_id,
                "spec": app_spec,
            })
            yield sse_event("done", {"message": "Analysis complete"})
        except Exception as e:
            yield sse_event("error", {"message": str(e)})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/generate/{job_id}")
async def generate(job_id: str, request: Request):
    """Generate code from a spec. Accepts optional edited spec in body."""
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}

    # Use edited spec if provided, otherwise use stored spec
    if "spec" in body:
        app_spec = body["spec"]
        specs_store[job_id] = app_spec
    else:
        app_spec = specs_store.get(job_id)

    if not app_spec:
        raise HTTPException(status_code=404, detail="No spec found. Analyze a video first.")

    async def stream() -> AsyncGenerator[str, None]:
        yield sse_event("step", {"step": 3, "message": "Generating project code..."})
        await asyncio.sleep(0.1)

        try:
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(None, generate_project, app_spec)

            yield sse_event("step", {"step": 4, "message": "Packaging project..."})
            await asyncio.sleep(0.1)

            app_name = app_spec.get("appName", "generated-app")

            project_dir = await loop.run_in_executor(None, write_project, app_name, files)
            zip_path = await loop.run_in_executor(None, zip_project, project_dir)

            yield sse_event("complete", {
                "appName": app_name,
                "description": app_spec.get("description", ""),
                "screensCount": len(app_spec.get("screens", [])),
                "filesCount": len(files),
                "downloadUrl": f"/api/download/{os.path.basename(zip_path)}",
            })
        except Exception as e:
            yield sse_event("error", {"message": str(e)})

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/api/download/{filename}")
async def download(filename: str):
    """Download a generated project zip."""
    filepath = os.path.join(config.OUTPUT_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, media_type="application/zip", filename=filename)
