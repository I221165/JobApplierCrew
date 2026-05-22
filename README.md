# JobApplierCrew

Multi-agent system that searches job boards, screens listings against your CV, writes a tailored CV + cover letter, and (optionally) compiles a PDF resume from your Overleaf template. Built with CrewAI + Groq, served as a CLI, a FastAPI backend, and a Next.js frontend.

## What's in v2

- **6 agents**: job analyzer, gap mapper, CV tailor, cover letter writer, LaTeX resume builder, browser autofill (vision)
- **FastAPI backend** with SQLite for persistence
- **Next.js frontend** with live progress streaming via Server-Sent Events
- **Background scheduler** (APScheduler) — saves your searches and runs them once every 24h, notifies you of fresh high-match jobs
- **3-tier caching** (search / scrape / analysis) so re-runs cost zero tokens
- **PDF generation** via cloud LaTeX compile

## Setup

### 1. Clone
```bash
git clone https://github.com/I221165/JobApplierCrew.git -b v2
cd JobApplierCrew
```

### 2. Python deps
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 3. Frontend deps
```bash
cd frontend
npm install
cd ..
```

### 4. Environment
```bash
cp .env.example .env
```
Open `.env` and fill in:
```
GROQ_API_KEY=...            # required — https://console.groq.com
SERPER_API_KEY=...          # required — https://serper.dev (free tier)
GEMINI_API_KEY=...          # optional — only for browser autofill
CANDIDATE_NAME=Your Name
CANDIDATE_EMAIL=your@email.com
PLAYWRIGHT_BROWSERS_PATH=F:\playwright-browsers   # optional, see "Browser autofill" below
```

### 5. (Optional) Your LaTeX resume template
If you want PDF resume output, drop your Overleaf `.tex` content into `resume_template.tex`. Leave it as comments to skip the PDF step.

## Running

### Option A: Web app (recommended)

Two terminals:

**Terminal 1 — backend**
```bash
.venv\Scripts\python.exe -m uvicorn api.server:app --port 8001 --reload
```
Swagger UI: http://localhost:8001/docs

**Terminal 2 — frontend**
```bash
cd frontend
npm run dev
```
Open http://localhost:3000

If you change the backend port, update `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

**Typical flow:**
1. `/cv` — upload PDF or paste your CV, paste optional LaTeX template, save
2. `/` — search role + location → batch screen → pick a passing job → Apply
3. `/applications/{id}` — watch live progress, download PDF when done
4. `/searches` — save searches to auto-run daily
5. `/notifications` — see new high-match jobs the scheduler found

### Option B: CLI (no frontend needed)

Put your CV in `my_cv.txt`, then:
```bash
python main.py
```
Interactive prompts walk you through search → screening → application.

## Browser autofill

The browser agent opens a real Chromium window, navigates to the job posting, and fills in the application form (stops before submitting — you review and submit manually). Currently CLI-only, not in the web app.

First-time setup:
```bash
.venv\Scripts\python.exe -m playwright install chromium
```
On Windows, if your C: drive is full, redirect the browser install:
```bash
$env:PLAYWRIGHT_BROWSERS_PATH = "F:\playwright-browsers"
```

## Architecture

```
frontend/ (Next.js 16 + Tailwind 4)
    │ HTTP + SSE
    ▼
api/ (FastAPI + SQLite)
    │ ├── scheduler.py  ← APScheduler ticks hourly
    │ └── tasks.py      ← background thread runs the crew
    ▼
services/ (pure functions, no I/O magic)
    ├── search.py       ← SerperDevTool, cached
    ├── scrape.py       ← ScrapeWebsiteTool, cached
    ├── analysis.py     ← analyzer agent, cached
    ├── crew.py         ← gap + tailor + cover_letter agents
    ├── latex.py        ← latex_filler agent + cloud PDF compile
    └── browser.py      ← browser-use agent (CLI only)
```

CLI (`main.py`) and FastAPI (`api/server.py`) both call into the same `services/` — so any fix in services improves both.

## Files not to commit
| File / dir | Reason |
|------------|--------|
| `.env` | API keys |
| `my_cv.txt`, `tailored_cv.txt`, `cover_letter.txt`, `tailored_cv.tex`, `tailored_cv.pdf` | Personal data |
| `.cache/` | Local query cache |
| `*.db` | SQLite DB |
| `generated/` | Per-application PDFs |
| `frontend/node_modules`, `frontend/.next` | Build artifacts |

Already covered in `.gitignore`.

## Stack
- [CrewAI 1.14](https://github.com/crewAIInc/crewAI) — agent orchestration
- [Groq](https://groq.com) — Llama 3.3 70B for text agents, Llama 4 Scout for vision
- [FastAPI](https://fastapi.tiangolo.com) + [SQLModel](https://sqlmodel.tiangolo.com) + [APScheduler](https://apscheduler.readthedocs.io)
- [browser-use](https://github.com/browser-use/browser-use) — autonomous browser control
- [Next.js 16](https://nextjs.org) + [Tailwind 4](https://tailwindcss.com)
- [latex.ytotech.com](https://latex.ytotech.com) — cloud LaTeX → PDF
- Python 3.13, Node 22
