from app.agents.base import BaseAgent
from app.config import settings
import re

class SynthesisAgent(BaseAgent):
    def __init__(self):
        super().__init__("synthesis_agent")
        self.model = settings.SYNTHESIS_MODEL

    async def execute(self, user_request: str, step_summary: dict, plan: dict = None) -> str:
        successful_steps = step_summary.get("successful_steps", {})
        empty_result_steps = step_summary.get("empty_result_steps", {})
        failed_steps = step_summary.get("failed_steps", {})
        successful_count = step_summary.get("successful_count", 0)
        empty_result_count = step_summary.get("empty_result_count", 0)
        failed_count = step_summary.get("failed_count", 0)
        total_steps = step_summary.get("total_steps", 0)

        # Build context for the synthesis
        context_parts = []
        context_parts.append(f"User request: {user_request}")
        context_parts.append(f"\nExecution Summary:")
        context_parts.append(f"- Total steps: {total_steps}")
        context_parts.append(f"- Successful steps: {successful_count}")
        context_parts.append(f"- Empty result steps: {empty_result_count}")
        context_parts.append(f"- Failed steps: {failed_count}")

        if plan:
            context_parts.append(f"\nPlanned Steps:")
            for i, step in enumerate(plan.get("steps", []), 1):
                context_parts.append(f"{i}. {step.get('action', 'Unknown action')} (Tool: {step.get('tool_name', 'unknown')})")

        if successful_steps:
            context_parts.append(f"\nSuccessful Step Results:")
            for step_id, result in successful_steps.items():
                context_parts.append(f"\n{step_id}: {result}")

        if empty_result_steps:
            context_parts.append(f"\nResearch with Insufficient Evidence:")
            for step_id, result in empty_result_steps.items():
                # Check if this is a web_search result
                if isinstance(result, dict) and "query" in result:
                    context_parts.append(f"\n{step_id}: Search for '{result.get('query', 'unknown')}' returned no verifiable evidence from available sources.")
                else:
                    context_parts.append(f"\n{step_id}: {result}")

        if failed_steps:
            context_parts.append(f"\nFailed Steps:")
            for step_id, failure in failed_steps.items():
                context_parts.append(f"\n{step_id}: {failure['error']} (Category: {failure['error_category']}, Retries: {failure['retry_count']})")

        context = "\n".join(context_parts)

        # Determine if there's sufficient evidence
        has_sufficient_evidence = successful_count > 0 or empty_result_count > 0
        all_research_failed = total_steps > 0 and successful_count == 0 and empty_result_count == 0

        prompt = f"""{context}

Synthesize these results into a clear, final response for the user.

IMPORTANT GUIDELINES:
- Include ONLY verifiable findings from successful steps.
- Do NOT fabricate information, sources, citations, or API responses.
- Research with insufficient evidence is NOT a failure - it simply means no verifiable information was found from available sources.
- When some research topics have insufficient evidence, clearly state which topics lack verifiable data while presenting findings for topics that did return results.
- Only conclude that a technology is unsupported when ALL relevant searches (including fallbacks) for that technology produced insufficient evidence.
- Distinguish between verified findings and unavailable evidence.
- List failed steps when relevant to explain missing information.
- When evidence is insufficient for a specific topic, explicitly state that verifiable information could not be found for that particular topic.
- Provide a polished, professional output.
- Do not expose internal tool names or raw JSON unless necessary.

MARKDOWN FORMATTING REQUIREMENTS:
- Use proper Markdown syntax: **bold**, *italic*, `code`, ## Headings
- If you create a table, you MUST use proper Markdown table format:
  - Header row: | Column 1 | Column 2 | Column 3 |
  - Separator row: |---|---|---|
  - Data rows: | Value 1 | Value 2 | Value 3 |
  - Example:
    | Feature | FastAPI | Flask |
    |---|---|---|
    | Async | Yes | Limited |
    | Performance | High | Moderate
- Use proper list syntax: - for bullet points, 1. for numbered lists
- Do NOT use literal <br> tags - use proper Markdown spacing instead
- Separate paragraphs with blank lines
- Use fenced code blocks (```language) for code examples
- IMPORTANT: Do NOT escape Markdown syntax. Use actual ** for bold, ## for headings, etc.
- Do NOT wrap Markdown in backticks or quotes.
- NEVER create tables without the separator row (|---|---|). Tables without separators will not render correctly.
"""

        if all_research_failed:
            prompt += "\n\nCRITICAL: All steps failed. You must inform the user that the task could not be completed due to failed operations. Do not attempt to fabricate an answer."

        raw_response = await self.provider.generate(
            prompt=prompt,
            model=self.model,
            system_prompt="You are the Synthesis Agent. You combine and format results from various workflow steps for the user. Never fabricate information or citations. Only report verifiable findings and clearly explain when information is unavailable or the task could not be completed."
        )

        # Post-process to clean up common Markdown issues
        return self._clean_markdown(raw_response)

    def _clean_markdown(self, text: str) -> str:
        """Clean up common Markdown formatting issues in LLM output."""
        # Replace literal <br> tags with newlines
        text = re.sub(r'<br\s*/?>', '\n\n', text, flags=re.IGNORECASE)

        # Fix multiple consecutive empty lines (max 2)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Don't remove or escape bold markers - keep them as-is for the frontend renderer
        # The frontend uses react-markdown which handles **bold** correctly

        # Fix headings that might have extra # symbols
        text = re.sub(r'#{7,}', '######', text)

        return text.strip()
