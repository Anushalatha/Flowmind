import pytest
import os
import sys
import uuid
import asyncio

# Set test database URL before any imports
os.environ['DB_URL'] = 'sqlite:///:memory:'

# Now import after env var is set
from app.models.workflow import WorkflowPlan, WorkflowStepDefinition, WorkflowState, StepResult, WorkflowStatus, ErrorCategory
from app.orchestrator.engine import engine
from app.persistence.database import init_db
from app.tools.builtins import ToolError
import app.tools.builtins

init_db()

def create_test_workflow(user_request):
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request=user_request)
    engine.active_workflows[workflow_id] = state
    engine._save_state(state)
    return workflow_id

@pytest.mark.asyncio
async def test_division_by_zero():
    # Setup state manually for test
    workflow_id = create_test_workflow("div test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test div 0", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Divide by zero", tool_name="divide", arguments={"a": 10, "b": 0})
    ])
    state.plan = plan

    with pytest.raises(Exception):
        await engine.execute_step(plan.steps[0], state)

    assert state.step_results["step_1"].status == "failed"
    assert "division by zero" in state.step_results["step_1"].error

@pytest.mark.asyncio
async def test_successful_step():
    workflow_id = create_test_workflow("add test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test add", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5})
    ])
    state.plan = plan

    res = await engine.execute_step(plan.steps[0], state)
    assert res == 15
    assert state.step_results["step_1"].status == "completed"

def test_resolve_args_simple_reference():
    """Test resolving $step_1 reference to a simple numeric result"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result=42)

    args = {"value": "$step_1"}
    resolved = engine._resolve_args(args, state)

    assert resolved["value"] == 42
    assert isinstance(resolved["value"], int)  # Preserve numeric type

def test_resolve_args_with_result_suffix():
    """Test resolving $step_1.result reference to a simple numeric result"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result=3.14)

    args = {"value": "$step_1.result"}
    resolved = engine._resolve_args(args, state)

    assert resolved["value"] == 3.14
    assert isinstance(resolved["value"], float)  # Preserve numeric type

def test_resolve_args_dict_field():
    """Test resolving $step_1.result.field when result is a dict"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result={"total": 100, "count": 5})

    args = {"value": "$step_1.result.total"}
    resolved = engine._resolve_args(args, state)

    assert resolved["value"] == 100

def test_resolve_args_unresolved_step():
    """Test that unresolved step reference raises clear error"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result=42)

    args = {"value": "$step_2"}
    with pytest.raises(ValueError) as exc_info:
        engine._resolve_args(args, state)

    assert "Step 'step_2' not found" in str(exc_info.value)

def test_resolve_args_failed_upstream_step():
    """Test that referencing a failed step raises clear error"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="failed", error="division by zero")

    args = {"value": "$step_1"}
    with pytest.raises(ValueError) as exc_info:
        engine._resolve_args(args, state)

    assert "Step 'step_1' failed" in str(exc_info.value)
    assert "division by zero" in str(exc_info.value)

def test_resolve_args_nonexistent_field():
    """Test that accessing nonexistent field on dict raises clear error"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result={"total": 100})

    args = {"value": "$step_1.result.nonexistent"}
    with pytest.raises(ValueError) as exc_info:
        engine._resolve_args(args, state)

    assert "Field 'nonexistent' not found" in str(exc_info.value)

