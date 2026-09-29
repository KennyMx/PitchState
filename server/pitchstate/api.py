"""Local inference companion API with bounded jobs and private per-session uploads."""

from __future__ import annotations
import json
import os
import secrets
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from .pipeline import analyze
from .perception import ROOT, SoccerModels
from .jev import JevJudge

load_dotenv(ROOT / ".env.local")
JOBS = ROOT / ".local/jobs"
JOBS.mkdir(parents=True, exist_ok=True)
MAX_BYTES = 100 * 1024 * 1024
jobs = {}
lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=1)
models = None
persist_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    # Explicit restart recovery: unfinished persisted jobs do not pretend to still run.
    for folder in JOBS.iterdir():
        if not folder.is_dir():
            continue
        record = folder / "job.json"
        if not record.exists():
            continue
        try:
            job = json.loads(record.read_text())
            if time.time() - job["created"] > 86400:
                shutil.rmtree(folder)
                continue
            if job["status"] in ("uploading", "queued", "running"):
                job["status"] = "failed"
                job["error"] = "Service restarted during analysis; submit the clip again."
            job["cancel"] = threading.Event()
            jobs[job["id"]] = job
        except (ValueError, KeyError):
            continue
    yield
    for job in jobs.values():
        job["cancel"].set()


app = FastAPI(
    title="PitchState inference companion", lifespan=lifespan, docs_url=None, redoc_url=None
)


def persist(job):
    target = JOBS / job["id"] / "job.json"
    with persist_lock:
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps({k: v for k, v in job.items() if k != "cancel"}))
        temporary.replace(target)


@app.middleware("http")
async def boundary(request: Request, call_next):
    # Public deployments may require an access token in addition to durable global job limits.
    # Default operation is a loopback companion, with no externally accessible listener.
    if os.getenv("PITCHSTATE_PUBLIC", "0") == "1" and request.url.path.startswith("/api/jobs"):
        expected = os.getenv("PITCHSTATE_ACCESS_TOKEN", "")
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if expected and not secrets.compare_digest(supplied, expected):
            return JSONResponse({"detail": "Authorized access required"}, 401)
    origin = request.headers.get("origin")
    allowed = {
        f"http://{h}:{p}" for h in ("localhost", "127.0.0.1") for p in ("5173", "5174", "8000")
    }
    if origin and origin not in allowed and origin != os.getenv("PITCHSTATE_ORIGIN"):
        return JSONResponse({"detail": "Origin not allowed"}, 403)
    size = request.headers.get("content-length")
    if size and (not size.isdigit() or int(size) > MAX_BYTES + 1024 * 1024):
        return JSONResponse({"detail": "Clip exceeds 100 MB"}, 413)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/health")
def health(request: Request):
    session = request.cookies.get("pitchstate_session") or secrets.token_urlsafe(32)
    available = all(
        (ROOT / "models" / f"football-{name}-detection.pt").exists()
        for name in ("player", "ball", "pitch")
    )
    response = JSONResponse(
        {
            "ready": available,
            "pipeline": "offline-soccer-v3",
            "jevConfigured": bool(os.getenv("JEV_API_KEY")),
            "maxClipSeconds": 60,
            "sampleFps": 5,
            "demoAvailable": Path(
                os.getenv("PITCHSTATE_DEMO_ANALYSIS", str(ROOT / ".local/real-analysis.json"))
            ).exists()
            and Path(os.getenv("PITCHSTATE_DEMO_VIDEO", str(ROOT / "data/2e57b9_0.mp4"))).exists(),
            "budget": JevJudge(ROOT / ".local").usage(),
        }
    )
    response.set_cookie(
        "pitchstate_session",
        session,
        httponly=True,
        samesite="strict",
        max_age=86400,
        secure=os.getenv("PITCHSTATE_PUBLIC") == "1",
    )
    return response


def public_job(job):
    return {
        k: job[k]
        for k in ("id", "status", "progress", "stage", "error", "created", "preview")
        if k in job
    }


def run_job(job):
    global models
    try:
        if job["cancel"].is_set():
            raise InterruptedError()
        job.update(status="running", stage="loading models")
        persist(job)
        if models is None:
            models = SoccerModels(device=os.getenv("PITCHSTATE_DEVICE", "auto"))

        def progress(info):
            job.update(progress=info["progress"], stage=info["stage"])
            persist(job)

        result = analyze(
            JOBS / job["id"] / "video.mp4",
            models=models,
            duration_limit=60,
            use_jev=job["jev"],
            home_attacks_right=job["homeAttacksRight"],
            progress=progress,
            cancelled=job["cancel"].is_set,
            output=JOBS / job["id"] / "analysis.json",
        )
        if job["cancel"].is_set():
            raise InterruptedError()
        result["name"] = job["name"]
        (JOBS / job["id"] / "analysis.json").write_text(json.dumps(result, allow_nan=False))
        job.update(status="complete", progress=100, stage="ready")
    except InterruptedError:
        job.update(status="cancelled", stage="cancelled")
    except Exception as error:
        # Do not return third-party exception bodies or filesystem paths to the browser.
        job.update(
            status="failed",
            stage="failed",
            error=f"Analysis failed ({type(error).__name__}). Check the local service log.",
        )
        print(f"Job {job['id']} failed: {type(error).__name__}", flush=True)
    finally:
        persist(job)


