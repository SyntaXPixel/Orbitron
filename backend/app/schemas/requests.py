from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator
from app.schemas.public import Priority

class LoginRequest(BaseModel):
    email: str
    password: str

class JobCreateRequest(BaseModel):
    satellite_id: str
    data_bytes: int = Field(..., ge=1, le=1_000_000_000_000)
    deadline_at: str
    priority: Priority
    allow_split: bool

class ScheduleRunRequest(BaseModel):
    algorithm: Literal["optimized"]
    expected_schedule_version: int

class DisruptionEventRequest(BaseModel):
    type: Literal["rain", "station_outage", "station_recovery"]
    station_id: str
    capacity_factor: Optional[float] = None
    expected_schedule_version: int

    @field_validator("capacity_factor")
    @classmethod
    def validate_capacity_factor(cls, v, info):
        event_type = info.data.get("type")
        if event_type == "rain":
            if v is None or not (0.0 <= v <= 1.0):
                raise ValueError("capacity_factor is required and must be between 0.0 and 1.0 for rain events")
        else:
            if v is not None:
                raise ValueError("capacity_factor must be null for station_outage and station_recovery")
        return v

class SimulationActionRequest(BaseModel):
    action: Literal["pause", "resume", "step", "reset"]
    step_seconds: Optional[int] = None
    seed: Optional[int] = None

    @field_validator("step_seconds")
    @classmethod
    def validate_step(cls, v, info):
        action = info.data.get("action")
        if action == "step":
            if v is None or v <= 0 or v > 60:
                raise ValueError("step_seconds must be between 1 and 60 simulation seconds")
        return v

    @field_validator("seed")
    @classmethod
    def validate_seed(cls, v, info):
        action = info.data.get("action")
        if action == "reset":
            if v is None:
                raise ValueError("seed is required for reset action")
        return v

class TransferCreateRequest(BaseModel):
    contact_id: str

class SecurityCheckRequest(BaseModel):
    test_case: Literal["expired_authorization", "wrong_station", "tampered_payload"]
    contact_id: Optional[str] = None

class EvaluationCreateRequest(BaseModel):
    scenario_id: str
