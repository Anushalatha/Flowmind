import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as workflow_router
from app.api.benchmark_endpoints import router as benchmark_router
from app.persistence.database import init_db
import app.tools.builtins

app = FastAPI(title="FlowMind API", description="Agentic Workflow Orchestration Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(workflow_router, prefix="/api")
app.include_router(benchmark_router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "healthy"}
