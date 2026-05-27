import csv
import re
from dataclasses import dataclass
from pathlib import Path

from backend.config.settings import SYMBOL_MASTER_PATH


@dataclass(frozen=True)
class CompanySymbol:
    symbol: str
    exchange: str
    yahoo_ticker: str
    company_name: str
    aliases: tuple[str, ...]
    sector: str | None = None


class SymbolRegistry:
    """Local symbol master for deterministic company/entity matching."""

    GENERIC_ALIASES = {
        "best",
        "buy",
        "current",
        "hold",
        "india",
        "it",
        "latest",
        "market",
        "price",
        "sell",
        "share",
        "stock",
        "top",
        "what",
        "which",
    }

    def __init__(self, csv_path: str | Path = SYMBOL_MASTER_PATH):
        self.csv_path = Path(csv_path)
        self._companies = self._load_companies()
        self._alias_index = self._build_alias_index()

    def _load_companies(self) -> list[CompanySymbol]:
        if not self.csv_path.exists():
            return []

        with self.csv_path.open(newline="", encoding="utf-8") as file:
            rows = csv.DictReader(file)
            companies = [
                CompanySymbol(
                    symbol=row["symbol"].strip(),
                    exchange=row.get("exchange", "NSE").strip() or "NSE",
                    yahoo_ticker=row["yahoo_ticker"].strip(),
                    company_name=row["company_name"].strip(),
                    aliases=tuple(
                        alias.strip()
                        for alias in row.get("aliases", "").split("|")
                        if alias.strip()
                    ),
                    sector=(row.get("sector") or "").strip() or None,
                )
                for row in rows
                if row.get("symbol") and row.get("yahoo_ticker") and row.get("company_name")
            ]
            return sorted(
                companies,
                key=lambda company: (
                    0 if company.exchange.upper() == "NSE" else 1,
                    company.company_name,
                ),
            )

    def _build_alias_index(self) -> list[tuple[str, CompanySymbol]]:
        aliases: list[tuple[str, CompanySymbol]] = []

        for company in self._companies:
            names = {
                company.symbol,
                company.company_name,
                company.yahoo_ticker.replace(".NS", ""),
                *company.aliases,
            }
            for name in names:
                normalized = self.normalize(name)
                if normalized and normalized not in self.GENERIC_ALIASES:
                    aliases.append((normalized, company))

        return sorted(aliases, key=lambda item: len(item[0]), reverse=True)

    @staticmethod
    def normalize(text: str | None) -> str:
        if text is None:
            return ""

        normalized = re.sub(r"[^a-z0-9&]+", " ", str(text).lower())
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _alias_match(query: str, alias: str) -> re.Match | None:
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        return re.search(pattern, query)

    def find_mentions(self, query: str) -> list[CompanySymbol]:
        normalized_query = self.normalize(query)
        candidates: list[tuple[int, int, int, CompanySymbol]] = []

        for alias, company in self._alias_index:
            match = self._alias_match(normalized_query, alias)
            if match:
                exchange_rank = 0 if company.exchange.upper() == "NSE" else 1
                candidates.append((match.start(), match.end(), -len(alias), exchange_rank, company))

        candidates.sort(key=lambda item: (item[0], item[2], item[3]))

        matches: list[CompanySymbol] = []
        seen: set[str] = set()
        occupied_spans: list[tuple[int, int]] = []

        for start, end, _, _, company in candidates:
            company_key = self.normalize(company.company_name)
            overlaps = any(start < used_end and end > used_start for used_start, used_end in occupied_spans)

            if company_key in seen or overlaps:
                continue

            matches.append(company)
            seen.add(company_key)
            occupied_spans.append((start, end))

        return matches

    def extract_company_names(self, query: str) -> list[str]:
        return [company.company_name for company in self.find_mentions(query)]

    def resolve_company(self, name_or_query: str) -> CompanySymbol | None:
        normalized = self.normalize(name_or_query)

        for company in self._companies:
            exact_names = {
                self.normalize(company.symbol),
                self.normalize(company.company_name),
                self.normalize(company.yahoo_ticker.replace(".NS", "")),
                *(self.normalize(alias) for alias in company.aliases),
            }
            if normalized in exact_names:
                return company

        matches = self.find_mentions(name_or_query)
        return matches[0] if matches else None

    def to_ticker_result(self, company: CompanySymbol, confidence: float = 0.97) -> dict:
        return {
            "ticker": company.yahoo_ticker,
            "company_name": company.company_name,
            "exchange": company.exchange,
            "confidence": confidence,
        }
