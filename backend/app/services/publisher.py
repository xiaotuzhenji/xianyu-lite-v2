"""
闲鱼商品发布服务 - 使用 Playwright 浏览器自动化

通过 seller.goofish.com 卖家发布页面自动上架商品
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp
from loguru import logger
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.account import Account
from ..models.delivery_config import DeliveryConfig
from ..models.item import Item
from ..models.publish_log import PublishLog
from ..utils.cookie_utils import is_token_error, merge_set_cookies, trans_cookies
from ..utils.crypto import generate_sign

_playwright = None
_playwright_browser = None
_playwright_lock = asyncio.Lock()
MAX_PUBLISH_IMAGES = 8


def _parse_image_urls(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def _image_count(value: Optional[str]) -> int:
    return len(_parse_image_urls(value))


def _merge_item_for_publish(target: Item, source: Item) -> None:
    if source.title and not target.title:
        target.title = source.title
    if source.description and not target.description:
        target.description = source.description
    if _image_count(source.image_urls) > _image_count(target.image_urls):
        target.image_urls = source.image_urls
    if source.price and not target.price:
        target.price = source.price
    if source.url:
        target.url = source.url
    target.publish_status = "published"
    target.publish_error = None


def _copy_item_for_republish(target: Item, source: Item, result_item_id: str, result_url: Optional[str]) -> None:
    target.item_id = result_item_id
    target.account_id = source.account_id
    target.title = source.title
    target.description = source.description
    target.image_urls = source.image_urls
    target.price = source.price
    target.status = "online"
    target.publish_status = "published"
    target.publish_error = None
    target.url = result_url or f"https://www.goofish.com/item/{result_item_id}"


def _extract_item_id_from_url(url: str) -> Optional[str]:
    if not url:
        return None
    match = (
        re.search(r"[?&](?:id|item_id)=(\d+)", url)
        or re.search(r"/item/(\d+)", url)
    )
    return match.group(1) if match else None


def _normalize_publish_result(source_item_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    if not str(result.get("item_id") or "").strip():
        parsed_item_id = _extract_item_id_from_url(str(result.get("item_url") or ""))
        if parsed_item_id:
            result["item_id"] = parsed_item_id
    if (
        result.get("success")
        and not str(result.get("item_id") or "").strip()
    ):
        result["success"] = False
        result["message"] = result.get("message") or "发布结果未返回商品ID，请同步商品确认后再重试"
    return result


async def _move_delivery_config(session: AsyncSession, account_id: str, old_item_id: str, new_item_id: str) -> None:
    if not old_item_id or not new_item_id or old_item_id == new_item_id:
        return
    old_result = await session.execute(
        select(DeliveryConfig).where(
            DeliveryConfig.account_id == account_id,
            DeliveryConfig.item_id == old_item_id,
        )
    )
    old_config = old_result.scalar_one_or_none()
    if not old_config:
        return
    new_result = await session.execute(
        select(DeliveryConfig).where(
            DeliveryConfig.account_id == account_id,
            DeliveryConfig.item_id == new_item_id,
        )
    )
    if new_result.scalar_one_or_none():
        await session.delete(old_config)
    else:
        old_config.item_id = new_item_id


def _guess_image_suffix(url: str, content_type: str) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }
    return mapping.get((content_type or "").lower(), ".jpg")


async def _download_remote_publish_image(url: str) -> Path:
    timeout = aiohttp.ClientTimeout(total=60)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.goofish.com/",
    }
    last_error: Optional[Exception] = None
    for extra_headers in ({}, headers):
        try:
            async with aiohttp.ClientSession(timeout=timeout, headers=extra_headers) as session:
                async with session.get(url, allow_redirects=True) as resp:
                    if resp.status != 200:
                        raise ValueError(f"status={resp.status}")
                    image_data = await resp.read()
                    if not image_data:
                        raise ValueError("empty body")
                    content_type = (resp.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
                    suffix = _guess_image_suffix(str(resp.url), content_type)
                    tmp = Path(f"/tmp/publish_{int(time.time() * 1000)}_{abs(hash(url)) % 100000}{suffix}")
                    tmp.write_bytes(image_data)
                    return tmp
        except Exception as exc:
            last_error = exc
    raise ValueError(f"远程图片下载失败: {url}, error={last_error}")


async def _offline_item(account_id: str, cookies_str: str, item_id: str) -> bool:
    if not account_id or not cookies_str or not item_id:
        return False
    cookies = trans_cookies(cookies_str)
    timestamp = str(int(time.time() * 1000))
    data_val = json.dumps({"itemIds": [item_id]}, separators=(",", ":"))
    token = cookies.get("_m_h5_tk", "").split("_")[0] if cookies.get("_m_h5_tk") else ""
    sign = generate_sign(timestamp, token, data_val)
    params = {
        "jsv": "2.7.2",
        "appKey": "34839810",
        "t": timestamp,
        "sign": sign,
        "v": "1.0",
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "needLoginPC": "true",
        "showErrorToast": "true",
        "api": "mtop.alibaba.idle.seller.pc.item.batch.offline",
        "sessionOption": "AutoLoginOnly",
        "spm_cnt": "a21107h.42826273.0.0",
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/x-www-form-urlencoded",
        "referer": "https://seller.goofish.com/?site=COMMONPRO",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/146.0.0.0 Safari/537.36",
        "cookie": cookies_str.replace("\n", "").replace("\r", ""),
    }
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            "https://h5api.m.goofish.com/h5/mtop.alibaba.idle.seller.pc.item.batch.offline/1.0/",
            params=params,
            data={"data": data_val},
            headers=headers,
        ) as response:
            res_json = await response.json(content_type=None)
            changed, _ = merge_set_cookies(cookies_str, response.headers.getall("set-cookie", []))
            if changed:
                logger.info(f"[下架] Cookie 已刷新: {account_id}")
            ret = (res_json.get("ret") or [""])[0]
            if "SUCCESS" not in ret:
                logger.warning(f"[下架] 接口失败: item={item_id}, ret={ret}")
                return False
            inner = ((res_json.get("data") or {}).get("data") or {})
            results = inner.get("itemProcessResultList") or []
            return any(str(item.get("itemId") or "") == item_id and bool(item.get("success")) for item in results) or bool(inner.get("sucCount"))


async def offline_item(session: AsyncSession, item_id: str, user_id: int) -> Dict[str, Any]:
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

    offline_ok = await _offline_item(item.account_id, account.cookie, item.item_id)
    if not offline_ok:
        return {"success": False, "message": "下架失败"}

    item.status = "offline"
    item.publish_status = "draft" if item.publish_status == "published" else item.publish_status
    item.publish_error = None
    await session.commit()
    return {"success": True, "message": "下架成功", "item_id": item_id}

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
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )
        return _playwright_browser

class XianyuPublisher:
    SELLER_HOME = "https://seller.goofish.com"
    GOOFISH_HOME = "https://www.goofish.com"
    LOGIN_URL = "https://login.taobao.com/member/login.jhtml"
    PUBLISH_URL = "https://www.goofish.com/publish?spm=a21ybx.item.sidebar.1.297e3da6aDZAmV"

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
            for domain in [".goofish.com", ".taobao.com", ".alipay.com"]:
                cookie_list.append({
                    "name": name, "value": value,
                    "domain": domain, "path": "/",
                })
        self.context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        )
        await self.context.add_cookies(cookie_list)
        self.page = await self.context.new_page()
        # Anti-detection: load stealth.js
        stealth_file = str(Path(__file__).parent / 'stealth.js')
        if Path(stealth_file).exists():
            await self.page.add_init_script(path=stealth_file)
        logger.info("[发布] 访问闲鱼首页建立会话...")
        await self.page.goto(self.GOOFISH_HOME, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        logger.info("[发布] 访问登录页同步登录态...")
        await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(2)
        logger.info("[发布] 进入发布页面...")
        await self.page.goto(self.PUBLISH_URL, wait_until="load", timeout=90000)
        await asyncio.sleep(8)
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
        if "login" in current_url.lower() or "auth" in current_url.lower() or "no-permission" in current_url.lower():
            return False
        try:
            body_text = await self.page.evaluate("() => document.body.innerText")
            if any(w in body_text for w in ["立即登录", "非法访问", "当前账号没有访问权限", "登录后可以"]):
                return False
        except Exception:
            pass
        return True

    async def _wait_for_form(self, timeout: int = 60000) -> bool:
        try:
            await self.page.wait_for_selector(
                "input, button, textarea, [contenteditable='true'], [class*='upload']",
                timeout=timeout,
            )
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
        if await self._fill_text_field(["标题", "宝贝标题", "商品标题"], title):
            return
        logger.info("未找到独立标题输入框，改为写入宝贝描述编辑器")

    async def _fill_contenteditable(self, selectors: list[str], value: str) -> bool:
        for selector in selectors:
            try:
                candidates = await self.page.query_selector_all(selector)
            except Exception:
                continue
            for candidate in candidates:
                try:
                    if not await candidate.is_visible():
                        continue
                    await candidate.click()
                    await asyncio.sleep(0.2)
                    await candidate.evaluate(
                        """(el, text) => {
                            el.focus();
                            el.innerText = text;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new Event('blur', { bubbles: true }));
                        }""",
                        value,
                    )
                    logger.info(f"✓ [富文本]: {value[:30]}")
                    return True
                except Exception:
                    continue
        return False

    async def _fill_price(self, price: float):
        if await self._fill_text_field(["价格", "售价", "转让价"], str(price)):
            return
        try:
            inputs = await self.page.query_selector_all('input[type="text"][placeholder="0.00"]')
            for price_input in inputs:
                try:
                    if not await price_input.is_visible() or not await price_input.is_enabled():
                        continue
                    await price_input.click()
                    await asyncio.sleep(0.2)
                    await price_input.fill("")
                    await price_input.fill(str(price))
                    logger.info(f"✓ [价格]: {price}")
                    return
                except Exception:
                    continue
        except Exception:
            pass
        raise Exception("未找到价格输入框")

    async def _fill_stock(self, stock: int = 999):
        await self._fill_text_field(["库存", "数量"], str(stock))

    async def _fill_description(self, title: str, desc: str):
        content = title if not desc else f"{title}\n\n{desc}" if title else desc
        if not content:
            return
        if await self._fill_text_field(["描述", "宝贝描述", "商品描述"], content):
            return
        if await self._fill_contenteditable(
            [
                'div[data-placeholder*="描述"]',
                'div[contenteditable="true"]',
                '[class*="editor"][contenteditable="true"]',
                '[role="textbox"][contenteditable="true"]',
            ],
            content,
        ):
            return
        raise Exception("未找到描述输入框")

    async def _upload_images(self, urls: list[str]) -> int:
        upload_input = await self.page.query_selector('input[type="file"]')
        if not upload_input:
            logger.warning("未找到文件上传input")
            return 0

        uploaded = 0
        tmp_files: list[Path] = []
        try:
            for index, url in enumerate(urls[:MAX_PUBLISH_IMAGES]):
                try:
                    if url.startswith("http://") or url.startswith("https://"):
                        tmp = await _download_remote_publish_image(url)
                        tmp_files.append(tmp)
                        continue
                    elif url.startswith("/uploads/"):
                        local_path = Path("/app") / url.lstrip("/")
                        if not local_path.exists():
                            continue
                        image_data = local_path.read_bytes()
                    else:
                        continue

                    suffix = ".jpg"
                    for ext in [".png", ".webp", ".gif", ".jpeg"]:
                        if url.lower().endswith(ext):
                            suffix = ext
                            break
                    tmp = Path(f"/tmp/publish_{int(time.time())}_{index}{suffix}")
                    tmp.write_bytes(image_data)
                    tmp_files.append(tmp)
                except Exception as e:
                    logger.warning(f"准备图片失败: {e}")
                    continue

            if not tmp_files:
                return 0

            await upload_input.set_input_files([str(path) for path in tmp_files])
            await asyncio.sleep(max(3, min(len(tmp_files) * 2, 12)))
            uploaded = len(tmp_files)
            logger.info(f"✓ 批量上传图片 {uploaded}/{MAX_PUBLISH_IMAGES}")
            return uploaded
        finally:
            for tmp in tmp_files:
                try:
                    tmp.unlink()
                except Exception:
                    pass

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
        if "item_id=" in current_url or "/item/" in current_url or "item?id=" in current_url:
            result["success"] = True
            result["item_url"] = current_url
            result["item_id"] = _extract_item_id_from_url(current_url)
            if not result.get("message"):
                result["message"] = "发布成功"
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
            await self._fill_description(title, desc)
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
        result = _normalize_publish_result(item.item_id, result)

        log.status = "published" if result["success"] else "failed"
        log.error_message = result.get("message")
        log.result_item_id = result.get("item_id")
        log.result_url = result.get("item_url")

        if result["success"]:
            previous_item_id = item.item_id
            is_draft_source = previous_item_id.startswith("draft-")
            result_item_id = str(result.get("item_id") or "").strip()
            if result_item_id and result_item_id != item.item_id:
                result_url = result.get("item_url")
                await _move_delivery_config(session, item.account_id, previous_item_id, result_item_id)
                if is_draft_source:
                    existing_stmt = select(Item).where(Item.item_id == result_item_id)
                    existing_result = await session.execute(existing_stmt)
                    existing_item = existing_result.scalar_one_or_none()
                    if existing_item and existing_item.id != item.id:
                        _copy_item_for_republish(existing_item, item, result_item_id, result_url)
                        await session.delete(item)
                        item = existing_item
                    else:
                        item.item_id = result_item_id
                        item.status = "online"
                        item.publish_status = "published"
                        item.publish_error = None
                        if result_url:
                            item.url = result_url
                else:
                    existing_stmt = select(Item).where(Item.item_id == result_item_id)
                    existing_result = await session.execute(existing_stmt)
                    existing_item = existing_result.scalar_one_or_none()
                    if existing_item:
                        _copy_item_for_republish(existing_item, item, result_item_id, result_url)
                    else:
                        existing_item = Item(item_id=result_item_id, account_id=item.account_id)
                        _copy_item_for_republish(existing_item, item, result_item_id, result_url)
                        session.add(existing_item)

                    try:
                        offline_ok = await _offline_item(item.account_id, cookies_str, previous_item_id)
                        if offline_ok:
                            item.status = "offline"
                            item.publish_status = "draft"
                            item.publish_error = None
                            existing_item.publish_error = None
                            logger.info(f"[下架] 旧商品已下架: {previous_item_id}")
                        else:
                            item.status = "online"
                            item.publish_status = "published"
                            item.publish_error = f"新商品已发布，但旧商品下架失败: {previous_item_id}"
                            existing_item.publish_error = None
                            logger.warning(f"[下架] 旧商品下架失败: {previous_item_id}")
                    except Exception as exc:
                        item.status = "online"
                        item.publish_status = "published"
                        item.publish_error = f"新商品已发布，但旧商品下架异常: {previous_item_id}"
                        existing_item.publish_error = None
                        logger.warning(f"[下架] 旧商品下架异常: {previous_item_id}, error={exc}")

                    item = existing_item
            else:
                item.status = "online"
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
