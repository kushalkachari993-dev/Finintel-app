import json
import re

from backend.api.schemas import ConversationContextMessage


FOLLOW_UP_TERMS = {
    "it",
    "its",
    "itself",
    "this",
    "that",
    "these",
    "those",
    "them",
    "they",
    "their",
    "theirs",
    "both",
    "former",
    "latter",
    "same",
    "above",
    "previous",
    "earlier"
}

FOLLOW_UP_PATTERNS = (
    r"^\s*(?:and|also|then)\b",
    r"\b(?:what|how)\s+about\b",
    r"\bwhich\s+(?:one|company|stock)\b",
    r"\b(?:tell|show|give)\s+me\s+more\b",
    r"\b(?:explain|tell me)\s+(?:why|how)\b",
    r"\b(?:you|your)\s+(?:said|mentioned|stated|concluded|answer|analysis)\b",
    r"\bbased\s+on\s+(?:that|this|your|the previous)\b",
    r"\bexplain\s+(?:that|this|it)\b",
    r"\b(?:more|further)\s+(?:detail|details|information|analysis)\b",
    r"\b(?:instead|alternatively)\b"
)

TERSE_FOLLOW_UP_QUERIES = {
    "why",
    "why not",
    "how so",
    "explain",
    "elaborate",
    "continue",
    "go on",
    "more",
    "more details",
    "source",
    "sources",
    "risks",
    "what risks",
    "valuation",
    "outlook",
    "debt",
    "margins",
    "growth",
    "dividends"
}

CONVERSATION_CONTEXT_MESSAGE_LIMIT = 8
CONVERSATION_CONTEXT_CONTENT_LIMIT = 2000
GENERATION_CONTEXT_MESSAGE_LIMIT = 6
GENERATION_CONTEXT_TOTAL_LIMIT = 6000


def response_context_text(
    response: dict | None
) -> str:

    if not isinstance(response, dict):

        return ""

    value = response.get(
        "data"
    )

    if value is None:

        value = response.get(
            "error"
        )

    if value is None:

        return ""

    if isinstance(value, str):

        text = value

    else:

        text = json.dumps(
            value,
            ensure_ascii=False,
            default=str,
            separators=(",", ":")
        )

    return text.strip()[
        :CONVERSATION_CONTEXT_CONTENT_LIMIT
    ]


def stored_conversation_context(
    *,
    principal_id: str,
    conversation_id: str,
    chat_audit_store
) -> list[ConversationContextMessage]:

    messages = chat_audit_store.list_messages(
        principal_id=principal_id,
        conversation_id=conversation_id
    )
    context: list[ConversationContextMessage] = []

    for message in messages[
        -CONVERSATION_CONTEXT_MESSAGE_LIMIT:
    ]:
        role = message.get(
            "role"
        )
        content = str(
            message.get(
                "content"
            ) or ""
        ).strip()

        if role == "assistant":
            payload = message.get(
                "payload"
            )
            response = (
                payload.get(
                    "response"
                )
                if isinstance(payload, dict)
                else None
            )
            content = (
                response_context_text(
                    response
                )
                or content
            )

        if role not in {
            "user",
            "assistant",
            "error"
        } or not content:

            continue

        context.append(
            ConversationContextMessage(
                role=role,
                content=content[
                    :CONVERSATION_CONTEXT_CONTENT_LIMIT
                ]
            )
        )

    return context


def conversation_context_for_request(
    *,
    principal_id: str,
    conversation_id: str,
    client_context: list[ConversationContextMessage],
    chat_audit_store
) -> list[ConversationContextMessage]:

    stored_context = stored_conversation_context(
        principal_id=principal_id,
        conversation_id=conversation_id,
        chat_audit_store=chat_audit_store
    )

    if stored_context:

        return stored_context

    return client_context[
        -CONVERSATION_CONTEXT_MESSAGE_LIMIT:
    ]


def build_generation_context(
    context: list[ConversationContextMessage]
) -> str:

    blocks: list[str] = []
    remaining = GENERATION_CONTEXT_TOTAL_LIMIT

    for message in reversed(
        context[-GENERATION_CONTEXT_MESSAGE_LIMIT:]
    ):
        if message.role not in {
            "user",
            "assistant"
        }:

            continue

        content = message.content.strip()

        if not content:

            continue

        label = (
            "USER"
            if message.role == "user"
            else "ASSISTANT"
        )
        prefix = f"{label}: "
        available = remaining - len(
            prefix
        ) - 1

        if available <= 0:

            break

        block = prefix + content[
            :available
        ]
        blocks.append(
            block
        )
        remaining -= len(
            block
        ) + 1

    return "\n".join(
        reversed(
            blocks
        )
    )


