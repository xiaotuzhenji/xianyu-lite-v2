import json
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..deps import get_current_user
from ..models.account import Account
from ..models.item import Item
from ..models.user import User
from ..utils.item_fetcher import ItemFetcher

router = APIRouter(prefix="/items", tags=["items"])

UPLOAD_DIR = Path("/app/uploads/items")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
    status: str = "draft"


class ItemUpdateRequest(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    url: Optional[str] = None
    description: Optional[str] = None
    image_urls: Optional[str] = None
    status: Optional[str] = None
    publish_status: Optional[str] = None
    publish_error: Optional[str] = None


def _parse_image_urls(value: str) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed if item]
    except Exception:
        return []
    return []


def _cleanup_uploaded_images(image_urls: str) -> None:
    for url in _parse_image_urls(image_urls):
        path = urlparse(url).path if "://" in url else url
        if not path.startswith("/uploads/items/"):
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
    account_query = select(Account).where(Account.status == "active")
    if account_id:
        account_query = account_query.where(Account.account_id == account_id)
    accounts = (await db.execute(account_query)).scalars().all()
    if not accounts:
        raise HTTPException(status_code=404, detail="没有可同步的账号")

    synced = 0
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

            for data in fetched.get("items", []):
                item_id = data.get("item_id")
                if not item_id:
                    continue
                item = (await db.execute(select(Item).where(Item.item_id == item_id))).scalar_one_or_none()
                if not item:
                    item = Item(item_id=item_id, account_id=acc_id)
                    db.add(item)
                item.account_id = acc_id
                item.title = (data.get("title") or "")[:30]
                item.price = data.get("price") or 0
                item.url = data.get("url") or f"https://www.goofish.com/item/{item_id}"
                item.image_urls = data.get("image_urls") or "[]"
                item.status = data.get("status") or "online"
                # If item is online on Xianyu, mark as already published
                if item.status == "online" and item.publish_status in ("draft", "failed"):
                    item.publish_status = "published"
                    item.publish_error = None
                synced += 1
            await db.commit()
        except Exception as exc:
            await db.rollback()
            errors.append({"account_id": acc_id, "error": str(exc)})

    return {"success": True, "synced": synced, "accounts": len(accounts), "errors": errors}


@router.post("")
async def create_item(
    data: ItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not data.account_id.strip():
        raise HTTPException(status_code=400, detail="account_id 不能为空")
    item_id = data.item_id.strip()
    if item_id:
        existing = (await db.execute(select(Item).where(Item.item_id == item_id))).scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=409, detail="商品ID已存在")
    else:
        existing = None

    is_draft = not item_id
    item = existing or Item(item_id=item_id or f"draft-{data.account_id}-{int(time.time())}", account_id=data.account_id)
    item.account_id = data.account_id
    item.title = data.title.strip()[:30]
    item.price = data.price or 0
    item.url = data.url.strip()
    item.description = (data.description or "").strip()
    item.image_urls = (data.image_urls or "[]").strip()
    item.status = "draft" if is_draft else (data.status.strip() or "draft")
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
    result = await db.execute(select(Item).where(Item.item_id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")
    if data.title is not None:
        item.title = data.title.strip()[:30]
    if data.price is not None:
        item.price = data.price
    if data.url is not None:
        item.url = data.url.strip()
    if data.description is not None:
        item.description = data.description.strip()
    if data.image_urls is not None:
        item.image_urls = data.image_urls.strip() or "[]"
    if data.status is not None:
        item.status = data.status.strip() or item.status
    if data.publish_status is not None:
        item.publish_status = data.publish_status.strip()
    if data.publish_error is not None:
        item.publish_error = data.publish_error.strip()
    await db.commit()
    await db.refresh(item)
    return {"success": True, "data": ItemResponse.model_validate(item)}


@router.delete("/{item_id}")
async def delete_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Item).where(Item.item_id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        return {"success": True}
    _cleanup_uploaded_images(item.image_urls or "[]")
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
    query = select(Item)
    total_query = select(func.count(Item.id))
    if account_id:
        query = query.where(Item.account_id == account_id)
        total_query = total_query.where(Item.account_id == account_id)
    total = (await db.execute(total_query)).scalar() or 0
    result = await db.execute(query.order_by(Item.id.desc()).offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()
    return {"success": True, "data": [ItemResponse.model_validate(item) for item in items], "total": total, "page": page, "page_size": page_size}
