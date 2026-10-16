import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import endpoints
from app.persistence.database import Base, EventRecord, WorkflowRecord


@pytest.fixture
def db_session_factory(tmp_path, monkeypatch):
    database_engine = create_engine(f"sqlite:///{tmp_path / 'workflows.db'}")
    Base.metadata.create_all(bind=database_engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=database_engine)
    monkeypatch.setattr(endpoints, "SessionLocal", session_factory)

    with session_factory() as db:
        db.add_all([
            WorkflowRecord(id="failed-id", user_request="original request", status="failed", state_json={}),
            WorkflowRecord(id="running-id", user_request="active request", status="running", state_json={}),
            WorkflowRecord(id="completed-id", user_request="completed request", status="completed", state_json={}),
        ])
        db.add(EventRecord(
            id="failed-event",
            workflow_id="failed-id",
            event_type="workflow.failed",
            status="failed",
            metadata_json={},
        ))
        db.commit()

    yield session_factory
    database_engine.dispose()


def test_list_workflows_can_filter_failed(db_session_factory):
    workflows = endpoints.list_workflows(status="failed", limit=200)

    assert [workflow["workflow_id"] for workflow in workflows] == ["failed-id"]


def test_rerun_uses_existing_request_and_preserves_history(db_session_factory, monkeypatch):
    requests = []
    monkeypatch.setattr(endpoints.engine, "new_workflow", lambda request: requests.append(request) or "new-id")

    response = asyncio.run(endpoints.rerun_workflow("failed-id"))

    assert response.workflow_id == "new-id"
    assert requests == ["original request"]
    with db_session_factory() as db:
        assert db.query(WorkflowRecord).filter_by(id="failed-id").one().status == "failed"
        assert db.query(EventRecord).filter_by(id="failed-event").count() == 1


def test_rerun_with_edited_request_creates_new_workflow(db_session_factory, monkeypatch):
    requests = []
    monkeypatch.setattr(endpoints.engine, "new_workflow", lambda request: requests.append(request) or "new-id")

    response = asyncio.run(
        endpoints.rerun_workflow(
            "failed-id",
            endpoints.RerunWorkflowRequest(request="edited request"),
        )
    )

    assert response.workflow_id == "new-id"
    assert requests == ["edited request"]
    with db_session_factory() as db:
        assert db.query(WorkflowRecord).filter_by(id="failed-id").one().user_request == "original request"


def test_rerun_rejects_empty_request(db_session_factory, monkeypatch):
    monkeypatch.setattr(endpoints.engine, "new_workflow", lambda request: pytest.fail("must not start"))

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            endpoints.rerun_workflow(
                "failed-id",
                endpoints.RerunWorkflowRequest(request="  "),
            )
        )

    assert error.value.status_code == 422


def test_delete_workflow_removes_record_and_events(db_session_factory):
    response = endpoints.delete_workflow("failed-id")

    assert response == {"workflow_id": "failed-id", "status": "deleted"}
    with db_session_factory() as db:
        assert db.query(WorkflowRecord).filter_by(id="failed-id").count() == 0
        assert db.query(EventRecord).filter_by(id="failed-event").count() == 0


def test_delete_workflow_rejects_active_workflow(db_session_factory):
    with pytest.raises(HTTPException) as error:
        endpoints.delete_workflow("running-id")

    assert error.value.status_code == 409
    with db_session_factory() as db:
        assert db.query(WorkflowRecord).filter_by(id="running-id").count() == 1


def test_delete_workflow_returns_not_found(db_session_factory):
    with pytest.raises(HTTPException) as error:
        endpoints.delete_workflow("missing-id")

    assert error.value.status_code == 404
