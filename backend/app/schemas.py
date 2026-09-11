from pydantic import BaseModel, Field


# body schema for /ask. min_length on question stops the llm getting "" and
# rambling, max_length keeps the prompt cheap.
class AskRequest(BaseModel):
    report_id: str = Field(..., min_length=4, description="ID returned by /upload")
    question: str = Field(..., min_length=2, max_length=1000)
