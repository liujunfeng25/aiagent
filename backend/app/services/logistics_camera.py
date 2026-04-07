"""
摄像头 API 封装：萤石(YS7) + 乐橙(IMOU)
环境变量：
  YS7_APP_KEY / YS7_APP_SECRET
  IMOU_APP_ID / IMOU_APP_SECRET
"""
import os
import time
import hashlib
import hmac
import uuid
import json
import requests
from typing import Optional

# ── 萤石(YS7 / Ezviz) ──────────────────────────────────────

_YS7_BASE = "https://open.ys7.com/api/lapp"


class Ys7Client:
    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        self.app_key = app_key or os.getenv("YS7_APP_KEY", "")
        self.app_secret = app_secret or os.getenv("YS7_APP_SECRET", "")
        self._token: Optional[str] = None
        self._token_expire: float = 0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expire:
            return self._token
        r = requests.post(
            f"{_YS7_BASE}/token/get",
            data={"appKey": self.app_key, "appSecret": self.app_secret},
            timeout=10,
        )
        d = r.json()
        if d.get("code") != "200":
            raise RuntimeError(f"YS7 获取 token 失败: {d}")
        self._token = d["data"]["accessToken"]
        expire_time = int(d["data"].get("expireTime", 0)) / 1000
        self._token_expire = expire_time if expire_time > time.time() else time.time() + 3600 * 6
        return self._token

    @staticmethod
    def live_use_ezopen() -> bool:
        """与 Ys7Api::liveUseEzopen；YS7_LIVE_USE_EZOPEN=0 时走 HLS。"""
        return os.getenv("YS7_LIVE_USE_EZOPEN", "1") != "0"

    @staticmethod
    def build_ezopen_live_url(device_serial: str, channel_no: int, quality: int) -> str:
        """ezopen://open.ys7.com/{serial}/{ch}.hd.live|live"""
        device_serial = (device_serial or "").strip()
        ch = int(channel_no) if channel_no >= 1 else 1
        if not device_serial:
            return ""
        suffix = "hd.live" if int(quality) == 1 else "live"
        return f"ezopen://open.ys7.com/{device_serial}/{ch}.{suffix}"

    @staticmethod
    def _pick_url_from_live_address_data(data, quality: int = 1) -> str:
        """
        解析 live/address/get 的 data 字段。
        与萤石文档「云直播 - 播放地址接口（设备）」一致：传 source 时 data 常为 **数组**，
        单条含 hls/hlsHd/url 等；旧版也可能为单对象。仅处理 dict 会导致 HLS 永远为空（见 open.ys7.com 云直播文档）。
        """
        q = int(quality) if int(quality) >= 1 else 1
        row = None
        if isinstance(data, list) and data:
            row = data[0] if isinstance(data[0], dict) else None
        elif isinstance(data, dict):
            row = data
        if not row:
            return ""
        if q == 1:
            return (
                (row.get("hlsHd") or row.get("hls") or row.get("url") or row.get("hlsUrl") or "")
                .strip()
            )
        return (
            (row.get("hls") or row.get("hlsHd") or row.get("url") or row.get("hlsUrl") or "")
            .strip()
        )

    def try_live_video_open(self, device_serial: str, channel_no: int) -> None:
        try:
            src = f"{(device_serial or '').strip()}:{int(channel_no)}"
            requests.post(
                f"{_YS7_BASE}/live/video/open",
                data={"accessToken": self._get_token(), "source": src},
                timeout=10,
            )
        except Exception:
            pass

    def get_live_address_hls(self, device_serial: str, channel_no: int, quality: int = 1) -> str:
        """与 Ys7Api::getLiveAddressHls：lapp live/address/get，source=设备:通道。"""
        device_serial = (device_serial or "").strip()
        ch = int(channel_no) if channel_no >= 1 else 1
        if not device_serial:
            return ""
        expire = max(60, min(86400, int(os.getenv("YS7_LIVE_URL_EXPIRE", "300"))))
        proto = int(os.getenv("YS7_LIVE_PROTOCOL", "2"))
        source = f"{device_serial}:{ch}"
        params = {
            "accessToken": self._get_token(),
            "source": source,
            "protocol": proto,
            "supportH265": 0,
        }
        if os.getenv("YS7_LIVE_ADDRESS_INCLUDE_EXPIRE", "0") == "1":
            params["expire"] = expire

        def try_get(p: dict):
            return requests.post(f"{_YS7_BASE}/live/address/get", data=p, timeout=15)

        self.try_live_video_open(device_serial, ch)
        r = try_get(params)
        try:
            d = r.json()
        except Exception:
            d = {}
        if not isinstance(d, dict):
            d = {}
        code = str(d.get("code", ""))
        if code == "10002":
            self._token = None
            self._token_expire = 0
            params["accessToken"] = self._get_token()
            r = try_get(params)
            try:
                d = r.json()
            except Exception:
                d = {}
            if not isinstance(d, dict):
                d = {}
            code = str(d.get("code", ""))
        if code == "200":
            url = self._pick_url_from_live_address_data(d.get("data"), quality)
            if url:
                return url
        # 补试：部分账号仅接受 deviceSerial+channelNo；另注意不能少传 source 时用 v2 或此组合
        r2 = requests.post(
            f"{_YS7_BASE}/live/address/get",
            data={
                "accessToken": self._get_token(),
                "deviceSerial": device_serial,
                "channelNo": ch,
                "protocol": proto,
                "quality": int(quality),
                "supportH265": 0,
                "expire": expire,
            },
            timeout=15,
        )
        try:
            d2 = r2.json()
        except Exception:
            d2 = {}
        if not isinstance(d2, dict):
            d2 = {}
        if str(d2.get("code", "")) == "200":
            return self._pick_url_from_live_address_data(d2.get("data"), quality)
        return ""

    def get_live_service_urls_grid(self, device_serial: str, channel_id) -> dict:
        """与 Ys7Api::getLiveServiceUrlsGrid。"""
        ch = int(channel_id) if int(channel_id or 1) >= 1 else 1
        device_serial = (device_serial or "").strip()
        if not device_serial:
            return {"error": "deviceSerial 为空"}
        if self.live_use_ezopen():
            self.try_live_video_open(device_serial, ch)
            hd = self.build_ezopen_live_url(device_serial, ch, 1)
            sd = self.build_ezopen_live_url(device_serial, ch, 2)
            if not hd:
                return {"error": "无法拼装 EZOPEN 地址"}
            return {"encrypted": {"hd": hd, "sd": sd}, "plain": {"hd": hd, "sd": sd}}
        hd = self.get_live_address_hls(device_serial, ch, 1)
        if not hd:
            return {"error": "无法获取高清 HLS"}
        sd = self.get_live_address_hls(device_serial, ch, 2) or hd
        return {"encrypted": {"hd": hd, "sd": sd}, "plain": {"hd": hd, "sd": sd}}

    def get_playable_hls_for_device(self, device_serial: str, channel_id) -> dict:
        grid = self.get_live_service_urls_grid(device_serial, channel_id)
        if "error" in grid:
            return {"hls": "", "stream_id": None, "error": grid["error"]}
        pl = grid.get("plain") or {}
        u = (pl.get("sd") or pl.get("hd") or "").strip()
        return {"hls": u, "stream_id": 1 if u else None}

    def get_live_address(self, device_serial: str, channel_no: int = 1) -> dict:
        """兼容旧调用：优先 lapp HLS。"""
        url = self.get_live_address_hls(device_serial, channel_no, 1)
        if url:
            return {"url": url, "expiry": ""}
        proto = int(os.getenv("YS7_LIVE_PROTOCOL", "2"))
        r = requests.post(
            f"{_YS7_BASE}/video/address/get",
            data={
                "accessToken": self._get_token(),
                "deviceSerial": device_serial,
                "channelNo": channel_no,
                "protocol": proto,
                "quality": 1,
            },
            timeout=10,
        )
        try:
            d = r.json()
        except Exception:
            d = {}
        if not isinstance(d, dict):
            d = {}
        if d.get("code") != "200":
            return {"error": d.get("msg", "获取直播地址失败")}
        raw = d.get("data")
        exp = raw.get("expiry", "") if isinstance(raw, dict) else ""
        return {
            "url": self._pick_url_from_live_address_data(raw, 1),
            "expiry": exp,
        }

    def ptz_mirror_command(self, device_serial: str, channel_no: int, command: int) -> dict:
        """与 Ys7Api::ptzMirror：device/ptz/mirror"""
        r = requests.post(
            f"{_YS7_BASE}/device/ptz/mirror",
            data={
                "accessToken": self._get_token(),
                "deviceSerial": device_serial,
                "channelNo": int(channel_no),
                "command": int(command),
            },
            timeout=10,
        )
        return r.json()

    def ptz_control(
        self,
        device_serial: str,
        channel_no: int,
        direction: int,
        speed: int = 1,
        action: int = 0,
    ) -> dict:
        """
        云台控制
        direction: 0上 1下 2左 3右 4左上 5左下 6右上 7右下 8焦距缩小 9焦距放大
        action: 0=开始 1=停止
        """
        r = requests.post(
            f"{_YS7_BASE}/device/ptz/start" if action == 0 else f"{_YS7_BASE}/device/ptz/stop",
            data={
                "accessToken": self._get_token(),
                "deviceSerial": device_serial,
                "channelNo": channel_no,
                "direction": direction,
                "speed": speed,
            },
            timeout=10,
        )
        d = r.json()
        return {"code": d.get("code"), "msg": d.get("msg")}

    def set_mirror(self, device_serial: str, channel_no: int, mirror_type: int) -> dict:
        """mirror_type: 0=不翻转 1=水平 2=垂直 3=水平+垂直（device/mirror/set，兼容旧版）"""
        r = requests.post(
            f"{_YS7_BASE}/device/mirror/set",
            data={
                "accessToken": self._get_token(),
                "deviceSerial": device_serial,
                "channelNo": channel_no,
                "mirrorType": mirror_type,
            },
            timeout=10,
        )
        d = r.json()
        return {"code": d.get("code"), "msg": d.get("msg")}

    def fetch_device_list(self) -> list:
        """从萤石平台拉取账号下所有设备+通道，返回可直接 upsert 的行列表"""
        token = self._get_token()
        page_size = 50
        rows = []
        for page in range(100):
            r = requests.post(
                f"{_YS7_BASE}/device/list",
                data={"accessToken": token, "pageStart": page * page_size, "pageSize": page_size},
                timeout=15,
            )
            d = r.json()
            if d.get("code") != "200":
                break
            devices = d.get("data") or []
            if not devices:
                break
            for dev in devices:
                serial = dev.get("deviceSerial", "")
                dev_name = dev.get("deviceName") or serial
                # 拉通道列表
                cr = requests.post(
                    f"{_YS7_BASE}/device/camera/list",
                    data={"accessToken": token, "deviceSerial": serial},
                    timeout=15,
                )
                cd = cr.json()
                channels = (cd.get("data") or []) if cd.get("code") == "200" else []
                if not channels:
                    channels = [{"channelNo": 1, "channelName": ""}]
                for ch in channels:
                    rows.append({
                        "device_serial": serial,
                        "channel_no": int(ch.get("channelNo", 1)),
                        "name": f"{dev_name}-{ch.get('channelName', '')}" if ch.get("channelName") else dev_name,
                        "brand": "ys7",
                    })
            if len(devices) < page_size:
                break
        return rows


