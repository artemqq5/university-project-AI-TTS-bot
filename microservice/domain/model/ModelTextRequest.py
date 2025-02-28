from pydantic import BaseModel


class ModelTextRequest(BaseModel):
    text: str
