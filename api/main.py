from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings
from api.routers import (
    health,
    governance,
    districts,
    jobs,
    skills,
    search,
    exports,
    ai_service,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.4.0",
    description="Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(governance.router)
app.include_router(districts.router)
app.include_router(jobs.router)
app.include_router(skills.router)
app.include_router(search.router)
app.include_router(exports.router)
app.include_router(ai_service.router)


@app.get("/")
def root():
    return {
        "message": "Welcome to Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform API",
        "docs": "/docs",
        "health": "/api/v1/health",
        "endpoints": [
            "/api/v1/governance/policies",
            "/api/v1/governance/health",
            "/api/v1/districts/",
            "/api/v1/districts/divisions",
            "/api/v1/districts/demand",
            "/api/v1/jobs/stats",
            "/api/v1/skills/demand",
            "/api/v1/skills/supply",
            "/api/v1/skills/velocity",
            "/api/v1/search?q=",
            "/api/v1/exports/skill-demand",
            "/api/v1/ai/ask?q=",
        ]
    }