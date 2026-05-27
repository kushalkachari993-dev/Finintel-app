from backend.intelligence.query_intelligence import (
    QueryIntelligence
)

engine = QueryIntelligence()

result = engine.extract(
    "Compare fundamentally strong undervalued IT companies for long term investment"
)

print(result)