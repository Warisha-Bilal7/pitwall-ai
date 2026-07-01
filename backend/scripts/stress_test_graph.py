import asyncio
from app.agents.graph import build_graph

# Each case: (query, category, what we're checking for)
TEST_CASES = [
    # ── Nicknames / first names (expect graceful "couldn't identify driver") ──
    ("How is Mad Max doing on pace?", "nickname",
     "Should either fail gracefully with 'couldn't identify driver' OR correctly resolve to Verstappen — currently expected to FAIL since _find_driver_number_in_query only matches surname/acronym"),
    ("How is Lando's tyre management?", "first-name",
     "First name 'Lando' won't match surname 'Norris' or acronym 'NOR' — expected to fail gracefully, not crash"),

    # ── Two-driver comparisons (expect silent wrong answer, not a crash) ──
    ("Compare Leclerc and Verstappen's pace", "two-driver",
     "_find_driver_number_in_query returns only the FIRST match — check whether the answer silently ignores one driver"),
    ("Who managed their tyres better, Norris or Piastri?", "two-driver-strategy",
     "Same single-match limitation, but for strategy_agent — both are McLaren so this also stresses team-name ambiguity"),

    # ── Ambiguous / no driver named ──
    ("How's the race going?", "ambiguous-no-driver",
     "No driver name present — check supervisor routing and whether RAG gives a real answer or a non-answer"),
    ("What's the overall strategy story of this race?", "ambiguous-strategy",
     "No driver named, but mentions 'strategy' as a keyword — check if supervisor wrongly routes to strategy_agent which REQUIRES a driver"),

    # ── Nonsense / off-topic ──
    ("What's the weather like in Tokyo?", "off-topic",
     "Completely unrelated to F1 — check whether the routing prompt has any guardrail or forces a bucket"),
    ("Can you write me a poem about racing?", "off-topic-creative",
     "Tests whether off-topic-but-thematically-adjacent queries get misrouted into a fabricated 'analysis'"),

    # ── Empty / control case ──
    ("Who had the most pit stops?", "control-should-work",
     "Should hit the RAG SQL-ish path cleanly as a sanity control"),
]


async def main():
    graph = build_graph()

    results = []

    for query, category, note in TEST_CASES:
        print(f"\n{'='*70}")
        print(f"[{category}] {query}")
        print(f"Watching for: {note}")
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

        try:
            result = await graph.ainvoke(state)
            print(f"\nROUTE: {result['route']}")
            print(f"\nFINAL ANSWER:\n{result['final_answer']}")
            results.append((category, query, "completed", result['final_answer']))
        except Exception as e:
            print(f"\n!!! CRASHED: {type(e).__name__}: {e}")
            results.append((category, query, "CRASHED", str(e)))

    # Summary at the end
    print(f"\n\n{'#'*70}")
    print("SUMMARY")
    print('#'*70)
    for category, query, status, _ in results:
        print(f"  [{status:10}] {category:25} | {query}")

if __name__ == "__main__":
    asyncio.run(main())