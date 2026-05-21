import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from sqlmodel import select

from api.db import Application, Job, get_session
from services.crew import build_application
from services.latex import compile_to_pdf, fill_latex_resume
from services.models import JobAnalysis

# Single worker thread so we don't accidentally hit rate limits with parallel crews.
_executor = ThreadPoolExecutor(max_workers=1)


def _update(app_id: str, **fields) -> None:
    """Patch an Application row by id."""
    with get_session() as session:
        app = session.get(Application, app_id)
        if app is None:
            return
        for k, v in fields.items():
            setattr(app, k, v)
        app.updated_at = datetime.utcnow()
        session.add(app)
        session.commit()


def _job_to_analysis(job: Job) -> JobAnalysis:
    """Reconstruct a JobAnalysis from a screened Job row."""
    return JobAnalysis(
        is_active=bool(job.is_active),
        role_match=bool(job.role_match),
        actual_title=job.actual_title or "",
        match_score=int(job.match_score or 0),
        must_have=json.loads(job.must_have_json or "[]"),
        nice_to_have=json.loads(job.nice_to_have_json or "[]"),
        keywords=json.loads(job.keywords_json or "[]"),
        tone=job.tone or "",
    )


def _run_application(app_id: str, cv: str, latex_template: str | None) -> None:
    """Runs in a background thread. Updates the Application row at each phase."""
    try:
        with get_session() as session:
            app = session.get(Application, app_id)
            if app is None:
                return
            job = session.get(Job, app.job_id)
            if job is None or job.match_score is None:
                _update(app_id, status="failed", error="job not screened yet")
                return
            job_analysis = _job_to_analysis(job)

        # Phase 1: gap analysis + tailoring + cover letter (one crew, multiple tasks)
        _update(app_id, status="gap_analysis", progress_message="Running gap analysis, CV tailoring, and cover letter...")
        gap, tailored, cover = build_application(cv, job_analysis)
        _update(
            app_id,
            status="cover_letter",
            progress_message="Cover letter ready",
            gap_analysis_json=gap.model_dump_json(),
            tailored_cv=tailored.full_cv,
            cover_subject=cover.subject_line,
            cover_body=cover.body,
        )

        # Phase 2: LaTeX (optional)
        if latex_template and any(
            line.strip() and not line.strip().startswith("%") for line in latex_template.splitlines()
        ):
            _update(app_id, status="latex", progress_message="Filling LaTeX template and compiling PDF...")
            latex = fill_latex_resume(tailored, latex_template)
            pdf_bytes, pdf_status = compile_to_pdf(latex.latex_code)
            pdf_path = None
            if pdf_bytes:
                Path("generated").mkdir(exist_ok=True)
                pdf_path = f"generated/{app_id}.pdf"
                Path(pdf_path).write_bytes(pdf_bytes)
            _update(
                app_id,
                latex_code=latex.latex_code,
                pdf_path=pdf_path,
                progress_message=pdf_status,
            )

        _update(app_id, status="done", progress_message="Application ready")

    except Exception as e:
        _update(app_id, status="failed", error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


def submit_application(app_id: str, cv: str, latex_template: str | None) -> None:
    """Queue an application run on the background worker."""
    _executor.submit(_run_application, app_id, cv, latex_template)
