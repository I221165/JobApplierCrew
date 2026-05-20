import crewai.llms.cache as _crewai_cache
_crewai_cache.mark_cache_breakpoint = lambda msg: msg  # bug in crewai 1.14: only Anthropic strips this

from crewai import Agent, Task, Crew, Process, LLM
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

llm = LLM(model="groq/llama-3.3-70b-versatile")

# ── Pydantic output models ────────────────────────────────────────────────────
class JobAnalysis(BaseModel):
    must_have: list[str]
    nice_to_have: list[str]
    keywords: list[str]
    tone: str

class TailoredCV(BaseModel):
    full_cv: str
    highlights: list[str]

class CoverLetter(BaseModel):
    subject_line: str
    body: str

# ── Load CV ───────────────────────────────────────────────────────────────────
with open("my_cv.txt", "r") as f:
    my_cv = f.read()

# ── Get job description from terminal ─────────────────────────────────────────
print("\n" + "="*60)
print("JOB APPLICATION CREW")
print("="*60)
print("Paste the job description below.")
print("When done, type END on a new line and press Enter.\n")

lines = []
while True:
    line = input()
    if line.strip().upper() == "END":
        break
    lines.append(line)

job_description = "\n".join(lines)

if not job_description.strip():
    print("No job description provided. Exiting.")
    exit()

print("\nGot it. Starting crew...\n")

# ── Agents ────────────────────────────────────────────────────────────────────
analyzer = Agent(
    role="Job Requirements Analyzer",
    goal="Extract key skills, requirements, and keywords from job descriptions",
    backstory="You are an expert HR consultant who understands exactly what recruiters look for.",
    llm=llm,
    verbose=True,
)

cv_tailor = Agent(
    role="CV Tailoring Specialist",
    goal="Rewrite and tailor CVs to match job requirements without lying",
    backstory="You are a professional CV writer who knows how to highlight relevant experience for specific roles.",
    llm=llm,
    verbose=True,
)

cover_letter_writer = Agent(
    role="Cover Letter Writer",
    goal="Write compelling, personalized cover letters",
    backstory="You write cover letters that get callbacks. You match the candidate's experience to the job perfectly.",
    llm=llm,
    verbose=True,
)

# ── Tasks ─────────────────────────────────────────────────────────────────────
analyze_job = Task(
    description=f"""
    Analyze this job description and extract:
    1. Must-have skills and requirements
    2. Nice-to-have skills
    3. Key keywords to include in the CV
    4. Company culture/tone hints

    Job Description:
    {job_description}
    """,
    expected_output="A structured breakdown of job requirements, must-have skills, keywords, and tone.",
    output_pydantic=JobAnalysis,
    agent=analyzer,
)

tailor_cv = Task(
    description=f"""
    Using the job analysis, rewrite the candidate's CV to best match the role.
    - Reorder and reword bullet points to highlight relevant experience
    - Naturally include the extracted keywords
    - Do NOT invent experience that isn't there
    - Keep it truthful but optimized
    - Also list 3-5 key highlights that make this candidate strong for the role

    Original CV:
    {my_cv}
    """,
    expected_output="A fully tailored CV and a list of key highlights.",
    output_pydantic=TailoredCV,
    agent=cv_tailor,
)

write_cover_letter = Task(
    description=f"""
    Write a professional, personalized cover letter for this job application.
    - Provide a strong subject line for the email
    - 3-4 paragraphs in the body
    - Match the company tone from the job analysis
    - Reference specific requirements from the job description
    - Show genuine enthusiasm without being cringe

    Base it on the tailored CV and job analysis above.
    """,
    expected_output="A subject line and complete cover letter body, ready to send.",
    output_pydantic=CoverLetter,
    agent=cover_letter_writer,
)

# ── Crew ──────────────────────────────────────────────────────────────────────
crew = Crew(
    agents=[analyzer, cv_tailor, cover_letter_writer],
    tasks=[analyze_job, tailor_cv, write_cover_letter],
    process=Process.sequential,
    verbose=True,
)

# ── Run ───────────────────────────────────────────────────────────────────────
result = crew.kickoff()

# ── Extract structured outputs from each task ─────────────────────────────────
job_analysis: JobAnalysis = analyze_job.output.pydantic
tailored: TailoredCV = tailor_cv.output.pydantic
cover: CoverLetter = write_cover_letter.output.pydantic

# ── Save tailored CV ──────────────────────────────────────────────────────────
with open("tailored_cv.txt", "w", encoding="utf-8") as f:
    f.write(tailored.full_cv)

# ── Save cover letter ─────────────────────────────────────────────────────────
with open("cover_letter.txt", "w", encoding="utf-8") as f:
    f.write(f"Subject: {cover.subject_line}\n\n")
    f.write(cover.body)

# ── Print summary ─────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("DONE")
print("="*60)

print("\nJob Requirements:")
print(f"  Must-have : {', '.join(job_analysis.must_have)}")
print(f"  Nice-have : {', '.join(job_analysis.nice_to_have)}")
print(f"  Tone      : {job_analysis.tone}")

print("\nYour Key Highlights for this Role:")
for h in tailored.highlights:
    print(f"  - {h}")

print(f"\nEmail Subject: {cover.subject_line}")

print("\nFiles saved:")
print("  tailored_cv.txt")
print("  cover_letter.txt")
