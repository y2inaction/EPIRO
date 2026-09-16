"""EPIRO FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.config import settings
from app.database import engine
from app.models import Base
from app.api import health, auth, users, organisations, evidence, stories, questions

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting EPIRO API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug: {settings.debug}")

    # Create tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")

    yield

    # Shutdown
    logger.info("Shutting down EPIRO API")


# Create FastAPI app
app = FastAPI(
    title="EPIRO API",
    description="Evidence, Public Information, Engagement, Intelligence & Readiness Operating System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request, exc):
    """Handle SQLAlchemy errors."""
    logger.error(f"Database error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Database error occurred"},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(organisations.router, prefix="/api/v1/organisations", tags=["Organisations"])
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence"])
app.include_router(stories.router, prefix="/api/v1/stories", tags=["Stories"])
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "EPIRO API",
        "version": "1.0.0",
        "description": "Evidence, Public Information, Engagement, Intelligence & Readiness Operating System",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        workers=settings.api_workers if not settings.debug else 1,
    )
