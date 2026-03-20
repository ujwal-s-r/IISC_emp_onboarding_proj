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
