"""
商品发布接口
"""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db, async_session_maker
from ..deps import get_current_user
from ..models.user import User
from ..models.item import Item
from ..services.publisher import publish_item

# Prevent background tasks from being garbage collected
_publish_tasks: set = set()

router = APIRouter(prefix="/publish", tags=["publish"])
logger = logging.getLogger(__name__)


class PublishRequest(BaseModel):
    item_id: str


@router.post("/item")
async def publish_single_item(
    data: PublishRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not data.item_id.strip():
        raise HTTPException(status_code=400, detail="item_id 不能为空")

    item_id = data.item_id.strip()
    owner_id = user.id

    stmt = select(Item).where(Item.item_id == item_id)
    item_result = await db.execute(stmt)
    item = item_result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="商品不存在")
    if item.publish_status == "publishing":
        raise HTTPException(status_code=400, detail="正在发布中，请稍候")

    item.publish_status = "publishing"
    item.publish_error = None
    await db.commit()

    task = asyncio.create_task(_background_publish(item_id, owner_id))
    _publish_tasks.add(task)
    task.add_done_callback(_publish_tasks.discard)

    logger.info(f"发布任务已提交: item={item_id}, user={owner_id}")
    return JSONResponse(
        status_code=202,
        content={"success": True, "message": "发布任务已提交，正在后台执行", "item_id": item_id},
    )


async def _background_publish(item_id: str, owner_id: int):
    async with async_session_maker() as db:
        try:
            result = await publish_item(db, item_id, owner_id)
            logger.info(f"后台发布完成: item={item_id}, success={result.get('success')}, msg={result.get('message')}")
        except Exception as e:
            logger.error(f"后台发布异常: item={item_id}, error={e}")
            try:
                stmt = select(Item).where(Item.item_id == item_id)
                r = await db.execute(stmt)
                item = r.scalar_one_or_none()
                if item:
                    item.publish_status = "failed"
                    item.publish_error = str(e)
                    await db.commit()
            except Exception:
                pass
