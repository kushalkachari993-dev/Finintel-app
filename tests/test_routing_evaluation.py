import json
from pathlib import Path

from backend.agents.router_agent import RouterAgent
from backend.intelligence.query_intelligence import QueryIntelligence


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "routing_eval_queries.json"
)


def load_cases():

    return json.loads(
        FIXTURE_PATH.read_text(
            encoding="utf-8"
        )
    )


def evaluate_cases():

    intelligence_engine = QueryIntelligence()
    router = RouterAgent()
    results = []

    for case in load_cases():

        intelligence = intelligence_engine.extract(
            case["query"]
        )

        routing = router.route(
            case["query"],
            intelligence=intelligence
        )

        actual_companies = set(
            intelligence.get(
                "companies",
                []
            )
        )

        expected_companies = set(
            case.get(
                "expected_companies",
                []
            )
        )

        results.append({
            "query": case["query"],
            "expected_route": case["expected_route"],
            "actual_route": routing["route"],
            "route_pass": routing["route"] == case["expected_route"],
            "expected_intent": case["expected_intent"],
            "actual_intent": intelligence["intent"],
            "intent_pass": intelligence["intent"] == case["expected_intent"],
            "expected_companies": sorted(expected_companies),
            "actual_companies": sorted(actual_companies),
            "companies_pass": actual_companies == expected_companies,
            "routing": routing,
            "intelligence": intelligence
        })

    return results


def test_routing_evaluation_accuracy():

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

    route_accuracy = route_passes / total
    intent_accuracy = intent_passes / total
    company_accuracy = company_passes / total

    failures = [
        item for item in results
        if not (
            item["route_pass"]
            and item["intent_pass"]
            and item["companies_pass"]
        )
    ]

    assert route_accuracy >= 0.85, failures
    assert intent_accuracy >= 0.85, failures
    assert company_accuracy >= 0.75, failures
