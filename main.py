import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg  # bug in crewai 1.14: only Anthropic strips this

from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

llm = LLM(model="groq/llama-3.3-70b-versatile")

search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()

# ── Pydantic models ───────────────────────────────────────────────────────────
class JobAnalysis(BaseModel):
    is_active: bool          # LLM decides from page content
    must_have: list[str]
    nice_to_have: list[str]
    keywords: list[str]
    tone: str

class RequirementMatch(BaseModel):
    requirement: str
    matched: bool
    candidate_evidence: str      # what in the CV matches, or "None"
    reframe_suggestion: str      # how to reframe/present existing experience

class GapAnalysis(BaseModel):
    strong_matches: list[RequirementMatch]
    weak_matches: list[RequirementMatch]
    gaps: list[str]              # requirements with zero match in CV
    cv_restructure_order: list[str]  # ordered sections to lead with

class TailoredCV(BaseModel):
    full_cv: str
    highlights: list[str]

class CoverLetter(BaseModel):
    subject_line: str
    body: str

# ── Load CV ───────────────────────────────────────────────────────────────────
with open("my_cv.txt", "r", encoding="utf-8") as f:
    my_cv = f.read()

# ── Terminal input ────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("JOB APPLICATION CREW")
print("="*60)
role = input("Job role (e.g. DevOps Engineer): ").strip()
location = input("Location (e.g. Islamabad, Pakistan): ").strip()
print(f"\nSearching Google for '{role}' jobs in '{location}'...\n")

# ── Phase 1: Real Google search ───────────────────────────────────────────────
from datetime import datetime, timedelta
cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

raw_results = search_tool.run(
    search_query=f"{role} job {location} site:rozee.pk OR site:indeed.com.pk OR site:linkedin.com after:{cutoff}"
)

organic = raw_results.get("organic", []) if isinstance(raw_results, dict) else []

def is_direct_listing(url: str) -> bool:
    direct = ["/jobs/view/", "/job/detail/", "/viewjob", "/job/view/"]
    search = ["/jsearch/", "jobs?q=", "jobs?l=", "/jobs/search"]
    return any(d in url for d in direct) and not any(s in url for s in search)

# Prefer direct listings, fall back to all results
listings = [
    {"title": i.get("title",""), "url": i.get("link",""), "snippet": i.get("snippet","")}
    for i in organic if is_direct_listing(i.get("link",""))
][:5]

if not listings:
    listings = [
        {"title": i.get("title",""), "url": i.get("link",""), "snippet": i.get("snippet","")}
        for i in organic[:5]
    ]

if not listings:
    print("No results found. Try a different role or location.")
    exit()

# ── Show listings ─────────────────────────────────────────────────────────────
print("="*60)
print("JOBS FOUND")
print("="*60)
for i, job in enumerate(listings, 1):
    print(f"\n[{i}] {job['title']}")
    print(f"    {job['url']}")
    print(f"    {job['snippet']}")

print(f"\n[Auto] Best match: {listings[0]['url']}")
print("\nEnter a number to pick a job, or press Enter to use the best match:")
choice = input("> ").strip()
chosen = listings[int(choice)-1] if choice.isdigit() and 1 <= int(choice) <= len(listings) else listings[0]
chosen_url = chosen["url"]
print(f"\nUsing: {chosen_url}")

# ── Phase 2: Real scrape ──────────────────────────────────────────────────────
print("Scraping job page...\n")
job_page_content = scrape_tool.run(website_url=chosen_url)
job_text = str(job_page_content)[:5000]

# ── Agents ────────────────────────────────────────────────────────────────────
analyzer = Agent(
    role="Job Requirements Analyzer",
    goal="Extract precise, actionable skills and requirements from job descriptions",
    backstory="You are a senior HR consultant. You read job descriptions and extract exactly what the employer needs.",
    llm=llm,
    verbose=True,
)

gap_mapper = Agent(
    role="Career Gap Analyst",
    goal="Map each job requirement to the candidate's actual experience and identify gaps",
    backstory=(
        "You are an expert career coach. You compare job requirements against a candidate's CV "
        "and for each requirement, you find matching evidence in the CV, suggest how to reframe it, "
        "and flag what's genuinely missing. You never invent experience."
    ),
    llm=llm,
    verbose=True,
)

cv_tailor = Agent(
    role="CV Tailoring Specialist",
    goal="Restructure the CV dynamically based on the gap analysis to maximise match with the job",
    backstory=(
        "You are a professional CV writer. Given a gap analysis that maps job requirements to a candidate's "
        "experience, you restructure the CV so the most relevant sections come first, reframe bullet points "
        "using the suggested language, and ensure every must-have requirement has a visible answer in the CV."
    ),
    llm=llm,
    verbose=True,
)

