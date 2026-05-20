# JobApplierCrew

A multi-agent CrewAI system that tailors your CV and writes a personalized cover letter for any job description — powered by Groq's Llama 3.3 70B.

## How it works

Three agents run sequentially:

1. **Job Analyzer** — reads the job description, extracts must-have skills, keywords, and tone
2. **CV Tailor** — rewrites your CV to highlight the most relevant experience (no lies, just optimization)
3. **Cover Letter Writer** — writes a personalized cover letter based on the analysis

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/I221165/JobApplierCrew.git
cd JobApplierCrew
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Add your Groq API key
```bash
cp .env.example .env
```
Then open `.env` and paste your key:
```
GROQ_API_KEY=your_groq_api_key_here
```
Get a free key at [console.groq.com](https://console.groq.com)

### 4. Add your CV
Create a file called `my_cv.txt` in the project folder and paste your CV/resume as plain text.

> `my_cv.txt` is intentionally gitignored — keep your personal data local.

### 5. Add the job description
Open `main.py` and paste the job description into the `job_description` variable.

### 6. Run it
```bash
python main.py
```

Output is printed to terminal and saved to `tailored_cv.txt`.

## Files not to commit
| File | Reason |
|------|--------|
| `.env` | Contains your API key |
| `my_cv.txt` | Your personal CV data |
| `tailored_cv.txt` | Generated output with personal info |

## Stack
- [CrewAI](https://github.com/crewAIInc/crewAI) — multi-agent framework
- [Groq](https://groq.com) — LLM inference (Llama 3.3 70B)
- Python 3.10+
