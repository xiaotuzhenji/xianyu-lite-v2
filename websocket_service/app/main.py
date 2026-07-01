import asyncio
import hashlib
import json
import os
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI
from loguru import logger

from .message_handler import MessageHandler
from .xianyu_async import XianyuWS

active_connections: dict = {}


def _db_url():
    mysql_host = os.getenv("MYSQL_HOST", "mysql")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_user = os.getenv("MYSQL_USER", "xianyu")
    mysql_password = os.getenv("MYSQL_PASSWORD", "xianyu123")
    mysql_database = os.getenv("MYSQL_DATABASE", "xianyu_lite")
    return f"mysql+aiomysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}?charset=utf8mb4"


async def _query_one(sql: str, params: dict):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(_db_url(), echo=False)
    try:
        async with async_sessionmaker(engine)() as session:
            result = await session.execute(text(sql), params)
            return result.mappings().first()
    finally:
        await engine.dispose()


async def _execute_sql(sql: str, params: dict):
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(_db_url(), echo=False)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(text(sql), params)
            await session.commit()
    finally:
        await engine.dispose()


def _build_handler(cookie_id: str) -> MessageHandler:
    handler = MessageHandler(cookie_id)
    handler.set_chat_handler(on_chat_message)
    handler.set_order_handler(on_order_message)
    handler.set_confirm_receipt_handler(on_confirm_receipt)
    return handler


