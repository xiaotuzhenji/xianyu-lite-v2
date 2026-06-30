import json
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models.account import Account
from ..models.delivery_config import DeliveryConfig
from ..models.item import Item
from ..models.user import User
from ..utils.item_fetcher import ItemFetcher

router = APIRouter(prefix="/items", tags=["items"])

UPLOAD_DIR = Path("/app/uploads/items")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_ITEM_IMAGES = 8


class ItemResponse(BaseModel):
    id: int
    item_id: str
    account_id: str = ""
    title: str = ""
    price: float = 0
    status: str = "online"
    publish_status: str = "draft"
    publish_error: Optional[str] = None
    url: str = ""
    description: Optional[str] = ""
    image_urls: str = ""

    class Config:
        from_attributes = True


class ItemCreateRequest(BaseModel):
    account_id: str
    item_id: str = ""
    title: str = ""
    price: float = 0
    url: str = ""
    description: Optional[str] = ""
    image_urls: str = "[]"


class ItemUpdateRequest(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    url: Optional[str] = None
    description: Optional[str] = None
    image_urls: Optional[str] = None


def _parse_image_urls(value: str, *, strict: bool = False) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        if strict:
            raise HTTPException(status_code=400, detail="\u56fe\u7247\u5730\u5740\u5fc5\u987b\u662f JSON \u6570\u7ec4")
        return []
    if not isinstance(parsed, list):
        if strict:
            raise HTTPException(status_code=400, detail="\u56fe\u7247\u5730\u5740\u5fc5\u987b\u662f JSON \u6570\u7ec4")
        return []
    return [str(item) for item in parsed if item]


def _validate_title(title: str) -> str:
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="\u5546\u54c1\u6807\u9898\u4e0d\u80fd\u4e3a\u7a7a")
    return clean_title[:30]


def _normalize_image_urls(value: str) -> str:
    urls = _parse_image_urls(value or "[]", strict=True)
    if len(urls) > MAX_ITEM_IMAGES:
        raise HTTPException(status_code=400, detail=f"\u5546\u54c1\u56fe\u7247\u6700\u591a {MAX_ITEM_IMAGES} \u5f20")
    return json.dumps(urls, ensure_ascii=False)


def _image_count(value: Optional[str]) -> int:
    return len(_parse_image_urls(value or "[]"))


def _validate_image_count(image_urls: str) -> None:
    if _image_count(image_urls) > MAX_ITEM_IMAGES:
        raise HTTPException(status_code=400, detail=f"\u5546\u54c1\u56fe\u7247\u6700\u591a {MAX_ITEM_IMAGES} \u5f20")


def _validate_price(price: float) -> None:
    if price < 0:
        raise HTTPException(status_code=400, detail="\u5546\u54c1\u4ef7\u683c\u4e0d\u80fd\u4e3a\u8d1f\u6570")


def _uploaded_image_path(url: str) -> str:
    path = urlparse(url).path if "://" in url else url
    return path if path.startswith("/uploads/items/") else ""


def _uploaded_image_paths(image_urls: str) -> set[str]:
    return {path for path in (_uploaded_image_path(url) for url in _parse_image_urls(image_urls)) if path}


def _cleanup_uploaded_images(image_urls: str, reserved_paths: Optional[set[str]] = None) -> None:
    reserved_paths = reserved_paths or set()
    for url in _parse_image_urls(image_urls):
        path = _uploaded_image_path(url)
        if not path or path in reserved_paths:
            continue
        filename = path.split("/uploads/items/", 1)[-1].strip("/")
        if not filename:
            continue
        target = UPLOAD_DIR / filename
        if target.exists() and target.is_file():
            try:
                target.unlink()
            except Exception:
                pass


def _can_delete_item(item: Item) -> bool:
    return item.status != "online" or item.item_id.startswith("draft-")


def _new_draft_item_id(account_id: str) -> str:
    return f"draft-{account_id}-{uuid.uuid4().hex[:12]}"


def _is_item_account_conflict(item: Optional[Item], account_id: str) -> bool:
    return bool(item and item.account_id != account_id)


