import os


async def fill_application_form(url: str, cover_body: str) -> str:
    """Open a real browser, fill the application form, and stop before submitting.

    Uses Llama 4 Scout via Groq (vision-capable, free tier). The browser window is visible
    so the user can review and submit manually.
    """
    from browser_use import Agent as BrowserAgent
    from browser_use.browser.profile import BrowserProfile
    from browser_use.llm.groq.chat import ChatGroq

    browser_llm = ChatGroq(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY"),
    )

    candidate_name = os.getenv("CANDIDATE_NAME", "")
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
