from app.tools.registry import registry, ToolDefinition, PermissionType
from app.models.workflow import ErrorCategory
import asyncio
import httpx

class ToolError(Exception):
    """Base exception for tool errors with error category."""
    def __init__(self, message: str, category: ErrorCategory = ErrorCategory.UNKNOWN):
        self.message = message
        self.category = category
        super().__init__(message)

def get_base_tools_descriptions():
    desc = []
    for name, tool in registry.list_tools().items():
        schema = tool.input_schema
        desc.append(f"- {name}: {tool.description} | Schema: {schema}")
    return "\n".join(desc)

def register_builtin_tools():
    # Calculator
    async def add(args):
        return args["a"] + args["b"]

    registry.register(ToolDefinition(
        name="add",
        description="Add two numbers together. Args: a (float), b (float). Returns: sum (number).",
        input_schema={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
        permission=PermissionType.SAFE,
        handler=add
    ))

    async def subtract(args):
        return args["a"] - args["b"]

    registry.register(ToolDefinition(
        name="subtract",
        description="Subtract b from a. Args: a (float), b (float). Returns: difference (number).",
        input_schema={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
        permission=PermissionType.SAFE,
        handler=subtract
    ))

    async def multiply(args):
        return args["a"] * args["b"]

    registry.register(ToolDefinition(
        name="multiply",
        description="Multiply two numbers. Args: a (float), b (float). Returns: product (number).",
        input_schema={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
        permission=PermissionType.SAFE,
        handler=multiply
    ))

    async def divide(args):
        if args["b"] == 0:
            raise ToolError("division by zero", ErrorCategory.PERMANENT_ERROR)
        return args["a"] / args["b"]

    registry.register(ToolDefinition(
        name="divide",
        description="Divide a by b. Args: a (float), b (float). Errors if b=0. Returns: quotient (number).",
        input_schema={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
        permission=PermissionType.SAFE,
        handler=divide
    ))

    async def calculate_percentage(args):
        return (args["percentage"] / 100) * args["value"]

    registry.register(ToolDefinition(
        name="calculate_percentage",
        description="Calculates a percentage of a value. Args: percentage (float), value (float). Returns: result (number).",
        input_schema={"type": "object", "properties": {"percentage": {"type": "number"}, "value": {"type": "number"}}, "required": ["percentage", "value"]},
        permission=PermissionType.SAFE,
        handler=calculate_percentage
    ))

    # Text tools
    async def word_count(args):
        return len(str(args["text"]).split())

    registry.register(ToolDefinition(
        name="word_count",
        description="Count words in text. Args: text (string). Returns: count (number).",
        input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
        permission=PermissionType.SAFE,
        handler=word_count
    ))

    # HTTP/Research tools
    async def web_search(args):
        """Search the web (Wikipedia) with bounded retries for transient errors."""
        query = args["query"]
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&utf8=&format=json"
        max_retries = 3

        for attempt in range(max_retries):
            try:
                headers = {
                    "User-Agent": "FlowMind/1.0 (Research Workflow; https://github.com/flowmind)",
                    "Accept": "application/json"
                }
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=10, headers=headers)
                    if res.status_code == 429:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise ToolError(f"Rate limit exceeded after {max_retries} retries", ErrorCategory.RATE_LIMIT)
                    elif res.status_code >= 400:
                        raise ToolError(f"HTTP {res.status_code}: {res.text[:200]}", ErrorCategory.PERMANENT_ERROR)

                    data = res.json()
                    if "query" not in data or "search" not in data["query"]:
                        raise ToolError("Invalid response format from Wikipedia API", ErrorCategory.PARSE_ERROR)

                    snippets = [item["snippet"] for item in data["query"]["search"][:3]]
                    return {
                        "success": True,
                        "snippets": snippets,
                        "source": "Wikipedia",
                        "query": query
                    }

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ToolError(f"Timeout after {max_retries} retries", ErrorCategory.TIMEOUT)
            except httpx.NetworkError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ToolError(f"Network error after {max_retries} retries", ErrorCategory.NETWORK_ERROR)
            except ToolError:
                raise
            except Exception as e:
                raise ToolError(f"Unexpected error: {str(e)}", ErrorCategory.UNKNOWN)

    registry.register(ToolDefinition(
        name="web_search",
        description="Search the web (Wikipedia) for a query. Args: query (string). Returns: {success (boolean), snippets (array), source (string), query (string)}. Use $step_X.result.snippets to get search results.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        permission=PermissionType.EXTERNAL_READ,
        handler=web_search
    ))

    async def web_search_fallback(args):
        """Fallback search with reformulated query when primary search returns no results."""
        original_query = args["query"]
        # Reformulate query to be more specific for research context
        # Add common research-related terms to improve result quality
        fallback_query = f"{original_query} features capabilities architecture"
        
        url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={fallback_query}&utf8=&format=json"
        max_retries = 2  # Fewer retries for fallback

        for attempt in range(max_retries):
            try:
                headers = {
                    "User-Agent": "FlowMind/1.0 (Research Workflow; https://github.com/flowmind)",
                    "Accept": "application/json"
                }
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=10, headers=headers)
                    if res.status_code == 429:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise ToolError(f"Rate limit exceeded after {max_retries} retries", ErrorCategory.RATE_LIMIT)
                    elif res.status_code >= 400:
                        raise ToolError(f"HTTP {res.status_code}: {res.text[:200]}", ErrorCategory.PERMANENT_ERROR)

                    data = res.json()
                    if "query" not in data or "search" not in data["query"]:
                        raise ToolError("Invalid response format from Wikipedia API", ErrorCategory.PARSE_ERROR)

                    snippets = [item["snippet"] for item in data["query"]["search"][:3]]
                    return {
                        "success": True,
                        "snippets": snippets,
                        "source": "Wikipedia (fallback)",
                        "query": fallback_query,
                        "original_query": original_query
                    }

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ToolError(f"Timeout after {max_retries} retries", ErrorCategory.TIMEOUT)
            except httpx.NetworkError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ToolError(f"Network error after {max_retries} retries", ErrorCategory.NETWORK_ERROR)
            except ToolError:
                raise
            except Exception as e:
                raise ToolError(f"Unexpected error: {str(e)}", ErrorCategory.UNKNOWN)

    registry.register(ToolDefinition(
        name="web_search_fallback",
        description="Fallback web search with reformulated query when primary search returns no results. Args: query (string). Returns: {success (boolean), snippets (array), source (string), query (string), original_query (string)}. Use this tool only when a primary web_search returns empty snippets.",
        input_schema={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
        permission=PermissionType.EXTERNAL_READ,
        handler=web_search_fallback
    ))

    # HTTP/Validation tools for API interaction workflows
    async def http_request(args):
        """Make an HTTP GET request to a public API with bounded retries."""
        url = args["url"]
        max_retries = 3

        for attempt in range(max_retries):
            try:
                headers = {
                    "User-Agent": "FlowMind/1.0 (Research Workflow; https://github.com/flowmind)",
                    "Accept": "application/json"
                }
                async with httpx.AsyncClient() as client:
                    res = await client.get(url, timeout=30, follow_redirects=True, headers=headers)
                    if res.status_code == 429:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            raise ToolError(f"Rate limit exceeded after {max_retries} retries", ErrorCategory.RATE_LIMIT)
                    elif res.status_code >= 400:
                        raise ToolError(f"HTTP {res.status_code}: {res.text[:200]}", ErrorCategory.PERMANENT_ERROR)

                    return {
                        "status_code": res.status_code,
                        "headers": dict(res.headers),
                        "body": res.text,
                        "success": True
                    }

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ToolError(f"Timeout after {max_retries} retries", ErrorCategory.TIMEOUT)
            except httpx.NetworkError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise ToolError(f"Network error after {max_retries} retries", ErrorCategory.NETWORK_ERROR)
            except ToolError:
                raise
            except Exception as e:
                raise ToolError(f"Unexpected error: {str(e)}", ErrorCategory.UNKNOWN)

    registry.register(ToolDefinition(
        name="http_request",
        description="Make an HTTP GET request to a public API. Args: url (string). Returns: {status_code (int), headers (dict), body (string), success (boolean)}. The 'body' field contains the raw response text.",
        input_schema={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
        permission=PermissionType.EXTERNAL_READ,
        handler=http_request
    ))

    async def validate_response(args):
        """Validate that a response contains valid JSON and check for required fields."""
        body = args["body"]
        required_fields = args.get("required_fields", [])
        try:
            import json
            data = json.loads(body)
            missing_fields = [f for f in required_fields if f not in data]
            return {
                "valid": True,
                "is_json": True,
                "missing_fields": missing_fields,
                "data": data
            }
        except json.JSONDecodeError as e:
            raise ToolError(f"JSON parse error: {str(e)}", ErrorCategory.PARSE_ERROR)

    registry.register(ToolDefinition(
        name="validate_response",
        description="Validate that a response body is valid JSON and check for required fields. Args: body (string), required_fields (array of strings, optional). Returns: {valid (boolean), is_json (boolean), missing_fields (array), data (object)}. The 'data' field contains the parsed JSON object.",
        input_schema={"type": "object", "properties": {"body": {"type": "string"}, "required_fields": {"type": "array", "items": {"type": "string"}}}, "required": ["body"]},
        permission=PermissionType.SAFE,
        handler=validate_response
    ))

    async def extract_fields(args):
        """Extract specific fields from a JSON response."""
        data = args["data"]
        fields = args["fields"]
        if not isinstance(data, dict):
            raise ToolError("Data must be a dictionary", ErrorCategory.PARSE_ERROR)
        extracted = {}
        for field in fields:
            if field in data:
                extracted[field] = data[field]
        return extracted

    registry.register(ToolDefinition(
        name="extract_fields",
        description="Extract specific fields from a JSON object. Args: data (object), fields (array of strings). Returns: object containing only the requested fields. Use $step_X.result.data to pass the parsed JSON from validate_response to this tool.",
        input_schema={"type": "object", "properties": {"data": {"type": "object"}, "fields": {"type": "array", "items": {"type": "string"}}}, "required": ["data", "fields"]},
        permission=PermissionType.SAFE,
        handler=extract_fields
    ))

register_builtin_tools()
