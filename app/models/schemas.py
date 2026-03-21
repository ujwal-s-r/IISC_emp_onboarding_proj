from pydantic import BaseModel, Field
from typing import List, Optional

class SkillBase(BaseModel):
    skill_name: str
    target_mastery: float
    team_relevance: float = 0.0
    priority_tier: str
    reasoning: Optional[str] = None

class RoleBase(BaseModel):
    title: str
    seniority: str
    jd_text: str

class RoleCreate(RoleBase):
    pass

class RoleResponse(RoleBase):
    id: str
    status: str
    target_skills: List[SkillBase] = []

    class Config:
        from_attributes = True

class RelevanceSignalBase(BaseModel):
    skill_name: str
    recency_category: str
    computed_relevance: float
    assigned_tier: str

class RoleFullResponse(RoleResponse):
    relevance_signals: List[RelevanceSignalBase] = []

class WebSocketMessage(BaseModel):
    step: str
    status: str # in_progress, completed, failed
    message: str
    data: Optional[dict] = None

class EmployeeBase(BaseModel):
    role_id: str
    status: str

class LearningPathResponse(BaseModel):
    skill_name: str
    tier: str
    course_title: Optional[str]
    course_url: Optional[str]
    reasoning_trace: Optional[str]
    sequence_order: int

    class Config:
        from_attributes = True

class EmployeeResponse(EmployeeBase):
    id: str
    resume_text: Optional[str] = None
    learning_paths: List[LearningPathResponse] = []

    class Config:
        from_attributes = True

