import asyncio
import os
from datetime import datetime, date
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
import aiohttp

scheduler = AsyncIOScheduler()

DATABASE_URL = os.getenv("DATABASE_URL", "mysql+aiomysql://xianyu:xianyu123@mysql:3306/xianyu_lite?charset=utf8mb4")
engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def check_websocket_health():
    """每分钟检查websocket连接状态, 断开则发送重启信号"""
    try:
        ws_url = "http://websocket:8001"
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ws_url}/status", timeout=5) as resp:
                data = await resp.json()
                if data.get("success"):
                    active_list = data.get("active", [])
                    logger.info(f"[Scheduler] WS active connections: {active_list}")
                    
                    # 检查数据库中有多少活跃账号
                    async with async_session_maker() as db:
                        result = await db.execute(text("SELECT account_id, cookie FROM accounts WHERE status = 'active'"))
                        accounts = result.all()
                    
                    for acc_id, cookie in accounts:
                        if str(acc_id) not in active_list:
                            logger.warning(f"[Scheduler] Account {acc_id} not connected, attempting restart...")
                            try:
                                async with aiohttp.ClientSession() as s2:
                                    await s2.post(f"{ws_url}/start/{acc_id}", params={"cookies": str(cookie)})
                                logger.info(f"[Scheduler] Restart signal sent for {acc_id}")
                            except Exception as e:
                                logger.error(f"[Scheduler] Restart failed for {acc_id}: {e}")
                            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"[Scheduler] WS health check error: {e}")


async def recover_error_accounts():
    """????? error ???????? cookie ?????????"""
    try:
        async with async_session_maker() as db:
            result = await db.execute(text(
                "SELECT account_id FROM accounts WHERE status = 'error' AND cookie IS NOT NULL AND cookie != '' LIMIT 10"
            ))
            ids = [row[0] for row in result.fetchall()]
        for aid in ids:
            try:
                async with async_session_maker() as db:
                    await db.execute(
                        text("UPDATE accounts SET status = 'active' WHERE account_id = :aid"),
                        {"aid": aid},
                    )
                    await db.commit()
                logger.info(f"[Scheduler] Recovered error account: {aid}")
            except Exception as e:
                logger.error(f"[Scheduler] Recovery failed for {aid}: {e}")
    except Exception as e:
        logger.error(f"[Scheduler] Account recovery error: {e}")

async def auto_deliver_orders():
    """扫描待发货订单并调用后端发货执行器。"""
    try:
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        async with async_session_maker() as db:
            result = await db.execute(text("""
                SELECT o.order_id FROM orders o
                LEFT JOIN delivery_logs l ON l.order_id = o.order_id
                WHERE o.status IN ('paid','pending')
                  AND (
                    l.id IS NULL
                    OR (l.status = 'failed' AND COALESCE(l.attempts, 0) < 3)
                    OR (
                      l.status = 'skipped'
                      AND EXISTS (
                        SELECT 1 FROM delivery_configs c
                        WHERE c.account_id = o.account_id
                          AND c.item_id = o.item_id
                          AND c.enabled = 1
                      )
                    )
                  )
                ORDER BY o.id ASC LIMIT 20
            """))
            order_ids = [row[0] for row in result.fetchall()]
        if not order_ids:
            return
        logger.info(f"[Scheduler] Auto deliver pending orders: {order_ids}")
        async with aiohttp.ClientSession() as session:
            for order_id in order_ids:
                try:
                    async with session.post(f"{backend_url}/internal/delivery/orders/{order_id}/deliver", timeout=30) as resp:
                        logger.info(f"[Scheduler] deliver {order_id}: {resp.status} {await resp.text()}")
                except Exception as e:
                    logger.error(f"[Scheduler] deliver {order_id} failed: {e}")
    except Exception as e:
        logger.error(f"[Scheduler] auto deliver error: {e}")

