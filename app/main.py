from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from app.utils.logger import logger
from app.utils.exceptions import AdaptIQException
from app.config import settings
from app.api.routers import employer
from app.api.routers.websocket import manager
from app.db.session import engine, Base

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

# Mount Routers
app.include_router(employer.router, prefix="/api/v1")

@app.exception_handler(AdaptIQException)
async def adaptiq_exception_handler(request: Request, exc: AdaptIQException):
    logger.error(f"Application Error: {exc.message} | Details: {exc.details}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "status": exc.status_code,
            "details": exc.details
        }
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

@app.websocket("/ws/employer/{session_id}")
async def employer_websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(session_id, websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)

@app.on_event("startup")
async def startup_event():
    logger.info("AdaptIQ Backend is starting up...")
    # Initialize Database Tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AdaptIQ Backend is shutting down...")

