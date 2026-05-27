from backend.config import settings


COMPLEX_ROUTES = {
    "COMPARISON",
    "NEWS",
    "DISCOVERY"
}


def select_groq_model(
    route: str,
    answer_detail: str = "brief"
) -> str:

    if answer_detail == "detailed" or route in COMPLEX_ROUTES:

        return settings.GROQ_COMPLEX_MODEL

    return settings.GROQ_FAST_MODEL
