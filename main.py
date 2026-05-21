import os
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.getenv("PLAYWRIGHT_BROWSERS_PATH", r"F:\playwright-browsers"))
os.environ["BROWSER_USE_HEADLESS"] = "false"  # force visible browser window

MATCH_THRESHOLD = 60   # skip jobs below this score
MAX_JOBS        = 5    # how many listings to pull from Google

import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg  # bug in crewai 1.14: only Anthropic strips this

import asyncio
from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime, timedelta

load_dotenv()

llm = LLM(model="groq/llama-3.3-70b-versatile")
search_tool = SerperDevTool()
scrape_tool = ScrapeWebsiteTool()

# ── Pydantic models ───────────────────────────────────────────────────────────
class JobAnalysis(BaseModel):
    is_active: bool
    role_match: bool          # does the actual job match the role the user searched for?
    actual_title: str         # what the job page actually advertises (e.g. "Senior DevOps Engineer")
    match_score: int          # 0-100, LLM estimates fit from CV vs requirements
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
    latex_code: str          # complete, compilable LaTeX with candidate's tailored data filled in

# ── Load CV ───────────────────────────────────────────────────────────────────
with open("my_cv.txt", "r", encoding="utf-8") as f:
    my_cv = f.read()

# ── Load LaTeX template (optional — empty file skips the PDF step) ────────────
try:
    with open("resume_template.tex", "r", encoding="utf-8") as f:
        latex_template = f.read()
    # treat header-comment-only file as "no template"
    has_template = any(line.strip() and not line.strip().startswith("%") for line in latex_template.splitlines())
except FileNotFoundError:
    latex_template = ""
    has_template = False

# ── Terminal input ────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("JOB APPLICATION CREW")
print("="*60)
role = input("Job role (e.g. DevOps Engineer): ").strip()
location = input("Location (e.g. Islamabad, Pakistan): ").strip()
print(f"\nSearching Google for '{role}' jobs in '{location}'...\n")

# ── Phase 1: Search ───────────────────────────────────────────────────────────
cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
raw_results = search_tool.run(
    search_query=f'{role} job {location} site:rozee.pk OR site:indeed.com.pk OR site:linkedin.com after:{cutoff}'
)
organic = raw_results.get("organic", []) if isinstance(raw_results, dict) else []

def is_direct_listing(url: str) -> bool:
    direct = ["/jobs/view/", "/job/detail/", "/viewjob", "/job/view/"]
    search = ["/jsearch/", "jobs?q=", "jobs?l=", "/jobs/search"]
    return any(d in url for d in direct) and not any(s in url for s in search)

all_results = [
    {"title": i.get("title",""), "url": i.get("link",""), "snippet": i.get("snippet","")}
    for i in organic
]
direct = [r for r in all_results if is_direct_listing(r["url"])]
others = [r for r in all_results if not is_direct_listing(r["url"])]
# prefer direct listings, then top up with the rest until we hit MAX_JOBS
listings = (direct + others)[:MAX_JOBS]

if not listings:
    print("No results found. Try a different role or location.")
    exit()

print("="*60)
print("JOBS FOUND")
print("="*60)
for i, job in enumerate(listings, 1):
    print(f"\n[{i}] {job['title']}")
    print(f"    {job['url']}")
    print(f"    {job['snippet']}")

