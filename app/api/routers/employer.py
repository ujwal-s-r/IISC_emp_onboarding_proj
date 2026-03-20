from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_db, AsyncSessionLocal
from app.models.domain import Role
from app.models.schemas import RoleResponse, RoleFullResponse
from app.services.employer_flow.orchestrator import orchestrate_employer_flow
from app.utils.logger import logger
import uuid

router = APIRouter(prefix="/employer", tags=["Employer"])


async def _run_orchestrator(
    role_id: str,
    jd_bytes: bytes,
    team_bytes: bytes,
    seniority: str,
):
    """
    Background task wrapper.
    Creates its own AsyncSession so the orchestrator can persist results
    independently after the HTTP response has already been sent.
    """
    async with AsyncSessionLocal() as db:
        try:
            await orchestrate_employer_flow(
                role_id=role_id,
                jd_bytes=jd_bytes,
                team_bytes=team_bytes,
                assumed_seniority=seniority,
                db=db,
            )
        except Exception as e:
            logger.error(f"Orchestrator failed for role {role_id}: {e}")
            from sqlalchemy import update as sql_update
            await db.execute(
                sql_update(Role).where(Role.id == role_id).values(status="failed")
            )
            await db.commit()


@router.post("/setup-role", response_model=RoleResponse)
async def setup_role(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    seniority: str = Form(...),
    jd_file: Optional[UploadFile] = File(None),
    jd_text: Optional[str] = Form(None),
    team_context_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    role_id = f"role_{uuid.uuid4().hex[:8]}"
    logger.info(f"Initializing role setup: '{title}' | ID: {role_id}")

    # Read bytes *now* (UploadFile is closed once response is sent)
    jd_bytes   = await jd_file.read() if jd_file else (jd_text or "").encode()
    team_bytes = await team_context_file.read()

    # Create pending role record
    db_role = Role(
        id=role_id,
        title=title,
        seniority=seniority,
        jd_text="Processing…",
        team_context_text="Processing…",
        status="pending",
    )
    try:
        db.add(db_role)
        await db.commit()
        await db.refresh(db_role)
        logger.info(f"Role record created: {role_id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create role record: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Kick off the full pipeline in the background
    background_tasks.add_task(
        _run_orchestrator,
        role_id=role_id,
        jd_bytes=jd_bytes,
        team_bytes=team_bytes,
        seniority=seniority,
    )

    return db_role


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(Role))
    return result.scalars().all()


@router.get("/roles/{role_id}", response_model=RoleFullResponse)
async def get_role(role_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role
