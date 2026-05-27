from backend.rag import RAGRetriever


def test_rag_retriever_finds_roe_context():

    retriever = RAGRetriever()

    results = retriever.search(
        "What is ROE?"
    )

    assert results
    assert results[0]["id"] == "roe"
    assert results[0]["source"]


def test_rag_retriever_builds_context_with_citation():

    retriever = RAGRetriever()

    results = retriever.search(
        "Explain debt to equity ratio"
    )

    context = retriever.build_context(
        results
    )

    assert "Debt to Equity Ratio" in context
    assert "CITATION:" in context
