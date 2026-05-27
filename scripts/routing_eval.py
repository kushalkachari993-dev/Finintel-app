import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(ROOT)
    )

from tests.test_routing_evaluation import evaluate_cases


def pct(value):

    return f"{value * 100:.1f}%"


def main():

    results = evaluate_cases()
    total = len(results)

    route_passes = sum(
        1 for item in results
        if item["route_pass"]
    )
    intent_passes = sum(
        1 for item in results
        if item["intent_pass"]
    )
    company_passes = sum(
        1 for item in results
        if item["companies_pass"]
    )

    print(f"Total cases: {total}")
    print(f"Routing accuracy: {pct(route_passes / total)}")
    print(f"Intent accuracy: {pct(intent_passes / total)}")
    print(f"Entity accuracy: {pct(company_passes / total)}")
    print()

    failures = [
        item for item in results
        if not (
            item["route_pass"]
            and item["intent_pass"]
            and item["companies_pass"]
        )
    ]

    if not failures:

        print("All routing evaluation cases passed.")
        return

    print("Failures:")

    for item in failures:

        print("-" * 72)
        print(f"Query: {item['query']}")
        print(
            "Route: "
            f"expected={item['expected_route']} "
            f"actual={item['actual_route']}"
        )
        print(
            "Intent: "
            f"expected={item['expected_intent']} "
            f"actual={item['actual_intent']}"
        )
        print(
            "Companies: "
            f"expected={item['expected_companies']} "
            f"actual={item['actual_companies']}"
        )
        print(
            "Reasoning: "
            f"{item['routing'].get('reasoning')}"
        )


if __name__ == "__main__":

    main()
