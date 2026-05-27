from pydantic import BaseModel
from typing import Optional


class RouterResponse(BaseModel):

    route: str

    confidence: float

    reasoning: Optional[str] = None