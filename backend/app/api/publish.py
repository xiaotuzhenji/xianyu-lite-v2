"""
商品发布接口
"""
import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import async_session_maker, get_db
from ..deps import get_current_user
from ..models.account import Account
from ..models.item import Item
from ..models.publish_log import PublishLog
from ..models.user import User
from ..services.publisher import offline_item, publish_item

_publish_tasks: set = set()
STALE_PUBLISH_TIMEOUT = timedelta(minutes=10)

router = APIRouter(prefix="/publish", tags=["publish"])
logger = logging.getLogger(__name__)


class PublishRequest(BaseModel):
    item_id: str


class OfflineRequest(BaseModel):
    item_id: str


async def _get_owned_item(db: AsyncSession, item_id: str, user: User):
    stmt = (
        select(Item)
        .join(Account, Item.account_id == Account.account_id)
        .where(Item.item_id == item_id, Account.owner_id == user.id)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


@router.post("/item")
async def publish_single_item(
    data: PublishRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item_id = data.item_id.strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id 不能为空")

    item = await _get_owned_item(db, item_id, user)
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")

    if item.publish_status == "publishing":
        log_stmt = (
            select(PublishLog)
            .where(PublishLog.item_id == item_id)
            .order_by(PublishLog.id.desc())
            .limit(1)
        )
        log_result = await db.execute(log_stmt)
        latest_log = log_result.scalars().first()
        is_stale = (
            latest_log is None
            or latest_log.status != "publishing"
            or latest_log.updated_at is None
            or datetime.now() - latest_log.updated_at >= STALE_PUBLISH_TIMEOUT
        )
        if not is_stale:
            raise HTTPException(status_code=400, detail="正在发布中，请稍候")

        item.publish_status = "failed"
        item.publish_error = "上一条发布任务已中断，已自动释放，可重新发布"
        if latest_log and latest_log.status == "publishing":
            latest_log.status = "failed"
            latest_log.error_message = "发布任务中断，系统已自动释放"
        await db.commit()

    item.publish_status = "publishing"
    item.publish_error = None
    await db.commit()

    owner_id = user.id
    task = asyncio.create_task(_background_publish(item_id, owner_id))
    _publish_tasks.add(task)
    task.add_done_callback(_publish_tasks.discard)

    logger.info(f"发布任务已提交 item={item_id}, user={owner_id}")
    return JSONResponse(
        status_code=202,
        content={
            "success": True,
            "message": "发布任务已提交，正在后台执行",
            "item_id": item_id,
        },
    )


@router.post("/item/offline")
async def offline_single_item(
    data: OfflineRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item_id = data.item_id.strip()
    if not item_id:
        raise HTTPException(status_code=400, detail="item_id 不能为空")

    item = await _get_owned_item(db, item_id, user)
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")
    if item.item_id.startswith("draft-"):
        raise HTTPException(status_code=400, detail="草稿商品不能下架")
    if item.status == "offline":
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "商品已下架", "item_id": item_id},
        )
    if item.publish_status == "publishing":
        raise HTTPException(status_code=400, detail="商品正在发布中，暂不能下架")

    result = await offline_item(db, item_id, user.id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "下架失败"))
    return JSONResponse(status_code=200, content=result)


async def _background_publish(item_id: str, owner_id: int):
    async with async_session_maker() as db:
        try:
            result = await publish_item(db, item_id, owner_id)
            logger.info(
                f"后台发布完成: item={item_id}, success={result.get('success')}, msg={result.get('message')}"
            )
        except Exception as exc:
            logger.error(f"后台发布异常: item={item_id}, error={exc}")
            try:
                stmt = select(Item).where(Item.item_id == item_id)
                result = await db.execute(stmt)
                item = result.scalar_one_or_none()
                if item:
                    item.publish_status = "failed"
                    item.publish_error = str(exc)
                    await db.commit()
            except Exception:
                pass
