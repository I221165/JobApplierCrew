from pydantic import BaseModel


class JobAnalysis(BaseModel):
    is_active: bool
    role_match: bool
    actual_title: str
    match_score: int
    must_have: list[str]
    nice_to_have: list[str]
    keywords: list[str]
    tone: str


class RequirementMatch(BaseModel):
    requirement: str
    matched: bool
    candidate_evidence: str
    reframe_suggestion: str


class GapAnalysis(BaseModel):
    strong_matches: list[RequirementMatch]
    weak_matches: list[RequirementMatch]
    gaps: list[str]
    cv_restructure_order: list[str]


class TailoredCV(BaseModel):
    full_cv: str
    highlights: list[str]


class CoverLetter(BaseModel):
    subject_line: str
    body: str


class LatexResume(BaseModel):
    latex_code: str
