import asyncio
from app.agents.graph import build_graph

TEST_QUERIES = [
    ("Why is Leclerc losing time?", "telemetry only"),
    ("Was Verstappen's pit timing optimal?", "strategy only"),
    ("Who had the fastest lap?", "rag only"),
    ("How did Norris manage his tyres and pace?", "multi-agent: telemetry + strategy"),
    ("How many pit stops did McLaren make?", "rag only"),
]

async def main():
    graph = build_graph()

    for query, expected in TEST_QUERIES:
        print(f"\n{'='*70}")
        print(f"Q: {query}")
        print(f"(expected: {expected})")
        print('='*70)

        state = {
            "query": query,
            "session_id": "a308f83a-debc-4035-ba62-193e65aa8768",
            "session_key": 11307,
            "route": None,
            "strategy_output": None,
            "telemetry_output": None,
            "rag_output": None,
            "final_answer": None,
        }

        result = await graph.ainvoke(state)
        print(f"\nROUTE: {result['route']}")
        print(f"\nFINAL ANSWER:\n{result['final_answer']}")

if __name__ == "__main__":
    asyncio.run(main())