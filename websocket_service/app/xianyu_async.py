import asyncio
import base64
import json
import time
import os
import random
import uuid
import aiohttp
from typing import Optional, Dict, Any
from loguru import logger

WEBSOCKET_URL = os.getenv("WEBSOCKET_URL", "wss://wss-goofish.dingtalk.com/")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "15"))
TOKEN_REFRESH_INTERVAL = int(os.getenv("TOKEN_REFRESH_INTERVAL", "72000"))


def generate_mid() -> str:
    return f"{int(1000 * random.random())}{int(time.time() * 1000)} 0"


def generate_uuid() -> str:
    return uuid.uuid4().hex


class XianyuWS:
    def __init__(self, cookie_id: str, cookies_str: str):
        self.cookie_id = cookie_id
        self.cookies_str = cookies_str
        self.cookies = self._parse_cookies(cookies_str)
        self.myid = self.cookies.get("unb", cookie_id)
        self.device_id = f"device_{cookie_id}_{int(time.time())}"
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self.running = False
        self.message_handler = None
        self._pending_mid_futures: Dict[str, asyncio.Future] = {}
        self.last_send_error = ""

    def _parse_cookies(self, s: str) -> dict:
        c = {}
        for item in s.split(";"):
            item = item.strip()
            if "=" in item:
                k, v = item.split("=", 1)
                c[k.strip()] = v.strip()
        return c

    async def connect(self):
        if self.session and not self.session.closed:
            await self.session.close()
        self.session = aiohttp.ClientSession()
        headers = {
            "Cookie": self.cookies_str,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        }
        try:
            self.ws = await self.session.ws_connect(WEBSOCKET_URL, headers=headers, timeout=30)
            self.running = True
            logger.info(f"[{self.cookie_id}] WebSocket connected")
            return True
        except Exception as e:
            logger.error(f"[{self.cookie_id}] WebSocket connect failed: {e}")
            return False

    async def send_heartbeat(self):
        if self.ws and not self.ws.closed:
            try:
                await self.ws.send_str(json.dumps({
                    "lwp": "/r/SyncStatus/ackDiff",
                    "headers": {"mid": generate_mid()},
                    "body": [{
                        "pipeline": "sync",
                        "tooLong2Tag": "PNM,1",
                        "channel": "sync",
                        "topic": "sync",
                        "highPts": 0,
                        "pts": int(time.time() * 1000) * 1000,
                        "seq": 0,
                        "timestamp": int(time.time() * 1000),
                    }],
                }))
            except Exception as e:
                logger.debug(f"[{self.cookie_id}] heartbeat send error: {e}")

    def _dispatch_mid_response(self, data: dict):
        headers = data.get("headers") or {}
        mid = headers.get("mid") or data.get("mid")
        if not mid:
            return
        future = self._pending_mid_futures.pop(str(mid), None)
        if future and not future.done():
            future.set_result(data)

    async def _send_ack(self, data: dict):
        if not self.ws or self.ws.closed:
            return
        headers = data.get("headers") if isinstance(data.get("headers"), dict) else {}
        if not headers:
            return
        ack_headers = {
            "mid": headers.get("mid", generate_mid()),
            "sid": headers.get("sid", ""),
        }
        for key in ("app-key", "ua", "dt"):
            if key in headers:
                ack_headers[key] = headers[key]
        try:
            await self.ws.send_str(json.dumps({"code": 200, "headers": ack_headers}, ensure_ascii=False))
        except Exception as exc:
            logger.debug(f"[{self.cookie_id}] ack send error: {exc}")

    @staticmethod
    def _response_error(data: dict) -> str:
        text = json.dumps(data, ensure_ascii=False, default=str)
        markers = ("CSI_FORBID", "FAIL", "ERROR", "forbid", "拒绝", "失败", "风控", "违禁")
        if any(marker in text for marker in markers):
            return text[:500]
        code = data.get("code") if isinstance(data, dict) else None
        if code not in (None, 200, "200"):
            return text[:500]
        return ""

    async def create_chat_conversation(self, to_user_id: str, item_id: str = "", timeout: float = 12.0) -> str:
        if not self.ws or self.ws.closed:
            raise ConnectionError("websocket not connected")
        if not to_user_id:
            raise ValueError("to_user_id required")
        mid = generate_mid()
        msg = {
            "lwp": "/r/SingleChatConversation/create",
            "headers": {"mid": mid},
            "body": [{
                "pairFirst": f"{to_user_id}@goofish",
                "pairSecond": f"{self.myid}@goofish",
                "bizType": "1",
                "extension": {"itemId": str(item_id)} if item_id else {},
                "ctx": {"appVersion": "1.0", "platform": "web"},
            }],
        }
        future = asyncio.get_running_loop().create_future()
        self._pending_mid_futures[mid] = future
        try:
            await self.ws.send_str(json.dumps(msg, ensure_ascii=False))
            response = await asyncio.wait_for(future, timeout=timeout)
            chat_id = self._extract_cid_from_create_chat_response(response)
            if not chat_id:
                raise ValueError("create conversation response missing cid")
            return chat_id
        finally:
            self._pending_mid_futures.pop(mid, None)

    @staticmethod
    def _extract_cid_from_create_chat_response(response: dict) -> Optional[str]:
        body = response.get("body") if isinstance(response, dict) else None
        first = body[0] if isinstance(body, list) and body else body if isinstance(body, dict) else None
        if not isinstance(first, dict):
            return None
        candidates = [
            first.get("singleChatConversation"),
            (first.get("singleChatUserConversation") or {}).get("singleChatConversation") if isinstance(first.get("singleChatUserConversation"), dict) else None,
            (first.get("data") or {}).get("singleChatConversation") if isinstance(first.get("data"), dict) else None,
            first,
        ]
        for candidate in candidates:
            if isinstance(candidate, dict):
                cid = candidate.get("cid") or candidate.get("id")
                if isinstance(cid, str) and cid:
                    return cid.split("@", 1)[0]
        return None

    async def send_message(self, chat_id: str, to_user_id: str, content: str, msg_type: str = "text", item_id: str = ""):
        self.last_send_error = ""
        if not self.ws or self.ws.closed:
            self.last_send_error = "websocket not connected"
            return False
        try:
            if not chat_id or chat_id == to_user_id:
                try:
                    chat_id = await self.create_chat_conversation(to_user_id, item_id=item_id)
                except Exception as exc:
                    logger.warning(f"[{self.cookie_id}] create conversation failed, fallback to user id: {exc}")
                    chat_id = to_user_id

            msg_content = {"contentType": 1, "text": {"text": content}}
            content_base64 = base64.b64encode(json.dumps(msg_content, ensure_ascii=False).encode("utf-8")).decode("utf-8")
            mid = generate_mid()
            future = asyncio.get_running_loop().create_future()
            self._pending_mid_futures[mid] = future
            msg = {
                "lwp": "/r/MessageSend/sendByReceiverScope",
                "headers": {"mid": mid},
                "body": [
                    {
                        "uuid": generate_uuid(),
                        "cid": f"{chat_id}@goofish",
                        "conversationType": 1,
                        "content": {
                            "contentType": 101,
                            "custom": {"type": 1, "data": content_base64},
                        },
                        "redPointPolicy": 0,
                        "extension": {"extJson": "{}"},
                        "ctx": {"appVersion": "1.0", "platform": "web"},
                        "mtags": {},
                        "msgReadStatusSetting": 1,
                    },
                    {
                        "actualReceivers": [
                            f"{to_user_id}@goofish",
                            f"{self.myid}@goofish",
                        ]
                    },
                ],
            }
            await self.ws.send_str(json.dumps(msg, ensure_ascii=False))
            try:
                response = await asyncio.wait_for(future, timeout=3)
                error = self._response_error(response)
                if error:
                    self.last_send_error = error
                    logger.warning(f"[{self.cookie_id}] send msg rejected: {error}")
                    return False
            except asyncio.TimeoutError:
                pass
            finally:
                self._pending_mid_futures.pop(mid, None)
            logger.info(f"[{self.cookie_id}] Sent msg to {to_user_id}: {content[:30]}...")
            return True
        except Exception as e:
            self.last_send_error = str(e)
            logger.error(f"[{self.cookie_id}] send msg error: {e}")
            return False

    async def listen(self):
        if not self.ws:
            return
        while self.running and not self.ws.closed:
            try:
                msg = await self.ws.receive(timeout=HEARTBEAT_INTERVAL)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self._send_ack(data)
                    self._dispatch_mid_response(data)
                    if self.message_handler:
                        await self.message_handler(self.cookie_id, data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    break
            except asyncio.TimeoutError:
                await self.send_heartbeat()
            except Exception as e:
                logger.error(f"[{self.cookie_id}] listen error: {e}")
                break

    async def run(self):
        self.running = True
        while self.running:
            connected = await self.connect()
            if connected:
                await self.listen()
            await asyncio.sleep(5)

    def is_connected(self) -> bool:
        return bool(self.ws and not self.ws.closed)

    async def stop(self):
        self.running = False
        if self.ws and not self.ws.closed:
            await self.ws.close()
        if self.session:
            await self.session.close()
