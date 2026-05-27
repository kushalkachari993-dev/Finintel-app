import csv
import re
import urllib.request
from pathlib import Path


SOURCE_URL = "http://content.indiainfoline.com/IIFLTT/Scripmaster.csv"
OUTPUT_PATH = Path("data/market/indian_equities.csv")

OUTPUT_FIELDS = [
    "symbol",
    "exchange",
    "yahoo_ticker",
    "company_name",
    "aliases",
    "sector",
    "isin",
    "scrip_code",
    "source",
]

SPECIAL_OVERRIDES = {
    "TCS": {
        "company_name": "TCS",
        "aliases": ["Tata Consultancy Services", "Tata Consultancy Services Limited"],
    },
    "INFY": {
        "company_name": "Infosys",
        "aliases": ["Infy", "Infosys Limited"],
    },
    "HDFCBANK": {
        "company_name": "HDFC Bank",
        "aliases": ["HDFC", "HDFC Bank Limited"],
    },
    "ICICIBANK": {
        "company_name": "ICICI Bank",
        "aliases": ["ICICI", "ICICI Bank Limited"],
    },
    "SBIN": {
        "company_name": "State Bank of India",
        "aliases": ["SBI", "State Bank"],
    },
    "RELIANCE": {
        "company_name": "Reliance Industries",
        "aliases": ["Reliance", "Reliance Industries Limited"],
    },
    "ASIANPAINT": {
        "company_name": "Asian Paints",
        "aliases": ["Asian Paints Limited"],
    },
    "TITAN": {
        "company_name": "Titan Company",
        "aliases": ["Titan", "Titan Company Limited"],
    },
    "BAJFINANCE": {
        "company_name": "Bajaj Finance",
        "aliases": ["Bajaj Finance Limited"],
    },
    "WIPRO": {
        "company_name": "Wipro",
        "aliases": ["Wipro Limited"],
    },
}


def clean_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9&-]", "", symbol.upper().strip())


def clean_company_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name.replace("&AMP;", "&")).strip()
    cleaned = re.sub(r"\bLTD\.?$", "LIMITED", cleaned, flags=re.IGNORECASE)
    title = cleaned.title()
    replacements = {
        "Hdfc": "HDFC",
        "Icici": "ICICI",
        "Idbi": "IDBI",
        "Idfc": "IDFC",
        "Ifci": "IFCI",
        "Lic": "LIC",
        "Nmdc": "NMDC",
        "Ntpc": "NTPC",
        "Ongc": "ONGC",
        "Sbi": "SBI",
        "Uti": "UTI",
        " Of ": " of ",
        " And ": " and ",
    }
    for old, new in replacements.items():
        title = title.replace(old, new)
    return title


def simplified_alias(name: str) -> str:
    alias = re.sub(
        r"\b(LIMITED|LTD|PRIVATE|PVT|CORPORATION)\b\.?",
        "",
        name,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", alias).strip()


def yahoo_ticker(exchange: str, symbol: str, scrip_code: str) -> str:
    if exchange == "NSE":
        return f"{symbol}.NS"
    return f"{scrip_code}.BO"


def normalize_exchange(exchange: str) -> str:
    return "NSE" if exchange == "N" else "BSE"


def is_supported_equity(row: dict) -> bool:
    name = row.get("Name", "").upper()
    full_name = row.get("FullName", "").upper()
    isin = row.get("ISIN", "").upper()

    return (
        row.get("ExchType") == "C"
        and row.get("Series") == "EQ"
        and row.get("AllowedToTrade") == "Y"
        and not name.endswith("INAV")
        and "TEST" not in name
        and not full_name.startswith("INAV")
        and "MUTUAL FUND" not in full_name
        and " ETF" not in full_name
        and not isin.startswith("DUMMY")
    )


def build_aliases(
    symbol: str,
    company_name: str,
    official_name: str,
    extra_aliases: list[str] | None = None,
) -> str:
    aliases = {
        symbol,
        company_name,
        official_name,
        simplified_alias(official_name),
    }
    aliases.update(extra_aliases or [])
    aliases.discard("")
    return "|".join(sorted(aliases))


def row_to_symbol_master(row: dict) -> dict:
    exchange = normalize_exchange(row["Exch"])
    symbol = clean_symbol(row["Name"])
    official_name = clean_company_name(row["FullName"])
    company_name = simplified_alias(official_name)
    scrip_code = row["Scripcode"].strip()
    override = SPECIAL_OVERRIDES.get(symbol, {})
    company_name = override.get("company_name", company_name)
    extra_aliases = override.get("aliases", [])

    return {
        "symbol": symbol,
        "exchange": exchange,
        "yahoo_ticker": yahoo_ticker(exchange, symbol, scrip_code),
        "company_name": company_name,
        "aliases": build_aliases(symbol, company_name, official_name, extra_aliases),
        "sector": "",
        "isin": row.get("ISIN", "").strip(),
        "scrip_code": scrip_code,
        "source": "IIFL_SCRIPMASTER",
    }


def fetch_rows() -> list[dict]:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "finintel-ai-symbol-master/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        text = response.read().decode("utf-8-sig")

    return list(csv.DictReader(text.splitlines()))


def main() -> None:
    rows = [
        row_to_symbol_master(row)
        for row in fetch_rows()
        if is_supported_equity(row)
    ]
    rows.sort(
        key=lambda row: (
            0 if row["exchange"] == "NSE" else 1,
            row["company_name"],
            row["symbol"],
        )
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} symbols to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
