"""
Version-safe structured output handling for LangChain.

Provides fallback mechanisms for JSON extraction when with_structured_output()
is unavailable or behaves differently across LangChain versions.
"""

import json
import re
from typing import Any, Dict, Optional, Type, TypeVar, Union
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract JSON from LLM response text.

    Handles common patterns:
    - Pure JSON response
    - JSON in markdown code blocks
    - JSON with surrounding text

    Args:
        text: Raw LLM response text

    Returns:
        Parsed JSON dict or None if extraction fails
    """
    if not text:
        return None

    text = text.strip()

    # Try 1: Direct JSON parse (cleanest case)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try 2: JSON in markdown code block
    # Matches ```json ... ``` or ``` ... ```
    code_block_pattern = r"```(?:json)?\s*\n?([\s\S]*?)\n?```"
    matches = re.findall(code_block_pattern, text)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Try 3: Find JSON object in text (first { to last })
    # This handles cases where LLM adds explanation before/after JSON
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end > brace_start:
        potential_json = text[brace_start:brace_end + 1]
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            pass

    # Try 4: Find JSON array
    bracket_start = text.find("[")
    bracket_end = text.rfind("]")
    if bracket_start != -1 and bracket_end > bracket_start:
        potential_json = text[bracket_start:bracket_end + 1]
        try:
            return json.loads(potential_json)
        except json.JSONDecodeError:
            pass

    return None


def parse_to_model(
    text: str,
    model_class: Type[T],
    strict: bool = True
) -> T:
    """
    Parse LLM response text into a Pydantic model.

    Args:
        text: Raw LLM response text
        model_class: Pydantic model class to parse into
        strict: If True, raise on parse failure. If False, return partial.

    Returns:
        Validated Pydantic model instance

    Raises:
        ValueError: If JSON extraction fails
        ValidationError: If Pydantic validation fails (when strict=True)
    """
    json_data = extract_json_from_text(text)

    if json_data is None:
        raise ValueError(f"Could not extract JSON from response: {text[:200]}...")

    try:
        return model_class.model_validate(json_data)
    except ValidationError as e:
        if strict:
            raise
        # In non-strict mode, try to construct with available fields
        # This allows partial parsing for debugging
        valid_fields = {}
        for field_name in model_class.model_fields:
            if field_name in json_data:
                valid_fields[field_name] = json_data[field_name]
        return model_class.model_construct(**valid_fields)


def create_json_prompt_suffix(model_class: Type[BaseModel]) -> str:
    """
    Create a prompt suffix that instructs the LLM to output valid JSON.

    Includes the JSON schema for the expected output format.

    Args:
        model_class: Pydantic model defining expected output

    Returns:
        Prompt suffix string
    """
    schema = model_class.model_json_schema()

    # Simplify schema for prompt (remove $defs, simplify types)
    simplified = _simplify_schema(schema)

    return f"""

Respond with valid JSON matching this schema:
```json
{json.dumps(simplified, indent=2)}
```

Important:
- Output ONLY the JSON object, no additional text
- Ensure all required fields are present
- Use null for optional fields if not applicable"""


def _simplify_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Simplify JSON schema for prompt inclusion."""
    result = {}

    if "properties" in schema:
        result["properties"] = {}
        for name, prop in schema["properties"].items():
            simplified_prop = {}
            if "type" in prop:
                simplified_prop["type"] = prop["type"]
            if "description" in prop:
                simplified_prop["description"] = prop["description"]
            if "enum" in prop:
                simplified_prop["enum"] = prop["enum"]
            if "items" in prop:
                simplified_prop["items"] = _simplify_schema(prop["items"])
            result["properties"][name] = simplified_prop

    if "required" in schema:
        result["required"] = schema["required"]

    if "type" in schema:
        result["type"] = schema["type"]

    return result


class StructuredOutputHandler:
    """
    Handler for structured output with automatic fallback.

    Tries LangChain's with_structured_output() first, falls back to
    manual JSON parsing if needed.
    """

    def __init__(self, model: Any, output_class: Type[T]):
        """
        Initialize handler.

        Args:
            model: LangChain chat model instance
            output_class: Pydantic model for output parsing
        """
        self.model = model
        self.output_class = output_class
        self._structured_model = None
        self._use_fallback = False

        # Try to create structured output model
        self._try_structured_output()

    def _try_structured_output(self):
        """Attempt to use LangChain's native structured output."""
        try:
            # Check if method exists and works
            if hasattr(self.model, "with_structured_output"):
                self._structured_model = self.model.with_structured_output(
                    self.output_class,
                    method="json_mode"  # More widely supported than function calling
                )
        except (TypeError, NotImplementedError, AttributeError):
            # Fall back to manual parsing
            self._use_fallback = True
        except Exception:
            # Any other error, use fallback
            self._use_fallback = True

    def invoke(self, messages: list, **kwargs) -> T:
        """
        Invoke model and return structured output.

        Args:
            messages: List of LangChain message objects
            **kwargs: Additional arguments for model.invoke()

        Returns:
            Validated Pydantic model instance
        """
        if self._structured_model and not self._use_fallback:
            try:
                result = self._structured_model.invoke(messages, **kwargs)
                # Some versions return the model directly, others return AIMessage
                if isinstance(result, self.output_class):
                    return result
                elif hasattr(result, "content"):
                    return parse_to_model(result.content, self.output_class)
                else:
                    return parse_to_model(str(result), self.output_class)
            except Exception:
                # If structured output fails, fall back to manual parsing
                self._use_fallback = True

        # Fallback: Add JSON instructions to prompt and parse manually
        # Modify the last message to include JSON schema
        modified_messages = list(messages)
        if modified_messages:
            last_msg = modified_messages[-1]
            if hasattr(last_msg, "content"):
                suffix = create_json_prompt_suffix(self.output_class)
                # Create new message with modified content
                from langchain_core.messages import HumanMessage
                modified_messages[-1] = HumanMessage(
                    content=last_msg.content + suffix
                )

        response = self.model.invoke(modified_messages, **kwargs)
        return parse_to_model(response.content, self.output_class)
