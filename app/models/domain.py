from sqlalchemy import Column, String, Float, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from app.db.session import Base
from datetime import datetime

class Role(Base):
    __tablename__ = "roles"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, index=True)
    seniority = Column(String) # Junior, Mid, Senior, Lead
    jd_text = Column(String, nullable=True)
    team_context_text = Column(String, nullable=True)
    status = Column(String, default="pending") # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)

    target_skills = relationship("TargetSkill", back_populates="role", cascade="all, delete-orphan")
    relevance_signals = relationship("TeamRelevanceSignal", back_populates="role", cascade="all, delete-orphan")
    curated_resources = relationship("CuratedResource", back_populates="role", cascade="all, delete-orphan")

class TargetSkill(Base):
    __tablename__ = "target_skills"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(String, ForeignKey("roles.id"))
    skill_name = Column(String, index=True)
    canonical_id = Column(String, nullable=True)
    target_mastery = Column(Float)
    knowledge_category = Column(String, nullable=True) # framework, language, platform, concept
    team_relevance = Column(Float, default=0.0)
    priority_tier = Column(String, default="T4")
    reasoning = Column(String, nullable=True)

    role = relationship("Role", back_populates="target_skills")

class TeamRelevanceSignal(Base):
    __tablename__ = "team_relevance_signals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(String, ForeignKey("roles.id"))
    skill_name = Column(String, index=True)
    recency_category = Column(String) # current_project, past_project, general
    computed_relevance = Column(Float) # 0.0 to 1.0
    assigned_tier = Column(String) # T1, T2, T3, T4

    role = relationship("Role", back_populates="relevance_signals")

class CuratedResource(Base):
    __tablename__ = "curated_resources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    role_id = Column(String, ForeignKey("roles.id"))
    title = Column(String)
    url = Column(String, nullable=True)
    content_chunk = Column(String, nullable=True)
    vector_id = Column(String, nullable=True)

    role = relationship("Role", back_populates="curated_resources")

class GraphExpansion(Base):
    __tablename__ = "graph_expansions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    skill_name = Column(String, index=True)
    parent_skills = Column(JSON) # List of inferred prerequisites
    source_role_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class Employee(Base):
    __tablename__ = "employees"

    id = Column(String, primary_key=True, index=True)
    role_id = Column(String, ForeignKey("roles.id"))
    resume_text = Column(String, nullable=True)
    career_timeline = Column(JSON, nullable=True) # Full parsed JSON from LLM
    status = Column(String, default="pending") # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)

    role = relationship("Role")
    mastery_scores = relationship("EmployeeMastery", back_populates="employee", cascade="all, delete-orphan")
    learning_paths = relationship("LearningPath", back_populates="employee", cascade="all, delete-orphan")

class EmployeeMastery(Base):
    __tablename__ = "employee_mastery"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.id"))
    skill_name = Column(String, index=True)
    canonical_id = Column(String, nullable=True)
    current_mastery = Column(Float)
    assessment_reasoning = Column(String, nullable=True)

    employee = relationship("Employee", back_populates="mastery_scores")

class LearningPath(Base):
    __tablename__ = "learning_paths"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(String, ForeignKey("employees.id"))
    skill_name = Column(String, index=True)
    canonical_id = Column(String, nullable=True)
    tier = Column(String) # From the employer Role's target
    course_title = Column(String, nullable=True)
    course_url = Column(String, nullable=True)
    reasoning_trace = Column(String, nullable=True)
    sequence_order = Column(Integer) # For DAG/Topological order

    employee = relationship("Employee", back_populates="learning_paths")
