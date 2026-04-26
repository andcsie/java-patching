"""Multi-LLM provider service supporting OpenAI, Anthropic, Gemini, and Ollama."""

import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Generate a completion from messages."""
        ...

    @abstractmethod
    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Stream a completion from messages."""
        ...


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str, model: str = "gpt-4-turbo"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.openai.com/v1"

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Generate a completion using OpenAI API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                },
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Stream a completion using OpenAI API."""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 4096),
                    "stream": True,
                },
                timeout=120.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and not line.endswith("[DONE]"):
                        import json

                        data = json.loads(line[6:])
                        if data["choices"][0].get("delta", {}).get("content"):
                            yield data["choices"][0]["delta"]["content"]


class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Generate a completion using Anthropic API."""
        # Convert OpenAI format to Anthropic format
        anthropic_messages = []
        system_message = None

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        async with httpx.AsyncClient() as client:
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
            }
            if system_message:
                payload["system"] = system_message

            response = await client.post(
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Stream a completion using Anthropic API."""
        anthropic_messages = []
        system_message = None

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        async with httpx.AsyncClient() as client:
            payload = {
                "model": kwargs.get("model", self.model),
                "messages": anthropic_messages,
                "max_tokens": kwargs.get("max_tokens", 4096),
                "stream": True,
            }
            if system_message:
                payload["system"] = system_message

            async with client.stream(
                "POST",
                f"{self.base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json

                        data = json.loads(line[6:])
                        if data.get("type") == "content_block_delta":
                            yield data["delta"].get("text", "")


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Generate a completion using Gemini API."""
        # Convert OpenAI format to Gemini format
        contents = []
        system_instruction = None

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}],
                })

        async with httpx.AsyncClient() as client:
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "maxOutputTokens": kwargs.get("max_tokens", 8192),
                },
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            model = kwargs.get("model", self.model)
            response = await client.post(
                f"{self.base_url}/models/{model}:generateContent",
                params={"key": self.api_key},
                json=payload,
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()

            # Handle various Gemini response structures
            if "candidates" not in data or not data["candidates"]:
                # Check for prompt feedback (content blocked)
                if "promptFeedback" in data:
                    block_reason = data["promptFeedback"].get("blockReason", "UNKNOWN")
                    logger.warning(f"[Gemini] Content blocked: {block_reason}")
                    raise ValueError(f"Gemini blocked content: {block_reason}")
                logger.warning(f"[Gemini] No candidates in response: {data}")
                raise ValueError("Gemini returned no candidates")

            candidate = data["candidates"][0]

            # Check for finish reason issues
            finish_reason = candidate.get("finishReason", "")
            if finish_reason == "SAFETY":
                logger.warning(f"[Gemini] Safety filter triggered: {candidate}")
                raise ValueError("Gemini blocked response due to safety filters")
            if finish_reason == "RECITATION":
                logger.warning(f"[Gemini] Recitation policy triggered: {candidate}")
                raise ValueError("Gemini blocked response due to recitation policy")
            if finish_reason == "MAX_TOKENS":
                # Try to extract partial content if available
                if "content" in candidate and "parts" in candidate["content"]:
                    partial = candidate["content"]["parts"][0].get("text", "")
                    if partial:
                        logger.warning(f"[Gemini] Response truncated (MAX_TOKENS), returning partial")
                        return partial
                logger.warning(f"[Gemini] MAX_TOKENS with no content: {candidate}")
                raise ValueError("Gemini response truncated - input too long")

            # Extract text from content
            if "content" not in candidate or "parts" not in candidate["content"]:
                logger.warning(f"[Gemini] Missing content in response: {candidate}")
                raise ValueError(f"Gemini response missing content (finish_reason: {finish_reason})")

            return candidate["content"]["parts"][0]["text"]

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Stream a completion using Gemini API."""
        contents = []
        system_instruction = None

        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}],
                })

        async with httpx.AsyncClient() as client:
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": kwargs.get("temperature", 0.7),
                    "maxOutputTokens": kwargs.get("max_tokens", 8192),
                },
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            model = kwargs.get("model", self.model)
            async with client.stream(
                "POST",
                f"{self.base_url}/models/{model}:streamGenerateContent",
                params={"key": self.api_key, "alt": "sse"},
                json=payload,
                timeout=120.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        import json

                        data = json.loads(line[6:])
                        if "candidates" in data and data["candidates"]:
                            candidate = data["candidates"][0]
                            if "content" in candidate and "parts" in candidate["content"]:
                                text = candidate["content"]["parts"][0].get("text", "")
                                if text:
                                    yield text


class OllamaProvider(LLMProvider):
    """Ollama (self-hosted) API provider - OpenAI compatible."""

    def __init__(self, base_url: str, model: str = "llama3"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def complete(self, messages: list[dict], **kwargs) -> str:
        """Generate a completion using Ollama API."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": kwargs.get("temperature", 0.7),
                        "num_predict": kwargs.get("max_tokens", 4096),
                    },
                },
                timeout=300.0,  # Longer timeout for local models
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    async def stream(self, messages: list[dict], **kwargs) -> AsyncIterator[str]:
        """Stream a completion using Ollama API."""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": kwargs.get("model", self.model),
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": kwargs.get("temperature", 0.7),
                        "num_predict": kwargs.get("max_tokens", 4096),
                    },
                },
                timeout=300.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json

                        data = json.loads(line)
                        if "message" in data and "content" in data["message"]:
                            yield data["message"]["content"]


class LLMService:
    """Service for managing multiple LLM providers."""

    def __init__(self):
        self.providers: dict[str, LLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize available LLM providers from settings."""
        if settings.openai_api_key:
            self.providers["openai"] = OpenAIProvider(
                settings.openai_api_key,
                settings.openai_model,
            )
            logger.info(f"[LLM] Initialized OpenAI provider with model: {settings.openai_model}")

        if settings.anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(
                settings.anthropic_api_key,
                settings.anthropic_model,
            )
            logger.info(f"[LLM] Initialized Anthropic provider with model: {settings.anthropic_model}")

        if settings.google_api_key:
            self.providers["gemini"] = GeminiProvider(
                settings.google_api_key,
                settings.google_model,
            )
            logger.info(f"[LLM] Initialized Gemini provider with model: {settings.google_model}")

        if settings.ollama_base_url:
            self.providers["ollama"] = OllamaProvider(
                settings.ollama_base_url,
                settings.ollama_model,
            )
            logger.info(f"[LLM] Initialized Ollama provider with model: {settings.ollama_model}")

        logger.info(f"[LLM] Available providers: {list(self.providers.keys())}, default: {settings.default_llm_provider}")

    @property
    def available_providers(self) -> list[str]:
        """Get list of available provider names."""
        return list(self.providers.keys())

    def get_provider(self, name: str | None = None) -> LLMProvider:
        """Get a specific provider or the default one."""
        if not self.providers:
            raise ValueError("No LLM providers configured")

        provider_name = name or settings.default_llm_provider
        if provider_name not in self.providers:
            # Fall back to first available provider
            provider_name = self.available_providers[0]

        return self.providers[provider_name]

    async def complete(
        self,
        messages: list[dict],
        provider: str | None = None,
        **kwargs,
    ) -> str:
        """Generate a completion using the specified or default provider."""
        llm = self.get_provider(provider)
        return await llm.complete(messages, **kwargs)

    async def stream(
        self,
        messages: list[dict],
        provider: str | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """Stream a completion using the specified or default provider."""
        llm = self.get_provider(provider)
        async for chunk in llm.stream(messages, **kwargs):
            yield chunk

    async def analyze_code_impact(
        self,
        code_snippet: str,
        change_description: str,
        provider: str | None = None,
    ) -> str:
        """Analyze the impact of a JDK change on a code snippet."""
        messages = [
            {
                "role": "system",
                "content": """You are an expert Java developer analyzing code for JDK upgrade compatibility.
Analyze the provided code snippet and the JDK change description.
Provide:
1. Impact assessment (how this change affects the code)
2. Risk level (LOW, MEDIUM, HIGH, CRITICAL)
3. Suggested fix with code example
4. Migration notes

Be concise but thorough.""",
            },
            {
                "role": "user",
                "content": f"""Code snippet:
```java
{code_snippet}
```

JDK Change:
{change_description}

Analyze the impact and provide recommendations.""",
            },
        ]

        return await self.complete(messages, provider)

    async def generate_migration_plan(
        self,
        impacts: list[dict],
        from_version: str,
        to_version: str,
        provider: str | None = None,
    ) -> str:
        """Generate a comprehensive migration plan for all impacts."""
        impacts_text = "\n".join(
            f"- {impact['file_path']}:{impact.get('line_number', '?')}: "
            f"{impact['description']} ({impact['change_type']})"
            for impact in impacts
        )

        messages = [
            {
                "role": "system",
                "content": """You are an expert Java developer creating a migration plan for JDK upgrades.
Create a comprehensive, prioritized migration plan including:
1. Executive summary
2. High-priority items (breaking changes)
3. Medium-priority items (deprecations, behavioral changes)
4. Low-priority items (optimizations, cleanups)
5. Testing recommendations
6. Rollback considerations

Format the response in clear markdown.""",
            },
            {
                "role": "user",
                "content": f"""Migrating from JDK {from_version} to {to_version}

Identified impacts:
{impacts_text}

Generate a detailed migration plan.""",
            },
        ]

        return await self.complete(messages, provider)

    async def explain_impact(
        self,
        code_snippet: str,
        file_path: str,
        line_number: int,
        change_description: str,
        change_type: str,
        cve_id: str | None = None,
        provider: str | None = None,
    ) -> dict:
        """Explain why a specific code pattern is impacted by a JDK change."""
        cve_info = f"\nCVE: {cve_id}" if cve_id else ""

        messages = [
            {
                "role": "system",
                "content": """You are a Java security and compatibility expert. Analyze code impacts from JDK changes.

Provide your response as JSON with these fields:
{
  "risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "explanation": "Clear explanation of why this code is affected",
  "runtime_behavior": "What happens if this code runs on the new JDK without changes",
  "security_implications": "Any security concerns (especially for CVE-related changes)",
  "recommendation": "Recommended action (fix now, test thoroughly, monitor, etc.)"
}

Be concise but specific. Focus on practical implications.""",
            },
            {
                "role": "user",
                "content": f"""File: {file_path}:{line_number}

Code:
```java
{code_snippet}
```

JDK Change ({change_type}):
{change_description}{cve_info}

Explain the impact on this code.""",
            },
        ]

        response = await self.complete(messages, provider, temperature=0.3)

        # Parse JSON response
        import json
        import re

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            response = json_match.group(1)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "risk_level": "MEDIUM",
                "explanation": response,
                "runtime_behavior": "Unknown",
                "security_implications": "Review manually",
                "recommendation": "Test thoroughly",
            }

    async def generate_fix(
        self,
        code_snippet: str,
        file_path: str,
        change_description: str,
        change_type: str,
        full_file_content: str | None = None,
        provider: str | None = None,
    ) -> dict:
        """Generate a code fix for an impacted code pattern."""
        import json
        import re

        original_snippet = code_snippet or ""
        code_snippet = original_snippet[:300]  # More context
        change_description = (change_description or "")[:200]

        # Check if the code actually needs fixing
        # Simple syntax like }, {, etc. usually don't need changes
        stripped = original_snippet.strip()
        if stripped in ['}', '{', '};', '{};', '']:
            return {
                "fixed_code": original_snippet,
                "explanation": "No code change needed - this is structural syntax",
                "no_change_needed": True,
            }

        messages = [
            {
                "role": "system",
                "content": """You are a Java expert. Analyze if code needs fixing for JDK compatibility.

Return JSON with this format:
{"fixed_code": "COMPLETE FIXED LINE", "explanation": "what was changed", "no_change_needed": false}

RULES:
1. If the code does NOT need changes, return: {"fixed_code": "ORIGINAL CODE HERE", "explanation": "No change needed - reason", "no_change_needed": true}
2. If the code DOES need changes, return the COMPLETE fixed line with the semicolon
3. Do NOT return partial snippets or method names alone
4. The fixed_code must be valid Java syntax that can replace the original line""",
            },
            {
                "role": "user",
                "content": f"""Analyze this code for JDK compatibility:

File: {file_path}
Original code: {code_snippet}
Issue type: {change_type}
Problem: {change_description}

Does this code need to be changed? If yes, provide the complete fixed line. If no, explain why no change is needed.""",
            },
        ]

        response = await self.complete(messages, provider, temperature=0.1, max_tokens=4096)
        logger.debug(f"[LLM] generate_fix response: {response[:300]}")

        # Clean response
        response = response.strip()
        response = re.sub(r"```(?:json)?\s*", "", response)
        response = re.sub(r"```\s*$", "", response)
        response = response.strip()

        # Try direct JSON parse first
        try:
            result = json.loads(response)
            if "fixed_code" in result and result["fixed_code"]:
                return result
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        json_match = re.search(r'\{[\s\S]*"fixed_code"[\s\S]*\}', response)
        if json_match:
            try:
                # Fix newlines in strings
                json_str = json_match.group(0)
                # Replace actual newlines with \n in string values
                json_str = re.sub(r':\s*"([^"]*)\n([^"]*)"', r': "\1\\n\2"', json_str)
                result = json.loads(json_str)
                if "fixed_code" in result:
                    return result
            except json.JSONDecodeError:
                pass

        # Fallback: extract values with regex
        # Handle escaped quotes in the value
        fixed_match = re.search(r'"fixed_code"\s*:\s*"((?:[^"\\]|\\.)*)"', response, re.DOTALL)
        explanation_match = re.search(r'"explanation"\s*:\s*"((?:[^"\\]|\\.)*)"', response, re.DOTALL)

        fixed_code = fixed_match.group(1) if fixed_match else code_snippet
        explanation = explanation_match.group(1) if explanation_match else "Fix applied"

        # Unescape the extracted values
        fixed_code = fixed_code.replace('\\"', '"').replace('\\n', '\n')
        explanation = explanation.replace('\\"', '"').replace('\\n', ' ')

        return {
            "fixed_code": fixed_code if fixed_code else code_snippet,
            "explanation": explanation,
            "imports_needed": [],
            "breaking_change": False,
        }

    async def generate_patch(
        self,
        file_path: str,
        original_content: str,
        impacts_with_fixes: list[dict],
        provider: str | None = None,
    ) -> dict:
        """Generate a unified diff patch programmatically from fixes."""
        import difflib

        # Extract fix data from impacts
        def get_fix_data(impact: dict) -> tuple[int, str, str, str] | None:
            """Returns (line_number, original_code, fixed_code, explanation) or None."""
            fix_data = impact.get("fix", {})
            if isinstance(fix_data, dict) and fix_data.get("error"):
                return None
            if not isinstance(fix_data, dict):
                return None

            # Skip fixes that explicitly indicate no change needed
            if fix_data.get("no_change_needed"):
                logger.debug(f"[Patch] Skipping no_change_needed fix: {fix_data.get('explanation', 'N/A')}")
                return None

            fixed_code = fix_data.get("fixed_code", "")
            explanation = fix_data.get("explanation", "")
            if not fixed_code:
                return None

            # Skip if fixed_code is same as original (no actual change)
            original = impact.get("code_snippet", "")
            if fixed_code.strip() == original.strip():
                logger.debug(f"[Patch] Skipping - fixed code same as original")
                return None

            line_num = impact.get("line_number", 0)
            return (line_num, original, fixed_code, explanation)

        # Collect valid fixes
        valid_fixes = []
        for impact in impacts_with_fixes:
            fix_data = get_fix_data(impact)
            if fix_data:
                valid_fixes.append(fix_data)

        if not valid_fixes:
            return {
                "unified_diff": "",
                "changes_summary": ["No valid fixes to apply"],
                "warnings": ["All fixes had errors or were empty"],
            }

        # Sort by line number
        valid_fixes.sort(key=lambda x: x[0])

        # Apply fixes to content
        content_lines = original_content.split('\n')
        patched_lines = content_lines.copy()
        changes_summary = []
        warnings = []

        # Track line offset as we make changes
        offset = 0
        for line_num, original_code, fixed_code, explanation in valid_fixes:
            idx = line_num - 1 + offset  # Convert to 0-indexed with offset

            if idx < 0 or idx >= len(patched_lines):
                warnings.append(f"Line {line_num} out of range")
                continue

            current_line = patched_lines[idx]

            # Get the fixed code - always do full line replacement to avoid corruption
            fixed_stripped = fixed_code.strip()

            if not fixed_stripped:
                warnings.append(f"Line {line_num}: Empty fix, skipping")
                continue

            # Preserve original indentation
            indent = len(current_line) - len(current_line.lstrip())
            indent_str = current_line[:indent]

            # Handle multi-line fixes
            fixed_lines = fixed_stripped.split('\n')
            if len(fixed_lines) == 1:
                # Single line fix - replace the entire line preserving indentation
                # But if fixed_code already has proper indentation/structure, use it directly
                if fixed_stripped.startswith(current_line.lstrip()[:20]) or ';' in fixed_stripped:
                    # Fixed code looks complete - use it with indentation
                    patched_lines[idx] = indent_str + fixed_stripped
                else:
                    # Fixed code might be partial - be cautious
                    patched_lines[idx] = indent_str + fixed_stripped
                changes_summary.append(f"L{line_num}: {explanation[:100]}" if explanation else f"L{line_num}: Replaced line")
            else:
                # Multi-line: replace current line with multiple lines
                new_lines = [indent_str + fl.strip() for fl in fixed_lines if fl.strip()]
                patched_lines[idx:idx+1] = new_lines
                offset += len(new_lines) - 1
                changes_summary.append(f"L{line_num}: Multi-line fix ({len(new_lines)} lines)")

        # Generate unified diff
        original_name = f"a/{file_path.split('/')[-1]}"
        patched_name = f"b/{file_path.split('/')[-1]}"

        diff = difflib.unified_diff(
            content_lines,
            patched_lines,
            fromfile=original_name,
            tofile=patched_name,
            lineterm='',
        )

        unified_diff = '\n'.join(diff)

        # Also return the full patched content for direct file writing
        patched_content = '\n'.join(patched_lines)

        return {
            "unified_diff": unified_diff,
            "patched_content": patched_content,
            "changes_summary": changes_summary,
            "warnings": warnings,
        }


# Global instance
llm_service = LLMService()
