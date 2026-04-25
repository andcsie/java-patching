"""Multi-LLM provider service supporting OpenAI, Anthropic, Gemini, and Ollama."""

from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx

from app.core.config import settings


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
            return data["candidates"][0]["content"]["parts"][0]["text"]

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
                        if "candidates" in data:
                            text = data["candidates"][0]["content"]["parts"][0].get("text", "")
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


# Global instance
llm_service = LLMService()
