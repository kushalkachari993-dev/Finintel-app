from pydantic import BaseModel
from typing import List
from typing import Optional
from typing import Dict
from typing import Any


class DiscoveryResponse(BaseModel):

    query_type: str

    summary: str

    key_points: List[str]

    mentioned_companies: List[str]

    confidence_score: float

    confidence_breakdown: Optional[Dict[str, Any]] = None

    sources_used: List[str]
