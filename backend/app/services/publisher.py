"""
闲鱼商品发布服务 - 使用 Playwright 浏览器自动化

通过 seller.goofish.com 卖家发布页面自动上架商品
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import Account
from ..models.item import Item
from ..models.publish_log import PublishLog
from ..utils.cookie_utils import is_token_error, trans_cookies

_playwright = None
_playwright_browser = None
_playwright_lock = asyncio.Lock()

async def _get_browser():
    global _playwright, _playwright_browser
    if _playwright_browser and _playwright_browser.is_connected():
        return _playwright_browser
    async with _playwright_lock:
        if _playwright_browser and _playwright_browser.is_connected():
            return _playwright_browser
        from playwright.async_api import async_playwright
        if _playwright is None:
            _playwright = await async_playwright().start()
        _playwright_browser = await _playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        return _playwright_browser

class XianyuPublisher:
    SELLER_HOME = "https://seller.goofish.com"
    PUBLISH_URL = "https://seller.goofish.com/?site=COMMONPRO#/seller-item/publish"

    def __init__(self, cookies_str: str):
        self.cookies_str = cookies_str
        self.browser = None
        self.context = None
        self.page = None

    async def __aenter__(self):
        browser = await _get_browser()
        cookies = trans_cookies(self.cookies_str)
        cookie_list = []
        for name, value in (cookies or {}).items():
            cookie_list.append({
                "name": name, "value": value,
                "domain": ".goofish.com", "path": "/",
            })
        self.context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        )
        await self.context.add_cookies(cookie_list)
        self.page = await self.context.new_page()
        logger.info("[发布] 访问卖家首页...")
        await self.page.goto(self.SELLER_HOME, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
        logger.info("[发布] 进入发布页面...")
        await self.page.goto(self.PUBLISH_URL, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)
        return self

    async def __aexit__(self, *args):
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
        except Exception:
            pass

    async def _check_login(self) -> bool:
        current_url = self.page.url
        if "login" in current_url.lower():
            return False
        try:
            body_text = await self.page.evaluate("() => document.body.innerText")
            if "立即登录" in body_text and "添加首图" not in body_text:
                return False
        except Exception:
            pass
        return True

    async def _wait_for_form(self, timeout: int = 30000) -> bool:
        try:
            await self.page.wait_for_selector("input, button, textarea, [class*='upload']", timeout=timeout)
            return True
        except Exception:
            return False

    async def _fill_text_field(self, hints: list[str], value: str) -> bool:
        for hint in hints:
            for tag in ["input", "textarea"]:
                try:
                    candidates = await self.page.query_selector_all(
                        f'{tag}[placeholder*="{hint}"], {tag}[aria-label*="{hint}"]'
                    )
                    for c in candidates:
                        try:
                            if await c.is_visible() and await c.is_enabled():
                                await c.click()
                                await asyncio.sleep(0.2)
                                await c.fill("")
                                await c.fill(value)
                                logger.info(f"✓ [{hint}]: {value[:30]}")
                                return True
                        except Exception:
                            continue
                except Exception:
                    continue
        return False

    async def _fill_title(self, title: str):
        if not await self._fill_text_field(["标题", "宝贝标题", "商品标题"], title):
            raise Exception("未找到标题输入框")

    async def _fill_price(self, price: float):
        if not await self._fill_text_field(["价格", "售价", "转让价"], str(price)):
            raise Exception("未找到价格输入框")

    async def _fill_stock(self, stock: int = 999):
        await self._fill_text_field(["库存", "数量"], str(stock))

    async def _fill_description(self, desc: str):
        await self._fill_text_field(["描述", "宝贝描述", "商品描述"], desc)

    async def _upload_images(self, urls: list[str]) -> int:
        import aiohttp, tempfile
        uploaded = 0
        for url in urls[:10]:
            try:
                upload_input = await self.page.query_selector('input[type="file"]')
                if not upload_input:
                    logger.warning("未找到文件上传input")
                    break
                if url.startswith("http://") or url.startswith("https://"):
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=30) as resp:
                            if resp.status != 200:
                                continue
                            image_data = await resp.read()
                elif url.startswith("/uploads/"):
                    local_path = Path("/app") / url.lstrip("/")
                    if local_path.exists():
                        image_data = local_path.read_bytes()
                    else:
                        continue
                else:
                    continue
                suffix = ".jpg"
                for ext in [".png", ".webp", ".gif", ".jpeg"]:
                    if url.lower().endswith(ext):
                        suffix = ext
                        break
                tmp = Path(f"/tmp/publish_{int(time.time())}_{uploaded}{suffix}")
                tmp.write_bytes(image_data)
                await upload_input.set_input_files(str(tmp))
                uploaded += 1
                await asyncio.sleep(1.5)
                logger.info(f"✓ 上传图片 {uploaded}/10")
                try:
                    tmp.unlink()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"上传图片失败: {e}")
                continue
        return uploaded

    async def _click_publish(self) -> bool:
        selectors = [
            'button:has-text("发布")', 'button:has-text("确认发布")',
            'button:has-text("提交")', 'span:has-text("发布")',
            '[class*="publish"] button', '[class*="submit"] button',
        ]
        for s in selectors:
            try:
                btn = await self.page.query_selector(s)
                if btn and await btn.is_visible() and await btn.is_enabled():
                    await btn.click()
                    logger.info(f"✓ 点击发布: {s}")
                    await asyncio.sleep(5)
                    return True
            except Exception:
                continue
        return False

    async def _get_result(self) -> dict:
        result = {"success": False, "item_id": None, "item_url": None, "screenshot": None}
        try:
            screenshot = await self.page.screenshot(full_page=True)
            result["screenshot"] = base64.b64encode(screenshot).decode()
        except Exception:
            pass
        await asyncio.sleep(3)
        try:
            body_text = await self.page.evaluate("() => document.body.innerText")
            if "发布成功" in body_text or "上架成功" in body_text:
                result["success"] = True
                result["message"] = "发布成功"
        except Exception:
            pass
        current_url = self.page.url
        if "item_id=" in current_url or "/item/" in current_url:
            result["success"] = True
            result["item_url"] = current_url
        return result

    async def publish(self, item_data: dict) -> dict:
        result = {"success": False, "message": "", "item_id": None, "item_url": None, "screenshot": None}
        logger.info(f"[发布] {item_data.get('title', '')[:30]}")
        if not await self._check_login():
            result["message"] = "Cookie已失效，请重新登录"
            return result
        if not await self._wait_for_form():
            result["message"] = "发布页面加载超时"
            return result
        title = str(item_data.get("title", "好物推荐")).strip()[:30]
        price = float(item_data.get("price", 0) or 0.1)
        stock = int(item_data.get("stock", 999) or 999)
        desc = str(item_data.get("description", "")).strip()[:500]
        images = item_data.get("images", [])
        try:
            await self._fill_title(title)
            await self._fill_price(price)
            await self._fill_stock(stock)
            if desc:
                await self._fill_description(desc)
            if images:
                uploaded = await self._upload_images(images)
                logger.info(f"图片: {uploaded} 张")
            await asyncio.sleep(2)
            clicked = await self._click_publish()
            if not clicked:
                result["message"] = "未找到发布按钮"
                try:
                    screenshot = await self.page.screenshot(full_page=True)
                    result["screenshot"] = base64.b64encode(screenshot).decode()
                except Exception:
                    pass
                return result
            pub_result = await self._get_result()
            result.update(pub_result)
        except Exception as e:
            logger.error(f"发布异常: {e}")
            result["message"] = str(e)
            try:
                screenshot = await self.page.screenshot(full_page=True)
                result["screenshot"] = base64.b64encode(screenshot).decode()
            except Exception:
                pass
        logger.info(f"[发布] 结果: {result.get('success')}")
        return result

async def publish_item(
    session: AsyncSession,
    item_id: str,
    user_id: int,
) -> Dict[str, Any]:
    stmt = select(Item).where(Item.item_id == item_id)
    item_result = await session.execute(stmt)
    item = item_result.scalar_one_or_none()
    if not item:
        return {"success": False, "message": "商品不存在"}
    account_stmt = (
        select(Account)
        .where(Account.account_id == item.account_id, Account.owner_id == user_id)
        .order_by(desc(Account.id))
        .limit(1)
    )
    account_result = await session.execute(account_stmt)
    account = account_result.scalars().first()
    if not account or not account.cookie:
        return {"success": False, "message": "账号不存在或Cookie为空"}
    log = PublishLog(
        item_id=item_id,
        account_id=item.account_id,
        title=item.title,
        status="publishing",
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)

    item.publish_status = "publishing"
    await session.commit()

    images = []
    if item.image_urls:
        try:
            images = json.loads(item.image_urls)
        except Exception:
            images = []

    item_data = {
        "title": item.title or "好物推荐",
        "description": item.description or "",
        "price": item.price or 0.1,
        "stock": 999,
        "images": images,
    }

    cookies_str = account.cookie
    try:
        async with XianyuPublisher(cookies_str) as publisher:
            result = await publisher.publish(item_data)

        log.status = "published" if result["success"] else "failed"
        log.error_message = result.get("message")
        log.result_item_id = result.get("item_id")
        log.result_url = result.get("item_url")

        if result["success"]:
            item.publish_status = "published"
            item.publish_error = None
            if result.get("item_url"):
                item.url = result["item_url"]
        else:
            item.publish_status = "failed"
            item.publish_error = result.get("message")

        await session.commit()
        return result

    except Exception as e:
        logger.error(f"发布商品 {item_id} 异常: {e}")
        log.status = "failed"
        log.error_message = str(e)
        item.publish_status = "failed"
        item.publish_error = str(e)
        await session.commit()
        return {"success": False, "message": str(e)}