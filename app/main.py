from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.utils.logger import logger
from app.utils.exceptions import AdaptIQException
from app.config import settings
from app.api.routers import employer, employee
from app.api.routers.websocket import router as websocket_router
from app.db.session import engine, Base

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://frontend:3000",   # Docker service name
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(employer.router, prefix="/api/v1")
app.include_router(employee.router, prefix="/api/v1")
app.include_router(websocket_router)

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

