import os
import time

import requests
from crewai import Agent, Crew, Process, Task

from services.llms import main_llm
from services.models import LatexResume, TailoredCV


def _agent() -> Agent:
    return Agent(
        role="LaTeX Resume Builder",
        goal=(
            "Fill a LaTeX resume template with the candidate's tailored CV content, keeping the template "
            "structure intact and producing valid LaTeX that compiles cleanly"
        ),
        backstory=(
            "You are an expert in LaTeX and ATS-friendly resume formatting. You take a LaTeX template and "
            "the candidate's tailored CV content, then output a complete .tex document where the candidate's "
            "real information replaces the template's placeholder data — without breaking any LaTeX syntax, "
            "packages, or styling. You escape special LaTeX characters (&, %, $, #, _, {, }, \\, ~, ^) and "
            "never invent content beyond what the tailored CV contains."
        ),
        llm=main_llm(),
        verbose=True,
    )


def fill_latex_resume(tailored: TailoredCV, latex_template: str, sleep_before: int = 30) -> LatexResume:
    """Run the LaTeX filler agent and return the completed LaTeX source.

    `sleep_before` exists because Groq's TPM resets every minute — a delay after the main crew
    keeps us within budget for free tier.
    """
    if sleep_before:
        print(f"\nWaiting {sleep_before}s for Groq TPM budget to reset before LaTeX fill...")
        time.sleep(sleep_before)

    agent = _agent()
    task = Task(
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
        agent=agent,
    )

    Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True).kickoff()
    return task.output.pydantic


def compile_to_pdf(latex_code: str, timeout: int = 60) -> tuple[bytes | None, str]:
    """POST the LaTeX to the cloud compile API. Returns (pdf_bytes_or_None, status_message)."""
    try:
        resp = requests.post(
            "https://latex.ytotech.com/builds/sync",
            json={
                "compiler": "pdflatex",
                "resources": [{"main": True, "content": latex_code}],
            },
            timeout=timeout,
        )
        if resp.status_code == 201 and resp.headers.get("Content-Type", "").startswith("application/pdf"):
            return resp.content, "pdf generated"
        return None, f"compile failed (HTTP {resp.status_code})"
    except Exception as e:
        return None, f"cloud compile error: {e}"
