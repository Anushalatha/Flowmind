from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, JSON, Boolean as SQLAlchemyBoolean
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings
from datetime import datetime
import os

Base = declarative_base()

class WorkflowRecord(Base):
    __tablename__ = "workflows"
    id = Column(String, primary_key=True, index=True)
    user_request = Column(Text, nullable=False)
    status = Column(String, nullable=False)
    state_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class EventRecord(Base):
    __tablename__ = "execution_events"
    id = Column(String, primary_key=True, index=True)
    workflow_id = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String)
    step_id = Column(String, nullable=True)
    agent_id = Column(String, nullable=True)
    tool_name = Column(String, nullable=True)
    status = Column(String)
    metadata_json = Column(JSON, default=dict)

class BenchmarkRunRecord(Base):
    __tablename__ = "benchmark_runs"
    id = Column(String, primary_key=True, index=True)
    suite_version = Column(String, nullable=False)
    mode = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    total_cases = Column(Integer, nullable=False)
    passed_cases = Column(Integer, nullable=False)
    failed_cases = Column(Integer, nullable=False)
    skipped_cases = Column(Integer, nullable=False)
    metrics_json = Column(JSON, default=dict)
    provider_config_json = Column(JSON, default=dict)
    environment_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class BenchmarkCaseResult(Base):
    __tablename__ = "benchmark_case_results"
    id = Column(String, primary_key=True, index=True)
    benchmark_run_id = Column(String, index=True)
    case_id = Column(String, nullable=False)
    category = Column(String, nullable=False)
    status = Column(String, nullable=False)
    workflow_id = Column(String, nullable=True)
    latency_seconds = Column(Integer, nullable=True)  # Stores milliseconds for precision, reported as seconds
    error_message = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=True)
    expected_status = Column(String, nullable=False)
    actual_status = Column(String, nullable=True)
    output_correct = Column(SQLAlchemyBoolean, nullable=True)
    execution_trace_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

# Ensure data directory exists for SQLite
if "sqlite" in settings.DB_URL and "data/" in settings.DB_URL:
    db_path = settings.DB_URL.replace("sqlite:////", "")
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    settings.DB_URL, connect_args={"check_same_thread": False} if "sqlite" in settings.DB_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
