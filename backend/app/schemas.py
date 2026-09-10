from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    report_id: str = Field(..., min_length=4, description="ID returned by /upload")
    question: str = Field(..., min_length=2, max_length=1000)
