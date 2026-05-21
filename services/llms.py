from crewai import LLM

_main_llm = None


def main_llm() -> LLM:
    """Lazy-initialised Groq Llama 3.3 70B used by all CrewAI text agents."""
    global _main_llm
    if _main_llm is None:
        _main_llm = LLM(model="groq/llama-3.3-70b-versatile")
    return _main_llm
