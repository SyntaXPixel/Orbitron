from typing import List, Optional
from pydantic import BaseModel, ConfigDict

class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    message: str

class ApiErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    details: List[ErrorDetail] = []
    request_id: str

class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: ApiErrorBody
