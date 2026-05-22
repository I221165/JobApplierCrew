"""Background scheduler: runs saved searches once per 24h, creates notifications for new high-match jobs."""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import select

from api.db import Job, Notification, SavedSearch, get_session
from services.analysis import screen_job
from services.scrape import scrape_job
from services.search import search_jobs

logger = logging.getLogger("scheduler")

scheduler = BackgroundScheduler()


def _ensure_job_row(session, listing: dict, role: str, location: str, analysis) -> str:
    """Insert/update a Job row from a listing dict + JobAnalysis. Returns job_id."""
    job_id = hashlib.md5(listing["url"].encode()).hexdigest()[:16]
    job = session.get(Job, job_id)
    if job is None:
        job = Job(
            id=job_id,
            url=listing["url"],
            title=listing["title"],
            snippet=listing["snippet"],
            role_searched=role,
            location=location,
        )
    job.actual_title = analysis.actual_title
    job.is_active = analysis.is_active
    job.role_match = analysis.role_match
    job.match_score = analysis.match_score
    job.must_have_json = json.dumps(analysis.must_have)
    job.nice_to_have_json = json.dumps(analysis.nice_to_have)
    job.keywords_json = json.dumps(analysis.keywords)
    job.tone = analysis.tone
    session.add(job)
    return job_id


def _run_one_saved_search(search: SavedSearch) -> str:
    """Run a single saved search end-to-end. Returns a status string."""
    try:
        listings = search_jobs(search.role, search.location, search.max_jobs)
        notify_count = 0

        for listing in listings:
            try:
                page_text = scrape_job(listing["url"])
                analysis = screen_job(listing["url"], page_text, search.cv_snapshot, search.role)

                with get_session() as session:
                    job_id = _ensure_job_row(session, listing, search.role, search.location, analysis)

                    qualifies = (
                        analysis.is_active
                        and analysis.role_match
                        and analysis.match_score >= search.min_score
                    )
                    if not qualifies:
                        session.commit()
                        continue

                    # Avoid duplicate notifications for the same (search, job) pair
                    existing = session.exec(
                        select(Notification).where(
                            Notification.saved_search_id == search.id,
                            Notification.job_id == job_id,
                        )
                    ).first()
                    if existing is None:
                        session.add(Notification(
                            id=uuid.uuid4().hex,
                            saved_search_id=search.id,
                            job_id=job_id,
                            match_score=analysis.match_score,
                        ))
                        notify_count += 1
                    session.commit()
            except Exception as e:
                logger.warning(f"failed listing {listing.get('url')}: {e}")

        return f"ok — {notify_count} new notification(s) from {len(listings)} listing(s)"
    except Exception as e:
        return f"failed: {type(e).__name__}: {e}"


def tick():
    """Called hourly by the scheduler. Finds saved searches due to run and runs them."""
    with get_session() as session:
        searches = session.exec(select(SavedSearch).where(SavedSearch.enabled == True)).all()  # noqa: E712
        due = [
            s for s in searches
            if s.last_run_at is None or datetime.utcnow() - s.last_run_at >= timedelta(hours=24)
        ]

    if not due:
        logger.info("scheduler tick: no searches due")
        return

    logger.info(f"scheduler tick: running {len(due)} due searches")
    for search in due:
        status = _run_one_saved_search(search)
        with get_session() as session:
            s = session.get(SavedSearch, search.id)
            if s:
                s.last_run_at = datetime.utcnow()
                s.last_run_status = status
                session.add(s)
                session.commit()
        logger.info(f"  {search.id} ({search.role} / {search.location}): {status}")


def start_scheduler() -> None:
    """Called once on app startup. Ticks hourly and runs `tick()`."""
    if scheduler.running:
        return
    scheduler.add_job(tick, "interval", hours=1, id="tick", replace_existing=True, next_run_time=datetime.utcnow() + timedelta(seconds=10))
    scheduler.start()
    logger.info("scheduler started — ticks every hour")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