def is_follow_up_query(
    query: str
) -> bool:

    words = {
        word.strip(".,?!:;").lower()
        for word in query.split()
    }
    query_lower = query.lower()
    normalized_query = " ".join(
        word.strip(".,?!:;").lower()
        for word in query.split()
    )
    pronoun_terms = set(
        FOLLOW_UP_TERMS
    )

    if re.search(
        r"\bit\s+(stocks?|sector|companies|shares?)\b",
        query_lower
    ):

        pronoun_terms.discard(
            "it"
        )

    return (
        bool(
            words & pronoun_terms
        )
        or normalized_query in TERSE_FOLLOW_UP_QUERIES
        or any(
            re.search(
                pattern,
                query_lower
            )
            for pattern in FOLLOW_UP_PATTERNS
        )
    )


def context_companies(
    context: list[ConversationContextMessage],
    *,
    query_intelligence
) -> list[str]:

    collected: list[str] = []

    for message in reversed(
        context
    ):
        if message.role != "user":

            continue

        message_companies = (
            query_intelligence
            .symbol_registry
            .extract_company_names(
                message.content
            )
        )

        if message_companies:

            collected = list(
                dict.fromkeys(
                    message_companies
                    + collected
                )
            )

        if not is_follow_up_query(
            message.content
        ):

            break

    return collected


def join_companies(
    companies: list[str]
) -> str:

    if len(companies) == 1:

        return companies[0]

    if len(companies) == 2:

        return f"{companies[0]} and {companies[1]}"

    return (
        ", ".join(
            companies[:-1]
        )
        + f", and {companies[-1]}"
    )


def standalone_follow_up_query(
    query: str,
    context: list[ConversationContextMessage],
    *,
    query_intelligence
) -> str:

    companies = context_companies(
        context,
        query_intelligence=query_intelligence
    )
    current_companies = (
        query_intelligence
        .symbol_registry
        .extract_company_names(
            query
        )
    )
    normalized_query = " ".join(
        word.strip(".,?!:;").lower()
        for word in query.split()
    )

    if companies and re.search(
        r"\b(?:compare|vs|versus)\b",
        query,
        flags=re.IGNORECASE
    ):
        comparison_companies = list(
            dict.fromkeys(
                companies
                + current_companies
            )
        )

        if len(comparison_companies) >= 2:

            return (
                "Compare "
                + join_companies(
                    comparison_companies
                )
            )

    if companies and re.match(
        r"^\s*(?:and|what about|how about)\b",
        query,
        flags=re.IGNORECASE
    ) and current_companies:
        comparison_companies = list(
            dict.fromkeys(
                companies
                + current_companies
            )
        )

        return (
            "Compare "
            + join_companies(
                comparison_companies
            )
        )

    if companies:
        subject = join_companies(
            companies
        )
        primary = companies[0]
        plural_possessive = (
            f"{subject}'"
            if subject.endswith("s")
            else f"{subject}'s"
        )
        replacements = (
            (
                r"\bwhich\s+(?:one|company|stock)\b",
                f"which of {subject}"
            ),
            (r"\bformer\b", companies[0]),
            (
                r"\blatter\b",
                companies[1]
                if len(companies) > 1
                else primary
            ),
            (r"\b(?:both|they|them|these|those)\b", subject),
            (r"\btheir\b", plural_possessive),
            (r"\bits\b", f"{primary}'s"),
            (r"\bitself\b", primary),
            (
                r"\b(?:it|this company|that company|the company)\b",
                primary
            )
        )
        resolved_query = query

        for pattern, replacement in replacements:
            resolved_query = re.sub(
                pattern,
                replacement,
                resolved_query,
                flags=re.IGNORECASE
            )

        if resolved_query != query:

            return resolved_query

        topic_match = re.match(
            r"^\s*(?:and|what about|how about)\s+(.+?)[?.!]*$",
            query,
            flags=re.IGNORECASE
        )

        if topic_match:

            return (
                f"Analyze {topic_match.group(1).strip()} "
                f"for {subject}"
            )

        if normalized_query in TERSE_FOLLOW_UP_QUERIES:

            if normalized_query in {
                "why",
                "why not",
                "how so"
            }:

                return f"Explain the reasoning for {subject}"

            if normalized_query in {
                "more",
                "more details",
                "explain",
                "elaborate",
                "continue",
                "go on"
            }:

                return f"Provide more details about {subject}"

            if normalized_query in {
                "source",
                "sources"
            }:

                return f"Show the sources for {subject}"

            return f"Analyze {normalized_query} for {subject}"

        return f"{query.rstrip()} regarding {subject}"

    previous_user_query = next(
        (
            message.content.strip()
            for message in reversed(
                context
            )
            if message.role == "user"
            and message.content.strip()
        ),
        ""
    )

    if previous_user_query:

        return (
            f"{query.rstrip()} regarding the previous topic: "
            f"{previous_user_query.lower()}"
        )

    return query


def contextual_query(
    query: str,
    context: list[ConversationContextMessage],
    *,
    query_intelligence
) -> str:

    if not context:

        return query

    if not is_follow_up_query(
        query
    ):

        return query

    return standalone_follow_up_query(
        query,
        context[-6:],
        query_intelligence=query_intelligence
    )

