from app.agents.llm import get_llm
from app.agents.state import AgentState
import json
import re


ROUTING_PROMPT = """You are the routing supervisor for PITWALL·AI, an F1 race intelligence system.

You have three specialist agents:
- "telemetry": analyzes lap pace, sector times, speed trap data, pace anomalies for a specific driver
- "strategy": analyzes pit stop timing, stint lengths, tyre degradation trends for a specific driver
- "rag": answers factual questions about the race using indexed documents — fastest lap, race summary, driver comparisons, general race information

Given a user question, decide which agent(s) should answer it.
Rules:
- Use "telemetry" ONLY when a specific driver is named or clearly implied and the question is about pace, lap times, speed, or anomalies
- Use "strategy" ONLY when a specific driver is named or clearly implied and the question is about pit stops, stint strategy, tyre management, or undercut/overcut
- Use "rag" for race-wide questions with no specific driver, factual/historical questions, multi-driver comparisons, or anything that doesn't require live lap data
- You can pick more than one agent if the question spans multiple domains AND a specific driver is named
- Always return a JSON object with a single key "route" containing a list of agent names

Examples:
Q: "Why is Leclerc losing time?" -> {{"route": ["telemetry"]}}
Q: "Was Verstappen's pit timing optimal?" -> {{"route": ["strategy"]}}
Q: "Who had the fastest lap?" -> {{"route": ["rag"]}}
Q: "How did Norris manage his tyres and pace?" -> {{"route": ["telemetry", "strategy"]}}
Q: "Compare Leclerc and Verstappen's pace" -> {{"route": ["telemetry"]}}
Q: "What's the overall strategy story of this race?" -> {{"route": ["rag"]}}
Q: "How many pit stops did McLaren make?" -> {{"route": ["rag"]}}
Q: "How's the race going?" -> {{"route": ["rag"]}}

User question: "{query}"

Respond ONLY with valid JSON. No explanation, no markdown, no backticks."""


def _parse_route(response_text: str) -> list[str]:
    """Safely parse the LLM's JSON routing decision."""
    valid_agents = {"telemetry", "strategy", "rag"}
    try:
        clean = re.sub(r"```json|```", "", response_text).strip()
        parsed = json.loads(clean)
        route = parsed.get("route", [])
        return [r for r in route if r in valid_agents] or ["rag"]
    except (json.JSONDecodeError, AttributeError):
        return ["rag"]


async def supervisor_node(state: AgentState) -> dict:
    """
    LangGraph node: classifies the query and sets state["route"].
    Does NOT call any specialist agents -- just decides who should.
    """
    llm = get_llm(temperature=0.0)
    prompt = ROUTING_PROMPT.format(query=state["query"])
    response = llm.invoke(prompt)
    route = _parse_route(response.content)

    print(f"  Supervisor routed to: {route}")

    return {"route": route}