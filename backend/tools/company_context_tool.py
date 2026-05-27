from backend.tools.tavily_search_tool import (
    TavilySearchTool
)

from backend.utils.retrieval_filter import (
    RetrievalFilter
)


class CompanyContextTool:

    def __init__(self):

        self.search_tool = TavilySearchTool()

    def build_query(
        self,
        company_name: str,
        ticker: str = None
    ):

        ticker_text = (
            f" {ticker}"
            if ticker
            else ""
        )

        return (
            f"{company_name}{ticker_text} "
            "business overview financial performance "
            "risks annual report India NSE BSE"
        )

    def get_company_context(
        self,
        company_name: str,
        ticker: str = None,
        max_results: int = 5
    ):

        query = self.build_query(
            company_name=company_name,
            ticker=ticker
        )

        results = self.search_tool.search(
            query=query,
            max_results=max_results
        )

        if (
            not results
            or (
                isinstance(results, list)
                and results
                and "error" in results[0]
            )
        ):

            return {
                "context_text": "",
                "sources_used": [],
                "results": []
            }

        filtered = RetrievalFilter.filter_results(
            results
        )

        if not filtered:

            filtered = results

        context_blocks = []
        sources_used = []

        for index, item in enumerate(
            filtered,
            start=1
        ):

            title = item.get(
                "title",
                ""
            )
            content = item.get(
                "content",
                ""
            )
            url = item.get(
                "url",
                ""
            )

            context_blocks.append(
                "\n".join([
                    f"SOURCE {index}",
                    f"TITLE: {title}",
                    f"CONTENT: {content}",
                    f"URL: {url}"
                ])
            )

            if url:

                sources_used.append(url)

        return {
            "context_text": "\n\n".join(
                context_blocks
            ),
            "sources_used": sources_used,
            "results": filtered
        }
