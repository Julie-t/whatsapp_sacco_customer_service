from pydantic import BaseModel


class AICompletionRequest(BaseModel):
    message: str


class AICompletionResponse(BaseModel):
    response: str
