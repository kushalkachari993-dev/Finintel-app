from urllib.parse import urlparse

from backend.config.trusted_finance_domains import (
    TRUSTED_FINANCE_DOMAINS
)


class RetrievalFilter:

    # ---------------------------------------------------
    # EXTRACT DOMAIN
    # ---------------------------------------------------

    @staticmethod
    def extract_domain(url: str):

        try:

            parsed = urlparse(url)

            domain = parsed.netloc.lower()

            if domain.startswith("www."):

                domain = domain.replace(
                    "www.",
                    ""
                )

            return domain

        except Exception:

            return ""

    # ---------------------------------------------------
    # TRUST CHECK
    # ---------------------------------------------------

    @staticmethod
    def is_trusted_domain(url: str):

        domain = (
            RetrievalFilter.extract_domain(
                url
            )
        )

        return any(

            trusted_domain in domain

            for trusted_domain
            in TRUSTED_FINANCE_DOMAINS
        )

    # ---------------------------------------------------
    # FILTER RESULTS
    # ---------------------------------------------------

    @staticmethod
    def filter_results(results: list):

        if not results:

            return []

        filtered = []

        seen_urls = set()

        for item in results:

            url = item.get("url", "")

            content = item.get(
                "content",
                ""
            )

            # -----------------------------------
            # SKIP EMPTY URL
            # -----------------------------------

            if not url:

                continue

            # -----------------------------------
            # TRUSTED DOMAIN CHECK
            # -----------------------------------

            if not RetrievalFilter.is_trusted_domain(
                url
            ):

                continue

            # -----------------------------------
            # DUPLICATE REMOVAL
            # -----------------------------------

            if url in seen_urls:

                continue

            seen_urls.add(url)

            # -----------------------------------
            # LOW CONTENT FILTER
            # -----------------------------------

            if len(content.strip()) < 80:

                continue

            filtered.append(item)

        return filtered