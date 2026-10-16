from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from sse_starlette.sse import EventSourceResponse
import asyncio
from pydantic import BaseModel
from typing import Dict, Any, List
from app.orchestrator.engine import engine
from app.persistence.database import SessionLocal, WorkflowRecord, EventRecord
from sqlalchemy import func
import json

router = APIRouter()

class WorkflowRequest(BaseModel):
    request: str

class WorkflowResponse(BaseModel):
    workflow_id: str
    status: str

@router.post("/workflows", response_model=WorkflowResponse)
async def create_workflow(req: WorkflowRequest):
    workflow_id = engine.new_workflow(req.request)
    return WorkflowResponse(workflow_id=workflow_id, status="started")

@router.get("/workflows")
def list_workflows():
    with SessionLocal() as db:
        records = db.query(WorkflowRecord).order_by(WorkflowRecord.created_at.desc()).limit(50).all()
        return [{"workflow_id": r.id, "status": r.status, "user_request": r.user_request} for r in records]

@router.get("/workflows/{workflow_id}")
def get_workflow(workflow_id: str):
    with SessionLocal() as db:
        record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Workflow not found")
        return record.state_json

@router.get("/workflows/{workflow_id}/events")
def get_workflow_events(workflow_id: str):
    with SessionLocal() as db:
        records = db.query(EventRecord).filter(EventRecord.workflow_id == workflow_id).order_by(EventRecord.timestamp.asc()).all()
        return [{
            "event_id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "event_type": r.event_type,
            "step_id": r.step_id,
            "agent_id": r.agent_id,
            "tool_name": r.tool_name,
            "status": r.status,
            "metadata": r.metadata_json
        } for r in records]

@router.get("/workflows/{workflow_id}/stream")
async def stream_workflow_events(workflow_id: str, request: Request):
    async def event_generator():
        # First send any historical events for this workflow
        with SessionLocal() as db:
            records = db.query(EventRecord).filter(EventRecord.workflow_id == workflow_id).order_by(EventRecord.timestamp.asc()).all()
            for r in records:
                payload = {
                    "event_id": r.id,
                    "timestamp": r.timestamp.isoformat(),
                    "event_type": r.event_type,
                    "step_id": r.step_id,
                    "agent_id": r.agent_id,
                    "tool_name": r.tool_name,
                    "status": r.status,
                    "metadata": r.metadata_json
                }
                yield json.dumps(payload)

        # Then subscribe to the live queue.
        # Simple polling of the active state/events isn't ideal, but for MVP we can tap into a pub/sub if we had one.
        # Since engine.events_queue is shared, pulling from it directly consumes the event for ONE client.
        # To make it broadcasting, we need an event hub. We will quickly adapt the engine for broadcast.
        
        from app.orchestrator.hub import hub
        subscriber_queue = asyncio.Queue()
        hub.subscribe(workflow_id, subscriber_queue)
        try:
            while True:
                if await request.is_disconnected():
                    break
                event = await subscriber_queue.get()
                payload = {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "step_id": event.step_id,
                    "agent_id": event.agent_id,
                    "tool_name": event.tool_name,
                    "status": event.status,
                    "metadata": event.metadata
                }
                yield json.dumps(payload)
        finally:
            hub.unsubscribe(workflow_id, subscriber_queue)
            
    return EventSourceResponse(event_generator())

@router.get("/metrics")
def get_metrics():
    with SessionLocal() as db:
        total_workflows = db.query(WorkflowRecord).count()
        if total_workflows == 0:
            return {
                "total_workflows": 0,
                "completed_workflows": 0,
                "failed_workflows": 0,
                "success_rate": 0,
                "average_latency": 0,
                "retry_rate": 0,
                "tool_usage": {},
                "agent_usage": {}
            }
            
        completed_workflows = db.query(WorkflowRecord).filter(WorkflowRecord.status == "completed").count()
        failed_workflows = db.query(WorkflowRecord).filter(WorkflowRecord.status == "failed").count()
        success_rate = (completed_workflows / total_workflows) * 100
        
        completed_records = db.query(WorkflowRecord).filter(WorkflowRecord.status == "completed").all()
        latency_sum = sum((r.updated_at - r.created_at).total_seconds() for r in completed_records if r.updated_at and r.created_at)
        average_latency = latency_sum / completed_workflows if completed_workflows > 0 else 0
        
        tool_events = db.query(EventRecord.tool_name, func.count(EventRecord.id)).filter(EventRecord.event_type == "tool.started").group_by(EventRecord.tool_name).all()
        tool_usage = {t[0]: t[1] for t in tool_events if t[0]}
        
        agent_events = db.query(EventRecord.agent_id, func.count(EventRecord.id)).filter(EventRecord.event_type == "step.started").group_by(EventRecord.agent_id).all()
        agent_usage = {a[0]: a[1] for a in agent_events if a[0]}
        
        total_tool_calls = sum(tool_usage.values())
        retries = db.query(EventRecord).filter(EventRecord.event_type == "retry.started").count()
        retry_rate = (retries / total_tool_calls * 100) if total_tool_calls > 0 else 0
        
        return {
            "total_workflows": total_workflows,
            "completed_workflows": completed_workflows,
            "failed_workflows": failed_workflows,
            "success_rate": success_rate,
            "average_latency": average_latency,
            "retry_rate": retry_rate,
            "tool_usage": tool_usage,
            "agent_usage": agent_usage
        }
