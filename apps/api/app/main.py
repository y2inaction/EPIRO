"""EPIRO FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api import auth, evidence, health, organisations, questions, search, stories, users
from app.config import settings
from app.rate_limit import RateLimitExceeded, limiter, rate_limit_exceeded_handler

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

EPIRO_DESCRIPTION = (
    "Evidence, Public Information, Engagement, Intelligence & " "Readiness Operating System"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting EPIRO API")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug: {settings.debug}")
    # Schema is owned by Alembic. The application never creates tables: doing
    # so silently diverged deployed databases from the migration history.

    yield

    # Shutdown
    logger.info("Shutting down EPIRO API")


# Create FastAPI app
app = FastAPI(
    title="EPIRO API",
    description=EPIRO_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan,
)

# Rate limiting. slowapi reads the limiter from application state.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

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
app.include_router(
    organisations.router,
    prefix="/api/v1/organisations",
    tags=["Organisations"],
)
app.include_router(evidence.router, prefix="/api/v1/evidence", tags=["Evidence"])
app.include_router(stories.router, prefix="/api/v1/stories", tags=["Stories"])
app.include_router(questions.router, prefix="/api/v1/questions", tags=["Questions"])
app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "EPIRO API",
        "version": "1.0.0",
        "description": EPIRO_DESCRIPTION,
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