# ── Agents ────────────────────────────────────────────────────────────────────
analyzer = Agent(
    role="Job Requirements Analyzer",
    goal="Extract precise job requirements and score how well a candidate's CV matches the role",
    backstory="You are a senior HR consultant. You read job pages alongside a candidate's CV and honestly score the fit.",
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

latex_filler = Agent(
    role="LaTeX Resume Builder",
    goal="Fill a LaTeX resume template with the candidate's tailored CV content, keeping the template structure intact and producing valid LaTeX that compiles cleanly",
    backstory=(
        "You are an expert in LaTeX and ATS-friendly resume formatting. You take a LaTeX template and the candidate's "
        "tailored CV content, then output a complete .tex document where the candidate's real information replaces the "
        "template's placeholder data — without breaking any LaTeX syntax, packages, or styling. You escape special LaTeX "
        "characters (&, %, $, #, _, {, }, \\, ~, ^) and never invent content beyond what the tailored CV contains."
    ),
    llm=llm,
    verbose=True,
)

# ── Phase 2: Screen jobs ──────────────────────────────────────────────────────
print("\n" + "="*60)
print("SCREENING JOBS")
print("="*60)

chosen = None
job_analysis = None
chosen_job_text = None

for job in listings:
    print(f"\n→ Checking: {job['title']}")

    job_page_content = scrape_tool.run(website_url=job['url'])
    job_text = str(job_page_content)[:5000]

    screen_task = Task(
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
        {my_cv}
        """,
        expected_output="Job analysis with is_active bool, role_match bool, actual_title, match_score, and requirements.",
        output_pydantic=JobAnalysis,
        agent=analyzer,
    )

    Crew(
        agents=[analyzer],
        tasks=[screen_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()

    result = screen_task.output.pydantic

    print(f"  Actual title: {result.actual_title}")

    if not result.is_active:
        print(f"  ✗ Closed/expired — skipping")
        continue

    if not result.role_match:
        print(f"  ✗ Role mismatch (you wanted '{role}', this is '{result.actual_title}') — skipping")
        continue

    print(f"  ✓ Active  |  Role matches  |  Match score: {result.match_score}%")

    if result.match_score < MATCH_THRESHOLD:
        print(f"  ✗ Below {MATCH_THRESHOLD}% threshold — skipping")
        continue

    # ── HITL: show details and ask user ──────────────────────────────────
    print(f"\n{'='*60}")
    print(f"MATCH FOUND — {result.match_score}%")
    print(f"{'='*60}")
    print(f"Title : {job['title']}")
    print(f"URL   : {job['url']}")
    print(f"\nMust-have requirements:")
    for req in result.must_have:
        print(f"  • {req}")
    if result.nice_to_have:
        print(f"\nNice-to-have:")
        for req in result.nice_to_have:
            print(f"  • {req}")
    print(f"\nTone: {result.tone}")

    decision = input("\nApply to this job? (y = yes / n = skip / q = quit): ").strip().lower()
    if decision == "q":
        print("Exiting.")
        exit()
    if decision != "y":
        print("Skipping — checking next job...")
        continue

    chosen = job
    job_analysis = result
    chosen_job_text = job_text
    break

if not chosen:
    print("\nNo jobs passed screening. Try a different role or location.")
    exit()

# ── Phase 3: Full application crew ────────────────────────────────────────────
print("\n" + "="*60)
print("RUNNING APPLICATION CREW")
print("="*60)

map_gaps = Task(
    description=f"""
    Job requirements for this role:
    - Must-have: {', '.join(job_analysis.must_have)}
    - Nice-to-have: {', '.join(job_analysis.nice_to_have)}
    - Tone: {job_analysis.tone}

    Compare each must-have requirement against the candidate's CV.

    For each requirement:
    - Direct evidence in CV → matched=True, quote the evidence, suggest exact wording to use
    - Partial/adjacent experience → matched=False, explain what's adjacent, suggest honest reframe
    - No match at all → add to gaps list

    Also suggest the ideal section order for the CV to lead with what matters most for this job.

    Candidate CV:
    {my_cv}
    """,
    expected_output="Full gap analysis with matches, weak matches, gaps, and CV structure order.",
    output_pydantic=GapAnalysis,
    agent=gap_mapper,
)

tailor_cv = Task(
    description=f"""
    Using the job requirements AND the gap analysis from the previous task, rewrite the candidate's CV.

    Rules:
    - Lead with sections that matter most (follow cv_restructure_order)
    - Strong matches: use the reframe_suggestion wording to highlight
    - Weak matches: apply reframe_suggestion to present adjacent experience honestly
    - Gaps: do NOT invent experience — skip or acknowledge briefly
    - Embed keywords naturally throughout
    - Never fabricate

    Original CV:
    {my_cv}
    """,
    expected_output="Dynamically restructured, tailored CV and 3-5 key highlights.",
    output_pydantic=TailoredCV,
    agent=cv_tailor,
)

write_cover_letter = Task(
    description="""
    Write a cover letter addressing the must-have requirements from the job analysis.
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

Crew(
    agents=[gap_mapper, cv_tailor, cover_letter_writer],
    tasks=[map_gaps, tailor_cv, write_cover_letter],
    process=Process.sequential,
    verbose=True,
).kickoff()

gap_analysis: GapAnalysis = map_gaps.output.pydantic
tailored: TailoredCV      = tailor_cv.output.pydantic
cover: CoverLetter        = write_cover_letter.output.pydantic

# ── LaTeX fill runs in its own crew with a delay (avoid Groq TPM limit) ───────
latex_resume: LatexResume | None = None
if has_template:
    import time
    print("\nWaiting 30s for Groq TPM budget to reset before LaTeX fill...")
    time.sleep(30)

    fill_latex = Task(
        description=f"""
        Take the LaTeX template below and produce a complete, compilable .tex document
        where ALL placeholder/sample data in the template is replaced with the candidate's
        real tailored CV content.

        Strict rules:
        - Keep the template's \\documentclass, \\usepackage lines, custom commands, and styling untouched
        - Replace only the content inside sections (header, experience, education, projects, skills, etc.)
        - Escape LaTeX special characters in candidate data: & % $ # _ {{ }} \\ ~ ^
        - Do NOT invent experience — only use what's in the tailored CV below
        - Output must start with \\documentclass and end with \\end{{document}}
        - Output the FULL .tex source (not a diff, not a summary)

        Candidate contact info:
        - Name:  {os.getenv("CANDIDATE_NAME", "")}
        - Email: {os.getenv("CANDIDATE_EMAIL", "")}

        Tailored CV content to put into the template:
        {tailored.full_cv}

        LaTeX template:
        {latex_template}
        """,
        expected_output="Complete .tex source code with the candidate's tailored data filled in.",
        output_pydantic=LatexResume,
        agent=latex_filler,
    )

    Crew(
        agents=[latex_filler],
        tasks=[fill_latex],
        process=Process.sequential,
        verbose=True,
    ).kickoff()

    latex_resume = fill_latex.output.pydantic

# ── Save files ────────────────────────────────────────────────────────────────
with open("tailored_cv.txt", "w", encoding="utf-8") as f:
    f.write(tailored.full_cv)

with open("cover_letter.txt", "w", encoding="utf-8") as f:
    f.write(f"Subject: {cover.subject_line}\n\n")
    f.write(cover.body)

# ── Save .tex and compile to PDF via cloud API ────────────────────────────────
pdf_status = "skipped (no template provided)"
if latex_resume:
    with open("tailored_cv.tex", "w", encoding="utf-8") as f:
        f.write(latex_resume.latex_code)
    pdf_status = "tex saved, pdf compile not attempted"

    try:
        import requests
        print("\nCompiling LaTeX to PDF via cloud API...")
        resp = requests.post(
            "https://latex.ytotech.com/builds/sync",
            json={
                "compiler": "pdflatex",
                "resources": [{"main": True, "content": latex_resume.latex_code}],
            },
            timeout=60,
        )
        if resp.status_code == 201 and resp.headers.get("Content-Type", "").startswith("application/pdf"):
            with open("tailored_cv.pdf", "wb") as f:
                f.write(resp.content)
            pdf_status = "tailored_cv.pdf generated"
        else:
            pdf_status = f"compile failed (HTTP {resp.status_code}) — open tailored_cv.tex in Overleaf to debug"
            # save the error log if API returned one
            try:
                err = resp.json()
                with open("latex_compile_error.json", "w", encoding="utf-8") as f:
                    import json as _json
                    _json.dump(err, f, indent=2)
                pdf_status += " (see latex_compile_error.json)"
            except Exception:
                pass
    except Exception as e:
        pdf_status = f"cloud compile error: {e} — open tailored_cv.tex in Overleaf manually"

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("APPLICATION READY")
print("="*60)
print(f"\nJob   : {chosen['title']}")
print(f"URL   : {chosen['url']}")
print(f"Match : {job_analysis.match_score}%")

print(f"\nStrong matches ({len(gap_analysis.strong_matches)}):")
for m in gap_analysis.strong_matches:
    print(f"  ✓ {m.requirement}")

if gap_analysis.weak_matches:
    print(f"\nWeak matches ({len(gap_analysis.weak_matches)}) — reframed:")
    for m in gap_analysis.weak_matches:
        print(f"  ~ {m.requirement}: {m.reframe_suggestion[:80]}")

if gap_analysis.gaps:
    print(f"\nGaps:")
    for g in gap_analysis.gaps:
        print(f"  ✗ {g}")

print(f"\nEmail Subject: {cover.subject_line}")
print("Files saved: tailored_cv.txt  |  cover_letter.txt")
print(f"PDF resume  : {pdf_status}")

# ── Phase 4: Browser agent ────────────────────────────────────────────────────
print("\n" + "="*60)
print("BROWSER AGENT — FILLING APPLICATION FORM")
print("="*60)
print("Opening job page and filling in your details...")
print("Will STOP before submitting — you review and submit manually.\n")

async def fill_application(url: str, cover_body: str) -> str:
    from browser_use import Agent as BrowserAgent
    from browser_use.browser.profile import BrowserProfile
    from browser_use.llm.groq.chat import ChatGroq

    # Llama 4 Scout: vision-capable, fast, on Groq's free tier
    browser_llm = ChatGroq(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    candidate_name  = os.getenv("CANDIDATE_NAME", "")
    candidate_email = os.getenv("CANDIDATE_EMAIL", "")

    task = f"""
    Go to this job posting: {url}

    Your goal is to start the application form. Steps:
    1. Navigate to the page.
    2. Find and click the "Apply" or "Easy Apply" button.
    3. Fill in any visible fields using:
       - Name:  {candidate_name}
       - Email: {candidate_email}
       - Cover letter / message / additional info: the text below
    4. IMPORTANT: Do NOT click Submit, Apply, or Send. Stop when fields are filled.
    5. Report which fields you found and what you filled in.

    Cover letter (paste into the message/cover letter field):
    {cover_body[:800]}
    """

    profile = BrowserProfile(headless=False)
    agent = BrowserAgent(task=task, llm=browser_llm, browser_profile=profile)
    result = await agent.run()
    return str(result)

browser_result = asyncio.run(fill_application(chosen["url"], cover.body))
print(browser_result)
print("\nForm is ready in the browser. Review and submit manually when satisfied.")