# ── 乐橙(IMOU) ─────────────────────────────────────────────

_IMOU_BASE = "https://openapi.lechange.cn:443/openapi"


def _imou_sign(app_id: str, app_secret: str, params: dict) -> tuple:
    """IMOU 签名：nonce+time+md5(secret)"""
    nonce = uuid.uuid4().hex[:8]
    ts = str(int(time.time()))
    sign_str = f"time:{ts},nonce:{nonce},appSecret:{hashlib.md5(app_secret.encode()).hexdigest()}"
    sign = hashlib.md5(sign_str.encode()).hexdigest()
    return nonce, ts, sign


class ImouClient:
    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
    ):
        self.app_id = app_id or os.getenv("IMOU_APP_ID", "")
        self.app_secret = app_secret or os.getenv("IMOU_APP_SECRET", "")

    def _call(self, api_path: str, params: dict) -> dict:
        nonce, ts, sign = _imou_sign(self.app_id, self.app_secret, params)
        body = {
            "system": {
                "ver": "1.0",
                "sign": sign,
                "appId": self.app_id,
                "time": ts,
                "nonce": nonce,
            },
            "params": params,
        }
        r = requests.post(
            f"{_IMOU_BASE}/{api_path}",
            json=body,
            timeout=15,
        )
        try:
            d = r.json()
        except Exception as e:
            return {"error": f"乐橙接口非 JSON: {e}"}
        if not isinstance(d, dict):
            return {"error": f"乐橙接口返回异常: {type(d).__name__}"}
        result = d.get("result") or {}
        if not isinstance(result, dict):
            return {"error": "乐橙接口 result 格式异常"}
        if result.get("code") != "0":
            return {"error": result.get("msg", api_path + " 调用失败")}
        payload = result.get("data")
        return payload if isinstance(payload, dict) else {}

    def get_live_address(self, device_id: str, channel_id: str = "0") -> dict:
        """获取直播地址（HLS）；多通道回退，减轻 channelId 配置错误导致的「token」类报错。"""
        order = []
        for c in (channel_id, "0", "1"):
            cs = str(c)
            if cs not in order:
                order.append(cs)
        last_err = ""
        for ch in order:
            data = self._call("getLiveStreamInfo", {"deviceId": device_id, "channelId": ch})
            if "error" in data:
                last_err = str(data.get("error") or "")
                continue
            if not isinstance(data, dict):
                last_err = "乐橙返回数据格式异常"
                continue
            streams = data.get("streams") or []
            hls_url = ""
            for s in streams:
                if not isinstance(s, dict):
                    continue
                if str(s.get("streamId", "")) == "0":
                    hls_url = (s.get("hls") or "").strip()
                    break
            if not hls_url and streams:
                first = streams[0]
                if isinstance(first, dict):
                    hls_url = (first.get("hls") or "").strip()
            if hls_url:
                return {"url": hls_url}
        return {"error": last_err or "无法获取直播地址"}

    def fetch_device_list(self) -> list:
        """从乐橙平台拉取账号下所有设备+通道"""
        rows = []
        page_size = 20
        for page in range(100):
            data = self._call("listDeviceDetailsByPage", {
                "page": str(page + 1),
                "pageSize": str(page_size),
                "source": "1",
            })
            if "error" in data:
                break
            devices = data.get("deviceList") or []
            if not devices:
                break
            for dev in devices:
                device_id = dev.get("deviceId", "")
                dev_name = dev.get("deviceName") or device_id
                channel_num = int(dev.get("channelNum") or 1)
                for ch in range(channel_num):
                    rows.append({
                        "device_serial": device_id,
                        "channel_no": ch,
                        "name": f"{dev_name}-CH{ch}" if channel_num > 1 else dev_name,
                        "brand": "imou",
                    })
            if len(devices) < page_size:
                break
        return rows

    def get_live_service_urls_grid(self, device_id: str, channel_id: str) -> dict:
        """与 ImouApi::getLiveServiceUrlsGrid 简化版（单路 HLS 填充四格）。"""
        device_id = (device_id or "").strip()
        if not device_id:
            return {"error": "deviceId 为空"}
        ch = str(channel_id if channel_id is not None else "0")
        r = self.get_live_address(device_id, ch)
        if r.get("error"):
            return {"error": r["error"]}
        u = (r.get("url") or "").strip()
        if not u:
            return {"error": "无法获取直播地址"}
        slot = {"hd": u, "sd": u}
        return {"encrypted": dict(slot), "plain": dict(slot)}

    def get_playable_hls_for_device(self, device_id: str, channel_id: str) -> dict:
        g = self.get_live_service_urls_grid(device_id, str(channel_id))
        if "error" in g:
            return {"hls": "", "stream_id": None, "error": g["error"]}
        pl = g.get("plain") or {}
        u = (pl.get("sd") or pl.get("hd") or "").strip()
        return {"hls": u, "stream_id": 1 if u else None}
