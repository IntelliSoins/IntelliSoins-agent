"""Unit tests — async HTTP clients with mocked httpx (no live Spark)."""

from __future__ import annotations

import asyncio
import json
import unittest
from typing import Any, AsyncIterator, Optional
from unittest.mock import AsyncMock, MagicMock

import _path  # noqa: F401
import httpx

from voice_agent.clients.llm import LlmClient, ToolCallAccumulator
from voice_agent.clients.tts import TtsClient
from voice_agent.clients.whisper import WhisperClient
from voice_agent.config import VoiceConfig


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


class _FakeStreamResponse:
    def __init__(self, lines: list[str], status_code: int = 200) -> None:
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("POST", "http://test"),
                response=httpx.Response(self.status_code),
            )

    async def aiter_lines(self) -> AsyncIterator[str]:
        for line in self._lines:
            yield line

    async def __aenter__(self) -> "_FakeStreamResponse":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


class TestWhisperClient(unittest.TestCase):
    def test_transcribe_posts_wav(self) -> None:
        cfg = VoiceConfig(
            whisper_url="http://spark:2022/v1/audio/transcriptions",
            whisper_language="fr",
        )
        mock_client = AsyncMock()
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value={"text": "  bonjour  "})
        mock_client.post = AsyncMock(return_value=response)

        client = WhisperClient(cfg, client=mock_client, owns_client=False)

        async def _go() -> str:
            return await client.transcribe(b"RIFF....", filename="clip.wav")

        text = _run(_go())
        self.assertEqual(text, "bonjour")
        kwargs = mock_client.post.await_args.kwargs
        self.assertEqual(mock_client.post.await_args.args[0], cfg.whisper_url)
        self.assertEqual(kwargs["data"]["language"], "fr")
        self.assertEqual(kwargs["files"]["file"][0], "clip.wav")

    def test_transcribe_cancels(self) -> None:
        cfg = VoiceConfig()
        mock_client = AsyncMock()
        client = WhisperClient(cfg, client=mock_client, owns_client=False)
        cancel = asyncio.Event()
        cancel.set()

        async def _go() -> None:
            await client.transcribe(b"x", cancel_event=cancel)

        with self.assertRaises(asyncio.CancelledError):
            _run(_go())
        mock_client.post.assert_not_awaited()


class TestLlmClient(unittest.TestCase):
    def test_tool_call_accumulator(self) -> None:
        acc = ToolCallAccumulator()
        acc.ingest(
            [
                {
                    "index": 0,
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "end_call", "arguments": ""},
                }
            ]
        )
        acc.ingest([{"index": 0, "function": {"arguments": '{"reason":'}}])
        acc.ingest([{"index": 0, "function": {"arguments": '"done"}'}}])
        final = acc.finalized()
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["function"]["name"], "end_call")
        self.assertEqual(final[0]["function"]["arguments"], '{"reason":"done"}')

    def test_stream_chat_content_and_tools(self) -> None:
        cfg = VoiceConfig(llm_url="http://spark:8000/v1/chat/completions")
        lines = [
            'data: {"choices":[{"delta":{"content":"Salut"}}]}',
            (
                'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
                '"function":{"name":"opt_out","arguments":"{\\"channels\\":'
                '[\\"voice\\"]}"}}]}}]}'
            ),
            'data: {"choices":[{"delta":{},"finish_reason":"tool_calls"}]}',
            "data: [DONE]",
        ]
        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=_FakeStreamResponse(lines))
        client = LlmClient(cfg, client=mock_client, owns_client=False)

        async def _go() -> tuple[str, list, Optional[str]]:
            return await client.collect_chat(
                [{"role": "user", "content": "stop"}]
            )

        content, tools, finish = _run(_go())
        self.assertEqual(content, "Salut")
        self.assertEqual(finish, "tool_calls")
        self.assertEqual(tools[0]["function"]["name"], "opt_out")
        args = json.loads(tools[0]["function"]["arguments"])
        self.assertEqual(args["channels"], ["voice"])

    def test_stream_chat_cancels(self) -> None:
        cfg = VoiceConfig()
        lines = [
            'data: {"choices":[{"delta":{"content":"A"}}]}',
            'data: {"choices":[{"delta":{"content":"B"}}]}',
        ]
        mock_client = MagicMock()
        mock_client.stream = MagicMock(return_value=_FakeStreamResponse(lines))
        client = LlmClient(cfg, client=mock_client, owns_client=False)
        cancel = asyncio.Event()

        async def _go() -> list[str]:
            parts: list[str] = []
            async for chunk in client.stream_chat(
                [{"role": "user", "content": "x"}], cancel_event=cancel
            ):
                parts.append(chunk.content)
                cancel.set()
            return parts

        with self.assertRaises(asyncio.CancelledError):
            _run(_go())


class TestTtsClient(unittest.TestCase):
    def test_synthesize_posts_json(self) -> None:
        cfg = VoiceConfig(
            tts_url="http://127.0.0.1:8884/v1/audio/speech",
            tts_model="michael-v8",
        )
        mock_client = AsyncMock()
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.content = b"WAVDATA"
        mock_client.post = AsyncMock(return_value=response)
        client = TtsClient(cfg, client=mock_client, owns_client=False)

        audio = _run(client.synthesize("**Bonjour.**"))
        self.assertEqual(audio, b"WAVDATA")
        payload = mock_client.post.await_args.kwargs["json"]
        self.assertEqual(payload["model"], "michael-v8")
        self.assertEqual(payload["input"], "Bonjour.")
        self.assertFalse(payload["stream"])

    def test_sentence_chunked_stream(self) -> None:
        cfg = VoiceConfig(tts_min_chars=5)
        mock_client = AsyncMock()
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.content = b"AUD"
        mock_client.post = AsyncMock(return_value=response)
        client = TtsClient(cfg, client=mock_client, owns_client=False)

        async def deltas() -> AsyncIterator[str]:
            for part in ("Bonjour. ", "Comment allez-vous?"):
                yield part

        async def _go() -> list[str]:
            out: list[str] = []
            async for seg in client.synthesize_streamed_text(deltas()):
                out.append(seg.text)
            return out

        texts = _run(_go())
        self.assertGreaterEqual(len(texts), 1)
        self.assertTrue(any("Bonjour" in t for t in texts))
        self.assertTrue(mock_client.post.await_count >= 1)

    def test_synthesize_cancels(self) -> None:
        cfg = VoiceConfig()
        mock_client = AsyncMock()
        client = TtsClient(cfg, client=mock_client, owns_client=False)
        cancel = asyncio.Event()
        cancel.set()
        with self.assertRaises(asyncio.CancelledError):
            _run(client.synthesize("hello", cancel_event=cancel))


if __name__ == "__main__":
    unittest.main()
