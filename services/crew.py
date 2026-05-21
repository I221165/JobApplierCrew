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
            goal="Write a targeted cover letter that directly addresses the job's must-have requirements",
            backstory=(
                "You write cover letters that get callbacks. You reference specific requirements and match them "
                "to the candidate's evidence."
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
        agent=agents["cover_letter_writer"],
    )

    Crew(
        agents=list(agents.values()),
        tasks=[map_gaps, tailor_cv, write_cover_letter],
        process=Process.sequential,
        verbose=True,
    ).kickoff()

    return (
        map_gaps.output.pydantic,
        tailor_cv.output.pydantic,
        write_cover_letter.output.pydantic,
    )
