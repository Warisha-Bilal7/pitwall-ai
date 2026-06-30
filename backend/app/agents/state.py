from typing import TypedDict, Optional


class AgentState(TypedDict):
    query: str
    session_id: str
    session_key: int
    route: Optional[list[str]]
    strategy_output: Optional[str]
    telemetry_output: Optional[str]
    rag_output: Optional[str]
    final_answer: Optional[str]