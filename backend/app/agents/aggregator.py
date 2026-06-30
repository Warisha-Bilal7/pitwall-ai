from app.agents.llm import get_llm
from app.agents.state import AgentState


AGGREGATION_PROMPT = """You are PITWALL·AI, an F1 race engineer giving a driver/team a debrief.

You have been given analysis from one or more specialist systems below. Synthesize this into a single, coherent answer to the user's original question. Speak like a race engineer on team radio: direct, confident, grounded in the numbers you were given. Do not invent any numbers that aren't present in the analysis below. If only one specialist reported, just present their finding clearly — don't pad it out.

Original question: "{query}"

{sections}

Give your final answer now. No preamble like "Based on the analysis" — just answer like an engineer would."""


def _build_sections(state: AgentState) -> str:
    sections = []
    if state.get("telemetry_output"):
        sections.append(f"TELEMETRY ANALYSIS:\n{state['telemetry_output']}")
    if state.get("strategy_output"):
        sections.append(f"STRATEGY ANALYSIS:\n{state['strategy_output']}")
    if state.get("rag_output"):
        sections.append(f"FACTUAL/RAG ANALYSIS:\n{state['rag_output']}")
    return "\n\n".join(sections)


async def aggregator_node(state: AgentState) -> dict:
    """
    LangGraph node: combines whichever specialist outputs are present
    into a single final_answer, in a consistent race-engineer voice.
    """
    sections = _build_sections(state)

    if not sections:
        return {"final_answer": "No analysis was available to answer that question."}

    llm = get_llm(temperature=0.3)
    prompt = AGGREGATION_PROMPT.format(query=state["query"], sections=sections)
    response = llm.invoke(prompt)

    print(f"  Aggregator produced final answer ({len(response.content)} chars)")

    return {"final_answer": response.content}