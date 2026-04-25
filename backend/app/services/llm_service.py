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

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
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
                    "maxOutputTokens": kwargs.get("max_tokens", 4096),
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

            # Extract text from content
            if "content" not in candidate or "parts" not in candidate["content"]:
                logger.warning(f"[Gemini] Missing content in response: {candidate}")
                raise ValueError(f"Gemini response missing content: {candidate}")

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
                    "maxOutputTokens": kwargs.get("max_tokens", 4096),
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

        if settings.anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(
                settings.anthropic_api_key,
                settings.anthropic_model,
            )

        if settings.google_api_key:
            self.providers["gemini"] = GeminiProvider(
                settings.google_api_key,
                settings.google_model,
            )

        if settings.ollama_base_url:
            self.providers["ollama"] = OllamaProvider(
                settings.ollama_base_url,
                settings.ollama_model,
            )

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
        context = ""
        if full_file_content:
            # Include some context but limit size
            context = f"\n\nFull file context (for imports/class structure):\n```java\n{full_file_content[:2000]}...\n```"

        messages = [
            {
                "role": "system",
                "content": """You are an expert Java developer fixing code for JDK compatibility.

Generate a fix for the impacted code. Provide your response as JSON:
{
  "fixed_code": "The corrected Java code snippet",
  "explanation": "Brief explanation of what was changed and why",
  "imports_needed": ["any.new.imports.Required"],
  "breaking_change": true/false,
  "test_suggestion": "How to test this change"
}

Rules:
- Maintain the same functionality
- Use modern Java idioms appropriate for the target JDK
- Prefer standard library over external dependencies
- Keep the fix minimal - don't refactor unrelated code""",
            },
            {
                "role": "user",
                "content": f"""File: {file_path}

Original code with issue:
```java
{code_snippet}
```

JDK Change ({change_type}):
{change_description}{context}

Generate a fix.""",
            },
        ]

        response = await self.complete(messages, provider, temperature=0.2)

        # Parse JSON response
        import json
        import re

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            response = json_match.group(1)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "fixed_code": code_snippet,
                "explanation": response,
                "imports_needed": [],
                "breaking_change": False,
                "test_suggestion": "Manual review required",
            }

    async def generate_patch(
        self,
        file_path: str,
        original_content: str,
        impacts_with_fixes: list[dict],
        provider: str | None = None,
    ) -> dict:
        """Generate a unified diff patch for a file with multiple fixes."""
        fixes_description = "\n\n".join(
            f"Line {fix.get('line_number', '?')}:\n"
            f"Original: {fix.get('original_code', 'N/A')}\n"
            f"Fixed: {fix.get('fixed_code', 'N/A')}\n"
            f"Reason: {fix.get('explanation', 'N/A')}"
            for fix in impacts_with_fixes
        )

        messages = [
            {
                "role": "system",
                "content": """You are a code patch generator. Create a unified diff patch that applies all fixes to a Java file.

Provide your response as JSON:
{
  "patched_content": "The complete patched file content",
  "unified_diff": "The unified diff (--- a/file\\n+++ b/file\\n@@ ... @@)",
  "changes_summary": ["List of changes made"],
  "warnings": ["Any warnings about the patch"]
}

Rules:
- Apply ALL fixes provided
- Maintain proper Java syntax
- Preserve formatting and comments where possible
- Handle overlapping changes gracefully""",
            },
            {
                "role": "user",
                "content": f"""File: {file_path}

Original content:
```java
{original_content}
```

Fixes to apply:
{fixes_description}

Generate the patched file and unified diff.""",
            },
        ]

        response = await self.complete(messages, provider, temperature=0.1, max_tokens=8192)

        # Parse JSON response
        import json
        import re

        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if json_match:
            response = json_match.group(1)

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            return {
                "patched_content": original_content,
                "unified_diff": "",
                "changes_summary": ["Failed to generate patch - manual review required"],
                "warnings": [response[:500]],
            }


# Global instance
llm_service = LLMService()
