from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.utils.logger import logger
from app.utils.exceptions import AdaptIQException
from app.config import settings

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

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

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("AdaptIQ Backend is shutting down...")

