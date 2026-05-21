import os

os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.getenv("PLAYWRIGHT_BROWSERS_PATH", r"F:\playwright-browsers"),
)
os.environ["BROWSER_USE_HEADLESS"] = "false"

import asyncio

from dotenv import load_dotenv

load_dotenv()

# Importing services applies the crewai cache_breakpoint patch via services/__init__.py
from services.analysis import screen_job
from services.browser import fill_application_form
from services.crew import build_application
from services.latex import compile_to_pdf, fill_latex_resume
from services.scrape import scrape_job
from services.search import search_jobs

MATCH_THRESHOLD = 60
MAX_JOBS = 5

# ── Load CV ───────────────────────────────────────────────────────────────────
with open("my_cv.txt", "r", encoding="utf-8") as f:
    my_cv = f.read()

# ── Load LaTeX template (optional — comments-only file disables PDF step) ─────
try:
    with open("resume_template.tex", "r", encoding="utf-8") as f:
        latex_template = f.read()
    has_template = any(
        line.strip() and not line.strip().startswith("%") for line in latex_template.splitlines()
    )
except FileNotFoundError:
    latex_template = ""
    has_template = False

# ── Terminal input ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("JOB APPLICATION CREW")
print("=" * 60)
role = input("Job role (e.g. DevOps Engineer): ").strip()
location = input("Location (e.g. Islamabad, Pakistan): ").strip()
print(f"\nSearching Google for '{role}' jobs in '{location}'...\n")

# ── Phase 1: Search ───────────────────────────────────────────────────────────
listings = search_jobs(role, location, max_jobs=MAX_JOBS)
if not listings:
    print("No results found. Try a different role or location.")
    exit()

print("=" * 60)
print("JOBS FOUND")
print("=" * 60)
for i, job in enumerate(listings, 1):
    print(f"\n[{i}] {job['title']}")
    print(f"    {job['url']}")
    print(f"    {job['snippet']}")

# ── Phase 2: Screen + HITL ────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SCREENING JOBS")
print("=" * 60)

chosen = None
job_analysis = None

for job in listings:
    print(f"\n→ Checking: {job['title']}")
    job_text = scrape_job(job["url"])
    result = screen_job(job["url"], job_text, my_cv, role)

    print(f"  Actual title: {result.actual_title}")

    if not result.is_active:
        print("  ✗ Closed/expired — skipping")
        continue
    if not result.role_match:
        print(f"  ✗ Role mismatch (you wanted '{role}', this is '{result.actual_title}') — skipping")
        continue
    print(f"  ✓ Active  |  Role matches  |  Match score: {result.match_score}%")
    if result.match_score < MATCH_THRESHOLD:
        print(f"  ✗ Below {MATCH_THRESHOLD}% threshold — skipping")
        continue

    # HITL
    print(f"\n{'=' * 60}")
    print(f"MATCH FOUND — {result.match_score}%")
    print(f"{'=' * 60}")
    print(f"Title : {job['title']}")
    print(f"URL   : {job['url']}")
    print("\nMust-have requirements:")
    for req in result.must_have:
        print(f"  • {req}")
    if result.nice_to_have:
        print("\nNice-to-have:")
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
    break

if not chosen:
    print("\nNo jobs passed screening. Try a different role or location.")
    exit()

# ── Phase 3: Application crew ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("RUNNING APPLICATION CREW")
print("=" * 60)
gap_analysis, tailored, cover = build_application(my_cv, job_analysis)

# ── Phase 3.5: LaTeX resume ───────────────────────────────────────────────────
pdf_status = "skipped (no template provided)"
latex_resume = None
if has_template:
    latex_resume = fill_latex_resume(tailored, latex_template)

# ── Save files ────────────────────────────────────────────────────────────────
with open("tailored_cv.txt", "w", encoding="utf-8") as f:
    f.write(tailored.full_cv)

with open("cover_letter.txt", "w", encoding="utf-8") as f:
    f.write(f"Subject: {cover.subject_line}\n\n")
    f.write(cover.body)

if latex_resume:
    with open("tailored_cv.tex", "w", encoding="utf-8") as f:
        f.write(latex_resume.latex_code)
    print("\nCompiling LaTeX to PDF via cloud API...")
    pdf_bytes, pdf_status = compile_to_pdf(latex_resume.latex_code)
    if pdf_bytes:
        with open("tailored_cv.pdf", "wb") as f:
            f.write(pdf_bytes)

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("APPLICATION READY")
print("=" * 60)
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
    print("\nGaps:")
    for g in gap_analysis.gaps:
        print(f"  ✗ {g}")

print(f"\nEmail Subject: {cover.subject_line}")
print("Files saved: tailored_cv.txt  |  cover_letter.txt")
print(f"PDF resume  : {pdf_status}")

# ── Phase 4: Browser autofill ─────────────────────────────────────────────────
print("\n" + "=" * 60)
print("BROWSER AGENT — FILLING APPLICATION FORM")
print("=" * 60)
print("Opening job page and filling in your details...")
print("Will STOP before submitting — you review and submit manually.\n")

browser_result = asyncio.run(fill_application_form(chosen["url"], cover.body))
print(browser_result)
print("\nForm is ready in the browser. Review and submit manually when satisfied.")
