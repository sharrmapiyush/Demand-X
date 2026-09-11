from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.config import settings
from api.routers import health

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.2.0",
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


@app.get("/")
def root():
    return {
        "message": "Welcome to Maharashtra Labour-Market Intelligence & Curriculum-Alignment Platform API",
        "docs": "/docs",
        "health": "/api/v1/health"
    }