def _fallback_order_id(data: dict) -> str:
    raw_order_id = str(data.get("order_id") or data.get("orderId") or data.get("trade_id") or data.get("tradeId") or "").strip()
    if raw_order_id:
        return raw_order_id[:64]
    source = str(data.get("message_id") or data.get("messageId") or data.get("id") or "").strip()
    if not source:
        source = json.dumps(data.get("raw") or data, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()
    return f"ws-{digest}"


def _safe_float(value) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0


def _build_order_payload(cookie_id: str, data: dict) -> dict:
    return {
        "account_id": cookie_id,
        "order_id": _fallback_order_id(data),
        "item_id": str(data.get("item_id") or data.get("itemId") or ""),
        "buyer_id": str(data.get("buyer_id") or data.get("buyerId") or data.get("sender_id") or data.get("from_user_id") or ""),
        "buyer_name": str(data.get("buyer_name") or data.get("buyerNick") or data.get("nick") or ""),
        "price": _safe_float(data.get("price") or data.get("amount") or 0),
        "status": str(data.get("status") or "paid"),
        "auto_deliver": True,
    }


async def _send_reply(cookie_id: str, data: dict, content: str):
    conn = active_connections.get(cookie_id)
    if not conn:
        logger.warning(f"[{cookie_id}] cannot send reply: account not connected")
        return False
    buyer_id = str(data.get("buyer_id") or data.get("sender_id") or data.get("from_user_id") or data.get("to_user_id") or "")
    chat_id = str(data.get("chat_id") or data.get("conversation_id") or buyer_id)
    item_id = str(data.get("item_id") or data.get("itemId") or "")
    if not buyer_id or not content:
        logger.warning(f"[{cookie_id}] cannot send reply: missing buyer_id/content")
        return False
    return await conn["instance"].send_message(chat_id, buyer_id, content, "text", item_id=item_id)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("WebSocket service starting...")
    try:
        from sqlalchemy import select, text
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        engine = create_async_engine(_db_url(), echo=False)
        async with async_sessionmaker(engine)() as session:
            result = await session.execute(select(text("account_id, cookie FROM accounts WHERE status = 'active'")))
            rows = result.fetchall()
            for row in rows:
                account_id, cookie = row
                if cookie:
                    logger.info(f"[startup] Auto-connecting account {account_id}")
                    instance = XianyuWS(str(account_id), str(cookie))
                    instance.message_handler = _build_handler(str(account_id)).handle
                    task = asyncio.create_task(instance.run())
                    active_connections[str(account_id)] = {"instance": instance, "task": task}
                    await asyncio.sleep(0.5)
        await engine.dispose()
    except Exception as exc:
        logger.error(f"[startup] Auto-load accounts failed: {exc}")
    yield
    for conn in active_connections.values():
        await conn["instance"].stop()
    active_connections.clear()


app = FastAPI(title="Xianyu Lite WS", lifespan=lifespan)


async def on_chat_message(cookie_id: str, data: dict):
    logger.info(f"[{cookie_id}] Chat message: {json.dumps(data, ensure_ascii=False)[:200]}")
    content = str(data.get("content") or data.get("text") or data.get("message") or "")
    item_id = str(data.get("item_id") or data.get("itemId") or "")
    if not content:
        return

    row = await _query_one(
        """
        SELECT reply_content FROM keyword_rules
        WHERE account_id = :account_id AND enabled = 1
          AND (:item_id = '' OR item_id IS NULL OR item_id = :item_id)
          AND :content LIKE CONCAT('%', keyword, '%')
        ORDER BY CASE WHEN item_id = :item_id THEN 0 ELSE 1 END, id DESC LIMIT 1
        """,
        {"account_id": cookie_id, "item_id": item_id, "content": content},
    )
    if row and row.get("reply_content"):
        await _send_reply(cookie_id, data, row["reply_content"])
        return

    row = await _query_one(
        """
        SELECT reply_content FROM default_replies
        WHERE account_id = :account_id AND enabled = 1
          AND (:item_id = '' OR item_id IS NULL OR item_id = :item_id)
        ORDER BY CASE WHEN item_id = :item_id THEN 0 ELSE 1 END, id DESC LIMIT 1
        """,
        {"account_id": cookie_id, "item_id": item_id},
    )
    if row and row.get("reply_content"):
        await _send_reply(cookie_id, data, row["reply_content"])


async def on_order_message(cookie_id: str, data: dict):
    logger.info(f"[{cookie_id}] Order message: {json.dumps(data, ensure_ascii=False)[:300]}")
    payload = _build_order_payload(cookie_id, data)
    if payload["order_id"].startswith("ws-"):
        logger.info(f"[{cookie_id}] Order message missing platform order_id, use fallback {payload['order_id']}")
    backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{backend_url}/internal/orders/event", json=payload, timeout=30) as resp:
                logger.info(f"[{cookie_id}] order event sync: {resp.status} {await resp.text()}")
    except Exception as exc:
        logger.error(f"[{cookie_id}] order event sync failed: {exc}")


async def on_confirm_receipt(cookie_id: str, data: dict):
    logger.info(f"[{cookie_id}] Confirm receipt: {json.dumps(data, ensure_ascii=False)[:200]}")
    item_id = str(data.get("item_id") or data.get("itemId") or "")
    buyer_id = str(data.get("buyer_id") or data.get("sender_id") or data.get("from_user_id") or "")
    order_id = str(data.get("order_id") or data.get("orderId") or data.get("trade_id") or data.get("tradeId") or "")
    row = await _query_one(
        """
        SELECT message_content, reply_once FROM confirm_receipt_configs
        WHERE account_id = :account_id AND enabled = 1
          AND (:item_id = '' OR item_id IS NULL OR item_id = :item_id)
        ORDER BY CASE WHEN item_id = :item_id THEN 0 ELSE 1 END, id DESC LIMIT 1
        """,
        {"account_id": cookie_id, "item_id": item_id},
    )
    if row and row.get("message_content"):
        if row.get("reply_once") and order_id:
            sent = await _query_one(
                "SELECT confirm_receipt_sent FROM orders WHERE order_id = :order_id LIMIT 1",
                {"order_id": order_id},
            )
            if sent and sent.get("confirm_receipt_sent"):
                logger.info(f"[{cookie_id}] confirm receipt already sent for order {order_id}")
                return
        ok = await _send_reply(cookie_id, data, row["message_content"])
        if ok and order_id:
            await _execute_sql(
                """
                INSERT INTO orders (order_id, account_id, item_id, buyer_id, status, confirm_receipt_sent)
                VALUES (:order_id, :account_id, :item_id, :buyer_id, 'received', 1)
                ON DUPLICATE KEY UPDATE
                  item_id = COALESCE(NULLIF(VALUES(item_id), ''), item_id),
                  buyer_id = COALESCE(NULLIF(VALUES(buyer_id), ''), buyer_id),
                  status = 'received',
                  confirm_receipt_sent = 1
                """,
                {"order_id": order_id, "account_id": cookie_id, "item_id": item_id, "buyer_id": buyer_id},
            )


@app.post("/start/{cookie_id}")
async def start_account(cookie_id: str, cookies: str = ""):
    if not cookies:
        return {"success": False, "error": "cookie required"}
    if cookie_id in active_connections:
        await active_connections[cookie_id]["instance"].stop()
    instance = XianyuWS(cookie_id, cookies)
    instance.message_handler = _build_handler(cookie_id).handle
    task = asyncio.create_task(instance.run())
    active_connections[cookie_id] = {"instance": instance, "task": task}
    return {"success": True}


@app.post("/send/{cookie_id}")
async def send_message(cookie_id: str, payload: dict):
    if cookie_id not in active_connections:
        return {"success": False, "error": "account not connected"}
    instance = active_connections[cookie_id]["instance"]
    if not instance.is_connected():
        return {"success": False, "error": "account websocket not connected"}
    buyer_id = payload.get("buyer_id") or payload.get("to_user_id")
    chat_id = payload.get("chat_id") or buyer_id
    content = payload.get("content") or ""
    msg_type = payload.get("msg_type") or "text"
    item_id = payload.get("item_id") or payload.get("itemId") or ""
    if not buyer_id or not content:
        return {"success": False, "error": "buyer_id and content required"}
    ok = await instance.send_message(chat_id, buyer_id, content, msg_type, item_id=item_id)
    return {"success": bool(ok), "error": "" if ok else instance.last_send_error}


@app.post("/stop/{cookie_id}")
async def stop_account(cookie_id: str):
    if cookie_id in active_connections:
        await active_connections[cookie_id]["instance"].stop()
        active_connections[cookie_id]["task"].cancel()
        del active_connections[cookie_id]
    return {"success": True}


@app.get("/status")
async def status():
    active = [cookie_id for cookie_id, conn in active_connections.items() if conn["instance"].is_connected()]
    configured = list(active_connections.keys())
    return {"success": True, "active": active, "configured": configured}


@app.get("/health")
async def health():
    return {"success": True}
