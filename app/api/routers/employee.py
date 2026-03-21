from fastapi import APIRouter, UploadFile, File, Form, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.db.session import get_db, AsyncSessionLocal
from app.models.domain import Employee, Role
from app.models.schemas import EmployeeResponse
from app.utils.logger import logger
import uuid

router = APIRouter(prefix="/employee", tags=["Employee"])


async def _run_employee_orchestrator(
    employee_id: str,
    role_id: str,
    resume_bytes: bytes,
):
    """
    Background task wrapper for employee onboarding pipeline.
    """
    async with AsyncSessionLocal() as db:
        try:
            # Here we will later call `orchestrate_employee_flow`
            logger.info(f"Background task started for employee {employee_id}")
            pass
        except Exception as e:
            logger.error(f"Orchestrator failed for employee {employee_id}: {e}")
            from sqlalchemy import update as sql_update
            await db.execute(
                sql_update(Employee).where(Employee.id == employee_id).values(status="failed")
            )
            await db.commit()


@router.post("/onboard-path", response_model=EmployeeResponse)
async def onboard_path(
    background_tasks: BackgroundTasks,
    role_id: str = Form(...),
    resume_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Standard format: emp_uuid
    employee_id = f"emp_{uuid.uuid4().hex[:8]}"
    logger.info(f"Initializing employee onboarding against role '{role_id}' | ID: {employee_id}")

    # Validate role exists
    from sqlalchemy import select
    role = await db.execute(select(Role).where(Role.id == role_id))
    if not role.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Role {role_id} not found.")

    # Read bytes *now* (UploadFile is closed once response is sent)
    resume_bytes = await resume_file.read()

    # Create pending employee record
    db_employee = Employee(
        id=employee_id,
        role_id=role_id,
        resume_text="Processing…",
        status="pending",
    )
    try:
        db.add(db_employee)
        await db.commit()
        await db.refresh(db_employee)
        logger.info(f"Employee record created: {employee_id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create employee record: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Kick off the full pipeline in the background
    background_tasks.add_task(
        _run_employee_orchestrator,
        employee_id=employee_id,
        role_id=role_id,
        resume_bytes=resume_bytes,
    )

    return {
        "id": db_employee.id,
        "role_id": db_employee.role_id,
        "status": db_employee.status,
        "resume_text": db_employee.resume_text,
        "learning_paths": []
    }


@router.get("/employees", response_model=List[EmployeeResponse])
async def list_employees(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Employee).options(selectinload(Employee.learning_paths))
    )
    return result.scalars().all()


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Employee)
        .options(selectinload(Employee.learning_paths))
        .where(Employee.id == employee_id)
    )
    employee = result.scalar_one_or_none()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee
