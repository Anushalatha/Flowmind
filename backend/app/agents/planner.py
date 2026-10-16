from app.agents.base import BaseAgent
from app.models.workflow import WorkflowPlan
from app.config import settings
from app.tools.registry import registry

class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__("planner")
        self.model = settings.PLANNER_MODEL

    async def execute(self, user_request: str) -> WorkflowPlan:
        tools_list = []
        for name, tool in registry.list_tools().items():
            tools_list.append(f"- {name}: {tool.description}")
        tools_str = "\n".join(tools_list)

        system_prompt = f"""You are the Planner Agent. Your job is to create a structured workflow plan from the user's natural language request.
You have access to the following tools:
{tools_str}

Available agents:
- execution_agent
- research_agent
- analysis_agent
- reviewer_agent
- synthesis_agent

Create a workflow plan consisting of a series of steps.
IMPORTANT: Each step MUST have a step_id in the format "step_1", "step_2", "step_3", etc. (sequential numbering starting from 1).
Each step must specify an assigned agent, an action description, a specific tool to use, the arguments for the tool, and any dependencies on previous steps.
If you need subsequent steps to use the outputs of previous steps, you should use the dependency resolution format by referencing the full step_id with a $ prefix, e.g. "$step_1" or "$step_1.result".
The depends_on field should contain the full step_id string (e.g., "step_1"), not just the number.

DEPENDENCY RESOLUTION AND TOOL OUTPUTS:
- When referencing a step's entire output, use "$step_X.result"
- When referencing a specific field from a step's output, use "$step_X.result.field_name"
- The field_name MUST match exactly what the tool returns (see tool descriptions for output structure)
- Examples:
  * For http_request: Use "$step_X.result.body" to get the response body text
  * For validate_response: Use "$step_X.result.data" to get the parsed JSON object
  * For web_search: Use "$step_X.result.snippets" to get the search results
- NEVER invent field names that are not documented in the tool description
- If a tool returns documented fields like "status_code, headers, body, success", you can only reference those documented fields

RESEARCH WORKFLOW BEST PRACTICES:
- For research requests, if you expect a topic might not have Wikipedia coverage, you can add a fallback web_search_fallback step that depends on the primary web_search step.
- The fallback step should only be added if the primary search is expected to potentially return no results.
- Use depends_on to ensure the fallback runs after the primary search.
- Example: primary web_search for specific topic → web_search_fallback with same topic → synthesis combines both results.

CRITICAL: Do NOT generate a "final_response", "synthesis", or "none" step. The workflow engine will automatically run synthesis after all tool steps complete to produce the final response. Only generate steps that use actual tools from the list above.
The tool_name field MUST be one of the available tools listed above. Never use "none", "null", "final_response", or any placeholder value.

ACTION DESCRIPTION REQUIREMENTS:
- The "action" field MUST be a descriptive, human-readable summary of what the step does
- The action field is used as the PRIMARY LABEL in the workflow graph - it must be meaningful
- Use specific details from the user request and tool arguments
- NEVER use generic verbs like "search", "fetch", "analyze", "validate", "extract" alone
- NEVER use the tool name as the action description
- Include actual numbers, queries, or field names from the arguments
- Examples of GOOD action descriptions:
  * "Search FastAPI documentation for async support"
  * "Calculate 18% of 2500"
  * "Add 350 to the percentage result"
  * "Divide the sum by 5"
  * "Fetch data from https://api.example.com"
  * "Validate JSON response structure"
  * "Extract title and description fields"
  * "Compare FastAPI vs Flask features"
  * "Generate technical recommendation"
- Examples of BAD action descriptions (DO NOT use these):
  * "search"
  * "calculate"
  * "add"
  * "divide"
  * "fetch"
  * "validate"
  * "analyze"
  * "extract"
  * "calculate_percentage"
  * "web_search"
  * "http_request"
- The action should be descriptive enough that a user can understand what the step does without seeing the tool arguments
- For web_search: Include the actual search query in the action description (e.g., "Search for FastAPI async support")
- For calculate_percentage: Include the actual percentage and value (e.g., "Calculate 18% of 2500")
- For http_request: Include the actual URL or what it's fetching (e.g., "Fetch data from https://api.example.com")
- For arithmetic operations: Include the actual numbers being operated on

Return a JSON object conforming strictly to the requested schema. Ensure that maximum steps do not exceed {settings.MAX_AGENT_STEPS}.
"""

        plan = await self.provider.structured_generate(
            prompt=f"User request: {user_request}",
            schema=WorkflowPlan,
            model=self.model,
            system_prompt=system_prompt
        )

        # Validate step IDs format
        for step in plan.steps:
            if not step.step_id.startswith("step_") or not step.step_id[5:].isdigit():
                raise ValueError(f"Invalid step_id format: '{step.step_id}'. Step IDs must be in format 'step_1', 'step_2', etc.")

        # Validate depends_on field format
        for step in plan.steps:
            for dep in step.depends_on:
                if not dep.startswith("step_") or not dep[5:].isdigit():
                    raise ValueError(f"Invalid depends_on format: '{dep}' in step '{step.step_id}'. Dependencies must be in format 'step_1', 'step_2', etc.")

        # Validate tool names
        available_tools = set(registry.list_tools().keys())
        invalid_tool_names = ["none", "null", "", "final_response", "synthesis"]
        for step in plan.steps:
            if step.tool_name in invalid_tool_names or step.tool_name not in available_tools:
                raise ValueError(f"Invalid tool_name '{step.tool_name}' in step '{step.step_id}'. Tool must be one of: {sorted(available_tools)}")

        # Validate action descriptions are not generic
        generic_verbs = ["search", "fetch", "analyze", "validate", "extract", "calculate", "add", "subtract", "multiply", "divide"]
        for step in plan.steps:
            action_lower = step.action.lower().strip()
            
            # Check if action is exactly a generic verb
            if action_lower in generic_verbs:
                raise ValueError(
                    f"Action description '{step.action}' in step '{step.step_id}' is too generic. "
                    f"Action must be descriptive and include specific details from the user request. "
                    f"Instead of '{step.action}', use something like 'Search for X' or 'Validate Y response'"
                )
            
            # Check if action is just the tool name (common LLM mistake)
            if action_lower == step.tool_name.lower():
                raise ValueError(
                    f"Action description '{step.action}' in step '{step.step_id}' is just the tool name. "
                    f"Action must be a descriptive sentence, not the tool name. "
                    f"Instead of '{step.action}', use something like 'Calculate 18% of 2500' or 'Add 350 to result'"
                )
            
            # Check if action contains actual numbers or specific content (this is good)
            # If it has numbers, it's likely descriptive enough for arithmetic operations
            has_number = any(char.isdigit() for char in step.action)
            
            # If it's an arithmetic operation and has numbers, it's descriptive enough
            if step.tool_name in ["calculate_percentage", "add", "subtract", "multiply", "divide"] and has_number:
                continue  # This is good, skip further checks
            
            # For web_search, check if it includes the query
            if step.tool_name == "web_search" and "query" in step.arguments:
                query = str(step.arguments["query"])
                if query.lower() in action_lower and len(query) > 3:
                    continue  # This is good, skip further checks
            
            # Check if action starts with a generic verb and is too short (only if it doesn't have numbers)
            for verb in generic_verbs:
                if action_lower.startswith(verb) and len(step.action) < len(verb) + 15 and not has_number:
                    raise ValueError(
                        f"Action description '{step.action}' in step '{step.step_id}' is too generic. "
                        f"Action must be descriptive and include specific details from the user request. "
                        f"Instead of '{step.action}', use something like 'Calculate 18% of 2500' or 'Add 350 to result'"
                    )
            
        # Validate dependency field references
        # Build a map of step_id -> tool_name for quick lookup
        step_tools = {step.step_id: step.tool_name for step in plan.steps}

        for step in plan.steps:
            for arg_name, arg_value in step.arguments.items():
                if isinstance(arg_value, str) and arg_value.startswith("$step_"):
                    parts = arg_value.split(".")
                    ref_step_id = parts[0][1:]  # Remove $ prefix

                    # Check if referenced step exists
                    if ref_step_id not in step_tools:
                        raise ValueError(f"Invalid dependency reference in step '{step.step_id}': Step '{ref_step_id}' does not exist")

                    # If a field is specified (e.g., $step_1.result.body or $step_1.body)
                    if len(parts) > 1:
                        field_parts = parts[1:]  # Everything after $step_X
                        # Skip "result" if present, get the actual field name
                        if field_parts[0] == "result":
                            if len(field_parts) > 1:
                                field_name = field_parts[1]
                            else:
                                # $step_X.result with no field - this is valid (entire result)
                                # This works for both scalar and dict results
                                continue
                        else:
                            field_name = field_parts[0]

                        # Get the tool being referenced to check its output structure
                        ref_tool_name = step_tools[ref_step_id]
                        ref_tool = registry.get_tool(ref_tool_name)

                        # Extract known output fields from tool description
                        # Tools document their output in the description like "Returns: {field1, field2, field3}"
                        # Or "Returns: result (number)" for scalar returns
                        desc = ref_tool.description.lower()
                        if "returns:" in desc:
                            returns_part = desc.split("returns:")[1].split(".")[0]
                            # Extract field names from the description
                            # This is a heuristic - the description should document the actual output
                            known_fields = []
                            if "{" in returns_part and "}" in returns_part:
                                field_str = returns_part.split("{")[1].split("}")[0]
                                known_fields = [f.strip() for f in field_str.split(",")]
                            # If no braces, it's likely a scalar return like "result (number)"
                            # In this case, we don't validate field access since there are no fields

                            # Only validate if we have known fields from the description AND it's a dict return
                            if known_fields and field_name not in known_fields:
                                raise ValueError(
                                    f"Invalid dependency reference in step '{step.step_id}': "
                                    f"Field '{field_name}' is not a documented output of tool '{ref_tool_name}'. "
                                    f"Tool '{ref_tool_name}' returns: {returns_part}. "
                                    f"Available fields: {known_fields}"
                                )

        return plan