@app.post("/api/jobs", status_code=202)
async def create_job(
    request: Request,
    video: UploadFile = File(...),
    use_jev: bool = Form(True),
    home_attacks_right: bool = Form(True),
    request_id: str | None = Form(None),
):
    session = request.cookies.get("pitchstate_session")
    if not session:
        raise HTTPException(403, "Initialize the session first")
    if request_id is not None and re.fullmatch(r"[a-f0-9]{32}", request_id) is None:
        raise HTTPException(400, "Invalid request identity")
    with lock:
        cutoff = time.time() - 86400
        for old_id, old in list(jobs.items()):
            if old["created"] < cutoff and old["status"] not in ("queued", "running", "uploading"):
                shutil.rmtree(JOBS / old_id, ignore_errors=True)
                jobs.pop(old_id, None)
        daily_limit = int(os.getenv("PITCHSTATE_DAILY_JOB_LIMIT", "12"))
        if sum(j["created"] >= cutoff for j in jobs.values()) >= daily_limit:
            raise HTTPException(
                429, "The daily analysis limit has been reached. Cached examples remain available."
            )
        if sum(j["status"] in ("uploading", "queued", "running") for j in jobs.values()) >= 2:
            raise HTTPException(429, "The local worker is busy; wait for a job to finish.")
        identity = request_id or secrets.token_hex(16)
        if identity in jobs:
            raise HTTPException(409, "This upload request already exists")
        job = {
            "id": identity,
            "owner": session,
            "name": Path(video.filename or "Uploaded clip").stem[:100],
            "mediaType": video.content_type
            if video.content_type in ("video/mp4", "video/webm", "video/quicktime")
            else "video/mp4",
            "created": time.time(),
            "status": "uploading",
            "progress": 0,
            "stage": "uploading",
            "jev": use_jev,
            "homeAttacksRight": home_attacks_right,
            "cancel": threading.Event(),
        }
        jobs[identity] = job
    directory = JOBS / identity
    directory.mkdir()
    size = 0
    try:
        with (directory / "video.mp4").open("wb") as handle:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "Choose a clip smaller than 100 MB")
                handle.write(chunk)
        if size == 0:
            raise HTTPException(400, "Video is empty")
        if await request.is_disconnected():
            raise HTTPException(499, "Upload disconnected before analysis")
        job["status"] = "queued"
        job["stage"] = "queued"
        persist(job)
        executor.submit(run_job, job)
        return public_job(job)
    except Exception:
        with lock:
            jobs.pop(identity, None)
        shutil.rmtree(directory, ignore_errors=True)
        raise
    finally:
        await video.close()


def owned(identity, request):
    job = jobs.get(identity)
    if job is None or not secrets.compare_digest(
        job["owner"], request.cookies.get("pitchstate_session", "")
    ):
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/jobs/{identity}")
def status(identity: str, request: Request):
    return public_job(owned(identity, request))


@app.get("/api/jobs/{identity}/analysis")
def result(identity: str, request: Request):
    job = owned(identity, request)
    if job["status"] != "complete":
        raise HTTPException(409, "Analysis is not complete")
    return FileResponse(JOBS / identity / "analysis.json", media_type="application/json")


@app.get("/api/jobs/{identity}/video")
def video(identity: str, request: Request):
    job = owned(identity, request)
    return FileResponse(JOBS / identity / "video.mp4", media_type=job.get("mediaType", "video/mp4"))


@app.delete("/api/jobs/{identity}")
def cancel(identity: str, request: Request):
    job = owned(identity, request)
    job["cancel"].set()
    if job["status"] == "queued":
        job.update(status="cancelled", stage="cancelled")
        persist(job)
    return {"cancelRequested": True}


@app.get("/api/demo/analysis")
def demo_analysis():
    path = Path(os.getenv("PITCHSTATE_DEMO_ANALYSIS", str(ROOT / ".local/real-analysis.json")))
    if not path.exists():
        raise HTTPException(404, "Run the evaluation clip to prepare the real demo")
    return FileResponse(path, media_type="application/json")


@app.get("/api/demo/video")
def demo_video():
    path = Path(os.getenv("PITCHSTATE_DEMO_VIDEO", str(ROOT / "data/2e57b9_0.mp4")))
    if not path.exists():
        raise HTTPException(404, "Download the evaluation clip first")
    return FileResponse(path, media_type="video/mp4")


# A production build can be served from the same origin as the API.
if (ROOT / "dist").exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="frontend")