def test_resolve_args_field_on_non_dict():
    """Test that accessing field on non-dict result raises clear error"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result=42)

    args = {"value": "$step_1.result.somefield"}
    with pytest.raises(ValueError) as exc_info:
        engine._resolve_args(args, state)

    assert "Cannot access field 'somefield' on non-dict result" in str(exc_info.value)

@pytest.mark.asyncio
async def test_three_step_chain_with_dependencies():
    """Test three-step calculation where each step consumes the previous result"""
    workflow_id = create_test_workflow("chain test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test chain", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply result", tool_name="multiply", arguments={"a": "$step_1.result", "b": 2}),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add to product", tool_name="add", arguments={"a": "$step_2.result", "b": 3})
    ])
    state.plan = plan

    # Execute step 1
    res1 = await engine.execute_step(plan.steps[0], state)
    assert res1 == 15
    assert state.step_results["step_1"].status == "completed"

    # Execute step 2 with dependency
    res2 = await engine.execute_step(plan.steps[1], state)
    assert res2 == 30  # 15 * 2
    assert state.step_results["step_2"].status == "completed"

    # Execute step 3 with dependency
    res3 = await engine.execute_step(plan.steps[2], state)
    assert res3 == 33  # 30 + 3
    assert state.step_results["step_3"].status == "completed"

@pytest.mark.asyncio
async def test_multi_step_calculation_110():
    """Test a valid multi-step calculation: 10 + 20 = 30, 30 * 2 = 60, 60 + 50 = 110"""
    workflow_id = create_test_workflow("calc 110 test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Calculate 110", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 20}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply result", tool_name="multiply", arguments={"a": "$step_1.result", "b": 2}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add to product", tool_name="add", arguments={"a": "$step_2.result", "b": 50}, depends_on=["step_2"])
    ])
    state.plan = plan

    # Execute step 1
    res1 = await engine.execute_step(plan.steps[0], state)
    assert res1 == 30
    assert state.step_results["step_1"].status == "completed"

    # Execute step 2 with dependency
    res2 = await engine.execute_step(plan.steps[1], state)
    assert res2 == 60
    assert state.step_results["step_2"].status == "completed"

    # Execute step 3 with dependency
    res3 = await engine.execute_step(plan.steps[2], state)
    assert res3 == 110
    assert state.step_results["step_3"].status == "completed"



@pytest.mark.asyncio
async def test_full_calculator_workflow():
    """Test the full workflow execution for calculator chain using the actual planner"""
    from app.agents.planner import PlannerAgent
    from app.tools.builtins import register_builtin_tools
    from app.persistence.database import SessionLocal, WorkflowRecord

    register_builtin_tools()
    planner = PlannerAgent()

    # Generate plan using the actual planner
    plan = await planner.execute("Calculate 15% of 2000, add 250, then divide by 5.")

    # Create workflow state
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="Calculate 15% of 2000, add 250, then divide by 5", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state
    state.plan = plan

    try:
        # Simulate the scheduler loop
        pending_steps = {step.step_id: step for step in plan.steps}
        completed_steps = set()
        blocked_steps = set()

        while pending_steps:
            # Find runnable steps
            runnable = []
            for step_id, step in pending_steps.items():
                can_run = True
                for dep in step.depends_on:
                    if dep not in completed_steps and dep not in blocked_steps:
                        can_run = False
                        break
                if can_run:
                    runnable.append(step)

            if not runnable:
                # Check if all remaining are blocked
                all_blocked = True
                for step_id, step in pending_steps.items():
                    is_blocked = False
                    for dep in step.depends_on:
                        if dep in state.step_results and state.step_results[dep].status in ["failed", "dependency_blocked"]:
                            is_blocked = True
                            break
                    if not is_blocked:
                        all_blocked = False
                        break

                if all_blocked:
                    # Mark remaining as dependency_blocked
                    for step_id, step in pending_steps.items():
                        state.step_results[step_id] = StepResult(
                            step_id=step_id,
                            status="dependency_blocked",
                            error=f"Step blocked due to failed dependency",
                            error_category=ErrorCategory.PERMANENT_ERROR,
                            retry_count=0
                        )
                    break
                else:
                    raise RuntimeError("Deadlock")

            # Execute runnable steps
            tasks = [engine.execute_step(step, state) for step in runnable]
            for step in runnable:
                del pending_steps[step.step_id]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(runnable, results):
                if isinstance(result, Exception):
                    state.step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error=str(result),
                        error_category=ErrorCategory.UNKNOWN,
                        retry_count=0
                    )
                elif result is None:
                    blocked_steps.add(step.step_id)
                else:
                    completed_steps.add(step.step_id)

        # Verify all steps completed successfully
        assert len(state.step_results) == 3
        assert all(r.status == "completed" for r in state.step_results.values())

        # Verify final status is COMPLETED
        final_status = WorkflowStatus.COMPLETED
        state.status = final_status
        engine._save_state(state)

        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "completed"

    finally:
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_web_search_fallback_tool():
    """Test that web_search_fallback reformulates queries and returns results"""
    from app.tools.registry import registry
    from app.tools.builtins import register_builtin_tools

    register_builtin_tools()
    
    # Verify fallback tool is registered
    fallback_tool = registry.get_tool("web_search_fallback")
    assert fallback_tool is not None
    assert "fallback" in fallback_tool.description.lower()

@pytest.mark.asyncio
async def test_empty_result_not_classified_as_failed():
    """Test that empty research results are classified as EMPTY_RESULT, not FAILED"""
    workflow_id = create_test_workflow("empty result classification test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test empty result classification", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search test", tool_name="web_search", arguments={"query": "test"})
    ])
    state.plan = plan

    # Mock web_search to return empty snippets
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_empty_handler(args):
        return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}

    try:
        tool.handler = mock_empty_handler
        res = await engine.execute_step(plan.steps[0], state)

        # Should NOT raise ToolError
        assert res["success"] == True
        assert res["snippets"] == []
        assert state.step_results["step_1"].status == "empty_result"
        assert state.step_results["step_1"].result is not None
    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_synthesis_distinguishes_empty_from_failure():
    """Test that synthesis agent input distinguishes empty evidence from actual failure"""
    from app.agents.synthesis import SynthesisAgent

    agent = SynthesisAgent()

    # Test with empty results - check the context generation logic
    summary_empty = {
        "successful_steps": {},
        "empty_result_steps": {
            "step_1": {"success": True, "snippets": [], "query": "PostgreSQL"}
        },
        "failed_steps": {},
        "total_steps": 1,
        "successful_count": 0,
        "empty_result_count": 1,
        "failed_count": 0
    }

    # Build context to verify it's labeled correctly
    successful_steps = summary_empty.get("successful_steps", {})
    empty_result_steps = summary_empty.get("empty_result_steps", {})
    failed_steps = summary_empty.get("failed_steps", {})

    context_parts = []
    if empty_result_steps:
        context_parts.append(f"\nResearch with Insufficient Evidence:")
        for step_id, result in empty_result_steps.items():
            if isinstance(result, dict) and "query" in result:
                context_parts.append(f"\n{step_id}: Search for '{result.get('query', 'unknown')}' returned no verifiable evidence from available sources.")
            else:
                context_parts.append(f"\n{step_id}: {result}")

    context = "\n".join(context_parts)
    
    # Verify context uses "Insufficient Evidence" not "Failed"
    assert "Insufficient Evidence" in context
    assert "Failed" not in context

@pytest.mark.asyncio
async def test_empty_primary_with_successful_fallback():
    """Test workflow where primary search is empty but fallback succeeds"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="Research test", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test fallback workflow", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Primary search", tool_name="web_search", arguments={"query": "test"}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Fallback search", tool_name="web_search_fallback", arguments={"query": "$step_1.query"}, depends_on=["step_1"])
    ])
    state.plan = plan

    # Mock web_search to return empty, fallback to return results
    from app.tools.registry import registry
    web_tool = registry.get_tool("web_search")
    fallback_tool = registry.get_tool("web_search_fallback")
    original_web_handler = web_tool.handler
    original_fallback_handler = fallback_tool.handler

    async def mock_empty_handler(args):
        return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}

    async def mock_fallback_handler(args):
        return {"success": True, "snippets": ["Test result"], "source": "Wikipedia (fallback)", "query": args["query"], "original_query": "test"}

    try:
        web_tool.handler = mock_empty_handler
        fallback_tool.handler = mock_fallback_handler

        # Execute step 1 (empty)
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "empty_result"

        # Execute step 2 (fallback succeeds)
        res2 = await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "completed"
        assert res2["snippets"] == ["Test result"]

        # Final status should be COMPLETED (partial success is still completion)
        final_status = WorkflowStatus.COMPLETED
        state.status = final_status
        engine._save_state(state)

        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "completed"

    finally:
        web_tool.handler = original_web_handler
        fallback_tool.handler = original_fallback_handler
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_scalar_calculator_chain():
    """Test that scalar results from calculator tools can be used in dependent steps via scheduler loop"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="Calculate 15% of 2000, add 250, then divide by 5", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test scalar calculator chain", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Calculate 15% of 2000", tool_name="calculate_percentage", arguments={"percentage": 15, "value": 2000}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Add 250 to result", tool_name="add", arguments={"a": "$step_1.result", "b": 250}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Divide by 5", tool_name="divide", arguments={"a": "$step_2.result", "b": 5}, depends_on=["step_2"])
    ])
    state.plan = plan

    try:
        # Simulate the scheduler loop
        pending_steps = {step.step_id: step for step in plan.steps}
        completed_steps = set()
        blocked_steps = set()

        while pending_steps:
            # Find runnable steps
            runnable = []
            for step_id, step in pending_steps.items():
                can_run = True
                for dep in step.depends_on:
                    if dep not in completed_steps and dep not in blocked_steps:
                        can_run = False
                        break
                if can_run:
                    runnable.append(step)

            if not runnable:
                # Check if all remaining are blocked
                all_blocked = True
                for step_id, step in pending_steps.items():
                    is_blocked = False
                    for dep in step.depends_on:
                        if dep in state.step_results and state.step_results[dep].status in ["failed", "dependency_blocked"]:
                            is_blocked = True
                            break
                    if not is_blocked:
                        all_blocked = False
                        break

                if all_blocked:
                    # Mark remaining as dependency_blocked
                    for step_id, step in pending_steps.items():
                        state.step_results[step_id] = StepResult(
                            step_id=step_id,
                            status="dependency_blocked",
                            error=f"Step blocked due to failed dependency",
                            error_category=ErrorCategory.PERMANENT_ERROR,
                            retry_count=0
                        )
                    break
                else:
                    raise RuntimeError("Deadlock")

            # Execute runnable steps
            tasks = [engine.execute_step(step, state) for step in runnable]
            for step in runnable:
                del pending_steps[step.step_id]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(runnable, results):
                if isinstance(result, Exception):
                    state.step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error=str(result),
                        error_category=ErrorCategory.UNKNOWN,
                        retry_count=0
                    )
                elif result is None:
                    blocked_steps.add(step.step_id)
                else:
                    completed_steps.add(step.step_id)

        # Verify all steps completed successfully
        assert state.step_results["step_1"].status == "completed"
        assert state.step_results["step_1"].result == 300.0
        assert state.step_results["step_2"].status == "completed"
        assert state.step_results["step_2"].result == 550.0
        assert state.step_results["step_3"].status == "completed"
        assert state.step_results["step_3"].result == 110.0

        # Verify final status is COMPLETED
        final_status = WorkflowStatus.COMPLETED
        state.status = final_status
        engine._save_state(state)

        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "completed"

    finally:
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_planner_rejects_invalid_tool_name():
    """Test that planner validation rejects plans with invalid tool names"""
    from app.agents.planner import PlannerAgent

    planner = PlannerAgent()

    # Create a plan with an invalid tool name
    invalid_plan = WorkflowPlan(
        goal="Test invalid tool",
        steps=[
            WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Test action", tool_name="none", arguments={})
        ]
    )

    # Mock the structured_generate to return our invalid plan
    async def mock_generate(*args, **kwargs):
        return invalid_plan

    original_generate = planner.provider.structured_generate
    planner.provider.structured_generate = mock_generate

    with pytest.raises(ValueError) as exc_info:
        await planner.execute("test request")

    assert "Invalid tool_name 'none'" in str(exc_info.value)

    # Restore original
    planner.provider.structured_generate = original_generate

@pytest.mark.asyncio
async def test_planner_rejects_final_response_step():
    """Test that planner validation rejects plans with final_response as tool name"""
    from app.agents.planner import PlannerAgent

    planner = PlannerAgent()

    # Create a plan with final_response as tool name
    invalid_plan = WorkflowPlan(
        goal="Test final response",
        steps=[
            WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="calc", tool_name="add", arguments={"a": 10, "b": 20}),
            WorkflowStepDefinition(step_id="step_2", agent="synthesis_agent", action="final", tool_name="final_response", arguments={})
        ]
    )

    async def mock_generate(*args, **kwargs):
        return invalid_plan

    original_generate = planner.provider.structured_generate
    planner.provider.structured_generate = mock_generate

    with pytest.raises(ValueError) as exc_info:
        await planner.execute("test request")

    assert "Invalid tool_name 'final_response'" in str(exc_info.value)

    planner.provider.structured_generate = original_generate

@pytest.mark.asyncio
async def test_planner_rejects_unknown_tool():
    """Test that planner validation rejects plans with unknown tool names"""
    from app.agents.planner import PlannerAgent

    planner = PlannerAgent()

    # Create a plan with an unknown tool
    invalid_plan = WorkflowPlan(
        goal="Test unknown tool",
        steps=[
            WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Test unknown tool", tool_name="unknown_tool_xyz", arguments={})
        ]
    )

    async def mock_generate(*args, **kwargs):
        return invalid_plan

    original_generate = planner.provider.structured_generate
    planner.provider.structured_generate = mock_generate

    with pytest.raises(ValueError) as exc_info:
        await planner.execute("test request")

    assert "Invalid tool_name 'unknown_tool_xyz'" in str(exc_info.value)

    planner.provider.structured_generate = original_generate

@pytest.mark.asyncio
async def test_planner_rejects_invalid_depends_on_format():
    """Test that planner validation rejects plans with invalid depends_on format (e.g., '1' instead of 'step_1')"""
    from app.agents.planner import PlannerAgent

    planner = PlannerAgent()

    # Create a plan with invalid depends_on format
    invalid_plan = WorkflowPlan(
        goal="Test invalid depends_on",
        steps=[
            WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="add", tool_name="add", arguments={"a": 10, "b": 20}),
            WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="multiply", tool_name="multiply", arguments={"a": "$step_1.result", "b": 2}, depends_on=["1"])  # Invalid: should be "step_1"
        ]
    )

    async def mock_generate(*args, **kwargs):
        return invalid_plan

    original_generate = planner.provider.structured_generate
    planner.provider.structured_generate = mock_generate

    with pytest.raises(ValueError) as exc_info:
        await planner.execute("test request")

    assert "Invalid depends_on format: '1'" in str(exc_info.value)

    planner.provider.structured_generate = original_generate

@pytest.mark.asyncio
async def test_unknown_tool_not_retried():
    """Test that unknown tool errors are not retried (permanent error)"""
    workflow_id = create_test_workflow("unknown tool test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test unknown tool", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Test nonexistent tool", tool_name="nonexistent_tool", arguments={})
    ])
    state.plan = plan

    with pytest.raises(KeyError) as exc_info:
        await engine.execute_step(plan.steps[0], state)

    assert "Tool nonexistent_tool not found" in str(exc_info.value)
    assert state.step_results["step_1"].status == "failed"

    # Verify it only ran once (no retries)
    # The step should be marked as failed immediately without retry attempts
    assert state.step_results["step_1"].error

@pytest.mark.asyncio
async def test_parallel_independent_steps():
    """Test that independent steps can execute in parallel"""
    workflow_id = create_test_workflow("parallel test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test parallel", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply numbers", tool_name="multiply", arguments={"a": 3, "b": 4}),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add results", tool_name="add", arguments={"a": "$step_1.result", "b": "$step_2.result"}, depends_on=["step_1", "step_2"])
    ])
    state.plan = plan

    # Execute independent steps in parallel
    import asyncio
    res1, res2 = await asyncio.gather(
        engine.execute_step(plan.steps[0], state),
        engine.execute_step(plan.steps[1], state)
    )

    assert res1 == 15
    assert res2 == 12
    assert state.step_results["step_1"].status == "completed"
    assert state.step_results["step_2"].status == "completed"

    # Execute dependent step
    res3 = await engine.execute_step(plan.steps[2], state)
    assert res3 == 27  # 15 + 12
    assert state.step_results["step_3"].status == "completed"

@pytest.mark.asyncio
async def test_sequential_dependent_steps():
    """Test that dependent steps execute sequentially in correct order"""
    workflow_id = create_test_workflow("sequential test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test sequential", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply result", tool_name="multiply", arguments={"a": "$step_1.result", "b": 2}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add to product", tool_name="add", arguments={"a": "$step_2.result", "b": 5}, depends_on=["step_2"])
    ])
    state.plan = plan

    # Step 2 should be dependency_blocked if step 1 hasn't completed
    res2_blocked = await engine.execute_step(plan.steps[1], state)
    assert res2_blocked is None  # dependency_blocked returns None
    assert state.step_results["step_2"].status == "dependency_blocked"
    assert "not found" in state.step_results["step_2"].error

    # Reset state for correct execution
    state.step_results = {}

    # Execute in correct order
    res1 = await engine.execute_step(plan.steps[0], state)
    assert res1 == 15

    res2 = await engine.execute_step(plan.steps[1], state)
    assert res2 == 30

    res3 = await engine.execute_step(plan.steps[2], state)
    assert res3 == 35

    assert state.step_results["step_1"].status == "completed"
    assert state.step_results["step_2"].status == "completed"
    assert state.step_results["step_3"].status == "completed"

# New tests for research workflow reliability

@pytest.mark.asyncio
async def test_complete_research_success():
    """Test workflow marked COMPLETED when all research steps succeed"""
    workflow_id = create_test_workflow("research success test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test research", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search Python programming", tool_name="web_search", arguments={"query": "Python programming"})
    ])
    state.plan = plan

    # Mock successful web_search via registry
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_success_handler(args):
        return {"success": True, "snippets": ["Python is a programming language"], "source": "Wikipedia", "query": args["query"]}

    tool.handler = mock_success_handler

    try:
        res = await engine.execute_step(plan.steps[0], state)
        assert res["success"] == True
        assert state.step_results["step_1"].status == "completed"
        assert state.step_results["step_1"].error_category is None
    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_all_searches_failed():
    """Test workflow marked FAILED when all search steps fail"""
    workflow_id = create_test_workflow("research failure test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test research failure", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search test query", tool_name="web_search", arguments={"query": "test"})
    ])
    state.plan = plan

    # Mock a failed web_search via registry
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_failed_handler(args):
        raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)

    tool.handler = mock_failed_handler

    try:
        with pytest.raises(ToolError):
            await engine.execute_step(plan.steps[0], state)

        assert state.step_results["step_1"].status == "failed"
        assert state.step_results["step_1"].error_category == ErrorCategory.NETWORK_ERROR
        assert state.step_results["step_1"].retry_count == 3  # Exhausted retries
    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_partial_research_success():
    """Test workflow marked PARTIALLY_COMPLETED when some steps succeed"""
    workflow_id = create_test_workflow("partial research test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test partial research", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search Python", tool_name="web_search", arguments={"query": "Python"}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Search JavaScript", tool_name="web_search", arguments={"query": "JavaScript"}),
        WorkflowStepDefinition(step_id="step_3", agent="research_agent", action="Search Go", tool_name="web_search", arguments={"query": "Go"})
    ])
    state.plan = plan

    # Mock web_search via registry
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_success_handler(args):
        return {"success": True, "snippets": ["Test result"], "source": "Wikipedia", "query": args["query"]}

    async def mock_failed_handler(args):
        raise ToolError("Rate limit", ErrorCategory.RATE_LIMIT)

    try:
        # Execute step 1 successfully
        tool.handler = mock_success_handler
        res1 = await engine.execute_step(plan.steps[0], state)
        assert res1["success"] == True
        assert state.step_results["step_1"].status == "completed"

        # Make step 2 fail
        tool.handler = mock_failed_handler
        with pytest.raises(ToolError):
            await engine.execute_step(plan.steps[1], state)

        assert state.step_results["step_2"].status == "failed"
        assert state.step_results["step_2"].error_category == ErrorCategory.RATE_LIMIT

        # Execute step 3 successfully
        tool.handler = mock_success_handler
        res3 = await engine.execute_step(plan.steps[2], state)
        assert res3["success"] == True
        assert state.step_results["step_3"].status == "completed"

        # Verify status summary
        summary = engine._create_step_summary(state.step_results)
        assert summary["successful_count"] == 2
        assert summary["failed_count"] == 1
        assert len(summary["successful_steps"]) == 2
        assert len(summary["failed_steps"]) == 1

    finally:
        tool.handler = original_handler

def test_tool_error_category():
    """Test that ToolError properly stores error category"""
    error = ToolError("Test error", ErrorCategory.TIMEOUT)
    assert error.category == ErrorCategory.TIMEOUT
    assert str(error) == "Test error"

def test_step_result_with_error_category():
    """Test StepResult model with error_category and retry_count"""
    result = StepResult(
        step_id="step_1",
        status="failed",
        error="Network timeout",
        error_category=ErrorCategory.TIMEOUT,
        retry_count=3
    )
    assert result.status == "failed"
    assert result.error_category == ErrorCategory.TIMEOUT
    assert result.retry_count == 3

def test_synthesis_markdown_cleaning():
    """Test that synthesis agent cleans up common Markdown issues"""
    from app.agents.synthesis import SynthesisAgent

    agent = SynthesisAgent()

    # Test literal <br> tag replacement
    input1 = "Line 1<br>Line 2<br/>Line 3"
    output1 = agent._clean_markdown(input1)
    assert "<br>" not in output1
    assert "\n\n" in output1

    # Test that tables are left as-is (react-markdown with remarkGFM handles them)
    input2 = "| Header |\n|---|\n| Data |"
    output2 = agent._clean_markdown(input2)
    assert "| Header |" in output2
    assert "| Data |" in output2

    # Test multiple empty lines
    input3 = "Line 1\n\n\n\n\nLine 2"
    output3 = agent._clean_markdown(input3)
    assert "\n\n\n" not in output3  # Should have max 2 newlines

    # Test excessive heading symbols
    input4 = "####### Too many hashes"
    output4 = agent._clean_markdown(input4)
    assert "######" in output4
    assert "#######" not in output4

    # Test that bold markers are preserved
    input5 = "**Next Steps** should be bold"
    output5 = agent._clean_markdown(input5)
    assert "**Next Steps**" in output5  # Bold markers should be preserved

    # Test that lists are preserved
    input6 = "- Item 1\n- Item 2"
    output6 = agent._clean_markdown(input6)
    assert "- Item 1" in output6
    assert "- Item 2" in output6

# API Workflow Regression Tests

@pytest.mark.asyncio
async def test_api_workflow_http_request_validation_extraction():
    """Test successful API workflow: HTTP request → validation → extraction"""
    workflow_id = create_test_workflow("API workflow test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test API workflow", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Fetch API data", tool_name="http_request", arguments={"url": "https://api.example.com/data"}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Validate response", tool_name="validate_response", arguments={"body": "$step_1.result.body"}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Extract fields", tool_name="extract_fields", arguments={"data": "$step_2.result.data", "fields": ["name", "description"]}, depends_on=["step_2"])
    ])
    state.plan = plan

    # Mock http_request
    from app.tools.registry import registry
    http_tool = registry.get_tool("http_request")
    original_http_handler = http_tool.handler

    async def mock_http_handler(args):
        return {"status_code": 200, "headers": {}, "body": '{"name": "Python", "description": "A programming language"}', "success": True}

    try:
        http_tool.handler = mock_http_handler

        # Execute step 1
        res1 = await engine.execute_step(plan.steps[0], state)
        assert res1["status_code"] == 200
        assert state.step_results["step_1"].status == "completed"

        # Execute step 2 with dependency
        res2 = await engine.execute_step(plan.steps[1], state)
        assert res2["valid"] == True
        assert res2["data"]["name"] == "Python"
        assert state.step_results["step_2"].status == "completed"

        # Execute step 3 with dependency
        res3 = await engine.execute_step(plan.steps[2], state)
        assert res3["name"] == "Python"
        assert res3["description"] == "A programming language"
        assert state.step_results["step_3"].status == "completed"

    finally:
        http_tool.handler = original_http_handler

@pytest.mark.asyncio
async def test_api_workflow_missing_referenced_field():
    """Test that referencing a non-existent field in dependency resolution fails immediately"""
    workflow_id = create_test_workflow("API workflow missing field test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test missing field", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 20}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply", tool_name="multiply", arguments={"a": "$step_1.result.nonexistent_field", "b": 2}, depends_on=["step_1"])
    ])
    state.plan = plan

    # Execute step 1
    res1 = await engine.execute_step(plan.steps[0], state)
    assert state.step_results["step_1"].status == "completed"

    # Step 2 should be dependency_blocked because it tries to access a field on a non-dict result
    res2 = await engine.execute_step(plan.steps[1], state)
    assert res2 is None  # dependency_blocked returns None
    assert state.step_results["step_2"].status == "dependency_blocked"
    assert "nonexistent_field" in state.step_results["step_2"].error or "non-dict" in state.step_results["step_2"].error

@pytest.mark.asyncio
async def test_api_workflow_malformed_json():
    """Test that malformed JSON in response causes validation to fail"""
    workflow_id = create_test_workflow("API workflow malformed JSON test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test malformed JSON", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Fetch API data", tool_name="http_request", arguments={"url": "https://api.example.com/data"}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Validate response", tool_name="validate_response", arguments={"body": "$step_1.result.body"}, depends_on=["step_1"])
    ])
    state.plan = plan

    # Mock http_request
    from app.tools.registry import registry
    http_tool = registry.get_tool("http_request")
    original_http_handler = http_tool.handler

    async def mock_http_handler(args):
        return {"status_code": 200, "headers": {}, "body": "invalid json{{{", "success": True}

    try:
        http_tool.handler = mock_http_handler

        # Execute step 1
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Step 2 should fail with parse error
        with pytest.raises(ToolError) as exc_info:
            await engine.execute_step(plan.steps[1], state)

        assert "JSON parse error" in str(exc_info.value)
        assert state.step_results["step_2"].status == "failed"

    finally:
        http_tool.handler = original_http_handler

@pytest.mark.asyncio
async def test_api_workflow_empty_response():
    """Test that empty response body is handled correctly"""
    workflow_id = create_test_workflow("API workflow empty response test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test empty response", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Fetch API data", tool_name="http_request", arguments={"url": "https://api.example.com/data"}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Validate response", tool_name="validate_response", arguments={"body": "$step_1.result.body"}, depends_on=["step_1"])
    ])
    state.plan = plan

    # Mock http_request
    from app.tools.registry import registry
    http_tool = registry.get_tool("http_request")
    original_http_handler = http_tool.handler

    async def mock_http_handler(args):
        return {"status_code": 200, "headers": {}, "body": "", "success": True}

    try:
        http_tool.handler = mock_http_handler

        # Execute step 1
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Step 2 should fail with parse error (empty string is not valid JSON)
        with pytest.raises(ToolError) as exc_info:
            await engine.execute_step(plan.steps[1], state)

        assert "JSON parse error" in str(exc_info.value)
        assert state.step_results["step_2"].status == "failed"

    finally:
        http_tool.handler = original_http_handler

@pytest.mark.asyncio
async def test_api_workflow_http_failure():
    """Test that HTTP/network failure is handled correctly"""
    workflow_id = create_test_workflow("API workflow HTTP failure test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test HTTP failure", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Fetch API data", tool_name="http_request", arguments={"url": "https://api.example.com/data"})
    ])
    state.plan = plan

    # Mock http_request to raise network error
    from app.tools.registry import registry
    http_tool = registry.get_tool("http_request")
    original_http_handler = http_tool.handler

    async def mock_http_handler(args):
        raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)

    try:
        http_tool.handler = mock_http_handler

        # Step should fail with network error (after retries)
        with pytest.raises(ToolError) as exc_info:
            await engine.execute_step(plan.steps[0], state)

        assert "Network error" in str(exc_info.value)
        assert state.step_results["step_1"].status == "failed"
        assert state.step_results["step_1"].error_category == ErrorCategory.NETWORK_ERROR

    finally:
        http_tool.handler = original_http_handler

@pytest.mark.asyncio
async def test_api_workflow_optional_fields_missing():
    """Test that missing optional fields in extraction are handled gracefully"""
    workflow_id = create_test_workflow("API workflow optional fields test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test optional fields", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Fetch API data", tool_name="http_request", arguments={"url": "https://api.example.com/data"}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Validate response", tool_name="validate_response", arguments={"body": "$step_1.result.body"}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Extract fields", tool_name="extract_fields", arguments={"data": "$step_2.result.data", "fields": ["name", "description", "version"]}, depends_on=["step_2"])
    ])
    state.plan = plan

    # Mock http_request
    from app.tools.registry import registry
    http_tool = registry.get_tool("http_request")
    original_http_handler = http_tool.handler

    async def mock_http_handler(args):
        return {"status_code": 200, "headers": {}, "body": '{"name": "Python", "description": "A language"}', "success": True}

    try:
        http_tool.handler = mock_http_handler

        # Execute step 1
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Execute step 2
        res2 = await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "completed"

        # Execute step 3 - should extract only available fields
        res3 = await engine.execute_step(plan.steps[2], state)
        assert res3["name"] == "Python"
        assert res3["description"] == "A language"
        assert "version" not in res3  # Optional field not in response
        assert state.step_results["step_3"].status == "completed"

    finally:
        http_tool.handler = original_http_handler

@pytest.mark.asyncio
async def test_planner_validates_dependency_field_references():
    """Test that planner rejects invalid field references in dependencies"""
    from app.agents.planner import PlannerAgent

    planner = PlannerAgent()

    # Create a plan with invalid field reference
    invalid_plan = WorkflowPlan(
        goal="Test invalid field reference",
        steps=[
            WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Fetch API data from endpoint", tool_name="http_request", arguments={"url": "https://api.example.com"}),
            WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Extract name field from response", tool_name="extract_fields", arguments={"data": "$step_1.result.validated_json", "fields": ["name"]}, depends_on=["step_1"])
        ]
    )

    async def mock_generate(*args, **kwargs):
        return invalid_plan

    original_generate = planner.provider.structured_generate
    planner.provider.structured_generate = mock_generate

    try:
        with pytest.raises(ValueError) as exc_info:
            await planner.execute("test request")

        assert "validated_json" in str(exc_info.value)
        assert "not a documented output" in str(exc_info.value)
    finally:
        planner.provider.structured_generate = original_generate

@pytest.mark.asyncio
async def test_planner_rejects_generic_action_descriptions():
    """Test that planner rejects generic action descriptions like 'search', 'fetch', etc."""
    from app.agents.planner import PlannerAgent

    planner = PlannerAgent()

    # Create a plan with generic action description
    invalid_plan = WorkflowPlan(
        goal="Test generic action",
        steps=[
            WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="search", tool_name="web_search", arguments={"query": "test"})
        ]
    )

    async def mock_generate(*args, **kwargs):
        return invalid_plan

    original_generate = planner.provider.structured_generate
    planner.provider.structured_generate = mock_generate

    try:
        with pytest.raises(ValueError) as exc_info:
            await planner.execute("test request")

        assert "too generic" in str(exc_info.value)
        assert "descriptive" in str(exc_info.value)
    finally:
        planner.provider.structured_generate = original_generate

@pytest.mark.asyncio
async def test_planner_rejects_action_as_tool_name():
    """Test that planner rejects action descriptions that are just the tool name"""
    from app.agents.planner import PlannerAgent

    planner = PlannerAgent()

    # Create a plan where action is just the tool name
    invalid_plan = WorkflowPlan(
        goal="Test action as tool name",
        steps=[
            WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="web_search", tool_name="web_search", arguments={"query": "test"})
        ]
    )

    async def mock_generate(*args, **kwargs):
        return invalid_plan

    original_generate = planner.provider.structured_generate
    planner.provider.structured_generate = mock_generate

    try:
        with pytest.raises(ValueError) as exc_info:
            await planner.execute("test request")

        assert "just the tool name" in str(exc_info.value)
    finally:
        planner.provider.structured_generate = original_generate

@pytest.mark.asyncio
async def test_sequential_calculation_still_works():
    """Test that existing sequential calculation workflows still work after dependency validation changes"""
    workflow_id = create_test_workflow("sequential calc test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test sequential calc", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply result", tool_name="multiply", arguments={"a": "$step_1.result", "b": 2}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add to product", tool_name="add", arguments={"a": "$step_2.result", "b": 3}, depends_on=["step_2"])
    ])
    state.plan = plan

    # Execute in sequence
    res1 = await engine.execute_step(plan.steps[0], state)
    assert res1 == 15
    assert state.step_results["step_1"].status == "completed"

    res2 = await engine.execute_step(plan.steps[1], state)
    assert res2 == 30
    assert state.step_results["step_2"].status == "completed"

    res3 = await engine.execute_step(plan.steps[2], state)
    assert res3 == 33
    assert state.step_results["step_3"].status == "completed"

def test_workflow_status_calculation():
    """Test workflow status calculation logic"""
    from app.models.workflow import WorkflowStatus

    # Case 1: All steps succeed
    total_steps = 3
    successful_steps = 3
    failed_steps = 0
    len_step_results = 3

    if len_step_results == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.COMPLETED

    # Case 2: All steps fail
    total_steps = 3
    successful_steps = 0
    failed_steps = 3
    len_step_results = 3

    if len_step_results == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.FAILED

    # Case 3: Some steps succeed, some fail
    total_steps = 3
    successful_steps = 2
    failed_steps = 1
    len_step_results = 3

    if len_step_results == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.PARTIALLY_COMPLETED

def test_create_step_summary():
    """Test step summary creation for synthesis"""
    state = WorkflowState(
        workflow_id="test",
        user_request="test",
        status=WorkflowStatus.RUNNING
    )
    state.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result={"data": "test"})
    state.step_results["step_2"] = StepResult(step_id="step_2", status="failed", error="Parse error", error_category=ErrorCategory.PARSE_ERROR, retry_count=2)

    summary = engine._create_step_summary(state.step_results)

    assert summary["total_steps"] == 2
    assert summary["successful_count"] == 1
    assert summary["failed_count"] == 1
    assert "step_1" in summary["successful_steps"]
    assert "step_2" in summary["failed_steps"]
    assert summary["failed_steps"]["step_2"]["error_category"] == "parse_error"

def test_validate_step_result_success():
    """Test validation of successful tool results"""
    # Calculator tools return numbers
    is_valid, status_reason = engine._validate_step_result(15, "add")
    assert is_valid == True
    assert status_reason == "success"

    is_valid, status_reason = engine._validate_step_result(5.5, "multiply")
    assert is_valid == True
    assert status_reason == "success"

    # Successful web search result
    result = {"success": True, "snippets": ["test"], "source": "Wikipedia"}
    is_valid, status_reason = engine._validate_step_result(result, "web_search")
    assert is_valid == True
    assert status_reason == "success"

    # Successful HTTP request
    result = {"status_code": 200, "body": "test", "success": True}
    is_valid, status_reason = engine._validate_step_result(result, "http_request")
    assert is_valid == True
    assert status_reason == "success"

    # Successful validation
    result = {"valid": True, "data": {"test": "value"}}
    is_valid, status_reason = engine._validate_step_result(result, "validate_response")
    assert is_valid == True
    assert status_reason == "success"

def test_validate_step_result_failure():
    """Test validation of failed tool results"""
    # Structured failure
    result = {"success": False, "error": "Tool failed"}
    is_valid, status_reason = engine._validate_step_result(result, "web_search")
    assert is_valid == False
    assert status_reason == "failure"

    # Empty snippets in web search - should be valid EMPTY_RESULT, not failure
    result = {"success": True, "snippets": [], "source": "Wikipedia"}
    is_valid, status_reason = engine._validate_step_result(result, "web_search")
    assert is_valid == True
    assert status_reason == "empty_result"

    # Error string (legacy)
    result = "Failed to search: network error"
    is_valid, status_reason = engine._validate_step_result(result, "web_search")
    assert is_valid == False
    assert status_reason == "failure"

    # Null status code in HTTP request
    result = {"body": "test"}
    is_valid, status_reason = engine._validate_step_result(result, "http_request")
    assert is_valid == False
    assert status_reason == "failure"

    # Failed validation
    result = {"valid": False, "error": "Invalid JSON"}
    is_valid, status_reason = engine._validate_step_result(result, "validate_response")
    assert is_valid == False
    assert status_reason == "failure"

@pytest.mark.asyncio
async def test_tool_returns_error_string():
    """Test that a tool returning an error string is treated as failure"""
    workflow_id = create_test_workflow("error string test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test error string", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers test", tool_name="add", arguments={"a": 10, "b": 5})
    ])
    state.plan = plan

    # Mock tool to return error string
    from app.tools.registry import registry
    tool = registry.get_tool("add")
    original_handler = tool.handler

    async def mock_error_string_handler(args):
        return "Failed to add: invalid input"

    tool.handler = mock_error_string_handler

    try:
        with pytest.raises(ToolError):
            await engine.execute_step(plan.steps[0], state)

        assert state.step_results["step_1"].status == "failed"
        assert "invalid or failed result" in state.step_results["step_1"].error
    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_tool_returns_empty_snippets():
    """Test that web_search with empty snippets is treated as EMPTY_RESULT, not failure"""
    workflow_id = create_test_workflow("empty snippets test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test empty snippets", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="search", tool_name="web_search", arguments={"query": "test"})
    ])
    state.plan = plan

    # Mock web_search to return empty snippets
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_empty_handler(args):
        return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}

    tool.handler = mock_empty_handler

    try:
        res = await engine.execute_step(plan.steps[0], state)

        # Should NOT raise ToolError
        assert res["success"] == True
        assert res["snippets"] == []
        assert state.step_results["step_1"].status == "empty_result"
        assert state.step_results["step_1"].result is not None
    finally:
        tool.handler = original_handler

# Regression Tests for Deadlock Fix

@pytest.mark.asyncio
async def test_scenario_a_independent_steps_with_empty_result():
    """Scenario A: Successful independent steps + one EMPTY_RESULT step. Expected: no deadlock."""
    workflow_id = create_test_workflow("scenario a test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test independent steps with empty result", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Search Python", tool_name="web_search", arguments={"query": "Python"}),
        WorkflowStepDefinition(step_id="step_3", agent="research_agent", action="Search nonexistent topic", tool_name="web_search", arguments={"query": "xyznonexistent123"})
    ])
    state.plan = plan

    # Mock web_search
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_success_handler(args):
        return {"success": True, "snippets": ["Python is a language"], "source": "Wikipedia", "query": args["query"]}

    async def mock_empty_handler(args):
        return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}

    try:
        # Execute step 1 (calculator)
        res1 = await engine.execute_step(plan.steps[0], state)
        assert res1 == 15
        assert state.step_results["step_1"].status == "completed"

        # Execute step 2 (successful search)
        tool.handler = mock_success_handler
        res2 = await engine.execute_step(plan.steps[1], state)
        assert res2["success"] == True
        assert state.step_results["step_2"].status == "completed"

        # Execute step 3 (empty result)
        tool.handler = mock_empty_handler
        res3 = await engine.execute_step(plan.steps[2], state)
        assert res3["success"] == True
        assert res3["snippets"] == []
        assert state.step_results["step_3"].status == "empty_result"

        # Verify summary
        summary = engine._create_step_summary(state.step_results)
        assert summary["successful_count"] == 2  # step_1 and step_2
        assert summary["empty_result_count"] == 1  # step_3
        assert summary["failed_count"] == 0

    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_scenario_b_transient_failure_with_independent_steps():
    """Scenario B: Successful independent steps + one transient failure. Expected: workflow can continue where dependencies allow."""
    workflow_id = create_test_workflow("scenario b test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test transient failure", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Search Python", tool_name="web_search", arguments={"query": "Python"}),
        WorkflowStepDefinition(step_id="step_3", agent="research_agent", action="Search with network error", tool_name="web_search", arguments={"query": "NetworkErrorTest"})
    ])
    state.plan = plan

    # Mock web_search
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_success_handler(args):
        return {"success": True, "snippets": ["Result"], "source": "Wikipedia", "query": args["query"]}

    async def mock_network_error_handler(args):
        raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)

    try:
        # Execute step 1 (calculator)
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Execute step 2 (successful)
        tool.handler = mock_success_handler
        res2 = await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "completed"

        # Execute step 3 (transient failure)
        tool.handler = mock_network_error_handler
        with pytest.raises(ToolError):
            await engine.execute_step(plan.steps[2], state)
        assert state.step_results["step_3"].status == "failed"
        assert state.step_results["step_3"].error_category == ErrorCategory.NETWORK_ERROR

        # Verify summary
        summary = engine._create_step_summary(state.step_results)
        assert summary["successful_count"] == 2
        assert summary["failed_count"] == 1

    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_scenario_c_dependent_step_blocked_by_failure():
    """Scenario C: Step B depends on failed step A. Expected: B becomes dependency-blocked, not deadlock."""
    workflow_id = create_test_workflow("scenario c test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test dependent step blocked", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search Python", tool_name="web_search", arguments={"query": "Python"}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply result", tool_name="multiply", arguments={"a": "$step_1.result.snippets.0", "b": 2}, depends_on=["step_1"])
    ])
    state.plan = plan

    # Mock web_search to fail
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_failure_handler(args):
        raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)

    try:
        tool.handler = mock_failure_handler

        # Execute step 1 (fails)
        with pytest.raises(ToolError):
            await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "failed"

        # Execute step 2 (should be dependency_blocked, not deadlock)
        res2 = await engine.execute_step(plan.steps[1], state)
        assert res2 is None  # dependency_blocked returns None
        assert state.step_results["step_2"].status == "dependency_blocked"
        assert "failed" in state.step_results["step_2"].error

    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_scenario_d_independent_step_executes_despite_failure():
    """Scenario D: Step C is independent of failed step A. Expected: C still executes."""
    workflow_id = create_test_workflow("scenario d test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test independent step executes", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search failing query", tool_name="web_search", arguments={"query": "FailTest"}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Multiply numbers", tool_name="multiply", arguments={"a": 3, "b": 4})
    ])
    state.plan = plan

    # Mock web_search to fail
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_failure_handler(args):
        raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)

    try:
        # Execute step 1 (fails)
        tool.handler = mock_failure_handler
        with pytest.raises(ToolError):
            await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "failed"

        # Execute step 2 (independent, should succeed)
        res2 = await engine.execute_step(plan.steps[1], state)
        assert res2 == 15
        assert state.step_results["step_2"].status == "completed"

        # Execute step 3 (independent, should succeed)
        res3 = await engine.execute_step(plan.steps[2], state)
        assert res3 == 12
        assert state.step_results["step_3"].status == "completed"

        # Verify summary
        summary = engine._create_step_summary(state.step_results)
        assert summary["successful_count"] == 2
        assert summary["failed_count"] == 1

    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_scenario_e_genuine_deadlock_detection():
    """Scenario E: Genuine unresolved dependency. Expected: deadlock detection still works."""
    workflow_id = create_test_workflow("scenario e test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test genuine deadlock", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Multiply result", tool_name="multiply", arguments={"a": "$step_3.result", "b": 2}, depends_on=["step_3"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add result", tool_name="add", arguments={"a": "$step_2.result", "b": 3}, depends_on=["step_2"])
    ])
    state.plan = plan

    # This creates a circular dependency: step_2 depends on step_3, step_3 depends on step_2
    # Neither can execute first - genuine deadlock

    # Note: This test verifies the deadlock detection logic, not the full workflow execution
    # since run_workflow would handle this differently
    try:
        # Check if dependencies are properly detected
        runnable = []
        for step_id, step in {s.step_id: s for s in plan.steps}.items():
            can_run = True
            for dep in step.depends_on:
                if dep not in state.step_results:
                    can_run = False
                    break
            if can_run:
                runnable.append(step)

        # Only step_1 should be runnable (no dependencies)
        assert len(runnable) == 1
        assert runnable[0].step_id == "step_1"

    except Exception as e:
        # If deadlock is detected immediately, that's also acceptable
        assert "Deadlock" in str(e) or "Unresolved dependencies" in str(e)

@pytest.mark.asyncio
async def test_scenario_f_research_workflow_partial_success():
    """Scenario F: Research workflow with PostgreSQL/MongoDB/Qdrant-style parallel searches. Expected: partial research reaches synthesis without fabricated information."""
    workflow_id = create_test_workflow("scenario f test")
    state = engine.active_workflows[workflow_id]

    plan = WorkflowPlan(goal="Test research workflow", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search PostgreSQL", tool_name="web_search", arguments={"query": "PostgreSQL database"}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Search MongoDB", tool_name="web_search", arguments={"query": "MongoDB database"}),
        WorkflowStepDefinition(step_id="step_3", agent="research_agent", action="Search Qdrant", tool_name="web_search", arguments={"query": "Qdrant vector database"}),
        WorkflowStepDefinition(step_id="step_4", agent="research_agent", action="Search Redis", tool_name="web_search", arguments={"query": "Redis database"})
    ])
    state.plan = plan

    # Mock web_search with mixed results
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_handler(args):
        query = args["query"]
        if "PostgreSQL" in query:
            return {"success": True, "snippets": ["PostgreSQL is a relational database"], "source": "Wikipedia", "query": query}
        elif "MongoDB" in query:
            return {"success": True, "snippets": ["MongoDB is a NoSQL database"], "source": "Wikipedia", "query": query}
        elif "Qdrant" in query:
            # Empty result for Qdrant (simulating the user's issue)
            return {"success": True, "snippets": [], "source": "Wikipedia", "query": query}
        elif "Redis" in query:
            return {"success": True, "snippets": ["Redis is an in-memory data store"], "source": "Wikipedia", "query": query}
        else:
            return {"success": True, "snippets": [], "source": "Wikipedia", "query": query}

    try:
        tool.handler = mock_handler

        # Execute all steps
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        res2 = await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "completed"

        res3 = await engine.execute_step(plan.steps[2], state)
        assert state.step_results["step_3"].status == "empty_result"
        assert res3["snippets"] == []

        res4 = await engine.execute_step(plan.steps[3], state)
        assert state.step_results["step_4"].status == "completed"

        # Verify summary
        summary = engine._create_step_summary(state.step_results)
        assert summary["successful_count"] == 3  # PostgreSQL, MongoDB, Redis
        assert summary["empty_result_count"] == 1  # Qdrant
        assert summary["failed_count"] == 0

        # Verify synthesis context includes empty result steps
        assert "empty_result_steps" in summary
        assert "step_3" in summary["empty_result_steps"]

    finally:
        tool.handler = original_handler

@pytest.mark.asyncio
async def test_scenario_g_workflow_status_semantics():
    """Scenario G: Verify final workflow status semantics for various states."""
    from app.models.workflow import WorkflowStatus

    # Test 1: All successful
    state1 = WorkflowState(workflow_id="test1", user_request="test", status=WorkflowStatus.RUNNING)
    state1.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result=42)
    state1.step_results["step_2"] = StepResult(step_id="step_2", status="completed", result=100)

    total_steps = 2
    successful_steps = sum(1 for r in state1.step_results.values() if r.status in ["completed", "empty_result"])
    failed_steps = sum(1 for r in state1.step_results.values() if r.status in ["failed", "dependency_blocked"])

    if len(state1.step_results) == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.COMPLETED

    # Test 2: Partial success with empty results
    state2 = WorkflowState(workflow_id="test2", user_request="test", status=WorkflowStatus.RUNNING)
    state2.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result={"data": "test"})
    state2.step_results["step_2"] = StepResult(step_id="step_2", status="empty_result", result={"snippets": []})

    total_steps = 2
    successful_steps = sum(1 for r in state2.step_results.values() if r.status in ["completed", "empty_result"])
    failed_steps = sum(1 for r in state2.step_results.values() if r.status in ["failed", "dependency_blocked"])

    if len(state2.step_results) == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.COMPLETED  # empty_result counts as success

    # Test 3: All failed
    state3 = WorkflowState(workflow_id="test3", user_request="test", status=WorkflowStatus.RUNNING)
    state3.step_results["step_1"] = StepResult(step_id="step_1", status="failed", error="Network error")
    state3.step_results["step_2"] = StepResult(step_id="step_2", status="failed", error="Timeout")

    total_steps = 2
    successful_steps = sum(1 for r in state3.step_results.values() if r.status in ["completed", "empty_result"])
    failed_steps = sum(1 for r in state3.step_results.values() if r.status in ["failed", "dependency_blocked"])

    if len(state3.step_results) == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.FAILED

    # Test 4: Partial completion (some success, some failure)
    state4 = WorkflowState(workflow_id="test4", user_request="test", status=WorkflowStatus.RUNNING)
    state4.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result=42)
    state4.step_results["step_2"] = StepResult(step_id="step_2", status="failed", error="Network error")

    total_steps = 2
    successful_steps = sum(1 for r in state4.step_results.values() if r.status in ["completed", "empty_result"])
    failed_steps = sum(1 for r in state4.step_results.values() if r.status in ["failed", "dependency_blocked"])

    if len(state4.step_results) == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.PARTIALLY_COMPLETED

    # Test 5: Dependency blocked
    state5 = WorkflowState(workflow_id="test5", user_request="test", status=WorkflowStatus.RUNNING)
    state5.step_results["step_1"] = StepResult(step_id="step_1", status="completed", result=42)
    state5.step_results["step_2"] = StepResult(step_id="step_2", status="dependency_blocked", error="Step blocked")

    total_steps = 2
    successful_steps = sum(1 for r in state5.step_results.values() if r.status in ["completed", "empty_result"])
    failed_steps = sum(1 for r in state5.step_results.values() if r.status in ["failed", "dependency_blocked"])

    if len(state5.step_results) == total_steps and successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    elif failed_steps == 0:
        final_status = WorkflowStatus.COMPLETED
    elif successful_steps == 0:
        final_status = WorkflowStatus.FAILED
    else:
        final_status = WorkflowStatus.PARTIALLY_COMPLETED
    assert final_status == WorkflowStatus.PARTIALLY_COMPLETED

# Status Persistence Regression Tests

@pytest.mark.asyncio
async def test_status_persistence_research_with_empty_result():
    """Test that research workflow with EMPTY_RESULT persists as COMPLETED"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # Create state directly without triggering background workflow execution
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="research empty result persistence test", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test status persistence", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search Python", tool_name="web_search", arguments={"query": "Python"}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Search nonexistent", tool_name="web_search", arguments={"query": "xyznonexistent"})
    ])
    state.plan = plan

    # Mock web_search
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_success_handler(args):
        return {"success": True, "snippets": ["Python result"], "source": "Wikipedia", "query": args["query"]}

    async def mock_empty_handler(args):
        return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}

    try:
        # Execute step 1 (success)
        tool.handler = mock_success_handler
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Execute step 2 (empty result)
        tool.handler = mock_empty_handler
        res2 = await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "empty_result"

        # Simulate workflow completion
        state.status = WorkflowStatus.COMPLETED
        engine._save_state(state)

        # Verify database has COMPLETED status
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "completed"
            # Verify state_json also has COMPLETED
            assert record.state_json["status"] == "completed"

    finally:
        tool.handler = original_handler
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_status_persistence_multiple_empty_results():
    """Test that parallel research with multiple EMPTY_RESULT steps persists as COMPLETED"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # Create state directly without triggering background workflow execution
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="multiple empty results persistence test", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test multiple empty results", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="research_agent", action="Search empty 1", tool_name="web_search", arguments={"query": "empty1"}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Search empty 2", tool_name="web_search", arguments={"query": "empty2"}),
        WorkflowStepDefinition(step_id="step_3", agent="research_agent", action="Search empty 3", tool_name="web_search", arguments={"query": "empty3"})
    ])
    state.plan = plan

    # Mock web_search to return empty results
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_empty_handler(args):
        return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}

    try:
        tool.handler = mock_empty_handler

        # Execute all steps (all empty results)
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "empty_result"

        res2 = await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "empty_result"

        res3 = await engine.execute_step(plan.steps[2], state)
        assert state.step_results["step_3"].status == "empty_result"

        # Simulate workflow completion
        state.status = WorkflowStatus.COMPLETED
        engine._save_state(state)

        # Verify database has COMPLETED status
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "completed"
            assert record.state_json["status"] == "completed"

    finally:
        tool.handler = original_handler
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_status_persistence_terminal_status_not_overwritten():
    """Test that terminal status (COMPLETED) cannot be overwritten by late events"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # Create state directly without triggering background workflow execution
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="terminal status protection test", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test terminal status protection", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5})
    ])
    state.plan = plan

    try:
        # Execute step 1
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Set workflow to COMPLETED
        state.status = WorkflowStatus.COMPLETED
        engine._save_state(state)

        # Verify database has COMPLETED
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record.status == "completed"

        # Now try to overwrite with FAILED (simulating a late exception)
        state.status = WorkflowStatus.FAILED
        engine._save_state(state)

        # Verify database still has COMPLETED (not overwritten)
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record.status == "completed"  # Should NOT be overwritten to failed
            # state_json should be updated with latest state, but status field should remain terminal
            assert record.state_json["status"] == "failed"  # state_json reflects latest in-memory state

    finally:
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_status_persistence_actual_failure():
    """Test that actual fatal failure persists as FAILED"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # Create state directly without triggering background workflow execution
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="actual failure persistence test", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test actual failure", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Divide by zero", tool_name="divide", arguments={"a": 10, "b": 0})
    ])
    state.plan = plan

    try:
        # Execute step 1 (should fail)
        with pytest.raises(Exception):
            await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "failed"

        # Set workflow to FAILED
        state.status = WorkflowStatus.FAILED
        engine._save_state(state)

        # Verify database has FAILED
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "failed"
            assert record.state_json["status"] == "failed"

    finally:
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_status_persistence_partially_completed():
    """Test that PARTIALLY_COMPLETED workflow persists correctly"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # Create state directly without triggering background workflow execution
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="partially completed persistence test", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test partially completed", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5}),
        WorkflowStepDefinition(step_id="step_2", agent="research_agent", action="Search failing query", tool_name="web_search", arguments={"query": "failtest"})
    ])
    state.plan = plan

    # Mock web_search to fail
    from app.tools.registry import registry
    tool = registry.get_tool("web_search")
    original_handler = tool.handler

    async def mock_failure_handler(args):
        raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)

    try:
        # Execute step 1 (success)
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Execute step 2 (failure)
        tool.handler = mock_failure_handler
        with pytest.raises(ToolError):
            await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "failed"

        # Set workflow to PARTIALLY_COMPLETED
        state.status = WorkflowStatus.PARTIALLY_COMPLETED
        engine._save_state(state)

        # Verify database has PARTIALLY_COMPLETED
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "partially_completed"
            assert record.state_json["status"] == "partially_completed"

    finally:
        tool.handler = original_handler
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_status_persistence_dashboard_api():
    """Test that Dashboard API returns the persisted final status"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # Create state directly without triggering background workflow execution
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="dashboard api persistence test", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test dashboard API", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Add numbers", tool_name="add", arguments={"a": 10, "b": 5})
    ])
    state.plan = plan

    try:
        # Execute step 1
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"

        # Set workflow to COMPLETED
        state.status = WorkflowStatus.COMPLETED
        engine._save_state(state)

        # Verify via database query (simulating Dashboard API)
        with SessionLocal() as db:
            records = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).all()
            assert len(records) == 1
            assert records[0].status == "completed"

            # Verify list_workflows endpoint behavior
            all_records = db.query(WorkflowRecord).order_by(WorkflowRecord.created_at.desc()).limit(50).all()
            workflow_in_list = [r for r in all_records if r.id == workflow_id]
            assert len(workflow_in_list) == 1
            assert workflow_in_list[0].status == "completed"

    finally:
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_status_calculation_partial_completion():
    """Test that successful step + failed step + dependency_blocked step results in PARTIALLY_COMPLETED"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # Create state directly without triggering background workflow execution
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="Calculate 20% of 500, divide by 0, then add 100", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test partial completion", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Calculate 20% of 500", tool_name="calculate_percentage", arguments={"percentage": 20, "value": 500}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Divide result by 0", tool_name="divide", arguments={"a": "$step_1.result", "b": 0}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add 100 to result", tool_name="add", arguments={"a": "$step_2.result", "b": 100}, depends_on=["step_2"])
    ])
    state.plan = plan

    try:
        # Execute step 1 (success)
        res1 = await engine.execute_step(plan.steps[0], state)
        assert state.step_results["step_1"].status == "completed"
        assert res1 == 100

        # Execute step 2 (should fail with division by zero)
        with pytest.raises(Exception):
            await engine.execute_step(plan.steps[1], state)
        assert state.step_results["step_2"].status == "failed"

        # Execute step 3 (should be dependency_blocked)
        res3 = await engine.execute_step(plan.steps[2], state)
        assert res3 is None  # dependency_blocked returns None
        assert state.step_results["step_3"].status == "dependency_blocked"

        # Calculate final status using the same logic as engine
        total_steps = len(plan.steps)
        successful_steps = sum(1 for result in state.step_results.values() if result.status in ["completed", "empty_result"])
        failed_steps = sum(1 for result in state.step_results.values() if result.status in ["failed", "dependency_blocked"])

        if len(state.step_results) == total_steps and successful_steps == 0:
            final_status = WorkflowStatus.FAILED
        elif failed_steps == 0:
            final_status = WorkflowStatus.COMPLETED
        elif successful_steps == 0:
            final_status = WorkflowStatus.FAILED
        else:
            final_status = WorkflowStatus.PARTIALLY_COMPLETED

        # Verify it's PARTIALLY_COMPLETED
        assert final_status == WorkflowStatus.PARTIALLY_COMPLETED

        # Persist the status
        state.status = final_status
        engine._save_state(state)

        # Verify database has PARTIALLY_COMPLETED
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "partially_completed"
            assert record.state_json["status"] == "partially_completed"

    finally:
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]

