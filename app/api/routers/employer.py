from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.domain import Role
from app.models.schemas import RoleResponse
from app.utils.logger import logger
import uuid

router = APIRouter(prefix="/employer", tags=["Employer"])

@router.post("/setup-role", response_model=RoleResponse)
async def setup_role(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    seniority: str = Form(...),
    jd_file: Optional[UploadFile] = File(None),
    jd_text: Optional[str] = Form(None),
    team_context_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Generate unique Role ID
    role_id = f"role_{uuid.uuid4().hex[:8]}"
    logger.info(f"Phase 1: Initializing role setup for: {title} | ID: {role_id}")

    # 2. Basic processing (Placeholder for PDF parsing in Phase 2)
    ext_jd_text = jd_text if jd_text else "Pending PDF Extraction"
    ext_team_text = "Pending PDF Extraction"

    # 3. Create Role record in SQLite
    db_role = Role(
        id=role_id,
        title=title,
        seniority=seniority,
        jd_text=ext_jd_text,
        team_context_text=ext_team_text,
        status="pending"
    )
    
    try:
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        logger.info(f"Phase 1: Role record created successfully in root DB.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create role: {str(e)}")
        raise 

    # In Phase 2, we will add the background_task to process the files
    return db_role

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: Session = Depends(get_db)):
    return db.query(Role).all()

