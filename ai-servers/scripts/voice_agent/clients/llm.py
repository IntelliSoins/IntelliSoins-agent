"""Async streaming OpenAI-compatible chat client (content + tool_calls)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping, Optional, Sequence

import httpx

from ..config import VoiceConfig


@dataclass
class ChatChunk:
    """One incremental unit from a chat completion stream."""

    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: Optional[str] = None
    raw: Optional[dict[str, Any]] = None


@dataclass
class ToolCallAccumulator:
    """Merge streamed tool_call deltas (OpenAI index-based fragments)."""

    items: dict[int, dict[str, Any]] = field(default_factory=dict)

    def ingest(self, deltas: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        updated: list[dict[str, Any]] = []
        for delta in deltas:
            idx = int(delta.get("index", 0))
            slot = self.items.setdefault(
                idx,
                {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            if delta.get("id"):
                slot["id"] = delta["id"]
            if delta.get("type"):
                slot["type"] = delta["type"]
            fn = delta.get("function") or {}
            if fn.get("name"):
                slot["function"]["name"] = (
                    slot["function"].get("name", "") + fn["name"]
                )
            if "arguments" in fn and fn["arguments"] is not None:
                slot["function"]["arguments"] = (
                    slot["function"].get("arguments", "") + fn["arguments"]
                )
            updated.append(dict(slot))
        return updated

    def finalized(self) -> list[dict[str, Any]]:
        return [self.items[i] for i in sorted(self.items)]


class LlmClient:
    """Streaming chat completions against Qwen on Spark (``VOICE_LLM_URL``)."""

    def __init__(
        self,
        config: VoiceConfig,
        *,
        client: Optional[httpx.AsyncClient] = None,
        owns_client: bool = False,
    ) -> None:
        self._config = config
        self._owns_client = owns_client or client is None
        self._client = client or httpx.AsyncClient()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "LlmClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def stream_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Optional[Sequence[Mapping[str, Any]]] = None,
        tool_choice: Any = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        extra: Optional[Mapping[str, Any]] = None,
        cancel_event: Optional[Any] = None,
    ) -> AsyncIterator[ChatChunk]:
        """Yield content / tool_call deltas; honour cancellation between lines."""
        payload: dict[str, Any] = {
            "model": model or self._config.llm_model,
            "messages": list(messages),
            "max_tokens": max_tokens if max_tokens is not None else self._config.max_tokens,
            "temperature": (
                temperature if temperature is not None else self._config.temperature
            ),
            "repetition_penalty": self._config.repetition_penalty,
            "stream": True,
        }
        if tools:
            payload["tools"] = list(tools)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if extra:
            payload.update(dict(extra))

        timeout = httpx.Timeout(self._config.llm_timeout_s, connect=10.0)
        headers = self._config.llm_headers()
        accum = ToolCallAccumulator()

        async with self._client.stream(
            "POST",
            self._config.llm_url,
            json=payload,
            headers=headers or None,
            timeout=timeout,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                self._raise_if_cancelled(cancel_event)
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choice = (obj.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                content = delta.get("content") or ""
                tool_deltas = delta.get("tool_calls") or []
                if tool_deltas:
                    accum.ingest(tool_deltas)
                tools_snapshot = accum.finalized() if accum.items else []
                finish = choice.get("finish_reason")
                if content or tool_deltas or finish:
                    yield ChatChunk(
                        content=content,
                        tool_calls=tools_snapshot if tool_deltas or finish else [],
                        finish_reason=finish,
                        raw=obj,
                    )

    async def collect_chat(
        self,
        messages: Sequence[Mapping[str, Any]],
        **kwargs: Any,
    ) -> tuple[str, list[dict[str, Any]], Optional[str]]:
        """Drain a stream into full content + finalized tool_calls."""
        content_parts: list[str] = []
        finish: Optional[str] = None
        last_tools: list[dict[str, Any]] = []
        async for chunk in self.stream_chat(messages, **kwargs):
            if chunk.content:
                content_parts.append(chunk.content)
            if chunk.tool_calls:
                last_tools = chunk.tool_calls
            if chunk.finish_reason:
                finish = chunk.finish_reason
        return "".join(content_parts), last_tools, finish

    @staticmethod
    def _raise_if_cancelled(cancel_event: Optional[Any]) -> None:
        if cancel_event is not None and cancel_event.is_set():
            import asyncio

            raise asyncio.CancelledError("voice_agent llm cancelled")
