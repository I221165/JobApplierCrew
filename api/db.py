from datetime import datetime
from typing import Optional

from sqlmodel import Field, Session, SQLModel, create_engine

DB_URL = "sqlite:///job_applier.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})


class Job(SQLModel, table=True):
    id: str = Field(primary_key=True)            # md5(url) — deterministic, matches scrape cache key
    url: str
    title: str
    snippet: str = ""
    role_searched: str                            # what the user typed
    location: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Populated after screening (nullable until then)
    actual_title: Optional[str] = None
    is_active: Optional[bool] = None
    role_match: Optional[bool] = None
    match_score: Optional[int] = None
    must_have_json: Optional[str] = None          # JSON list
    nice_to_have_json: Optional[str] = None
    keywords_json: Optional[str] = None
    tone: Optional[str] = None


class Application(SQLModel, table=True):
    id: str = Field(primary_key=True)             # uuid4
    job_id: str = Field(foreign_key="job.id")
    status: str = "queued"                        # queued | gap_analysis | tailoring | cover_letter | latex | done | failed
    progress_message: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Outputs (filled as crew progresses)
    gap_analysis_json: Optional[str] = None
    tailored_cv: Optional[str] = None
    cover_subject: Optional[str] = None
    cover_body: Optional[str] = None
    latex_code: Optional[str] = None
    pdf_path: Optional[str] = None                # path on disk relative to project root


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
