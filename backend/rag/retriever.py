import json
import math
import re
from collections import Counter
from pathlib import Path

from backend.config.settings import (
    RAG_MIN_SCORE,
    RAG_TOP_K
)


TOKEN_PATTERN = re.compile(
    r"[a-zA-Z][a-zA-Z0-9_/-]*"
)


class RAGRetriever:

    def __init__(
        self,
        knowledge_path: Path | None = None
    ):

        self.knowledge_path = (
            knowledge_path
            or Path("data/knowledge/educational_finance.json")
        )
        self.documents = self.load_documents()
        self.document_vectors = [
            self.vectorize(
                self.document_text(document)
            )
            for document in self.documents
        ]

    def load_documents(self):

        if not self.knowledge_path.exists():

            return []

        return json.loads(
            self.knowledge_path.read_text(
                encoding="utf-8"
            )
        )

    def tokenize(
        self,
        text: str
    ):

        return [
            token.lower()
            for token in TOKEN_PATTERN.findall(
                text or ""
            )
        ]

    def vectorize(
        self,
        text: str
    ):

        return Counter(
            self.tokenize(text)
        )

    def document_text(
        self,
        document: dict
    ):

        fields = [
            document.get("title", ""),
            document.get("summary", ""),
            document.get("content", ""),
            " ".join(
                document.get(
                    "keywords",
                    []
                )
            )
        ]

        return " ".join(fields)

    def cosine_score(
        self,
        left: Counter,
        right: Counter
    ):

        if not left or not right:

            return 0.0

        overlap = set(left) & set(right)
        numerator = sum(
            left[token] * right[token]
            for token in overlap
        )
        left_norm = math.sqrt(
            sum(
                value * value
                for value in left.values()
            )
        )
        right_norm = math.sqrt(
            sum(
                value * value
                for value in right.values()
            )
        )

        if left_norm == 0 or right_norm == 0:

            return 0.0

        return numerator / (
            left_norm * right_norm
        )

    def search(
        self,
        query: str,
        top_k: int = RAG_TOP_K,
        min_score: float = RAG_MIN_SCORE
    ):

        query_vector = self.vectorize(query)
        scored = []

        for document, document_vector in zip(
            self.documents,
            self.document_vectors
        ):

            score = self.cosine_score(
                query_vector,
                document_vector
            )

            if score >= min_score:

                scored.append({
                    "id": document.get("id"),
                    "title": document.get("title"),
                    "summary": document.get("summary"),
                    "content": document.get("content"),
                    "source": document.get("source"),
                    "score": round(score, 4)
                })

        scored.sort(
            key=lambda item: item["score"],
            reverse=True
        )

        return scored[:top_k]

    def build_context(
        self,
        results: list[dict]
    ):

        if not results:

            return ""

        chunks = []

        for index, result in enumerate(
            results,
            start=1
        ):

            chunks.append(
                "\n".join([
                    f"SOURCE {index}",
                    f"TITLE: {result.get('title')}",
                    f"SUMMARY: {result.get('summary')}",
                    f"CONTENT: {result.get('content')}",
                    f"CITATION: {result.get('source')}"
                ])
            )

        return "\n\n".join(chunks)
