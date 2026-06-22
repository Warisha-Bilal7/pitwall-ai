from typing import TypedDict, Optional


class AgentState(TypedDict):
    """
    Shared state passed between all nodes in the PITWALL·AI agent graph.

    Each specialist agent reads `query`/`session_id`/`session_key` and writes
    ONLY to its own output field. The supervisor reads `route` to decide
    which agents to invoke, and the aggregator reads all *_output fields
    to compose `final_answer`.
    """
    query: str                          # original user question
    session_id: str                     # internal UUID (string form) of the session
    session_key: int                    # OpenF1 session_key, used for RAG lookups

    route: list[str]                    # subset of ["strategy", "telemetry", "rag"]

    strategy_output: Optional[str]
    telemetry_output: Optional[str]
    rag_output: Optional[str]

    final_answer: Optional[str]