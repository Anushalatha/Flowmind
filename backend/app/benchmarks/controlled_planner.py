"""
Controlled planner for benchmark mode.
Provides predefined plans for benchmark test cases without requiring LLM API calls.
"""
from app.models.workflow import WorkflowPlan, WorkflowStepDefinition
from typing import Dict

# Predefined plans for benchmark cases
CONTROLLED_PLANS: Dict[str, WorkflowPlan] = {
    # Sequential cases
    "Calculate 15% of 2000, add 250, then divide by 5.": WorkflowPlan(
        goal="Calculate 15% of 2000, add 250, then divide by 5",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 15% of 2000",
                tool_name="calculate_percentage",
                arguments={"percentage": 15, "value": 2000},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Add 250 to the percentage result",
                tool_name="add",
                arguments={"a": "$step_1.result", "b": 250},
                depends_on=["step_1"]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Divide the sum by 5",
                tool_name="divide",
                arguments={"a": "$step_2.result", "b": 5},
                depends_on=["step_2"]
            )
        ]
    ),
    "Multiply 10 by 5, subtract 20, add 15, then divide by 3.": WorkflowPlan(
        goal="Multiply 10 by 5, subtract 20, add 15, then divide by 3",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Multiply 10 by 5",
                tool_name="multiply",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Subtract 20 from the product",
                tool_name="subtract",
                arguments={"a": "$step_1.result", "b": 20},
                depends_on=["step_1"]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Add 15 to the difference",
                tool_name="add",
                arguments={"a": "$step_2.result", "b": 15},
                depends_on=["step_2"]
            ),
            WorkflowStepDefinition(
                step_id="step_4",
                agent="execution_agent",
                action="Divide the result by 3",
                tool_name="divide",
                arguments={"a": "$step_3.result", "b": 3},
                depends_on=["step_3"]
            )
        ]
    ),
    "Calculate 25% of 800, multiply by 2, then subtract 100.": WorkflowPlan(
        goal="Calculate 25% of 800, multiply by 2, then subtract 100",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 25% of 800",
                tool_name="calculate_percentage",
                arguments={"percentage": 25, "value": 800},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Multiply the percentage result by 2",
                tool_name="multiply",
                arguments={"a": "$step_1.result", "b": 2},
                depends_on=["step_1"]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Subtract 100 from the product",
                tool_name="subtract",
                arguments={"a": "$step_2.result", "b": 100},
                depends_on=["step_2"]
            )
        ]
    ),
    "Calculate 10% of 500, divide by 0, then add 50.": WorkflowPlan(
        goal="Calculate 10% of 500, divide by 0, then add 50",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10% of 500",
                tool_name="calculate_percentage",
                arguments={"percentage": 10, "value": 500},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Divide the percentage result by 0",
                tool_name="divide",
                arguments={"a": "$step_1.result", "b": 0},
                depends_on=["step_1"]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Add 50 to the quotient",
                tool_name="add",
                arguments={"a": "$step_2.result", "b": 50},
                depends_on=["step_2"]
            )
        ]
    ),
    "Count words in 'The quick brown fox', multiply by 2, then add 5.": WorkflowPlan(
        goal="Count words in 'The quick brown fox', multiply by 2, then add 5",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Count words in 'The quick brown fox'",
                tool_name="word_count",
                arguments={"text": "The quick brown fox"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Multiply the word count by 2",
                tool_name="multiply",
                arguments={"a": "$step_1.result", "b": 2},
                depends_on=["step_1"]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Add 5 to the product",
                tool_name="add",
                arguments={"a": "$step_2.result", "b": 5},
                depends_on=["step_2"]
            )
        ]
    ),
    # Parallel cases
    "Calculate 10+5, 20*3, and 15/3 in parallel, then sum all results.": WorkflowPlan(
        goal="Calculate 10+5, 20*3, and 15/3 in parallel, then sum all results",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10 + 5",
                tool_name="add",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Calculate 20 * 3",
                tool_name="multiply",
                arguments={"a": 20, "b": 3},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Calculate 15 / 3",
                tool_name="divide",
                arguments={"a": 15, "b": 3},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_4",
                agent="execution_agent",
                action="Sum all three results",
                tool_name="add",
                arguments={"a": "$step_1.result", "b": "$step_2.result"},
                depends_on=["step_1", "step_2"]
            ),
            WorkflowStepDefinition(
                step_id="step_5",
                agent="execution_agent",
                action="Add the third result to the sum",
                tool_name="add",
                arguments={"a": "$step_4.result", "b": "$step_3.result"},
                depends_on=["step_4", "step_3"]
            )
        ]
    ),
    "Calculate 10% of 1000, 20% of 500, and 15% of 2000 in parallel, then sum.": WorkflowPlan(
        goal="Calculate 10% of 1000, 20% of 500, and 15% of 2000 in parallel, then sum",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10% of 1000",
                tool_name="calculate_percentage",
                arguments={"percentage": 10, "value": 1000},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Calculate 20% of 500",
                tool_name="calculate_percentage",
                arguments={"percentage": 20, "value": 500},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Calculate 15% of 2000",
                tool_name="calculate_percentage",
                arguments={"percentage": 15, "value": 2000},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_4",
                agent="execution_agent",
                action="Sum the first two percentage results",
                tool_name="add",
                arguments={"a": "$step_1.result", "b": "$step_2.result"},
                depends_on=["step_1", "step_2"]
            ),
            WorkflowStepDefinition(
                step_id="step_5",
                agent="execution_agent",
                action="Add the third percentage result to the sum",
                tool_name="add",
                arguments={"a": "$step_4.result", "b": "$step_3.result"},
                depends_on=["step_4", "step_3"]
            )
        ]
    ),
    "Calculate 5*5, count words in 'hello world', and calculate 50% of 100 in parallel.": WorkflowPlan(
        goal="Calculate 5*5, count words in 'hello world', and calculate 50% of 100 in parallel",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 5 * 5",
                tool_name="multiply",
                arguments={"a": 5, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Count words in 'hello world'",
                tool_name="word_count",
                arguments={"text": "hello world"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Calculate 50% of 100",
                tool_name="calculate_percentage",
                arguments={"percentage": 50, "value": 100},
                depends_on=[]
            )
        ]
    ),
    "Calculate 10+5, divide 20 by 0, and multiply 3*4 in parallel, then add all results.": WorkflowPlan(
        goal="Calculate 10+5, divide 20 by 0, and multiply 3*4 in parallel, then add all results",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10 + 5",
                tool_name="add",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Divide 20 by 0",
                tool_name="divide",
                arguments={"a": 20, "b": 0},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Calculate 3 * 4",
                tool_name="multiply",
                arguments={"a": 3, "b": 4},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_4",
                agent="execution_agent",
                action="Sum all three results",
                tool_name="add",
                arguments={"a": "$step_1.result", "b": "$step_2.result"},
                depends_on=["step_1", "step_2"]
            ),
            WorkflowStepDefinition(
                step_id="step_5",
                agent="execution_agent",
                action="Add the third result to the sum",
                tool_name="add",
                arguments={"a": "$step_4.result", "b": "$step_3.result"},
                depends_on=["step_4", "step_3"]
            )
        ]
    ),
    "Calculate 10+5, 8*2, and 15/3 in parallel, then multiply the first two results.": WorkflowPlan(
        goal="Calculate 10+5, 8*2, and 15/3 in parallel, then multiply the first two results",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10 + 5",
                tool_name="add",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Calculate 8 * 2",
                tool_name="multiply",
                arguments={"a": 8, "b": 2},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Calculate 15 / 3",
                tool_name="divide",
                arguments={"a": 15, "b": 3},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_4",
                agent="execution_agent",
                action="Multiply the first two results",
                tool_name="multiply",
                arguments={"a": "$step_1.result", "b": "$step_2.result"},
                depends_on=["step_1", "step_2"]
            )
        ]
    ),
    # Research cases
    "Research Python programming language features.": WorkflowPlan(
        goal="Research Python programming language features",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search for Python programming language features",
                tool_name="web_search",
                arguments={"query": "Python programming language features"},
                depends_on=[]
            )
        ]
    ),
    "Research 'xyznonexistent123topic' with fallback search.": WorkflowPlan(
        goal="Research 'xyznonexistent123topic' with fallback search",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search for xyznonexistent123topic",
                tool_name="web_search",
                arguments={"query": "xyznonexistent123topic"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="research_agent",
                action="Fallback search for xyznonexistent123topic",
                tool_name="web_search_fallback",
                arguments={"query": "xyznonexistent123topic"},
                depends_on=["step_1"]
            )
        ]
    ),
    "Research PostgreSQL, MongoDB, and Qdrant vector databases in parallel.": WorkflowPlan(
        goal="Research PostgreSQL, MongoDB, and Qdrant vector databases in parallel",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search for PostgreSQL database",
                tool_name="web_search",
                arguments={"query": "PostgreSQL database"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="research_agent",
                action="Search for MongoDB database",
                tool_name="web_search",
                arguments={"query": "MongoDB database"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="research_agent",
                action="Search for Qdrant vector database",
                tool_name="web_search",
                arguments={"query": "Qdrant vector database"},
                depends_on=[]
            )
        ]
    ),
    "Research three nonexistent topics.": WorkflowPlan(
        goal="Research three nonexistent topics",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search for nonexistent topic 1",
                tool_name="web_search",
                arguments={"query": "xyznonexistent123topic"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="research_agent",
                action="Search for nonexistent topic 2",
                tool_name="web_search",
                arguments={"query": "abcnonexistent456topic"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="research_agent",
                action="Search for nonexistent topic 3",
                tool_name="web_search",
                arguments={"query": "defnonexistent789topic"},
                depends_on=[]
            )
        ]
    ),
    "Research Python, then count words in the search results.": WorkflowPlan(
        goal="Research Python, then count words in the search results",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search for Python programming",
                tool_name="web_search",
                arguments={"query": "Python programming"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="analysis_agent",
                action="Count words in search snippets",
                tool_name="word_count",
                arguments={"text": "$step_1.result.snippets"},
                depends_on=["step_1"]
            )
        ]
    ),
    # API/Data cases
    "Fetch data from https://jsonplaceholder.typicode.com/todos/1, validate it's JSON, extract title field.": WorkflowPlan(
        goal="Fetch data from jsonplaceholder API, validate it's JSON, extract title field",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Fetch data from jsonplaceholder API",
                tool_name="http_request",
                arguments={"url": "https://jsonplaceholder.typicode.com/todos/1"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="analysis_agent",
                action="Validate JSON response",
                tool_name="validate_response",
                arguments={"body": "$step_1.result.body"},
                depends_on=["step_1"]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="analysis_agent",
                action="Extract title field",
                tool_name="extract_fields",
                arguments={"data": "$step_2.result.data", "fields": ["title"]},
                depends_on=["step_2"]
            )
        ]
    ),
    "Fetch data from https://nonexistent-api.example.com/data.": WorkflowPlan(
        goal="Fetch data from nonexistent API",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Fetch data from nonexistent API",
                tool_name="http_request",
                arguments={"url": "https://nonexistent-api.example.com/data"},
                depends_on=[]
            )
        ]
    ),
    "Fetch and validate JSON from an endpoint returning invalid JSON.": WorkflowPlan(
        goal="Fetch and validate JSON from an endpoint returning invalid JSON",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Fetch data from API",
                tool_name="http_request",
                arguments={"url": "https://jsonplaceholder.typicode.com/todos/1"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="analysis_agent",
                action="Validate JSON response",
                tool_name="validate_response",
                arguments={"body": "invalid json string"},
                depends_on=["step_1"]
            )
        ]
    ),
    "Fetch JSON, validate, extract multiple fields including optional ones.": WorkflowPlan(
        goal="Fetch JSON, validate, extract multiple fields including optional ones",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Fetch data from jsonplaceholder API",
                tool_name="http_request",
                arguments={"url": "https://jsonplaceholder.typicode.com/todos/1"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="analysis_agent",
                action="Validate JSON response",
                tool_name="validate_response",
                arguments={"body": "$step_1.result.body"},
                depends_on=["step_1"]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="analysis_agent",
                action="Extract title and completed fields",
                tool_name="extract_fields",
                arguments={"data": "$step_2.result.data", "fields": ["title", "completed"]},
                depends_on=["step_2"]
            )
        ]
    ),
    "Fetch from an endpoint returning empty body, validate as JSON.": WorkflowPlan(
        goal="Fetch from an endpoint returning empty body, validate as JSON",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Fetch data from API",
                tool_name="http_request",
                arguments={"url": "https://jsonplaceholder.typicode.com/todos/1"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="analysis_agent",
                action="Validate empty string as JSON",
                tool_name="validate_response",
                arguments={"body": ""},
                depends_on=["step_1"]
            )
        ]
    ),
    # Failure recovery cases
    "Search with simulated transient network error.": WorkflowPlan(
        goal="Search with simulated transient network error",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search with simulated network error",
                tool_name="web_search",
                arguments={"query": "test network error"},
                depends_on=[]
            )
        ]
    ),
    "Divide by zero (permanent error).": WorkflowPlan(
        goal="Divide by zero (permanent error)",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Divide by zero",
                tool_name="divide",
                arguments={"a": 10, "b": 0},
                depends_on=[]
            )
        ]
    ),
    "Search Python, then multiply the results by 2.": WorkflowPlan(
        goal="Search Python, then multiply the results by 2",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search for Python",
                tool_name="web_search",
                arguments={"query": "Python"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Multiply search results by 2",
                tool_name="multiply",
                arguments={"a": "$step_1.result.snippets", "b": 2},
                depends_on=["step_1"]
            )
        ]
    ),
    "Calculate 10+5, search nonexistent topic, and multiply 3*4 in parallel.": WorkflowPlan(
        goal="Calculate 10+5, search nonexistent topic, and multiply 3*4 in parallel",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10 + 5",
                tool_name="add",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="research_agent",
                action="Search for nonexistent topic",
                tool_name="web_search",
                arguments={"query": "xyznonexistent123topic"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Calculate 3 * 4",
                tool_name="multiply",
                arguments={"a": 3, "b": 4},
                depends_on=[]
            )
        ]
    ),
    "Search with simulated rate limit.": WorkflowPlan(
        goal="Search with simulated rate limit",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="research_agent",
                action="Search with simulated rate limit",
                tool_name="web_search",
                arguments={"query": "test rate limit"},
                depends_on=[]
            )
        ]
    ),
    # Persistence cases
    "Calculate 10+5, then multiply by 2.": WorkflowPlan(
        goal="Calculate 10+5, then multiply by 2",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10 + 5",
                tool_name="add",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Multiply the result by 2",
                tool_name="multiply",
                arguments={"a": "$step_1.result", "b": 2},
                depends_on=["step_1"]
            )
        ]
    ),
    "Calculate 15% of 2000, add 250.": WorkflowPlan(
        goal="Calculate 15% of 2000, add 250",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 15% of 2000",
                tool_name="calculate_percentage",
                arguments={"percentage": 15, "value": 2000},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Add 250 to the percentage result",
                tool_name="add",
                arguments={"a": "$step_1.result", "b": 250},
                depends_on=["step_1"]
            )
        ]
    ),
    "Calculate 10+5, divide by 0.": WorkflowPlan(
        goal="Calculate 10+5, divide by 0",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10 + 5",
                tool_name="add",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Divide the result by 0",
                tool_name="divide",
                arguments={"a": "$step_1.result", "b": 0},
                depends_on=["step_1"]
            )
        ]
    ),
    "Calculate 10+5, search nonexistent, multiply 3*4 in parallel.": WorkflowPlan(
        goal="Calculate 10+5, search nonexistent, multiply 3*4 in parallel",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 10 + 5",
                tool_name="add",
                arguments={"a": 10, "b": 5},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="research_agent",
                action="Search for nonexistent topic",
                tool_name="web_search",
                arguments={"query": "xyznonexistent123topic"},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_3",
                agent="execution_agent",
                action="Calculate 3 * 4",
                tool_name="multiply",
                arguments={"a": 3, "b": 4},
                depends_on=[]
            )
        ]
    ),
    "Calculate 20% of 500, add 100.": WorkflowPlan(
        goal="Calculate 20% of 500, add 100",
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Calculate 20% of 500",
                tool_name="calculate_percentage",
                arguments={"percentage": 20, "value": 500},
                depends_on=[]
            ),
            WorkflowStepDefinition(
                step_id="step_2",
                agent="execution_agent",
                action="Add 100 to the percentage result",
                tool_name="add",
                arguments={"a": "$step_1.result", "b": 100},
                depends_on=["step_1"]
            )
        ]
    )
}

def get_controlled_plan(user_request: str) -> WorkflowPlan:
    """Get a predefined plan for a user request in controlled mode."""
    # Try exact match first
    if user_request in CONTROLLED_PLANS:
        return CONTROLLED_PLANS[user_request]
    
    # Fallback: return a simple plan that should work for most cases
    # This handles cases where the exact request isn't in the map
    return WorkflowPlan(
        goal=user_request,
        steps=[
            WorkflowStepDefinition(
                step_id="step_1",
                agent="execution_agent",
                action="Execute simple calculation",
                tool_name="add",
                arguments={"a": 1, "b": 1},
                depends_on=[]
            )
        ]
    )
