import json
import time
from typing import Any, Dict

import aiohttp

from .cookie_utils import is_token_error, merge_set_cookies
from .crypto import generate_sign, trans_cookies

STATUS_MAP = {
    "待付款": "pending_payment",
    "待发货": "paid",
    "已发货": "shipped",
    "交易成功": "received",
    "交易关闭": "closed",
    "退款中": "refunding",
    "退款成功": "refunded",
    "已退款": "refunded",
}


class OrderFetcher:
    PAGE_SIZE = 30

    def __init__(self, account_id: str, cookies_str: str):
        self.account_id = account_id
        self.cookies_str = cookies_str
        self.cookies = trans_cookies(cookies_str)
        self.cookie_changed = False

    async def fetch_page(self, page: int = 1, query_code: str = "ALL") -> Dict[str, Any]:
        timestamp = str(int(time.time() * 1000))
        data = {
            "pageNumber": page,
            "rowsPerPage": self.PAGE_SIZE,
            "orderIds": "",
            "queryCode": query_code,
            "orderSearchParam": "{}",
        }
        data_val = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        token = self.cookies.get("_m_h5_tk", "").split("_")[0] if self.cookies.get("_m_h5_tk") else ""
        sign = generate_sign(timestamp, token, data_val)
        params = {
            "jsv": "2.7.2",
            "appKey": "34839810",
            "t": timestamp,
            "sign": sign,
            "v": "1.0",
            "type": "json",
            "accountSite": "xianyu",
            "dataType": "json",
            "timeout": "20000",
            "api": "mtop.taobao.idle.trade.merchant.sold.get",
            "valueType": "string",
            "sessionOption": "AutoLoginOnly",
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "idle_site_biz_code": "COMMONPRO",
            "cookie": self.cookies_str,
            "referer": "https://seller.goofish.com/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0.0.0 Safari/537.36",
        }

        async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(), timeout=aiohttp.ClientTimeout(total=25)) as session:
            async with session.post(
                "https://h5api.m.goofish.com/h5/mtop.taobao.idle.trade.merchant.sold.get/1.0/",
                params=params,
                data={"data": data_val},
                headers=headers,
            ) as response:
                res_json = await response.json(content_type=None)
                changed, merged = merge_set_cookies(self.cookies_str, response.headers.getall("set-cookie", []))
                if changed:
                    self.cookies_str = merged
                    self.cookies = trans_cookies(merged)
                    self.cookie_changed = True

                ret = res_json.get("ret") or []
                ret_msg = ret[0] if ret else ""
                if "SUCCESS" not in ret_msg:
                    if "TOKEN_EXOIRED" in ret_msg or "TOKEN_EXPIRED" in ret_msg:
                        changed2, merged2 = merge_set_cookies(self.cookies_str, response.headers.getall("set-cookie", []))
                        if changed2:
                            self.cookies_str = merged2
                            self.cookies = trans_cookies(merged2)
                            self.cookie_changed = True
                            return await self.fetch_page(page, query_code=query_code)
                    return {
                        "success": False,
                        "error": ret_msg or "unknown",
                        "retryable": is_token_error(ret_msg),
                        "cookies_str": self.cookies_str,
                        "raw": res_json,
                    }

                # SUCCESS: parse orders
                data_list = (res_json.get("data") or {}).get("itemDOList") or []
                orders = []
                for item in data_list:
                    order_info = item.get("orderInfo") or {}
                    buyer_info = item.get("buyerInfo") or {}
                    buyer_id = ""
                    buyer_name = ""
                    if isinstance(buyer_info, dict):
                        buyer_id = str(buyer_info.get("userId") or "")
                        buyer_name = buyer_info.get("userNick") or ""
                    elif isinstance(buyer_info, list) and buyer_info:
                        buyer_id = str(buyer_info[0].get("userId") or "") if isinstance(buyer_info[0], dict) else ""
                        buyer_name = buyer_info[0].get("userNick") or "" if isinstance(buyer_info[0], dict) else ""
                    item_id = str(order_info.get("itemId") or "")
                    if not item_id:
                        item_list = item.get("itemList") or []
                        item_id = str(item_list[0].get("itemId") or "") if item_list else ""
                    orders.append({
                        "order_id": str(order_info.get("orderId") or order_info.get("id") or ""),
                        "item_id": item_id,
                        "buyer_id": buyer_id,
                        "buyer_name": buyer_name,
                        "price": float(order_info.get("price") or order_info.get("actualPayFee") or 0),
                        "status": STATUS_MAP.get(order_info.get("status") or order_info.get("orderStatus") or "", "pending"),
                        "raw": order_info,
                    })
                has_more = len(orders) >= self.PAGE_SIZE
                return {
                    "success": True,
                    "items": [o for o in orders if o["order_id"]],
                    "has_more": has_more,
                    "cookies_str": self.cookies_str,
                }

    async def fetch_all(self, query_code: str = "ALL", max_pages: int = 3) -> dict:
        all_items = []
        for page in range(1, max_pages + 1):
            result = await self.fetch_page(page, query_code=query_code)
            if result.get("retryable"):
                result = await self.fetch_page(page, query_code=query_code)
            if not result.get("success"):
                return result
            items = result.get("items") or []
            all_items.extend(items)
            if not result.get("has_more"):
                break
        return {"success": True, "items": all_items, "cookies_str": self.cookies_str}
