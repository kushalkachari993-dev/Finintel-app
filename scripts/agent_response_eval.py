import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(ROOT)
    )

from backend.evaluators.response_quality import evaluate_response


FIXTURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "agent_response_eval_cases.json"
)


def main():

    cases = json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )

    failures = []

    for case in cases:

        issues = evaluate_response(
            route=case["route"],
            response=case["response"]
        )

        if issues:

            failures.append({
                "route": case["route"],
                "issues": issues
            })

    total = len(cases)
    passed = total - len(failures)

    print(f"Total response cases: {total}")
    print(
        "Agent response contract pass rate: "
        f"{passed / total * 100:.1f}%"
    )
    print(f"Failures: {len(failures)}")
    print()

    if not failures:

        print("All agent response evaluation cases passed.")
        return

    for failure in failures:

        print("-" * 72)
        print(f"Route: {failure['route']}")

        for issue in failure["issues"]:

            print(f"- {issue}")


if __name__ == "__main__":

    main()