async def refresh_cookies():
    """通过调用 MTOP 接口触发 Set-Cookie 刷新，更新存储的 Cookie。"""
    import hashlib
    import json as _json
    from http.cookies import SimpleCookie

    try:
        async with async_session_maker() as db:
            result = await db.execute(text("SELECT account_id, cookie FROM accounts WHERE status = 'active' AND cookie IS NOT NULL AND cookie != ''"))
            accounts = result.all()
        updated = 0
        async with aiohttp.ClientSession() as session:
            for acc in accounts:
                cookie_id, cookie = acc
                if not cookie:
                    continue
                try:
                    # parse cookies
                    cookies_dict = {}
                    for c in cookie.split(";"):
                        c = c.strip()
                        if "=" not in c:
                            continue
                        k, v = c.split("=", 1)
                        k = k.strip()
                        if k:
                            cookies_dict[k] = v.strip()

                    token = cookies_dict.get("_m_h5_tk", "").split("_")[0] if cookies_dict.get("_m_h5_tk") else ""
                    t = str(int(time.time()) * 1000)
                    data_val = _json.dumps({}, separators=(",", ":"), ensure_ascii=False)
                    sign = hashlib.md5(f"{token}&{t}&34839810&{data_val}".encode("utf-8")).hexdigest()

                    params = {
                        "jsv": "2.7.2", "appKey": "34839810", "t": t, "sign": sign,
                        "v": "1.0", "type": "originaljson", "accountSite": "xianyu",
                        "dataType": "json", "timeout": "20000",
                        "api": "mtop.taobao.idle.trade.merchant.sold.get",
                        "sessionOption": "AutoLoginOnly",
                    }
                    headers = {
                        "accept": "application/json",
                        "content-type": "application/x-www-form-urlencoded",
                        "cookie": cookie,
                        "referer": "https://seller.goofish.com/",
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                    }
                    async with session.post(
                        "https://h5api.m.goofish.com/h5/mtop.taobao.idle.trade.merchant.sold.get/1.0/",
                        params=params, data={"data": data_val}, headers=headers,
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        if resp.status == 200:
                            set_cookies = resp.headers.getall("set-cookie", [])
                            new_cookies = dict(cookies_dict)
                            changed = False
                            for hdr in set_cookies:
                                parsed = SimpleCookie()
                                try:
                                    parsed.load(hdr)
                                except Exception:
                                    continue
                                for name, morsel in parsed.items():
                                    val = morsel.value
                                    if name and new_cookies.get(name) != val:
                                        new_cookies[name] = val
                                        changed = True
                            if changed:
                                merged = "; ".join(f"{k}={v}" for k, v in new_cookies.items())
                                async with async_session_maker() as db2:
                                    await db2.execute(
                                        text("UPDATE accounts SET cookie = :cookie, last_active_at = NOW() WHERE account_id = :aid"),
                                        {"cookie": merged, "aid": cookie_id},
                                    )
                                    await db2.commit()
                                updated += 1
                                logger.info(f"[Scheduler] Cookie refreshed for {cookie_id}")
                            else:
                                logger.debug(f"[Scheduler] Cookie unchanged for {cookie_id}")
                except Exception as e:
                    logger.error(f"[Scheduler] Cookie refresh error for {cookie_id}: {e}")
                await asyncio.sleep(1)
        logger.info(f"[Scheduler] Cookie refresh done: {updated}/{len(accounts)} updated")
    except Exception as e:
        logger.error(f"[Scheduler] Cookie refresh error: {e}")

async def pull_orders():
    try:
        backend_url = os.getenv("BACKEND_URL", "http://backend:8000")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{backend_url}/internal/orders/sync",
                params={"query_code": "NOT_SHIP", "max_pages": 3},
                timeout=90,
            ) as resp:
                logger.info(f"[Scheduler] pull orders: {resp.status} {await resp.text()}")
    except Exception as e:
        logger.error(f"[Scheduler] Pull orders error: {e}")

async def daily_statistics():
    from sqlalchemy import text
    try:
        async with async_session_maker() as db:
            today = date.today()
            await db.execute(text("""
                INSERT INTO daily_stats (account_id, stat_date, orders_count, orders_amount)
                SELECT account_id, CURDATE(), COUNT(*), COALESCE(SUM(price), 0)
                FROM orders WHERE DATE(created_at) = CURDATE()
                GROUP BY account_id
                ON DUPLICATE KEY UPDATE orders_count = VALUES(orders_count), orders_amount = VALUES(orders_amount)
            """))
            await db.commit()
            logger.info(f"[Scheduler] Daily stats generated for {today}")
    except Exception as e:
        logger.error(f"[Scheduler] Daily stats error: {e}")

def setup_scheduler():
    scheduler.add_job(check_websocket_health, "interval", minutes=1, id="ws_health")
    scheduler.add_job(recover_error_accounts, "interval", minutes=1, id="recover_accounts")
    scheduler.add_job(auto_deliver_orders, "interval", minutes=1, id="auto_deliver")
    scheduler.add_job(refresh_cookies, "interval", hours=2, id="refresh_cookies")
    scheduler.add_job(pull_orders, "interval", minutes=30, id="pull_orders")
    scheduler.add_job(daily_statistics, "cron", hour=0, minute=5, id="daily_statistics")
    scheduler.start()
    logger.info("Scheduler started")

if __name__ == "__main__":
    setup_scheduler()
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
