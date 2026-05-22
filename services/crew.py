from crewai import Agent, Crew, Process, Task

from services.llms import main_llm
from services.models import CoverLetter, GapAnalysis, JobAnalysis, TailoredCV


def _agents() -> dict[str, Agent]:
    llm = main_llm()
    return {
        "gap_mapper": Agent(
            role="Career Gap Analyst",
            goal="Map each job requirement to the candidate's actual experience and identify gaps",
            backstory=(
                "You are an expert career coach. You compare job requirements against a candidate's CV "
                "and for each requirement, you find matching evidence in the CV, suggest how to reframe it, "
                "and flag what's genuinely missing. You never invent experience."
            ),
            llm=llm,
            verbose=True,
        ),
        "cv_tailor": Agent(
            role="CV Tailoring Specialist",
            goal="Restructure the CV dynamically based on the gap analysis to maximise match with the job",
            backstory=(
                "You are a professional CV writer. Given a gap analysis that maps job requirements to a candidate's "
                "experience, you restructure the CV so the most relevant sections come first, reframe bullet points "
                "using the suggested language, and ensure every must-have requirement has a visible answer in the CV."
            ),
            llm=llm,
            verbose=True,
        ),
        "cover_letter_writer": Agent(
            role="Cover Letter Writer",
            goal="Write a sharply focused cover letter that addresses ONLY the target role's requirements, never bleeding in unrelated CV experience",
            backstory=(
                "You write cover letters that get callbacks. Your single most important discipline: "
                "you stay laser-focused on the role being applied for. If a candidate has DevOps AND AI "
                "experience and applies for an AI role, you write an AI-only letter. Mentioning the wrong "
                "domain confuses recruiters and looks like a generic mass-application. You quantify impact "
                "with numbers, name specific technologies, and never use filler phrases like 'I am passionate "
                "about' or 'I am writing to apply for'. You match the company's tone exactly."
            ),
            llm=llm,
            verbose=True,
        ),
    }


def build_application(cv: str, job_analysis: JobAnalysis) -> tuple[GapAnalysis, TailoredCV, CoverLetter]:
    """Run the 3-agent crew: gap analysis → tailored CV → cover letter."""
    agents = _agents()

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
        {cv}
        """,
        expected_output="Full gap analysis with matches, weak matches, gaps, and CV structure order.",
        output_pydantic=GapAnalysis,
        agent=agents["gap_mapper"],
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
        {cv}
        """,
        expected_output="Dynamically restructured, tailored CV and 3-5 key highlights.",
        output_pydantic=TailoredCV,
        agent=agents["cv_tailor"],
    )

    write_cover_letter = Task(
        description=f"""
        Write a cover letter for the role: "{job_analysis.actual_title}"
        Company tone: {job_analysis.tone}
        Must-have requirements for this role: {', '.join(job_analysis.must_have)}

        STRICT FOCUS RULE (most important):
        The candidate may have many skills across multiple domains. The cover letter must ONLY
        mention skills, projects, and experience that map to a "strong_match" in the gap analysis
        from the previous task. Do NOT pull in adjacent or unrelated experience from the CV,
        even if it's impressive. If the role is "AI Engineer", do not talk about DevOps work.
        If the role is "DevOps", do not talk about ML work. One letter = one focus.

        LENGTH: 250-350 words total. Hard cap at 400. Recruiters scan in ~8 seconds.

        STRUCTURE (4 paragraphs):

        Paragraph 1 — Opening hook (2-3 sentences):
          - Lead with the single strongest qualification, not "I am writing to apply..."
          - State the role you're applying for naturally
          - One concrete fact about why this candidate fits

        Paragraph 2 — Evidence (4-5 sentences):
          - Pick the 2-3 STRONGEST matches from the gap analysis
          - For each: name the specific technology/project AND quantify impact
            (numbers, scale, outcomes — pull these from the candidate_evidence field)
          - This is the "show, don't tell" paragraph

        Paragraph 3 — Company alignment / honesty (2-3 sentences):
          - Tie the candidate's approach to the company tone above
          - If there's ONE significant weak match, address it briefly and honestly
            (e.g. "While my Kubernetes production experience is recent, I've...")
          - Never beg, never apologise for gaps

        Paragraph 4 — Close (1-2 sentences):
          - Clear, confident call to action (mention being available to discuss / interview)
          - No "I would be eternally grateful", no "Thank you for your time" filler

        SUBJECT LINE: 8-12 words. Reference the role + ONE standout qualification.
          Good: "AI Engineer application — 2+ years building RAG systems"
          Bad:  "Application for the AI Engineer position at your company"

        FORBIDDEN PHRASES:
          - "I am writing to apply"
          - "I am passionate about"
          - "I would be a great fit"
          - "Please find attached"
          - "Thank you for considering my application"
        """,
        expected_output="Subject line (8-12 words) and a 250-350 word cover letter body with 4 paragraphs.",
        output_pydantic=CoverLetter,
        agent=agents["cover_letter_writer"],
    )

    Crew(
        agents=list(agents.values()),
        tasks=[map_gaps, tailor_cv, write_cover_letter],
        process=Process.sequential,
        verbose=True,
        max_rpm=2,   # Groq free tier: 12K TPM. 3 heavy tasks back-to-back blow the cap.
                     # max_rpm=2 forces a ~60s wait before the 3rd task, letting TPM refill.
    ).kickoff()

    return (
        map_gaps.output.pydantic,
        tailor_cv.output.pydantic,
        write_cover_letter.output.pydantic,
    )
