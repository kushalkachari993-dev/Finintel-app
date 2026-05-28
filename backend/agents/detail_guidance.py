def answer_detail_guidance(
    answer_detail: str
) -> str:

    if answer_detail != "detailed":
        return (
            "Answer in brief mode: be concise, direct, and focused on the "
            "user's exact question."
        )

    return (
        "Answer in detailed mode: stay specific to the user's exact question, "
        "but provide richer reasoning. Include more explanation, practical "
        "interpretation, caveats, and source-aware context where available. "
        "Do not turn the answer into a full analyst report unless the user "
        "asked for a report. Avoid invented facts, target prices, or "
        "investment recommendations."
    )


def answer_detail_tokens(
    answer_detail: str,
    brief_tokens: int,
    detailed_tokens: int
) -> int:

    if answer_detail == "detailed":
        return detailed_tokens

    return brief_tokens
