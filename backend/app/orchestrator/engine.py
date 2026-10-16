import asyncio
import uuid
import re
from datetime import datetime
from typing import Dict, Any, List
from app.models.workflow import WorkflowState, WorkflowStatus, StepResult, WorkflowPlan, ErrorCategory, StepStatus
from app.models.events import ExecutionEvent
from app.agents.planner import PlannerAgent
from app.agents.synthesis import SynthesisAgent
from app.tools.registry import registry
from app.tools.builtins import ToolError
from app.persistence.database import SessionLocal, WorkflowRecord, EventRecord
from pydantic import ValidationError

class WorkflowEngine:
    def __init__(self):
        self.planner = PlannerAgent()
        self.synthesis = SynthesisAgent()
        self.events_queue = asyncio.Queue()
        self.active_workflows: Dict[str, WorkflowState] = {}

    def new_workflow(self, request: str) -> str:
        workflow_id = str(uuid.uuid4())
        state = WorkflowState(workflow_id=workflow_id, user_request=request)
        self.active_workflows[workflow_id] = state
        self._save_state(state)
        # We spawn the execution as a background task with proper error handling
        task = asyncio.create_task(self.run_workflow(workflow_id))
        task.add_done_callback(lambda t: self._handle_task_exception(t, workflow_id))
        return workflow_id

    def _handle_task_exception(self, task, workflow_id: str):
        """Handle exceptions from background tasks to prevent silent failures."""
        try:
            exception = task.exception()
            if exception is not None:
                print(f"Background task failed for workflow {workflow_id}: {exception}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(f"Error handling task exception for workflow {workflow_id}: {e}")

    async def emit(self, event: ExecutionEvent):
        await self.events_queue.put(event)
        self._save_event(event)
        from app.orchestrator.hub import hub
        await hub.publish(event)
        print(f"[{event.timestamp}] {event.event_type} - {event.status} ({event.workflow_id})")

    def _save_state(self, state: WorkflowState):
        with SessionLocal() as db:
            record = db.query(WorkflowRecord).filter(WorkflowRecord.id == state.workflow_id).first()
            if not record:
                record = WorkflowRecord(id=state.workflow_id, user_request=state.user_request, status=state.status.value, state_json=state.model_dump(mode='json'))
                db.add(record)
            else:
                # IMPORTANT: Do not overwrite terminal status (COMPLETED, FAILED, PARTIALLY_COMPLETED)
                # This prevents late step/tool events from overwriting the final workflow status
                terminal_statuses = ["completed", "failed", "partially_completed"]
                if record.status not in terminal_statuses:
                    record.status = state.status.value
                # Always update state_json to capture latest step results
                record.state_json = state.model_dump(mode='json')
            db.commit()

    def _save_event(self, event: ExecutionEvent):
        with SessionLocal() as db:
            record = EventRecord(
                id=event.event_id,
                workflow_id=event.workflow_id,
                timestamp=event.timestamp,
                event_type=event.event_type,
                step_id=event.step_id,
                agent_id=event.agent_id,
                tool_name=event.tool_name,
                status=event.status,
                metadata_json=event.metadata
            )
            db.add(record)
            db.commit()
            
    def _resolve_args(self, args: dict, state: WorkflowState) -> dict:
        resolved = {}
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("$step_"):
                # Dependency resolution
                # Format: $step_1 or $step_1.result or $step_1.result.field
                parts = v.split(".")
                step_id = parts[0][1:] # remove $ prefix (so $step_1 becomes step_1)

                # Check if step exists
                if step_id not in state.step_results:
                    available_steps = list(state.step_results.keys())
                    raise ValueError(f"Unresolved dependency: Step '{step_id}' not found in step results. Available steps: {available_steps}")

                step_result = state.step_results[step_id]

                # Check if upstream step failed or was dependency blocked
                # EMPTY_RESULT is allowed - the step executed successfully but returned no data
                if step_result.status in ["failed", "dependency_blocked"]:
                    raise ValueError(f"Cannot resolve dependency: Step '{step_id}' failed with error: {step_result.error}")

                # Check if step has a result
                if step_result.result is None:
                    raise ValueError(f"Cannot resolve dependency: Step '{step_id}' has no result")

                res = step_result.result

                # Handle field access
                if len(parts) > 1:
                    # parts[1] could be "result" or a direct field name
                    # If parts[1] is "result", we may have parts[2] as the actual field
                    if parts[1] == "result":
                        if len(parts) > 2:
                            # Format: $step_1.result.field
                            if isinstance(res, dict):
                                field = parts[2]
                                if field not in res:
                                    raise ValueError(f"Cannot resolve dependency: Field '{field}' not found in step '{step_id}' result")
                                resolved[k] = res[field]
                            else:
                                raise ValueError(f"Cannot resolve dependency: Cannot access field '{parts[2]}' on non-dict result from step '{step_id}'")
                        else:
                            # Format: $step_1.result (no field specified)
                            # Return the entire result for backward compatibility
                            resolved[k] = res
                    else:
                        # Format: $step_1.field (no .result prefix)
                        if isinstance(res, dict):
                            field = parts[1]
                            if field not in res:
                                raise ValueError(f"Cannot resolve dependency: Field '{field}' not found in step '{step_id}' result")
                            resolved[k] = res[field]
                        else:
                            raise ValueError(f"Cannot resolve dependency: Cannot access field '{parts[1]}' on non-dict result from step '{step_id}'")
                else:
                    # No field specified, return the entire result
                    resolved[k] = res
            else:
                resolved[k] = v
        return resolved

    def _validate_step_result(self, result: Any, tool_name: str) -> tuple[bool, str]:
        """
        Validate that a tool result indicates actual success.
        Returns (is_valid, status_reason) where:
        - is_valid: True if tool executed successfully
        - status_reason: "success", "empty_result", or "failure"
        """
        # Calculator and text tools return numbers directly - these are always valid
        if tool_name in ["add", "subtract", "multiply", "divide", "calculate_percentage", "word_count"]:
            if isinstance(result, (int, float)):
                return True, "success"
            return False, "failure"

        # Check for structured failure indicators
        if isinstance(result, dict):
            if result.get("success") is False:
                return False, "failure"
            
            # Check for empty results in expected fields
            if tool_name == "web_search":
                # Web search with empty snippets is a valid EMPTY_RESULT, not a failure
                if result.get("snippets") is not None and len(result.get("snippets", [])) == 0:
                    return True, "empty_result"
            elif tool_name == "http_request":
                # HTTP request should have a status code and body
                if result.get("status_code") is None:
                    return False, "failure"
            elif tool_name == "validate_response":
                # Validation should have valid flag
                if result.get("valid") is False:
                    return False, "failure"
        
        # Check for error strings (legacy behavior)
        elif isinstance(result, str) and (result.startswith("Failed to") or result.startswith("Error:")):
            return False, "failure"
        
        return True, "success"

    def _create_step_summary(self, step_results: Dict[str, StepResult]) -> Dict[str, Any]:
        """Create a summary of step results for synthesis, including failure details."""
        summary = {
            "successful_steps": {},
            "empty_result_steps": {},
            "failed_steps": {},
            "total_steps": len(step_results),
            "successful_count": 0,
            "empty_result_count": 0,
            "failed_count": 0
        }

        for step_id, result in step_results.items():
            if result.status == "completed":
                summary["successful_steps"][step_id] = {
                    "result": result.result,
                    "retry_count": result.retry_count
                }
                summary["successful_count"] += 1
            elif result.status == "empty_result":
                # Empty result is a valid execution outcome, not a failure
                summary["empty_result_steps"][step_id] = {
                    "result": result.result,
                    "retry_count": result.retry_count
                }
                summary["empty_result_count"] += 1
            elif result.status == "dependency_blocked":
                # Step was blocked due to failed dependency
                summary["failed_steps"][step_id] = {
                    "error": result.error or "Step blocked due to failed dependency",
                    "error_category": result.error_category.value if result.error_category else "dependency_blocked",
                    "retry_count": result.retry_count
                }
                summary["failed_count"] += 1
            else:
                # Actual failure (failed, skipped, etc.)
                summary["failed_steps"][step_id] = {
                    "error": result.error,
                    "error_category": result.error_category.value if result.error_category else "unknown",
                    "retry_count": result.retry_count
                }
                summary["failed_count"] += 1

        return summary

    async def run_workflow(self, workflow_id: str):
        state = self.active_workflows[workflow_id]
        try:
            await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=workflow_id, event_type="workflow.started", status="started"))
            
            state.status = WorkflowStatus.PLANNING
            self._save_state(state)
            await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=workflow_id, event_type="planner.started", status="started"))
            
            plan = await self.planner.execute(state.user_request)
            state.plan = plan
            state.status = WorkflowStatus.RUNNING
            self._save_state(state)
            await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=workflow_id, event_type="planner.completed", status="completed", metadata={"plan": plan.model_dump(mode='json')}))

            # Execute steps
            # To handle dependencies simply in V1, we build a graph.
            # For parallel execution, we can use asyncio.gather for tasks that have no pending dependencies.
            
            pending_steps = {step.step_id: step for step in plan.steps}
            completed_steps = set()
            blocked_steps = set()  # Steps that are dependency_blocked and can't execute
            
            while pending_steps:
                # Find runnable steps (dependencies are met)
                runnable = []
                for step_id, step in pending_steps.items():
                    can_run = True
                    for dep in step.depends_on:
                        # A dependency is considered satisfied if:
                        # 1. It's in completed_steps (executed successfully or empty_result)
                        # 2. It's in blocked_steps (dependency_blocked - can't execute but won't succeed)
                        if dep not in completed_steps and dep not in blocked_steps:
                            can_run = False
                            break
                    if can_run:
                        runnable.append(step)
                        
                if not runnable:
                    # Check if all remaining pending steps are blocked (not a deadlock)
                    # A deadlock only occurs if there are pending steps whose dependencies will never be satisfied
                    all_blocked = True
                    for step_id, step in pending_steps.items():
                        # Check if this step is blocked due to failed dependencies
                        is_blocked = False
                        for dep in step.depends_on:
                            if dep in state.step_results and state.step_results[dep].status in ["failed", "dependency_blocked"]:
                                is_blocked = True
                                break
                        if not is_blocked:
                            all_blocked = False
                            break

                    if all_blocked:
                        # All remaining steps are blocked due to failed dependencies
                        # This is not a deadlock - we just can't proceed
                        # Mark remaining steps as dependency_blocked
                        for step_id, step in pending_steps.items():
                            state.step_results[step_id] = StepResult(
                                step_id=step_id,
                                status="dependency_blocked",
                                error=f"Step blocked due to failed dependency",
                                error_category=ErrorCategory.PERMANENT_ERROR,
                                retry_count=0
                            )
                            # Emit event for blocked step
                            await self.emit(ExecutionEvent(
                                event_id=str(uuid.uuid4()),
                                workflow_id=workflow_id,
                                event_type="step.blocked",
                                step_id=step_id,
                                agent_id=step.agent,
                                tool_name=step.tool_name,
                                status="dependency_blocked",
                                metadata={"error": "Step blocked due to failed dependency"}
                            ))
                        self._save_state(state)
                        break  # Exit the loop, workflow will complete with partial results
                    else:
                        # Genuine deadlock: steps are pending but none can run and none are blocked
                        raise RuntimeError("Deadlock in workflow execution. Unresolved dependencies.")
                    
                # Run steps in parallel
                tasks = [self.execute_step(step, state) for step in runnable]
                
                # Removing from pending before yielding control to prevent double execution if state iteration fails
                for step in runnable:
                    del pending_steps[step.step_id]
                    
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for step, result in zip(runnable, results):
                    if isinstance(result, Exception):
                        # Step failed - record and continue for partial completion detection
                        state.errors.append({"step_id": step.step_id, "error": str(result)})
                        state.step_results[step.step_id] = StepResult(
                            step_id=step.step_id,
                            status="failed",
                            error=str(result),
                            error_category=ErrorCategory.UNKNOWN,
                            retry_count=0
                        )
                        self._save_state(state)
                        # If this is a critical failure (e.g., tool not found), raise immediately
                        if "Tool .+ not found" in str(result) or "Unresolved dependency" in str(result):
                            raise result
                    elif result is None:
                        # Step was dependency_blocked - it's already recorded in state.step_results
                        # Add to blocked_steps so dependent steps know this dependency won't be satisfied
                        blocked_steps.add(step.step_id)
                    else:
                        # Step completed successfully (including empty_result)
                        completed_steps.add(step.step_id)

            # Determine final status based on step results
            total_steps = len(plan.steps)
            # Count both completed and empty_result as successful execution
            successful_steps = sum(1 for result in state.step_results.values() if result.status in ["completed", "empty_result"])
            failed_steps = sum(1 for result in state.step_results.values() if result.status in ["failed", "dependency_blocked"])
            blocked_steps = sum(1 for result in state.step_results.values() if result.status == "dependency_blocked")

            # Workflow status logic:
            # - COMPLETED: All steps executed successfully (including empty results)
            # - PARTIALLY_COMPLETED: Some steps succeeded/empty, some failed/blocked
            # - FAILED: All steps failed or no steps could execute
            if len(state.step_results) == total_steps and successful_steps == 0:
                # All steps failed
                final_status = WorkflowStatus.FAILED
            elif failed_steps == 0:
                # All steps succeeded (including empty results)
                final_status = WorkflowStatus.COMPLETED
            elif successful_steps == 0:
                # All steps failed
                final_status = WorkflowStatus.FAILED
            else:
                # Some steps succeeded (including empty results), some failed/blocked
                final_status = WorkflowStatus.PARTIALLY_COMPLETED

            # Run synthesis with failure context
            step_summary = self._create_step_summary(state.step_results)
            synth_res = await self.synthesis.execute(state.user_request, step_summary, plan.model_dump() if plan else None)
            state.final_response = synth_res
            state.status = final_status
            self._save_state(state)
            await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=workflow_id, event_type="workflow.completed", status=final_status.value, metadata={"final_response": synth_res, "successful_steps": successful_steps, "failed_steps": failed_steps, "empty_result_steps": step_summary.get("empty_result_count", 0)}))
            
        except Exception as e:
            # Only set FAILED if workflow hasn't already reached a terminal status
            terminal_statuses = [WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.PARTIALLY_COMPLETED]
            if state.status not in terminal_statuses:
                state.status = WorkflowStatus.FAILED
                state.errors.append({"workflow": str(e)})
                # First, ensure workflow state is persisted
                try:
                    self._save_state(state)
                except Exception as state_error:
                    print(f"CRITICAL: Failed to save workflow state: {state_error}")
                    import traceback
                    traceback.print_exc()

                print(f"Workflow failed with error: {str(e)}")
                import traceback
                traceback.print_exc()

                # Then, attempt to emit failure event - handle separately from state persistence
                try:
                    await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=workflow_id, event_type="workflow.failed", status="failed", metadata={"error": str(e)}))
                except Exception as event_error:
                    print(f"Failed to emit workflow.failed event: {event_error}")
                    import traceback
                    traceback.print_exc()
                    # Event emission failure should not prevent workflow from being marked as FAILED
                    # The state was already saved above
            else:
                # Workflow already reached terminal status, just log the exception
                print(f"Exception occurred after workflow reached terminal status {state.status}: {str(e)}")
                import traceback
                traceback.print_exc()
                # Still save state to capture any partial updates, but don't change status
                try:
                    self._save_state(state)
                except Exception as state_error:
                    print(f"Failed to save workflow state after terminal status: {state_error}")

    async def execute_step(self, step: Any, state: WorkflowState) -> Any:
        # Agent execution wrapping a tool.
        # Implements retry logic
        max_retries = 3
        attempt = 0

        await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="step.started", step_id=step.step_id, agent_id=step.agent, tool_name=step.tool_name, status="started"))

        while attempt <= max_retries:
            attempt += 1
            try:
                # Resolve args - mark as dependency_blocked if dependencies failed
                try:
                    resolved_args = self._resolve_args(step.arguments, state)
                except ValueError as e:
                    # Dependency resolution errors are deterministic - mark as dependency_blocked
                    error_str = str(e)
                    await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="step.completed", step_id=step.step_id, agent_id=step.agent, tool_name=step.tool_name, status="dependency_blocked", metadata={"error": error_str, "error_category": ErrorCategory.PERMANENT_ERROR.value}))
                    state.step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status="dependency_blocked",
                        error=error_str,
                        error_category=ErrorCategory.PERMANENT_ERROR,
                        retry_count=0
                    )
                    self._save_state(state)
                    # Return None to indicate step was blocked (not a failure to retry)
                    return None

                # Get tool
                tool_def = registry.get_tool(step.tool_name)

                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="tool.started", step_id=step.step_id, agent_id=step.agent, tool_name=step.tool_name, status="started", metadata={"args": resolved_args}))

                # Execute tool
                if asyncio.iscoroutinefunction(tool_def.handler):
                    result = await tool_def.handler(resolved_args)
                else:
                    result = tool_def.handler(resolved_args)

                # Validate tool result - check if it indicates failure or empty result
                is_valid, status_reason = self._validate_step_result(result, step.tool_name)
                
                if not is_valid:
                    error_msg = f"Tool returned invalid or failed result: {result}"
                    raise ToolError(error_msg, ErrorCategory.PERMANENT_ERROR)
                
                # Determine step status based on validation result
                step_status = StepStatus.COMPLETED
                if status_reason == "empty_result":
                    step_status = StepStatus.EMPTY_RESULT
                
                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="tool.completed", step_id=step.step_id, agent_id=step.agent, tool_name=step.tool_name, status="completed", metadata={"result": result, "status_reason": status_reason}))

                # Save result
                state.step_results[step.step_id] = StepResult(
                    step_id=step.step_id,
                    status=step_status,
                    result=result,
                    retry_count=attempt - 1,
                    started_at=datetime.utcnow(),
                    completed_at=datetime.utcnow()
                )
                self._save_state(state)

                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="step.completed", step_id=step.step_id, status=step_status.value))

                return result

            except ToolError as e:
                # ToolError with category - check if retryable
                error_str = str(e)
                error_category = e.category
                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="tool.failed", step_id=step.step_id, agent_id=step.agent, tool_name=step.tool_name, status="failed", metadata={"error": error_str, "error_category": error_category.value if error_category else "unknown"}))

                # Permanent errors should not be retried
                if error_category == ErrorCategory.PERMANENT_ERROR:
                    state.step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error=error_str,
                        error_category=error_category.value if error_category else None,
                        retry_count=attempt - 1
                    )
                    self._save_state(state)  # Save state before raising
                    raise e

                # Max retries reached - save with the original error category
                if attempt > max_retries:
                    state.step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error=error_str,
                        error_category=error_category.value if error_category else None,
                        retry_count=attempt - 1
                    )
                    # Directly update the database to force-save the final step result
                    with SessionLocal() as db:
                        record = db.query(WorkflowRecord).filter(WorkflowRecord.id == state.workflow_id).first()
                        if record:
                            record.state_json = state.model_dump(mode='json')
                            db.commit()
                    raise e

                # Retryable transient errors
                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="retry.started", step_id=step.step_id, status="started", metadata={"attempt": attempt}))
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

            except ValueError as e:
                # Dependency resolution errors - should have been handled above, but catch as safety
                error_str = str(e)
                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="tool.failed", step_id=step.step_id, agent_id=step.agent, tool_name=step.tool_name, status="failed", metadata={"error": error_str, "error_category": ErrorCategory.PERMANENT_ERROR.value}))
                state.step_results[step.step_id] = StepResult(
                    step_id=step.step_id,
                    status="failed",
                    error=error_str,
                    error_category=ErrorCategory.PERMANENT_ERROR,
                    retry_count=0
                )
                self._save_state(state)
                raise e

            except Exception as e:
                # Other exceptions - check if it's a ToolError that wasn't caught above
                error_str = str(e)
                error_category = ErrorCategory.UNKNOWN
                
                # Check if this is a ToolError and extract the category
                if isinstance(e, ToolError):
                    error_category = e.category
                
                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="tool.failed", step_id=step.step_id, agent_id=step.agent, tool_name=step.tool_name, status="failed", metadata={"error": error_str, "error_category": error_category.value if error_category else "unknown"}))

                # Check for deterministic failures that shouldn't be retried
                non_retryable_patterns = ["division by zero", "KeyError", "invalid argument"]
                is_non_retryable = any(nr in error_str for nr in non_retryable_patterns)
                # Check for "Tool X not found" and "Field X not found" patterns using regex
                if re.search(r"Tool .+ not found", error_str) or re.search(r"Field .+ not found", error_str):
                    is_non_retryable = True

                if is_non_retryable or attempt > max_retries:
                    state.step_results[step.step_id] = StepResult(
                        step_id=step.step_id,
                        status="failed",
                        error=error_str,
                        error_category=error_category.value if error_category else ErrorCategory.UNKNOWN.value,
                        retry_count=attempt
                    )
                    self._save_state(state)  # Save state before raising
                    raise e

                # Retryable
                await self.emit(ExecutionEvent(event_id=str(uuid.uuid4()), workflow_id=state.workflow_id, event_type="retry.started", step_id=step.step_id, status="started", metadata={"attempt": attempt}))
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

engine = WorkflowEngine()
