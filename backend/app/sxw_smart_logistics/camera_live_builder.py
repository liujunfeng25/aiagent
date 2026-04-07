"""与 ajax.php#get_vehicle_cameras_live 一致的直播载荷生成。"""
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.logistics_camera import Ys7Client, ImouClient


def _ys7_m3u8_from_ezopen(
    base: dict,
    ys7: Ys7Client,
    serial: str,
    channel_id: str,
    ys7_ez: bool,
    ys7_tok: str,
) -> None:
    """
    EZOpen 的 ezopen:// 无法在浏览器 <video> 直接播放；在仍使用 EZOpen 配置时，
    并行拉取萤石 HLS(m3u8) 填入 hls，原地址写入 ezopen_url 备用。
    """
    if not ys7_ez or base.get("camera_source") != "ys7":
        return
    raw = (base.get("hls") or "").strip()
    if not raw.lower().startswith("ezopen://"):
        return
    ch_int = int(channel_id) if str(channel_id).isdigit() else 1
    if ch_int < 1:
        ch_int = 1
    h_hd = ys7.get_live_address_hls(serial, ch_int, 1)
    h_sd = ys7.get_live_address_hls(serial, ch_int, 2) or h_hd
    pick = (h_sd or h_hd or "").strip()
    if not pick or pick.lower().startswith("ezopen://"):
        return
    base["ezopen_url"] = raw
    base["hls"] = pick
    base["ys7_play_mode"] = "hls"
    base["ys7_access_token"] = ys7_tok
    sd_pl, hd_pl = (h_sd or ""), (h_hd or "")
    if sd_pl and pick == sd_pl:
        base["stream_id"] = 1
    elif hd_pl and pick == hd_pl:
        base["stream_id"] = 0
    else:
        base["stream_id"] = None
    ht = (hd_pl or "").strip()
    base["hls_hd_toggle"] = ht if ht and ht != pick else ""


def _maybe_inject_hls_instead_of_ezopen(
    base: dict,
    ys7_client: Ys7Client,
    device_id: str,
    channel_id: str,
    ys7_ez: bool,
    ys7_tok: str,
) -> None:
    """
    与食迅 PHP 默认一致：保留 ezopen:// + 前端 EZUIKit（支持 H.265）。
    仅当 YS7_BROWSER_HLS_FALLBACK=1 时才改填 m3u8 给原生 <video>（设备须 H.264）。
    """
    if os.getenv("YS7_BROWSER_HLS_FALLBACK", "0").strip() != "1":
        return
    _ys7_m3u8_from_ezopen(base, ys7_client, device_id, channel_id, ys7_ez, ys7_tok)


def build_cameras_live_payload(sxw_db: Session, vehicle_id: int) -> list:
    rows = sxw_db.execute(
        text(
            "select d.id as camera_device_id, d.device_name, d.device_guid, d.channel_id, d.camera_source "
            "from sl_vehicle_bind_camera b "
            "inner join sl_camera_device d on b.camera_device_id = d.id "
            "where b.vehicle_id = :vid and d.status = 1 "
            "order by b.id desc"
        ),
        {"vid": vehicle_id},
    ).mappings().all()

    ys7_client = Ys7Client()
    ys7_ez = Ys7Client.live_use_ezopen()
    ys7_tok = ""
    if ys7_ez:
        try:
            ys7_tok = ys7_client._get_token()
        except Exception:
            ys7_tok = ""

    out = []
    for r in rows:
        device_id = (str(r["device_guid"]).strip() if r.get("device_guid") else "")
        ch_raw = r.get("channel_id")
        channel_id = str(ch_raw) if ch_raw is not None and str(ch_raw) != "" else "0"
        cam_src = (str(r["camera_source"]).strip().lower() if r.get("camera_source") else "imou") or "imou"
        base = {
            "camera_device_id": int(r["camera_device_id"]),
            "device_name": r.get("device_name") or "",
            "device_guid": device_id,
            "channel_id": channel_id,
            "camera_source": cam_src,
        }
        if not device_id:
            base["error"] = "未配置设备序列号（device_guid）"
            out.append(base)
            continue

        ch_int = 1
        if cam_src == "ys7":
            client = ys7_client
            try:
                ch_int = int(channel_id) if str(channel_id).isdigit() else 1
                if ch_int < 1:
                    ch_int = 1
                grid = client.get_live_service_urls_grid(device_id, ch_int)
            except Exception as e:
                grid = {"error": str(e)}
        else:
            client = ImouClient()
            try:
                grid = client.get_live_service_urls_grid(device_id, channel_id)
            except Exception as e:
                grid = {"error": str(e)}

        if "error" not in grid:
            enc = grid.get("encrypted") or {}
            pl = grid.get("plain") or {}
            base["live_urls"] = {
                "plain": {"hd": pl.get("hd") or "", "sd": pl.get("sd") or ""},
                "encrypted": {"hd": enc.get("hd") or "", "sd": enc.get("sd") or ""},
            }
            default = (pl.get("sd") or "").strip() or ""
            if not default:
                default = (
                    (pl.get("hd") or "").strip()
                    or (enc.get("sd") or "").strip()
                    or (enc.get("hd") or "").strip()
                )
            hd_toggle = (pl.get("hd") or "").strip() or (enc.get("hd") or "").strip()
            if hd_toggle and hd_toggle != default:
                base["hls_hd_toggle"] = hd_toggle
            else:
                base["hls_hd_toggle"] = ""
            if default:
                base["hls"] = default
                sd_pl, hd_pl = (pl.get("sd") or ""), (pl.get("hd") or "")
                if sd_pl and default == sd_pl:
                    base["stream_id"] = 1
                elif hd_pl and default == hd_pl:
                    base["stream_id"] = 0
                else:
                    base["stream_id"] = None
                if cam_src == "ys7":
                    base["ys7_play_mode"] = "ezuikit" if ys7_ez else "hls"
                    if ys7_ez:
                        base["ys7_access_token"] = ys7_tok
                    _maybe_inject_hls_instead_of_ezopen(
                        base, ys7_client, device_id, str(ch_int), ys7_ez, ys7_tok
                    )
                out.append(base)
                continue

        # fallback playable hls
        if cam_src == "ys7":
            try:
                ch_int = int(channel_id) if str(channel_id).isdigit() else 1
                if ch_int < 1:
                    ch_int = 1
                play = ys7_client.get_playable_hls_for_device(device_id, ch_int)
            except Exception as e:
                play = {"error": str(e)}
        else:
            try:
                play = client.get_playable_hls_for_device(device_id, channel_id)
            except Exception as e:
                play = {"error": str(e)}

        if play.get("error"):
            base["error"] = grid.get("error", play.get("error"))
            out.append(base)
            continue
        base["hls"] = play.get("hls") or ""
        base["stream_id"] = play.get("stream_id")
        if cam_src == "ys7":
            base["ys7_play_mode"] = "ezuikit" if ys7_ez else "hls"
            if ys7_ez:
                base["ys7_access_token"] = ys7_tok
            _maybe_inject_hls_instead_of_ezopen(
                base, ys7_client, device_id, str(ch_int), ys7_ez, ys7_tok
            )
        out.append(base)
    return out
