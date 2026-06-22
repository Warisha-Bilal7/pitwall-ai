from app.database import AsyncSessionLocal
from app.services.embeddings import search_similar_documents
from app.agents.llm import get_llm
from app.agents.state import AgentState


async def rag_agent(state: AgentState) -> AgentState:
    """
    LangGraph node: semantic search over RaceDocument embeddings (pgvector),
    scoped to the current session, then asks the LLM to answer the query
    grounded in the retrieved documents.
    """
    query = state["query"]
    session_key = state["session_key"]

    async with AsyncSessionLocal() as db:
        docs = await search_similar_documents(
            db, query=query, session_key=session_key, limit=5
        )

    if not docs:
        state["rag_output"] = (
            "I don't have any indexed race documents for this session yet. "
            "Try running the document build pipeline first."
        )
        return state

    context = "\n\n".join(
        f"[{d.doc_type}] {d.content}" for d in docs
    )

    llm = get_llm(temperature=0.2)
    prompt = f"""You are a Formula 1 race historian answering questions using retrieved
race documents.

Retrieved context:
{context}

User question: "{query}"

Answer using ONLY the information in the retrieved context above. If the context
doesn't contain enough information to fully answer, say so explicitly rather than
guessing. Keep the answer to 3-5 sentences."""

    response = llm.invoke(prompt)
    state["rag_output"] = response.content
    return state