cover_letter_writer = Agent(
    role="Cover Letter Writer",
    goal="Write a targeted cover letter that directly addresses the job's must-have requirements",
    backstory="You write cover letters that get callbacks. You reference specific requirements and match them to the candidate's evidence.",
    llm=llm,
    verbose=True,
)

# ── Tasks ─────────────────────────────────────────────────────────────────────
analyze_job = Task(
    description=f"""
    Analyze this job page and extract:
    1. is_active: is this job still actively accepting applications? Read the page carefully —
       look for "closed", "expired", "no longer accepting", application deadlines that have passed,
       or any signal the role is filled. If the page looks like a live job posting, set True.
    2. Must-have skills and requirements (be specific, not generic)
    3. Nice-to-have skills
    4. Exact keywords to appear in the CV
    5. Company culture and tone

    Job page content:
    {job_text}
    """,
    expected_output="Precise job requirements, must-haves, keywords, and tone.",
    output_pydantic=JobAnalysis,
    agent=analyzer,
)

map_gaps = Task(
    description=f"""
    You have the job analysis from the previous task.
    Now compare each must-have requirement against the candidate's CV.

    For each requirement:
    - If there's direct evidence in the CV: mark matched=True, quote the evidence, suggest exact wording to use
    - If there's partial/adjacent experience: mark matched=False, explain what's adjacent, suggest how to reframe it honestly
    - If there's no match at all: add it to gaps list

    Also suggest the ideal section order for the CV to lead with what matters most for THIS job.

    Candidate CV:
    {my_cv}
    """,
    expected_output="A full gap analysis with matches, weak matches, gaps, and recommended CV structure order.",
    output_pydantic=GapAnalysis,
    agent=gap_mapper,
)

tailor_cv = Task(
    description=f"""
    Using the job analysis AND the gap analysis from previous tasks, rewrite the candidate's CV.

    Rules:
    - Lead with the sections that matter most for this role (follow cv_restructure_order)
    - For each strong match: use the reframe_suggestion wording to highlight it
    - For each weak match: apply the reframe_suggestion to present adjacent experience honestly
    - For gaps: do NOT invent experience. Skip or acknowledge briefly
    - Embed the job keywords naturally throughout
    - Keep it truthful — only reframe, never fabricate

    Original CV:
    {my_cv}
    """,
    expected_output="A dynamically restructured, tailored CV and 3-5 key highlights.",
    output_pydantic=TailoredCV,
    agent=cv_tailor,
)

write_cover_letter = Task(
    description="""
    Write a cover letter that directly addresses the must-have requirements from the job analysis.
    Use the strong matches from the gap analysis as your evidence.
    - Strong subject line
    - 3-4 paragraphs: hook → match strong requirements → address weak areas honestly → close
    - Match the company tone
    - No cringe enthusiasm
    """,
    expected_output="Subject line and complete cover letter body.",
    output_pydantic=CoverLetter,
    agent=cover_letter_writer,
)

# ── Run crew ──────────────────────────────────────────────────────────────────
print("Starting application crew...\n")
apply_crew = Crew(
    agents=[analyzer, gap_mapper, cv_tailor, cover_letter_writer],
    tasks=[analyze_job, map_gaps, tailor_cv, write_cover_letter],
    process=Process.sequential,
    verbose=True,
)

apply_crew.kickoff()

# ── Extract outputs ───────────────────────────────────────────────────────────
job_analysis: JobAnalysis   = analyze_job.output.pydantic

if not job_analysis.is_active:
    print("\n⚠️  The LLM detected this job is no longer active. Run again and pick a different listing.")
    exit()

gap_analysis: GapAnalysis   = map_gaps.output.pydantic
tailored: TailoredCV        = tailor_cv.output.pydantic
cover: CoverLetter          = write_cover_letter.output.pydantic

# ── Save files ────────────────────────────────────────────────────────────────
with open("tailored_cv.txt", "w", encoding="utf-8") as f:
    f.write(tailored.full_cv)

with open("cover_letter.txt", "w", encoding="utf-8") as f:
    f.write(f"Subject: {cover.subject_line}\n\n")
    f.write(cover.body)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("DONE")
print("="*60)

print(f"\nJob : {chosen['title']}")
print(f"URL : {chosen_url}")

print(f"\nStrong matches ({len(gap_analysis.strong_matches)}):")
for m in gap_analysis.strong_matches:
    print(f"  ✓ {m.requirement}")

if gap_analysis.weak_matches:
    print(f"\nWeak matches ({len(gap_analysis.weak_matches)}) — reframed:")
    for m in gap_analysis.weak_matches:
        print(f"  ~ {m.requirement}: {m.reframe_suggestion[:80]}")

if gap_analysis.gaps:
    print(f"\nGaps (not in your CV):")
    for g in gap_analysis.gaps:
        print(f"  ✗ {g}")

print(f"\nEmail Subject: {cover.subject_line}")
print("\nFiles saved: tailored_cv.txt  |  cover_letter.txt")
