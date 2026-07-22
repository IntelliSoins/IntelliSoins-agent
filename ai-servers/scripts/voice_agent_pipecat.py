#!/usr/bin/env python3
"""Pipecat WebRTC voice agent over existing DGX Spark endpoints.

P0:
  SmallWebRTC + Silero VAD + Smart Turn v3
  -> Spark Whisper :2022 -> Qwen :8000 -> VoxCPM bridge :8884

P1:
  Exact PostgreSQL call trace, subject-scoped confirmed memory, allowlisted
  tools, and deterministic red-flag escalation independent of the LLM.

This service intentionally runs alongside the legacy FastRTC tutor. It uses
port 8027 by default; the legacy service remains on 8024 for rollback.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import uvicorn
from fastapi import BackgroundTasks, FastAPI
from fastapi.responses import RedirectResponse
from loguru import logger
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import (
    LocalSmartTurnAnalyzerV3,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.observers.loggers.metrics_log_observer import MetricsLogObserver
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import SmallWebRTCRunnerArguments
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import TransportParams
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.transports.smallwebrtc.request_handler import (
    SmallWebRTCPatchRequest,
    SmallWebRTCRequest,
    SmallWebRTCRequestHandler,
)
from pipecat.transports.smallwebrtc.transport import SmallWebRTCTransport
from pipecat.turns.user_mute.always_user_mute_strategy import (
    AlwaysUserMuteStrategy,
)
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner
from pipecat_ai_prebuilt.frontend import PipecatPrebuiltUI

from voice_agent.config import load_config
from voice_agent.pipecat_adapter import (
    SafetyGateProcessor,
    SparkVoxCPMTTSService,
    SparkWhisperSTTService,
    TurnFinalizerProcessor,
    build_function_schemas,
)
from voice_agent.runtime import VoiceRuntime

HOST = os.environ.get("VOICE_PIPECAT_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOICE_PIPECAT_PORT", "8027"))
SUBJECT_ID = os.environ.get("VOICE_SUBJECT_ID", "").strip()
BARGE_IN = os.environ.get("VOICE_BARGE_IN", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
EXPLICIT_CONSENT_VERIFIED = os.environ.get(
    "VOICE_EXPLICIT_CONSENT_VERIFIED", "0"
).lower() in {"1", "true", "yes", "on"}
SSL_CERT = os.environ.get("VOICE_SSL_CERT", "")
SSL_KEY = os.environ.get("VOICE_SSL_KEY", "")

SYSTEM_PROMPT = os.environ.get(
    "VOICE_SYSTEM_PROMPT",
    (
        "Tu es un agent vocal francophone pour des rappels et suivis. "
        "Réponds en français québécois naturel, en texte oral bref, sans markdown. "
        "Une seule question à la fois. Utilise uniquement les outils annoncés. "
        "Pour le triage, recueille les faits et route vers un humain; ne pose jamais "
        "de diagnostic et ne recommande jamais de traitement. Confirme explicitement "
        "avant d'enregistrer un consentement. Un refus ou une demande de retrait doit "
        "être respecté immédiatement."
    ),
)

app = FastAPI(title="Agent vocal Pipecat Spark", version="0.1.0")
app.mount("/client", PipecatPrebuiltUI)
webrtc_handler = SmallWebRTCRequestHandler(host=HOST)
_active_sessions: set[str] = set()


def _openai_base_url(chat_completions_url: str) -> str:
    """Convert ``.../v1/chat/completions`` to an OpenAI SDK base URL."""
    parts = urlsplit(chat_completions_url)
    path = parts.path.rstrip("/")
    suffix = "/chat/completions"
    if path.endswith(suffix):
        path = path[: -len(suffix)]
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


async def run_bot(
    connection: SmallWebRTCConnection,
    *,
    session_id: str,
) -> None:
    """Run one isolated Pipecat pipeline for a WebRTC peer."""
    if not SUBJECT_ID:
        raise RuntimeError(
            "VOICE_SUBJECT_ID is required and must come from trusted runtime config"
        )

    config = load_config()
    runtime = VoiceRuntime.create(
        config,
        subject_id=SUBJECT_ID,
        session_id=session_id,
        explicit_consent_verified=EXPLICIT_CONSENT_VERIFIED,
        channel="webrtc",
        barge_in=BARGE_IN,
    )
    runtime.start()
    _active_sessions.add(session_id)

    transport = SmallWebRTCTransport(
        connection,
        params=TransportParams(
            audio_in_enabled=True,
            audio_in_sample_rate=16000,
            audio_in_channels=1,
            audio_out_enabled=True,
            audio_out_sample_rate=48000,
            audio_out_channels=1,
        ),
    )
    stt = SparkWhisperSTTService(config)
    tts = SparkVoxCPMTTSService(config, runtime)
    llm = OpenAILLMService(
        api_key=config.llm_key or "spark-local",
        base_url=_openai_base_url(config.llm_url),
        retry_timeout_secs=config.llm_timeout_s,
        retry_on_timeout=False,
        settings=OpenAILLMService.Settings(
            model=config.llm_model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            system_instruction=SYSTEM_PROMPT,
            extra={"repetition_penalty": config.repetition_penalty},
        ),
    )

    messages: list[dict] = []
    remembered = runtime.memory_context()
    if remembered and remembered != "[]":
        messages.append(
            {
                "role": "developer",
                "content": (
                    "MÉMOIRE CONFIRMÉE DU CONTACT. Utilise-la comme contexte, "
                    "sans la présenter comme une nouvelle confirmation:\n"
                    f"{remembered}"
                ),
            }
        )
    context = LLMContext(
        messages=messages,
        tools=build_function_schemas(runtime),
        tool_choice="auto",
    )

    mute_strategies = [] if BARGE_IN else [AlwaysUserMuteStrategy()]
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(
                sample_rate=16000,
                params=VADParams(
                    confidence=0.65,
                    start_secs=0.2,
                    stop_secs=0.5,
                    min_volume=0.5,
                ),
            ),
            user_turn_strategies=UserTurnStrategies(
                stop=[
                    TurnAnalyzerUserTurnStopStrategy(
                        turn_analyzer=LocalSmartTurnAnalyzerV3()
                    )
                ]
            ),
            user_mute_strategies=mute_strategies,
            user_turn_stop_timeout=5.0,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            SafetyGateProcessor(runtime),
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
            TurnFinalizerProcessor(runtime),
        ]
    )
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=48000,
            enable_metrics=True,
            enable_usage_metrics=True,
            report_only_initial_ttfb=False,
        ),
        observers=[MetricsLogObserver(), UserBotLatencyObserver()],
        idle_timeout_secs=300,
        conversation_id=session_id,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client):
        logger.info(
            "Pipecat client connected session={} subject={} barge_in={}",
            session_id,
            SUBJECT_ID,
            BARGE_IN,
        )

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client):
        logger.info("Pipecat client disconnected session={}", session_id)
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=False, handle_sigterm=False)
    try:
        await runner.add_workers(worker)
        await runner.run()
    except Exception as exc:
        await asyncio.to_thread(
            runtime.finish_turn,
            stopped_reason="pipeline_error",
            error=str(exc),
        )
        raise
    finally:
        await asyncio.to_thread(runtime.close, stopped_reason="session_closed")
        _active_sessions.discard(session_id)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="/client/")


@app.get("/health")
async def health():
    config = load_config()
    return {
        "status": "ok",
        "service": "voice-agent-pipecat",
        "port": PORT,
        "active_sessions": len(_active_sessions),
        "spark": {
            "whisper": config.whisper_url,
            "llm": config.llm_url,
            "tts": config.tts_url,
        },
        "features": {
            "smart_turn_v3": True,
            "barge_in": BARGE_IN,
            "postgres": config.db_enabled,
            "tools": True,
            "deterministic_red_flags": True,
        },
    }


@app.post("/api/offer")
async def offer(request: SmallWebRTCRequest, background_tasks: BackgroundTasks):
    session_id = str(uuid.uuid4())

    async def connection_callback(connection: SmallWebRTCConnection):
        background_tasks.add_task(
            run_bot,
            connection,
            session_id=session_id,
        )

    return await webrtc_handler.handle_web_request(
        request=request,
        webrtc_connection_callback=connection_callback,
    )


@app.patch("/api/offer")
async def ice_candidate(request: SmallWebRTCPatchRequest):
    await webrtc_handler.handle_patch_request(request)
    return {"status": "success"}


def main() -> None:
    cert = Path(SSL_CERT).expanduser() if SSL_CERT else None
    key = Path(SSL_KEY).expanduser() if SSL_KEY else None
    public_bind = HOST not in {"127.0.0.1", "localhost", "::1"}
    if public_bind and not (
        cert and key and cert.is_file() and key.is_file()
    ):
        raise RuntimeError(
            "Public WebRTC bind requires VOICE_SSL_CERT and VOICE_SSL_KEY"
        )

    kwargs = {
        "app": app,
        "host": HOST,
        "port": PORT,
        "log_level": "info",
    }
    if cert and key and cert.is_file() and key.is_file():
        kwargs["ssl_certfile"] = str(cert)
        kwargs["ssl_keyfile"] = str(key)
    uvicorn.run(**kwargs)


if __name__ == "__main__":
    main()
