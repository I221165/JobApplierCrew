import asyncio
import hashlib
import json
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from api.db import Application, Job, get_session, init_db
from api.tasks import submit_application
from services.analysis import screen_job
from services.scrape import scrape_job
from services.search import search_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Job Applier API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/response schemas ──────────────────────────────────────────────────
class SearchRequest(BaseModel):
    role: str
    location: str
    max_jobs: int = 5


class ScreenRequest(BaseModel):
    cv: str


class ApplyRequest(BaseModel):
    cv: str
    latex_template: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "job-applier"}


@app.post("/search")
def search(req: SearchRequest):
    listings = search_jobs(req.role, req.location, max_jobs=req.max_jobs)
    with get_session() as session:
        job_ids = []
        for listing in listings:
            job_id = hashlib.md5(listing["url"].encode()).hexdigest()[:16]
            existing = session.get(Job, job_id)
            if existing is None:
                session.add(Job(
                    id=job_id,
                    url=listing["url"],
                    title=listing["title"],
                    snippet=listing["snippet"],
                    role_searched=req.role,
                    location=req.location,
                ))
            job_ids.append(job_id)
        session.commit()
    return {"job_ids": job_ids, "count": len(job_ids)}


@app.get("/jobs")
def list_jobs(role: str | None = None, location: str | None = None):
    with get_session() as session:
        stmt = select(Job)
        if role:
            stmt = stmt.where(Job.role_searched == role)
        if location:
            stmt = stmt.where(Job.location == location)
        jobs = session.exec(stmt).all()
        return [j.model_dump() for j in jobs]


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return job.model_dump()


@app.post("/jobs/{job_id}/screen")
def screen(job_id: str, req: ScreenRequest):
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")

        page_text = scrape_job(job.url)
        analysis = screen_job(job.url, page_text, req.cv, job.role_searched)

        job.actual_title = analysis.actual_title
        job.is_active = analysis.is_active
        job.role_match = analysis.role_match
        job.match_score = analysis.match_score
        job.must_have_json = json.dumps(analysis.must_have)
        job.nice_to_have_json = json.dumps(analysis.nice_to_have)
        job.keywords_json = json.dumps(analysis.keywords)
        job.tone = analysis.tone
        session.add(job)
        session.commit()

        return {"job_id": job_id, "analysis": analysis.model_dump()}


@app.post("/jobs/{job_id}/apply")
def apply(job_id: str, req: ApplyRequest):
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        if job.match_score is None:
            raise HTTPException(400, "Job has not been screened yet — call /screen first")

        app_id = uuid.uuid4().hex
        session.add(Application(id=app_id, job_id=job_id, status="queued", progress_message="Queued"))
        session.commit()

    submit_application(app_id, req.cv, req.latex_template)
    return {"application_id": app_id, "status": "queued"}


@app.get("/applications/{app_id}")
def get_application(app_id: str):
    with get_session() as session:
        app = session.get(Application, app_id)
        if app is None:
            raise HTTPException(404, "Application not found")
        return app.model_dump()


@app.get("/applications/{app_id}/stream")
async def stream_application(app_id: str):
    """SSE stream of status updates. Closes when status == done or failed."""

    async def event_generator():
        last_status = None
        last_progress = None
        while True:
            with get_session() as session:
                app = session.get(Application, app_id)
                if app is None:
                    yield {"event": "error", "data": json.dumps({"error": "Application not found"})}
                    return

                if app.status != last_status or app.progress_message != last_progress:
                    yield {
                        "event": "update",
                        "data": json.dumps({
                            "status": app.status,
                            "progress_message": app.progress_message,
                            "error": app.error,
                        }),
                    }
                    last_status = app.status
                    last_progress = app.progress_message

                if app.status in ("done", "failed"):
                    yield {
                        "event": "complete",
                        "data": json.dumps({
                            "status": app.status,
                            "cover_subject": app.cover_subject,
                            "pdf_path": app.pdf_path,
                        }),
                    }
                    return

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@app.get("/applications/{app_id}/pdf")
def get_application_pdf(app_id: str):
    with get_session() as session:
        app = session.get(Application, app_id)
        if app is None or not app.pdf_path or not os.path.exists(app.pdf_path):
            raise HTTPException(404, "PDF not available")
        return FileResponse(app.pdf_path, media_type="application/pdf", filename=f"{app_id}.pdf")
