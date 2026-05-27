import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(ROOT)
    )

from backend.rag import RAGRetriever


CASES = [
    ("What is ROE?", "roe"),
    ("Explain PE ratio", "pe-ratio"),
    ("What does debt to equity mean?", "debt-to-equity"),
    ("Define free cash flow", "free-cash-flow"),
    ("What is dividend yield?", "dividend-yield"),
    ("Explain operating margin", "operating-margin"),
    ("What is market capitalization?", "market-capitalization")
]


def main():

    retriever = RAGRetriever()
    passes = 0
    failures = []

    for query, expected_id in CASES:

        results = retriever.search(query)
        actual_id = (
            results[0]["id"]
            if results
            else None
        )

        if actual_id == expected_id:

            passes += 1

        else:

            failures.append({
                "query": query,
                "expected": expected_id,
                "actual": actual_id
            })

    total = len(CASES)

    print(f"Total RAG cases: {total}")
    print(f"RAG top-1 accuracy: {passes / total * 100:.1f}%")
    print(f"Failures: {len(failures)}")

    for failure in failures:

        print("-" * 72)
        print(f"Query: {failure['query']}")
        print(f"Expected: {failure['expected']}")
        print(f"Actual: {failure['actual']}")


if __name__ == "__main__":

    main()
