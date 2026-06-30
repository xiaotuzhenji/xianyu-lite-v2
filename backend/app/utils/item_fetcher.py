import asyncio
import json
import time
from typing import Any, Dict, Optional

import aiohttp

from .cookie_utils import is_token_error, merge_set_cookies
from .crypto import generate_sign, trans_cookies


def _extract_image_urls(value: Any) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    visited: set[int] = set()

    def push(candidate: Any) -> None:
        if not isinstance(candidate, str):
            return
        text = candidate.strip()
        if not text or text in seen:
            return
        if text.startswith(("http://", "https://", "/")):
            lower = text.lower()
            if (
                "tps-42-42" in lower
                or "tps-84-60" in lower
                or "tps-40-40" in lower
                or "icon" in lower
                or "avatar" in lower
                or "default" in lower
            ):
                return
            seen.add(text)
            urls.append(text)

    def walk(node: Any) -> None:
        if node is None or len(urls) >= 8:
            return
        if isinstance(node, str):
            text = node.strip()
            if not text:
                return
            if text.startswith("{") or text.startswith("["):
                try:
                    walk(json.loads(text))
                    return
                except Exception:
                    pass
            push(text)
            return
        if isinstance(node, list):
            node_id = id(node)
            if node_id in visited:
                return
            visited.add(node_id)
            for item in node:
                walk(item)
                if len(urls) >= 8:
                    break
            return
        if isinstance(node, dict):
            node_id = id(node)
            if node_id in visited:
                return
            visited.add(node_id)
            for key in (
                "picUrl",
                "picurl",
                "imgUrl",
                "imageUrl",
                "pictureUrl",
                "picture",
                "image",
                "coverUrl",
                "cover",
                "url",
                "src",
                "mainUrl",
                "thumbUrl",
                "thumbnail",
                "largePicUrl",
                "bigPicUrl",
                "smallPicUrl",
                "originalPicUrl",
            ):
                push(node.get(key))
            for key in (
                "picInfo",
                "picInfos",
                "imageInfo",
                "imageInfos",
            ):
                walk(node.get(key))
            for key in (
                "picUrls",
                "picUrlList",
                "imageUrls",
                "imageList",
                "images",
                "pics",
                "gallery",
                "photos",
                "list",
                "urls",
                "items",
            ):
                walk(node.get(key))
            for item in node.values():
                if isinstance(item, (dict, list)):
                    walk(item)
                else:
                    push(item)

    walk(value)
    return urls


class ItemFetcher:
    def __init__(self, account_id: str, cookies_str: str):
        self.account_id = account_id
        self.cookies_str = cookies_str
        self.cookies = trans_cookies(cookies_str)
        self.session: Optional[aiohttp.ClientSession] = None
        self.cookie_changed = False

    async def __aenter__(self):
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://www.goofish.com",
            "referer": "https://www.goofish.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "cookie": self.cookies_str,
        }
        self.session = aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=30))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()

    def _cookie_user_id(self) -> str:
        return self.cookies.get("unb") or self.account_id

    async def fetch_page(self, page: int = 1, page_size: int = 20) -> Dict[str, Any]:
        if not self.session:
            raise RuntimeError("session not initialized")

        data = {
            "needGroupInfo": False,
            "pageNumber": page,
            "pageSize": page_size,
            "groupName": "在售",
            "groupId": "58877261",
            "defaultGroup": True,
            "userId": self._cookie_user_id(),
        }
        data_val = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        t = str(int(time.time()) * 1000)
        token = self.cookies.get("_m_h5_tk", "").split("_")[0] if self.cookies.get("_m_h5_tk") else ""
        sign = generate_sign(t, token, data_val)
        params = {
            "jsv": "2.7.2",
            "appKey": "34839810",
            "t": t,
            "sign": sign,
            "v": "1.0",
            "type": "originaljson",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": "mtop.idle.web.xyh.item.list",
            "sessionOption": "AutoLoginOnly",
            "spm_cnt": "a21ybx.im.0.0",
            "spm_pre": "a21ybx.collection.menu.1.272b5141NafCNK",
        }

        async with self.session.post(
            "https://h5api.m.goofish.com/h5/mtop.idle.web.xyh.item.list/1.0/",
            params=params,
            data={"data": data_val},
        ) as response:
            res_json = await response.json(content_type=None)
            changed, merged = merge_set_cookies(self.cookies_str, response.headers.getall("set-cookie", []))
            if changed:
                self.cookies_str = merged
                self.cookies = trans_cookies(merged)
                self.cookie_changed = True

            ret = res_json.get("ret") or []
            ret_msg = ret[0] if ret else ""
            if "SUCCESS" in ret_msg:
                items = []
                for card in res_json.get("data", {}).get("cardList", []) or []:
                    card_data = card.get("cardData") or {}
                    if not card_data:
                        continue
                    price_raw = (card_data.get("priceInfo") or {}).get("price") or 0
                    try:
                        price = float(str(price_raw).replace(",", ""))
                    except Exception:
                        price = 0
                    items.append({
                        "item_id": str(card_data.get("id") or ""),
                        "title": card_data.get("title") or "",
                        "price": price,
                        "url": card_data.get("detailUrl") or "",
                        "image_urls": json.dumps(_extract_image_urls(card_data), ensure_ascii=False),
                        "status": "online",
                        "raw": card_data,
                    })
                return {
                    "success": True,
                    "items": [item for item in items if item["item_id"]],
                    "has_more": len(items) >= page_size,
                    "cookies_str": self.cookies_str,
                }

            return {
                "success": False,
                "error": ret_msg or "获取商品失败",
                "retryable": is_token_error(ret_msg) and changed,
                "cookies_str": self.cookies_str,
                "raw": res_json,
            }

    async def fetch_all(self, page_size: int = 20, max_pages: int = 10) -> Dict[str, Any]:
        all_items = []
        truncated = False
        for page in range(1, max_pages + 1):
            result = await self.fetch_page(page, page_size)
            if result.get("retryable"):
                result = await self.fetch_page(page, page_size)
            if not result.get("success"):
                return result
            items = result.get("items") or []
            all_items.extend(items)
            if not result.get("has_more"):
                break
            await asyncio.sleep(0.5)
        else:
            truncated = True
        return {"success": True, "items": all_items, "cookies_str": self.cookies_str, "truncated": truncated}
