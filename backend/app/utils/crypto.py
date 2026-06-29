import hashlib
import random
import time
import json
from typing import Dict, Optional

def trans_cookies(cookies_str: str) -> Dict[str, str]:
    if not cookies_str:
        return {}
    cookies = {}
    for cookie in cookies_str.split(";"):
        cookie = cookie.strip()
        if not cookie or "=" not in cookie:
            continue
        key, value = cookie.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies

def generate_sign(t: str, token: str, data: str) -> str:
    app_key = "34839810"
    msg = f"{token}&{t}&{app_key}&{data}"
    return hashlib.md5(msg.encode("utf-8")).hexdigest()

def generate_device_id(user_id: str) -> str:
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    result = []
    for i in range(36):
        if i in [8, 13, 18, 23]:
            result.append("-")
        elif i == 14:
            result.append("4")
        else:
            if i == 19:
                result.append(chars[(int(16 * random.random()) & 0x3) | 0x8])
            else:
                result.append(chars[int(16 * random.random())])
    return "".join(result) + "-" + user_id

def generate_mid() -> str:
    random_part = int(1000 * random.random())
    timestamp = int(time.time() * 1000)
    return f"{random_part}{timestamp} 0"
