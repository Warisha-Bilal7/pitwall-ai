from langchain_groq import ChatGroq
from app.config import get_settings
import os

_llm: ChatGroq | None = None


def get_llm(temperature: float = 0.2) -> ChatGroq:
    """
    Returns a shared ChatGroq client. Reused across agents to avoid
    re-reading settings/env on every call.
    """
    global _llm
    settings = get_settings()
    os.environ["GROQ_API_KEY"] = settings.groq_api_key

    if _llm is None:
        _llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=temperature)
    return _llm