import logging
from datetime import datetime
from datetime import timezone

from tavily import TavilyClient

from backend.config.settings import (
    TAVILY_API_KEY,
    SEARCH_CACHE_SECONDS
)

from backend.utils.simple_cache import build_cache


logger = logging.getLogger(__name__)


class TavilySearchTool:

    cache = build_cache(
        ttl_seconds=SEARCH_CACHE_SECONDS,
        namespace="search"
    )

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.client = TavilyClient(
            api_key=TAVILY_API_KEY
        )

    # ---------------------------------------------------
    # SEARCH
    # ---------------------------------------------------

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "advanced"
    ):

        cache_key = (
            query.strip().lower(),
            max_results,
            search_depth
        )

        cached = self.cache.get(
            cache_key
        )

        if cached is not None:

            logger.info(
                "search_cache_hit query=%r",
                query
            )

            return cached

        try:

            retrieved_at = datetime.now(
                timezone.utc
            ).isoformat()

            # -----------------------------------
            # TAVILY API CALL
            # -----------------------------------

            response = self.client.search(

                query=query,

                search_depth=search_depth,

                max_results=max_results
            )

            # -----------------------------------
            # FORMAT RESULTS
            # -----------------------------------

            results = []

            for item in response.get(
                "results",
                []
            ):

                results.append({

                    "title":
                    item.get("title"),

                    "content":
                    item.get("content"),

                    "url":
                    item.get("url"),

                    "retrieved_at":
                    retrieved_at
                })

            return self.cache.set(
                cache_key,
                results
            )

        except Exception as e:

            logger.exception(
                "search_failed query=%r",
                query
            )

            return [

                {
                    "error":
                    str(e)
                }
            ]
