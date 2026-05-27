from pydantic import BaseModel
from pydantic import Field
from typing import List
from typing import Optional


class EducationalResponse(BaseModel):

    topic: str

    simple_definition: str

    detailed_explanation: str

    why_it_matters: str

    practical_interpretation: str

    limitations: str

    example: str

    confidence_score: float

    disclaimer: str

    sources_used: Optional[List[str]] = Field(
        default_factory=list
    )
