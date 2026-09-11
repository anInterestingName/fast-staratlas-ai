from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.demo import DemoCreate, DemoItem, DemoListResponse

router = APIRouter(prefix="/demo", tags=["demo"])

_SEED_ITEM = DemoItem(
    id=1,
    name="star-atlas",
    message="Hello from the demo API",
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
)
_DEMO_STORE: dict[int, DemoItem] = {1: _SEED_ITEM.model_copy()}
_NEXT_ID = 2


def reset_demo_store() -> None:
    global _NEXT_ID
    _DEMO_STORE.clear()
    _DEMO_STORE[1] = _SEED_ITEM.model_copy()
    _NEXT_ID = 2


@router.get("", response_model=DemoListResponse)
def list_demo_items(
    q: str | None = Query(default=None, description="Optional name keyword filter"),
) -> DemoListResponse:
    items = list(_DEMO_STORE.values())
    if q:
        keyword = q.lower()
        items = [item for item in items if keyword in item.name.lower()]
    return DemoListResponse(total=len(items), items=items)


@router.get("/{item_id}", response_model=DemoItem)
def get_demo_item(item_id: int) -> DemoItem:
    item = _DEMO_STORE.get(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demo item not found")
    return item


@router.post("", response_model=DemoItem, status_code=status.HTTP_201_CREATED)
def create_demo_item(payload: DemoCreate) -> DemoItem:
    global _NEXT_ID
    item = DemoItem(
        id=_NEXT_ID,
        name=payload.name,
        message=payload.message,
        created_at=datetime.now(UTC),
    )
    _DEMO_STORE[_NEXT_ID] = item
    _NEXT_ID += 1
    return item