async def _get_owned_account(db: AsyncSession, account_id: str, user: User) -> Optional[Account]:
    stmt = select(Account).where(Account.account_id == account_id, Account.owner_id == user.id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _get_owned_item(db: AsyncSession, item_id: str, user: User) -> Optional[Item]:
    stmt = (
        select(Item)
        .join(Account, Item.account_id == Account.account_id)
        .where(Item.item_id == item_id, Account.owner_id == user.id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _find_published_draft_item(
    db: AsyncSession,
    account_id: str,
    actual_item_id: str,
) -> Optional[Item]:
    stmt = (
        select(Item)
        .where(
            Item.account_id == account_id,
            Item.item_id.like("draft-%"),
            Item.publish_status == "published",
            Item.url.like(f"%{actual_item_id}%"),
        )
        .order_by(Item.id.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


def _merge_item_fields(target: Item, source: Item) -> None:
    if source.title and not target.title:
        target.title = source.title
    if source.description and not target.description:
        target.description = source.description
    if (
        source.image_urls
        and source.image_urls != "[]"
        and _image_count(source.image_urls) > _image_count(target.image_urls)
    ):
        target.image_urls = source.image_urls
    if source.price and not target.price:
        target.price = source.price
    if source.publish_status == "published":
        target.publish_status = "published"
        target.publish_error = None
    if source.url and (not target.url or "goofish.com/item/" in target.url):
        target.url = source.url


async def _move_delivery_config(db: AsyncSession, account_id: str, old_item_id: str, new_item_id: str) -> None:
    if not old_item_id or not new_item_id or old_item_id == new_item_id:
        return
    old_result = await db.execute(
        select(DeliveryConfig).where(
            DeliveryConfig.account_id == account_id,
            DeliveryConfig.item_id == old_item_id,
        )
    )
    old_config = old_result.scalar_one_or_none()
    if not old_config:
        return
    new_result = await db.execute(
        select(DeliveryConfig).where(
            DeliveryConfig.account_id == account_id,
            DeliveryConfig.item_id == new_item_id,
        )
    )
    if new_result.scalar_one_or_none():
        await db.delete(old_config)
    else:
        old_config.item_id = new_item_id


async def _delete_delivery_config(db: AsyncSession, account_id: str, item_id: str) -> None:
    await db.execute(
        delete(DeliveryConfig).where(
            DeliveryConfig.account_id == account_id,
            DeliveryConfig.item_id == item_id,
        )
    )


@router.post("/upload-image")
async def upload_item_image(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择图片")

    suffix = Path(file.filename).suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail="仅支持 jpg/jpeg/png/webp/gif")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片内容为空")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片不能超过 10MB")

    filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}{suffix}"
    target = UPLOAD_DIR / filename
    target.write_bytes(content)

    return {
        "success": True,
        "data": {
            "filename": filename,
            "url": f"/uploads/items/{filename}",
        },
    }


@router.post("/sync")
async def sync_items(
    account_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    account_query = select(Account).where(Account.status == "active", Account.owner_id == user.id)
    if account_id:
        account_query = account_query.where(Account.account_id == account_id)
    accounts = (await db.execute(account_query)).scalars().all()
    if not accounts:
        raise HTTPException(status_code=404, detail="没有可同步的账号")

    synced = 0
    offline_count = 0
    errors = []
    for account in accounts:
        acc_id = account.account_id
        if not account.cookie:
            errors.append({"account_id": acc_id, "error": "Cookie 为空"})
            continue
        try:
            async with ItemFetcher(acc_id, account.cookie) as fetcher:
                fetched = await fetcher.fetch_all(page_size=20, max_pages=10)
            if fetched.get("cookies_str") and fetched["cookies_str"] != account.cookie:
                account.cookie = fetched["cookies_str"]
            if not fetched.get("success"):
                errors.append({"account_id": acc_id, "error": fetched.get("error", "同步失败")})
                await db.commit()
                continue

            remote_item_ids = set()
            for data in fetched.get("items", []):
                item_id = str(data.get("item_id") or "").strip()
                if item_id:
                    remote_item_ids.add(item_id)

            for data in fetched.get("items", []):
                item_id = str(data.get("item_id") or "").strip()
                if not item_id:
                    continue
                item = (await db.execute(select(Item).where(Item.item_id == item_id))).scalar_one_or_none()
                if _is_item_account_conflict(item, acc_id):
                    errors.append({"account_id": acc_id, "error": f"商品ID {item_id} 已属于其他账号，已跳过"})
                    continue
                if (
                    item
                    and item.status == "online"
                    and (not item.publish_status or item.publish_status == "draft")
                    and not item.item_id.startswith("draft-")
                ):
                    item.publish_status = "published"
                    item.publish_error = None
                draft_item = await _find_published_draft_item(db, acc_id, item_id)
                if item and draft_item and item.id != draft_item.id:
                    await _move_delivery_config(db, acc_id, draft_item.item_id, item_id)
                    _merge_item_fields(item, draft_item)
                    await db.delete(draft_item)
                elif not item and draft_item:
                    await _move_delivery_config(db, acc_id, draft_item.item_id, item_id)
                    item = draft_item
                    item.item_id = item_id

                if not item:
                    item = Item(item_id=item_id, account_id=acc_id, publish_status="draft")
                    db.add(item)
                elif item.item_id != item_id:
                    item.item_id = item_id
                item.account_id = acc_id
                item.title = (data.get("title") or "")[:30]
                item.price = data.get("price") or 0
                item.url = data.get("url") or f"https://www.goofish.com/item/{item_id}"
                fetched_image_urls = data.get("image_urls") or "[]"
                if _image_count(fetched_image_urls) >= _image_count(item.image_urls):
                    item.image_urls = fetched_image_urls
                item.status = data.get("status") or "online"
                if item.status == "online" and (not item.publish_status or item.publish_status in ("draft", "failed")):
                    item.publish_status = "published"
                    item.publish_error = None
                synced += 1

            if not fetched.get("truncated"):
                db_items = (
                    await db.execute(
                        select(Item).where(
                            Item.account_id == acc_id,
                            Item.status == "online",
                            ~Item.item_id.like("draft-%"),
                        )
                    )
                ).scalars().all()
                for db_item in db_items:
                    if db_item.item_id not in remote_item_ids:
                        db_item.status = "offline"
                        if db_item.publish_status == "published":
                            db_item.publish_status = "draft"
                        db_item.publish_error = None
                        offline_count += 1

            await db.commit()
        except Exception as exc:
            await db.rollback()
            errors.append({"account_id": acc_id, "error": str(exc)})

    return {"success": True, "synced": synced, "offline": offline_count, "accounts": len(accounts), "errors": errors}

@router.post("")
async def create_item(
    data: ItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    account_id = data.account_id.strip()
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id 不能为空")
    if not await _get_owned_account(db, account_id, user):
        raise HTTPException(status_code=404, detail="账号不存在或无权限")
    if data.item_id.strip():
        raise HTTPException(status_code=400, detail="\u65b0\u5efa\u5546\u54c1\u4e0d\u80fd\u6307\u5b9a\u5546\u54c1ID\uff0c\u8bf7\u53d1\u5e03\u6210\u529f\u540e\u7531\u5e73\u53f0\u81ea\u52a8\u56de\u5199")

    item = Item(item_id=_new_draft_item_id(account_id), account_id=account_id)
    item.account_id = account_id
    item.title = _validate_title(data.title)
    _validate_price(data.price or 0)
    item.price = data.price or 0
    item.url = data.url.strip()
    item.description = (data.description or "").strip()
    item.image_urls = _normalize_image_urls(data.image_urls or "[]")
    item.status = "draft"
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"success": True, "data": ItemResponse.model_validate(item)}


@router.put("/{item_id}")
async def update_item(
    item_id: str,
    data: ItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await _get_owned_item(db, item_id, user)
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")
    if data.title is not None:
        item.title = _validate_title(data.title)
    if data.price is not None:
        _validate_price(data.price)
        item.price = data.price
    if data.url is not None:
        item.url = data.url.strip()
    if data.description is not None:
        item.description = data.description.strip()
    if data.image_urls is not None:
        item.image_urls = _normalize_image_urls(data.image_urls)
    await db.commit()
    await db.refresh(item)
    return {"success": True, "data": ItemResponse.model_validate(item)}


@router.delete("/{item_id}")
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await _get_owned_item(db, item_id, user)
    if not item:
        return {"success": True}
    if not _can_delete_item(item):
        raise HTTPException(status_code=400, detail="请先下架后再删除")
    other_items = (
        await db.execute(select(Item.image_urls).where(Item.id != item.id))
    ).scalars().all()
    reserved_paths: set[str] = set()
    for other_image_urls in other_items:
        reserved_paths.update(_uploaded_image_paths(other_image_urls or "[]"))
    _cleanup_uploaded_images(item.image_urls or "[]", reserved_paths)
    await _delete_delivery_config(db, item.account_id, item.item_id)
    await db.delete(item)
    await db.commit()
    return {"success": True}


@router.get("")
async def list_items(
    account_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    owned_accounts = select(Account.account_id).where(Account.owner_id == user.id)
    query = select(Item).where(Item.account_id.in_(owned_accounts))
    total_query = select(func.count(Item.id)).where(Item.account_id.in_(owned_accounts))
    if account_id:
        query = query.where(Item.account_id == account_id)
        total_query = total_query.where(Item.account_id == account_id)
    total = (await db.execute(total_query)).scalar() or 0
    result = await db.execute(query.order_by(Item.id.desc()).offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()
    return {"success": True, "data": [ItemResponse.model_validate(item) for item in items], "total": total, "page": page, "page_size": page_size}
