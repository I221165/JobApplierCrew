import asyncio
import hashlib
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

load_dotenv()

from api.db import Application, Job, Notification, SavedSearch, get_session, init_db
from api.scheduler import start_scheduler, stop_scheduler
from api.tasks import submit_application
from services.analysis import screen_job
from services.scrape import scrape_job
from services.search import search_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


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


class SavedSearchRequest(BaseModel):
    role: str
    location: str
    cv: str
    max_jobs: int = 5
    min_score: int = 60


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "job-applier"}


@app.post("/cv/parse")
async def parse_cv(file: UploadFile = File(...)):
    """Accept a PDF (or plain text) upload, return extracted text. No persistence — the frontend stores it in localStorage."""
    name = (file.filename or "").lower()
    raw = await file.read()
    if name.endswith(".pdf"):
        import io
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(raw))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
            if not text:
                raise HTTPException(422, "Could not extract text from this PDF (it may be scanned/image-only).")
            return {"text": text, "pages": len(reader.pages)}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Failed to parse PDF: {e}")
    if name.endswith(".txt") or file.content_type == "text/plain":
        try:
            return {"text": raw.decode("utf-8"), "pages": 1}
        except UnicodeDecodeError:
            raise HTTPException(400, "Could not decode text file as UTF-8.")
    raise HTTPException(415, "Unsupported file type. Upload a .pdf or .txt file.")


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


@app.post("/searches")
def create_saved_search(req: SavedSearchRequest):
    sid = uuid.uuid4().hex
    with get_session() as session:
        session.add(SavedSearch(
            id=sid,
            role=req.role,
            location=req.location,
            max_jobs=req.max_jobs,
            min_score=req.min_score,
            cv_snapshot=req.cv,
        ))
        session.commit()
    return {"id": sid}


@app.get("/searches")
def list_saved_searches():
    with get_session() as session:
        rows = session.exec(select(SavedSearch).order_by(SavedSearch.created_at.desc())).all()
        # exclude cv_snapshot from list view (large)
        return [
            {k: v for k, v in r.model_dump().items() if k != "cv_snapshot"}
            for r in rows
        ]


@app.delete("/searches/{search_id}")
def delete_saved_search(search_id: str):
    with get_session() as session:
        row = session.get(SavedSearch, search_id)
        if row is None:
            raise HTTPException(404, "Saved search not found")
        session.delete(row)
        session.commit()
    return {"status": "deleted"}


@app.post("/searches/{search_id}/run")
def run_saved_search_now(search_id: str):
    """Trigger one saved search immediately (instead of waiting for the scheduler)."""
    from api.scheduler import _run_one_saved_search
    with get_session() as session:
        s = session.get(SavedSearch, search_id)
        if s is None:
            raise HTTPException(404, "Saved search not found")
        status = _run_one_saved_search(s)
        s.last_run_at = datetime.utcnow()
        s.last_run_status = status
        session.add(s)
        session.commit()
    return {"status": status}


@app.get("/notifications")
def list_notifications(unread_only: bool = False):
    """Notifications joined with their job details for direct display."""
    with get_session() as session:
        stmt = select(Notification).order_by(Notification.created_at.desc())
        if unread_only:
            stmt = stmt.where(Notification.read == False)  # noqa: E712
        notifs = session.exec(stmt).all()
        out = []
        for n in notifs:
            job = session.get(Job, n.job_id)
            out.append({
                **n.model_dump(),
                "job": job.model_dump() if job else None,
            })
        return out


@app.post("/notifications/{notif_id}/read")
def mark_notification_read(notif_id: str):
    with get_session() as session:
        n = session.get(Notification, notif_id)
        if n is None:
            raise HTTPException(404, "Notification not found")
        n.read = True
        session.add(n)
        session.commit()
    return {"status": "ok"}


@app.get("/applications/{app_id}/pdf")
def get_application_pdf(app_id: str):
    with get_session() as session:
        app = session.get(Application, app_id)
        if app is None or not app.pdf_path or not os.path.exists(app.pdf_path):
            raise HTTPException(404, "PDF not available")
        return FileResponse(app.pdf_path, media_type="application/pdf", filename=f"{app_id}.pdf")
