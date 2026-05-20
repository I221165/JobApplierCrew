from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv

load_dotenv()

MODEL = "groq/llama-3.3-70b-versatile"

# ── Load your CV ──────────────────────────────────────────────────────────────
with open("my_cv.txt", "r") as f:
    my_cv = f.read()

# ── Input ─────────────────────────────────────────────────────────────────────
job_description = """
DevOps Engineer """

# ── Agents ────────────────────────────────────────────────────────────────────
analyzer = Agent(
    role="Job Requirements Analyzer",
    goal="Extract key skills, requirements, and keywords from job descriptions",
    backstory="You are an expert HR consultant who understands exactly what recruiters look for.",
    llm=MODEL,
    verbose=True,
)

cv_tailor = Agent(
    role="CV Tailoring Specialist",
    goal="Rewrite and tailor CVs to match job requirements without lying",
    backstory="You are a professional CV writer who knows how to highlight relevant experience for specific roles.",
    llm=MODEL,
    verbose=True,
)

cover_letter_writer = Agent(
    role="Cover Letter Writer",
    goal="Write compelling, personalized cover letters",
    backstory="You write cover letters that get callbacks. You match the candidate's experience to the job perfectly.",
    llm=MODEL,
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
    agent=analyzer,
)

tailor_cv = Task(
    description=f"""
    Using the job analysis, rewrite the candidate's CV to best match the role.
    - Reorder and reword bullet points to highlight relevant experience
    - Naturally include the extracted keywords
    - Do NOT invent experience that isn't there
    - Keep it truthful but optimized

    Original CV:
    {my_cv}
    """,
    expected_output="A fully tailored CV in clean text format ready to copy-paste.",
    agent=cv_tailor,
)

write_cover_letter = Task(
    description=f"""
    Write a professional, personalized cover letter for this job application.
    - 3-4 paragraphs
    - Match the company tone from the job analysis
    - Reference specific requirements from the job description
    - Show genuine enthusiasm without being cringe

    Base it on the tailored CV and job analysis above.
    """,
    expected_output="A complete cover letter in plain text, ready to send.",
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

print("\n" + "="*60)
print("FINAL OUTPUT")
print("="*60)
print(result)

# Save outputs to files
with open("tailored_cv.txt", "w") as f:
    f.write(str(result))

print("\nSaved to tailored_cv.txt")
