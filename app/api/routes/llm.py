import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.responses import StreamingResponse

from app.llm.config_provider import LLMConfigProvider
from app.llm.deps import get_chat_model_factory, get_chat_orchestrator, get_config_provider
from app.llm.errors import ConfigNotFoundError, LLMError
from app.llm.factory import ChatModelFactory
from app.llm.item import LLMConfigItem
from app.llm.orchestrator import ChatOrchestrator, PreparedChat
from app.schemas.llm import (
    ChatRequest,
    ChatResponse,
    ImageAsset,
    ImageGenerateRequest,
    ImageResponse,
    LLMConfigCreateRequest,
    LLMConfigListResponse,
    LLMConfigPublic,
    public_config,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm", tags=["llm"])


def _sse_frame(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/configs", response_model=LLMConfigListResponse)
def list_configs(
    provider: Annotated[LLMConfigProvider, Depends(get_config_provider)],
) -> LLMConfigListResponse:
    items = [public_config(item) for item in provider.list_configs()]
    return LLMConfigListResponse(total=len(items), items=items)


@router.get("/configs/{name}", response_model=LLMConfigPublic)
def get_config(
    name: str,
    provider: Annotated[LLMConfigProvider, Depends(get_config_provider)],
) -> LLMConfigPublic:
    item = provider.get_config(name)
    if item is None:
        raise ConfigNotFoundError(name)
    return public_config(item)


@router.post("/configs", response_model=LLMConfigPublic, status_code=201)
def create_config(
    payload: LLMConfigCreateRequest,
    provider: Annotated[LLMConfigProvider, Depends(get_config_provider)],
    factory: Annotated[ChatModelFactory, Depends(get_chat_model_factory)],
) -> LLMConfigPublic:
    item = LLMConfigItem.model_validate(payload.model_dump(exclude={"name"}))
    created = provider.create_config(payload.name, item)
    factory.clear_cache()
    return public_config(created)


@router.put("/configs/{name}", response_model=LLMConfigPublic)
def update_config(
    name: str,
    payload: LLMConfigItem,
    provider: Annotated[LLMConfigProvider, Depends(get_config_provider)],
    factory: Annotated[ChatModelFactory, Depends(get_chat_model_factory)],
) -> LLMConfigPublic:
    updated = provider.update_config(name, payload)
    factory.clear_cache()
    return public_config(updated)


@router.delete("/configs/{name}", status_code=204)
def delete_config(
    name: str,
    provider: Annotated[LLMConfigProvider, Depends(get_config_provider)],
    factory: Annotated[ChatModelFactory, Depends(get_chat_model_factory)],
) -> Response:
    provider.delete_config(name)
    factory.clear_cache()
    return Response(status_code=204)


@router.post("/chat", response_model=None)
async def chat(
    payload: ChatRequest,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> ChatResponse | StreamingResponse:
    prepared = orchestrator.prepare(payload.config, payload.fallback, payload.messages)
    if prepared.primary.stream:
        return StreamingResponse(
            _sse_events(orchestrator, prepared),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )
    result = await orchestrator.chat_prepared(prepared)
    return ChatResponse(config=result.config, content=result.content, usage=result.usage)


@router.post("/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> StreamingResponse:
    prepared = orchestrator.prepare(payload.config, payload.fallback, payload.messages)
    return StreamingResponse(
        _sse_events(orchestrator, prepared),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.post("/images/generate", response_model=ImageResponse)
async def generate_image(
    payload: ImageGenerateRequest,
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
) -> ImageResponse:
    result = await orchestrator.generate_image(payload.config, payload.fallback, payload.prompt)
    return ImageResponse(
        config=result.config,
        images=[ImageAsset(b64_json=item.get("b64_json"), url=item.get("url")) for item in result.images],
    )


@router.post("/images/edit", response_model=ImageResponse)
async def edit_image(
    orchestrator: Annotated[ChatOrchestrator, Depends(get_chat_orchestrator)],
    config: Annotated[str, Form()],
    prompt: Annotated[str, Form()],
    image: Annotated[UploadFile, File()],
    fallback: Annotated[str | None, Form()] = None,
    mask: Annotated[UploadFile | None, File()] = None,
) -> ImageResponse:
    image_bytes = await image.read()
    mask_bytes = await mask.read() if mask is not None else None
    result = await orchestrator.edit_image(
        config,
        fallback,
        prompt,
        image_bytes,
        mask_bytes,
        image.filename or "image.png",
        mask.filename if mask is not None else "mask.png",
    )
    return ImageResponse(
        config=result.config,
        images=[ImageAsset(b64_json=item.get("b64_json"), url=item.get("url")) for item in result.images],
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
