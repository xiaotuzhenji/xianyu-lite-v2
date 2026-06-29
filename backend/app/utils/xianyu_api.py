import json
import time
import asyncio
from typing import Dict, Any, Optional

import aiohttp
from loguru import logger

from .crypto import generate_sign, trans_cookies

MTOP_BASE = "https://h5api.m.goofish.com/h5"
APP_KEY = "34839810"

async def mtop_call(
    api: str,
    data: dict,
    cookies_str: str,
    version: str = "1.0",
    extra_params: Optional[Dict] = None,
) -> Dict[str, Any]:
    cookies = trans_cookies(cookies_str)
    token = cookies.get("_m_h5_tk", "").split("_")[0] if cookies.get("_m_h5_tk") else ""
    t = str(int(time.time()) * 1000)
    data_val = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    sign = generate_sign(t, token, data_val)

    params = {
        "jsv": "2.7.2",
        "appKey": APP_KEY,
        "t": t,
        "sign": sign,
        "v": version,
        "type": "originaljson",
        "accountSite": "xianyu",
        "dataType": "json",
        "timeout": "20000",
        "api": api,
        "sessionOption": "AutoLoginOnly",
    }
    if extra_params:
        params.update(extra_params)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.goofish.com",
        "Referer": "https://www.goofish.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Cookie": cookies_str,
    }

    url = f"{MTOP_BASE}/{api}/{version}/"

    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, params=params, data={"data": data_val}, headers=headers) as resp:
                    res_json = await resp.json(content_type=None)
                    ret = res_json.get("ret") or [""]
                    ret_msg = ret[0] if ret else ""

                    if "SUCCESS::" in ret_msg:
                        return {"success": True, "data": res_json.get("data", {})}

                    if any(m in ret_msg for m in ("FAIL_SYS_TOKEN_EXOIRED", "FAIL_SYS_TOKEN_EXPIRED")):
                        set_cookies = resp.headers.getall("Set-Cookie", [])
                        if set_cookies:
                            for sc in set_cookies:
                                if "=" in sc:
                                    k, v = sc.split("=", 1)
                                    k = k.strip()
                                    v = v.split(";")[0]
                                    cookies[k] = v
                            token = cookies.get("_m_h5_tk", "").split("_")[0]
                            if token:
                                sign = generate_sign(t, token, data_val)
                                params["sign"] = sign
                                headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
                                continue

                    if "FAIL_SYS_SESSION_EXPIRED" in ret_msg:
                        return {"success": False, "session_expired": True, "error": ret_msg}

                    if any(m in ret_msg for m in ("FAIL_SYS_USER_VALIDATE", "RGV587")):
                        return {"success": False, "risk_control": True, "error": ret_msg}

                    return {"success": False, "error": ret_msg or "调用失败", "data": res_json}

        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(0.5)
                continue
            return {"success": False, "error": str(e)}

    return {"success": False, "error": "重试次数过多"}
