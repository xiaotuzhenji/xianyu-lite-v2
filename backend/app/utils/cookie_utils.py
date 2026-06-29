from http.cookies import SimpleCookie
from typing import Iterable

from .crypto import trans_cookies


def merge_set_cookies(cookies_str: str, set_cookie_headers: Iterable[str]) -> tuple[bool, str]:
    cookies = trans_cookies(cookies_str)
    changed = False

    for header in set_cookie_headers:
        parsed = SimpleCookie()
        try:
            parsed.load(header)
        except Exception:
            continue
        for name, morsel in parsed.items():
            value = morsel.value
            if name and cookies.get(name) != value:
                cookies[name] = value
                changed = True

    if not changed:
        return False, cookies_str
    return True, "; ".join(f"{key}={value}" for key, value in cookies.items())


def is_token_error(ret_msg: str) -> bool:
    lower = (ret_msg or "").lower()
    return "token" in lower or "令牌" in ret_msg or "FAIL_SYS_TOKEN" in ret_msg
