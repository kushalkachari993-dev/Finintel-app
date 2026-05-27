from backend.tools.tavily_search_tool import (
    TavilySearchTool
)


class NewsTool:

    # ---------------------------------------------------
    # INIT
    # ---------------------------------------------------

    def __init__(self):

        self.search_tool = (
            TavilySearchTool()
        )

    # ---------------------------------------------------
    # COMPANY NEWS
    # ---------------------------------------------------

    def get_company_news(
        self,
        company_name: str,
        max_results: int = 5
    ):

        try:

            search_query = (
                f"Latest stock market news about "
                f"{company_name}"
            )

            results = (

                self.search_tool
                .search(
                    query=search_query,
                    max_results=max_results
                )
            )

            return results

        except Exception as e:

            return [

                {
                    "error":
                    str(e)
                }
            ]

    # ---------------------------------------------------
    # GENERAL / MACRO NEWS
    # ---------------------------------------------------

    def get_general_news(
        self,
        topic: str,
        max_results: int = 5
    ):

        try:

            results = (

                self.search_tool
                .search(
                    query=topic,
                    max_results=max_results
                )
            )

            return results

        except Exception as e:

            return [

                {
                    "error":
                    str(e)
                }
            ]

    # ---------------------------------------------------
    # BUILD CONTEXT
    # ---------------------------------------------------

    def build_news_context(
        self,
        news_articles: list
    ):

        if not news_articles:

            return (
                "No news articles found."
            )

        context = ""

        for index, article in enumerate(

            news_articles,

            start=1
        ):

            title = article.get(
                "title",
                ""
            )

            content = article.get(
                "content",
                ""
            )

            url = article.get(
                "url",
                ""
            )

            context += f"""
ARTICLE {index}

TITLE:
{title}

CONTENT:
{content}

SOURCE:
{url}

-----------------------------------

"""

        return context.strip()