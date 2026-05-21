import hashlib

from crewai import Agent, Crew, Process, Task

from services.cache import cache_get, cache_set
from services.llms import main_llm
from services.models import JobAnalysis


def _agent() -> Agent:
    return Agent(
        role="Job Requirements Analyzer",
        goal="Extract precise job requirements and score how well a candidate's CV matches the role",
        backstory=(
            "You are a senior HR consultant. You read job pages alongside a candidate's CV "
            "and honestly score the fit."
        ),
        llm=main_llm(),
        verbose=False,
    )


def screen_job(job_url: str, job_text: str, cv: str, role: str) -> JobAnalysis:
    """Run the screening LLM (or hit cache) and return a JobAnalysis."""
    cv_hash = hashlib.md5(cv.encode()).hexdigest()[:8]
    analysis_key = f"{job_url}|{role}|{cv_hash}"

    cached = cache_get("analysis", analysis_key)
    if cached:
        return JobAnalysis(**cached)

    agent = _agent()
    task = Task(
        description=f"""
        The user searched for the role: "{role}"

        Analyze this job page alongside the candidate's CV.

        1. is_active: True if the job is still open (look for Apply button, no "closed"/"expired"/"no longer accepting" signals).

        2. actual_title: the exact job title as advertised on the page (e.g. "Senior DevOps Engineer", "DevOps Intern").

        3. role_match: True if the actual job title is in the same role family as what the user searched.
           Rule of thumb:
           - If the user DID NOT specify a seniority (e.g. "devops", "data scientist", "frontend"),
             accept ANY seniority for that role family — intern, junior, mid, senior, staff all qualify.
             Example: user="devops" + page="Senior DevOps Engineer" → True
             Example: user="devops" + page="DevOps Intern"          → True
           - If the user DID specify a seniority (e.g. "devops intern", "senior backend"),
             then the seniority must roughly match. Intern ≠ Senior, Junior ≠ Staff.
             Example: user="devops intern" + page="Senior DevOps Engineer" → False
             Example: user="devops intern" + page="DevOps Intern"          → True
           - Different role family is always False, regardless of seniority.
             Example: user="data scientist" + page="data engineer" → False
             Example: user="devops" + page="maths instructor"      → False

        4. match_score: integer 0-100. How well does the candidate's CV match the job requirements?
           - 80-100: strong match on most must-haves
           - 60-79:  decent match, some gaps
           - 40-59:  partial match, significant gaps
           - 0-39:   poor match

        5. Extract must_have, nice_to_have, keywords, tone as usual.

        Job page:
        {job_text}

        Candidate CV:
        {cv}
        """,
        expected_output="Job analysis with is_active bool, role_match bool, actual_title, match_score, and requirements.",
        output_pydantic=JobAnalysis,
        agent=agent,
    )

    Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    result = task.output.pydantic
    cache_set("analysis", analysis_key, result.model_dump())
    return result
