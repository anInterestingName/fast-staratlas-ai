import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.llm.config_provider import LLMConfigProvider
from app.llm.deps import get_chat_orchestrator, get_config_provider
from app.llm.errors import LLMError
from app.llm.orchestrator import ChatOrchestrator, PreparedChat
from app.schemas.llm import ChatRequest, ChatResponse, LLMProfileItem, LLMProfileListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])


def _http_exception(exc: LLMError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message})


def _sse_frame(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/profiles", response_model=LLMProfileListResponse)
def list_profiles(
    provider: Annotated[LLMConfigProvider, Depends(get_config_provider)],
) -> LLMProfileListResponse:
    profiles = provider.list_profiles()
    items = [LLMProfileItem(name=item.name, ready=item.ready, model=item.model) for item in profiles]
    return LLMProfileListResponse(total=len(items), items=items)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> ChatResponse:
    try:
        result = await orchestrator.chat(payload.profile, payload.messages)
    except LLMError as exc:
        raise _http_exception(exc) from exc
    return ChatResponse(profile=result.profile, content=result.content, usage=result.usage)


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> StreamingResponse:
    try:
        prepared = orchestrator.prepare(payload.profile, payload.messages)
    except LLMError as exc:
        raise _http_exception(exc) from exc
    return StreamingResponse(
        _sse_events(orchestrator, prepared),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def _sse_events(
    orchestrator: ChatOrchestrator,
    prepared: PreparedChat,
) -> AsyncIterator[str]:
    try:
        async for event in orchestrator.chat_stream(prepared):
            yield _sse_frame(event.event, event.data)
    except LLMError as exc:
        yield _sse_frame("error", {"code": exc.code, "message": exc.message})
    except Exception as exc:
        logger.warning("llm_stream_unexpected error_type=%s", type(exc).__name__)
        yield _sse_frame("error", {"code": "upstream_failed", "message": "上游调用失败"})