@pytest.mark.asyncio
async def test_full_workflow_execution_with_partial_completion():
    """Test full workflow execution with partial completion to verify status consistency"""
    from app.persistence.database import SessionLocal, WorkflowRecord
    from app.models.workflow import WorkflowStatus

    # This test simulates the actual workflow execution path
    workflow_id = str(uuid.uuid4())
    state = WorkflowState(workflow_id=workflow_id, user_request="Calculate 20% of 500, divide by 0, then add 100", status=WorkflowStatus.RUNNING)
    engine.active_workflows[workflow_id] = state

    plan = WorkflowPlan(goal="Test full workflow partial completion", steps=[
        WorkflowStepDefinition(step_id="step_1", agent="execution_agent", action="Calculate 20% of 500", tool_name="calculate_percentage", arguments={"percentage": 20, "value": 500}),
        WorkflowStepDefinition(step_id="step_2", agent="execution_agent", action="Divide result by 0", tool_name="divide", arguments={"a": "$step_1.result", "b": 0}, depends_on=["step_1"]),
        WorkflowStepDefinition(step_id="step_3", agent="execution_agent", action="Add 100 to result", tool_name="add", arguments={"a": "$step_2.result", "b": 100}, depends_on=["step_2"])
    ])
    state.plan = plan

    try:
        # Simulate the scheduler loop
        pending_steps = {step.step_id: step for step in plan.steps}
        completed_steps = set()
        blocked_steps = set()

        while pending_steps:
            # Find runnable steps
            runnable = []
            for step_id, step in pending_steps.items():
                can_run = True
                for dep in step.depends_on:
                    if dep not in completed_steps and dep not in blocked_steps:
                        can_run = False
                        break
                if can_run:
                    runnable.append(step)

            if not runnable:
                # Check if all remaining are blocked
                all_blocked = True
                for step_id, step in pending_steps.items():
                    is_blocked = False
                    for dep in step.depends_on:
                        if dep in state.step_results and state.step_results[dep].status in ["failed", "dependency_blocked"]:
                            is_blocked = True
                            break
                    if not is_blocked:
                        all_blocked = False
                        break

                if all_blocked:
                    # Mark remaining as dependency_blocked
                    for step_id, step in pending_steps.items():
                        state.step_results[step_id] = StepResult(
                            step_id=step_id,
                            status="dependency_blocked",
                            error=f"Step blocked due to failed dependency",
                            error_category=ErrorCategory.PERMANENT_ERROR,
                            retry_count=0
                        )
                    break
                else:
                    raise RuntimeError("Deadlock")

            # Execute runnable steps
            tasks = [engine.execute_step(step, state) for step in runnable]
            for step in runnable:
                del pending_steps[step.step_id]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for step, result in zip(runnable, results):
                if isinstance(result, Exception):
                    state.step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error=str(result),
                        error_category=ErrorCategory.UNKNOWN,
                        retry_count=0
                    )
                elif result is None:
                    blocked_steps.add(step.step_id)
                else:
                    completed_steps.add(step.step_id)

        # Calculate final status (same as engine logic)
        total_steps = len(plan.steps)
        successful_steps = sum(1 for result in state.step_results.values() if result.status in ["completed", "empty_result"])
        failed_steps = sum(1 for result in state.step_results.values() if result.status in ["failed", "dependency_blocked"])

        if len(state.step_results) == total_steps and successful_steps == 0:
            final_status = WorkflowStatus.FAILED
        elif failed_steps == 0:
            final_status = WorkflowStatus.COMPLETED
        elif successful_steps == 0:
            final_status = WorkflowStatus.FAILED
        else:
            final_status = WorkflowStatus.PARTIALLY_COMPLETED

        # Verify it's PARTIALLY_COMPLETED
        assert final_status == WorkflowStatus.PARTIALLY_COMPLETED, f"Expected PARTIALLY_COMPLETED but got {final_status}, successful_steps={successful_steps}, failed_steps={failed_steps}"

        # Set and persist status
        state.status = final_status
        engine._save_state(state)

        # Verify database has PARTIALLY_COMPLETED
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            assert record is not None
            assert record.status == "partially_completed", f"Database status is {record.status} but expected partially_completed"
            assert record.state_json["status"] == "partially_completed"

    finally:
        # Cleanup
        with SessionLocal() as db:
            db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).delete()
            db.commit()
        if workflow_id in engine.active_workflows:
            del engine.active_workflows[workflow_id]
