import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from backend.config import settings
from backend.llm.groq_provider import GroqProvider
from backend.schemas.report_schema import ReportResponse
from backend.tools.company_context_tool import CompanyContextTool
from backend.tools.financial_metrics_interpreter import FinancialMetricsInterpreter
from backend.tools.stock_data_tool import StockDataTool
from backend.tools.ticker_resolver import TickerResolver
from backend.utils.confidence_engine import ConfidenceEngine
from backend.utils.json_parser import JSONParser
from backend.utils.provider_errors import is_provider_error_text


logger = logging.getLogger(__name__)


class ReportAgent:

    def __init__(self):

        self.groq = GroqProvider()
        self.ticker_resolver = TickerResolver()
        self.stock_tool = StockDataTool()
        self.interpreter = FinancialMetricsInterpreter()
        self.company_context_tool = CompanyContextTool()
        self.confidence_engine = ConfidenceEngine()

    def extract_candidates(
        self,
        query: str,
        intelligence: dict
    ) -> list[str]:

        companies = [
            str(company).strip()
            for company in intelligence.get(
                "companies",
                []
            )
            if str(company).strip()
        ]

        if companies:
            return companies[:4]

        cleaned_query = re.sub(
            r"\b(generate|create|prepare|report|analysis|detailed|best|top)\b",
            " ",
            query,
            flags=re.IGNORECASE
        )
        parts = [
            part.strip()
            for part in re.split(
                r"\bvs\b|\bversus\b|\band\b|,",
                cleaned_query,
                flags=re.IGNORECASE
            )
            if part.strip()
        ]

        local_parts = [
            part
            for part in parts
            if self.ticker_resolver.symbol_registry.resolve_company(
                part
            )
        ]

        if local_parts:
            return local_parts[:4]

        sector = intelligence.get(
            "sector"
        )
        sector_candidates = {
            "IT": [
                "TCS",
                "Infosys",
                "HCLTech",
                "Tech Mahindra"
            ],
            "BANKING": [
                "HDFC Bank",
                "ICICI Bank",
                "Axis Bank",
                "SBI"
            ],
            "PHARMA": [
                "Sun Pharma",
                "Dr Reddys",
                "Cipla",
                "Lupin"
            ],
            "FMCG": [
                "HUL",
                "ITC",
                "Nestle India",
                "Dabur"
            ],
            "AUTOMOBILE": [
                "Maruti",
                "Tata Motors",
                "Mahindra",
                "Bajaj Auto"
            ]
        }

        if sector in sector_candidates:
            return sector_candidates[sector]

        return [query]

    def resolve_candidates(
        self,
        candidates: list[str]
    ) -> list[dict]:

        with ThreadPoolExecutor(
            max_workers=min(
                4,
                max(
                    len(candidates),
                    1
                )
            )
        ) as executor:
            resolved = list(
                executor.map(
                    self.ticker_resolver.resolve,
                    candidates
                )
            )

        unique = {}

        for item in resolved:
            if item and item.get("ticker"):
                unique[item["ticker"]] = item

        return list(
            unique.values()
        )

    def fetch_company_section(
        self,
        company: dict
    ) -> dict:

        ticker = company.get(
            "ticker"
        )
        stock_data = self.stock_tool.get_stock_data(
            ticker
        )

        if (
            not stock_data
            or "error" in stock_data
        ):
            return {
                "success": False,
                "company": company,
                "sources": []
            }

        interpretation = self.interpreter.generate_interpretation(
            stock_data
        )
        context = self.company_context_tool.get_company_context(
            company_name=company.get(
                "company_name",
                ticker
            ),
            ticker=ticker,
            max_results=3
        )

        return {
            "success": True,
            "company": company,
            "stock_data": stock_data,
            "interpretation": interpretation,
            "context": context.get(
                "context_text",
                ""
            ),
            "sources": context.get(
                "sources_used",
                []
            )
        }

    def fetch_report_inputs(
        self,
        companies: list[dict]
    ) -> list[dict]:

        with ThreadPoolExecutor(
            max_workers=min(
                4,
                max(
                    len(companies),
                    1
                )
            )
        ) as executor:
            return list(
                executor.map(
                    self.fetch_company_section,
                    companies
                )
            )

    @staticmethod
    def compact_metrics(
        stock_data: dict
    ) -> dict:

        return {
            "current_price": stock_data.get("current_price"),
            "market_cap": stock_data.get("market_cap"),
            "pe_ratio": stock_data.get("pe_ratio"),
            "pb_ratio": stock_data.get("pb_ratio"),
            "roe": stock_data.get("roe"),
            "profit_margin": stock_data.get("profit_margin"),
            "revenue_growth": stock_data.get("revenue_growth"),
            "debt_to_equity": stock_data.get("debt_to_equity"),
            "data_quality_score": stock_data.get("data_quality_score")
        }

    def build_fallback_report(
        self,
        query: str,
        report_inputs: list[dict],
        sources_used: list[str],
        confidence_score: float,
        confidence_breakdown: dict
    ) -> dict:

        companies = []

        for item in report_inputs:
            if not item.get(
                "success"
            ):
                continue

            company = item["company"]
            stock_data = item["stock_data"]
            interpretation = item.get(
                "interpretation",
                {}
            )

            companies.append({
                "company_name": company.get(
                    "company_name",
                    stock_data.get(
                        "company_name",
                        ""
                    )
                ),
                "ticker": company.get(
                    "ticker",
                    ""
                ),
                "business_snapshot": (
                    f"{stock_data.get('company_name') or company.get('company_name')} "
                    f"operates in {stock_data.get('sector') or 'its listed sector'}."
                ),
                "key_metrics": self.compact_metrics(
                    stock_data
                ),
                "financial_quality": json.dumps(
                    interpretation,
                    ensure_ascii=False,
                    default=str
                )[:500],
                "valuation_view": (
                    "Review valuation using P/E, P/B, growth, profitability and "
                    "sector context rather than one ratio in isolation."
                ),
                "growth_drivers": [
                    "Revenue growth trend",
                    "Margin stability",
                    "Sector demand cycle"
                ],
                "risks": [
                    "Earnings disappointment",
                    "Valuation compression",
                    "Sector or macro slowdown"
                ],
                "analyst_takeaway": (
                    "Suitable for shortlist review only after validating latest "
                    "earnings, valuation and business risk."
                ),
                "sources": item.get(
                    "sources",
                    []
                )
            })

        stock_overview = (
            "This report combines available company fundamentals, market data, "
            "and source-backed context into a structured research view."
        )
        key_insights = [
            "Use the report as a shortlist and validation aid, not as a buy/sell call.",
            "Prioritize companies with stronger profitability, cleaner balance sheets, and resilient growth.",
            "Check valuation comfort against sector peers and expected earnings growth.",
            "Validate the latest quarterly results, management commentary, and exchange filings."
        ]
        current_performance = (
            "Current performance should be judged using price, valuation, "
            "profitability, revenue trend, margin quality, and data freshness."
        )
        risk_assessment = (
            "Key risks include earnings disappointment, valuation compression, "
            "sector slowdown, changing market sentiment, and incomplete source coverage."
        )
        valuation_outlook = (
            "Valuation should be interpreted through scenarios rather than a single "
            "target price: compare current multiples with growth durability, ROE, "
            "cash generation, and sector conditions."
        )

        return {
            "report_title": f"Analyst report: {query}",
            "query": query,
            "report_type": "ANALYST_REPORT",
            "executive_summary": (
                "This report combines available market data, company context, "
                "and source-backed research signals into a structured analyst view."
            ),
            "stock_overview": stock_overview,
            "key_insights": key_insights,
            "current_performance": current_performance,
            "risk_assessment": risk_assessment,
            "valuation_outlook": valuation_outlook,
            "research_view": (
                "Neutral research view until the latest filings, valuation, "
                "growth trend, and risk profile are validated."
            ),
            "source_quality": {
                "source_count": len(sources_used),
                "quality_view": (
                    "Source confidence improves when company filings, exchange "
                    "data, and reputable market sources are available."
                )
            },
            "sector_context": (
                "Sector context should be validated against current demand, "
                "earnings revisions, margins, and macro conditions."
            ),
            "companies": companies,
            "comparative_view": (
                "Compare companies on quality, valuation, growth durability, "
                "balance-sheet risk, and source-backed recent developments."
            ),
            "investment_view": (
                "Use this as a research starting point, not a buy/sell call."
            ),
            "watchlist_triggers": [
                "Quarterly result trend",
                "Margin or ROE movement",
                "Valuation versus growth",
                "Important company disclosures"
            ],
            "key_risks": [
                "Financial data can lag live market conditions.",
                "News and sentiment can change quickly.",
                "Model output should be cross-checked with primary filings."
            ],
            "next_checks": [
                "Read the latest quarterly results.",
                "Compare valuation with sector peers.",
                "Check management commentary and exchange filings."
            ],
            "sources_used": sources_used,
            "confidence_score": confidence_score,
            "confidence_breakdown": confidence_breakdown,
            "disclaimer": (
                "This report is for educational purposes only and is not "
                "investment advice."
            )
        }

    def generate(
        self,
        query: str,
        intelligence: dict | None = None,
        model: str | None = None
    ):

        intelligence = intelligence or {}
        candidates = self.extract_candidates(
            query,
            intelligence
        )
        resolved_companies = self.resolve_candidates(
            candidates
        )

        if not resolved_companies:
            return {
                "success": False,
                "data": None,
                "error": "Could not identify companies for report generation."
            }

        report_inputs = self.fetch_report_inputs(
            resolved_companies
        )
        successful_inputs = [
            item
            for item in report_inputs
            if item.get(
                "success"
            )
        ]

        if not successful_inputs:
            return {
                "success": False,
                "data": None,
                "error": "Insufficient company data for report generation."
            }

        sources_used = list(
            dict.fromkeys(
                source
                for item in successful_inputs
                for source in item.get(
                    "sources",
                    []
                )
                if source
            )
        )
        confidence_result = self.confidence_engine.calculate_confidence(
            retrieval_success_count=len(successful_inputs),
            retrieval_total_count=max(
                len(resolved_companies),
                1
            ),
            resolved_entities=len(resolved_companies),
            requested_entities=max(
                len(candidates),
                1
            ),
            data_fields_present=8,
            expected_data_fields=10,
            llm_parse_success=True,
            schema_validation_success=True,
            trusted_sources_count=len(sources_used),
            total_sources_count=max(
                len(sources_used),
                1
            ),
            query_complexity=self.confidence_engine.detect_query_complexity(
                companies=[
                    item["company"].get(
                        "company_name",
                        ""
                    )
                    for item in successful_inputs
                ],
                has_comparison=len(successful_inputs) > 1,
                has_discovery=not intelligence.get(
                    "companies"
                ),
                has_news="news" in query.lower()
            ),
            ambiguity_detected=False,
            api_failures=len(report_inputs) - len(successful_inputs)
        )

        prompt = f"""
Create a detailed Indian equity analyst report.

Rules:
- Use only the supplied data and source context.
- Do not invent metrics, events, or sources.
- Keep the tone institutional, balanced, and source-grounded.
- Monetary values for Indian companies should be in INR terms when mentioned.
- Return only valid JSON. No markdown.

User query:
{query}

Query intelligence:
{json.dumps(intelligence, indent=2, default=str)}

Company research inputs:
{json.dumps(successful_inputs, indent=2, default=str)}

Return JSON in this exact shape:
{{
  "report_title": "",
  "query": "",
  "report_type": "ANALYST_REPORT",
  "executive_summary": "",
  "stock_overview": "",
  "key_insights": [],
  "current_performance": "",
  "risk_assessment": "",
  "valuation_outlook": "",
  "research_view": "",
  "source_quality": {{
    "source_count": 0,
    "quality_view": ""
  }},
  "sector_context": "",
  "companies": [
    {{
      "company_name": "",
      "ticker": "",
      "business_snapshot": "",
      "key_metrics": {{}},
      "financial_quality": "",
      "valuation_view": "",
      "growth_drivers": [],
      "risks": [],
      "analyst_takeaway": "",
      "sources": []
    }}
  ],
  "comparative_view": "",
  "investment_view": "",
  "watchlist_triggers": [],
  "key_risks": [],
  "next_checks": [],
  "sources_used": [],
  "confidence_score": 0.0,
  "disclaimer": ""
}}

Field guidance:
- stock_overview: 1 rich paragraph similar to a professional stock overview.
- key_insights: 5-7 specific bullets based only on supplied data/context.
- current_performance: price/fundamental performance paragraph using available metrics.
- risk_assessment: balanced risk paragraph, no alarmism.
- valuation_outlook: scenario-based valuation/outlook paragraph, no invented target prices.
- research_view: one of "Positive", "Neutral", or "Cautious" plus a short reason. Do not say Buy/Sell/Hold.
- source_quality: explain source count and whether the report is strongly or lightly sourced.
"""

        raw_response = self.groq.generate_raw(
            prompt=prompt,
            temperature=0.2,
            max_tokens=2600,
            model=model or settings.GROQ_COMPLEX_MODEL
        )

        parsed = None
        llm_success = True

        if is_provider_error_text(
            raw_response
        ):
            return {
                "success": False,
                "data": None,
                "error": raw_response
            }

        parsed = JSONParser.parse(
            raw_response
        )

        if not parsed:
            llm_success = False
            parsed = self.build_fallback_report(
                query=query,
                report_inputs=successful_inputs,
                sources_used=sources_used,
                confidence_score=confidence_result["confidence_score"],
                confidence_breakdown=confidence_result["breakdown"]
            )

        parsed["query"] = query
        parsed["report_type"] = "ANALYST_REPORT"
        parsed["sources_used"] = sources_used
        parsed.setdefault(
            "stock_overview",
            parsed.get(
                "executive_summary",
                ""
            )
        )
        parsed.setdefault(
            "key_insights",
            []
        )
        parsed.setdefault(
            "current_performance",
            ""
        )
        parsed.setdefault(
            "risk_assessment",
            ""
        )
        parsed.setdefault(
            "valuation_outlook",
            parsed.get(
                "comparative_view",
                ""
            )
        )
        parsed.setdefault(
            "research_view",
            parsed.get(
                "investment_view",
                "Neutral research view; validate the latest filings and risk profile."
            )
        )
        parsed.setdefault(
            "source_quality",
            {
                "source_count": len(sources_used),
                "quality_view": "Source quality depends on the reliability and freshness of retrieved links."
            }
        )
        parsed["confidence_score"] = confidence_result[
            "confidence_score"
        ]
        parsed["confidence_breakdown"] = confidence_result[
            "breakdown"
        ]
        parsed.setdefault(
            "disclaimer",
            "This report is for educational purposes only and is not investment advice."
        )

        try:
            validated = ReportResponse(
                **parsed
            )

            return {
                "success": True,
                "data": validated.model_dump(),
                "error": None
            }

        except Exception:
            logger.exception(
                "report_schema_validation_failed query=%r llm_success=%s",
                query,
                llm_success
            )

            fallback = self.build_fallback_report(
                query=query,
                report_inputs=successful_inputs,
                sources_used=sources_used,
                confidence_score=confidence_result["confidence_score"],
                confidence_breakdown=confidence_result["breakdown"]
            )

            validated = ReportResponse(
                **fallback
            )

            return {
                "success": True,
                "data": validated.model_dump(),
                "error": None
            }
