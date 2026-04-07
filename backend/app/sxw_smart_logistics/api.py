"""
智能物流 API（食迅 smart_logistics_bind 等价 + 兼容字段 code/status）。
"""
from __future__ import annotations

import os
import time
import requests
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import SXW_MYSQL_HOST, resolve_sxw_mysql_database
from app.database import get_db
from app.deps import get_sxw_db, sxw_supp_code_dep
from app.models import SlCameraDevice, SlVehicleBindBeidou, SlVehicleBindCamera, LogisticsFee
from app.services.logistics_beidou import Gps18Client, find_device_by_macid_in_list, normalize_beidou_macid
from app.services.logistics_camera import Ys7Client, ImouClient
from app.sxw_logistics_models import SxwSlCameraDevice, SxwSlVehicleBindBeidou, SxwSlVehicleBindCamera, SxwVehicle

from app.sxw_smart_logistics.camera_live_builder import build_cameras_live_payload
from app.sxw_smart_logistics.common import (
    bind_mac_uid_strict,
    bind_beidou_row,
    mysql_bind_count_maps,
    plateno_parts,
    resolve_mds,
    resolve_beidou_mac_and_user_id,
    shipper_label,
    vehicle_ids_with_duplicate_beidou_macid,
    vehicle_ids_with_duplicate_vehicle_imei,
    vehicle_or_404,
)
from app.sxw_smart_logistics.history_postprocess import (
    HISTORY_MAX_SPAN_SEC,
    apply_history_post_chain,
    history_demo_points,
    raw_points_to_sxw_points,
)
from app.sxw_smart_logistics import responses

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────

class BeidouBindCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    mds: Optional[str] = None
    unit_id: Optional[str] = None
    login_name: Optional[str] = None
    login_password: Optional[str] = None


class CameraDeviceCreate(BaseModel):
    name: str
    brand: str = "ys7"
    device_serial: str
    channel_no: int = 1
    app_key: Optional[str] = None
    app_secret: Optional[str] = None
    remark: Optional[str] = None


class CameraBindCreate(BaseModel):
    camera_id: Optional[int] = None
    camera_device_id: Optional[int] = None
    position_label: Optional[str] = None

    @model_validator(mode="after")
    def _need_one(self):
        if not (self.camera_id or self.camera_device_id):
            raise ValueError("需要 camera_id 或 camera_device_id")
        return self

    def resolved_camera_row_id(self) -> int:
        return int(self.camera_device_id or self.camera_id or 0)


class PtzRequest(BaseModel):
    direction: int
    speed: int = 1
    action: int = 0


class MirrorRequest(BaseModel):
    mirror_type: int = 0


class SxwPtzBody(BaseModel):
    vehicle_id: int
    camera_device_id: int
    op: str  # start|stop
    direction: int = -1
    speed: int = 1


class SxwMirrorBody(BaseModel):
    vehicle_id: int
    camera_device_id: int
    command: int


class TrackSxwBody(BaseModel):
    start_time: int
    end_time: int
    force_demo: bool = False

    @model_validator(mode="after")
    def _normalize_ts(self):
        if self.start_time > 20000000000:
            object.__setattr__(self, "start_time", int(self.start_time // 1000))
        if self.end_time > 20000000000:
            object.__setattr__(self, "end_time", int(self.end_time // 1000))
        return self


class FeeCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    fee_date: str
    plateno: str = ""
    driver_name: str = ""
    follow_fee: float = 0
    follow_fee2: float = 0
    freight: float = 0
    staff_cost: float = 0
    toll_fee: float = 0
    parking_fee: float = 0
    fixed_cost: float = 0
    kilo: float = 0
    fuel_economy: float = 0
    fine_amount: float = 0
    remark: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, data: Any):
        if isinstance(data, dict) and "fuel_economy" in data:
            fe = data["fuel_economy"]
            if fe == "" or fe is None:
                data["fuel_economy"] = 0
            else:
                data["fuel_economy"] = float(fe)
        return data


def _fee_compute_total(p: FeeCreate) -> float:
    return (
        float(p.follow_fee or 0)
        + float(p.follow_fee2 or 0)
        + float(p.freight or 0)
        + float(p.staff_cost or 0)
        + float(p.toll_fee or 0)
        + float(p.parking_fee or 0)
        + float(p.fixed_cost or 0)
        + float(p.kilo or 0) * float(p.fuel_economy or 0)
        + float(p.fine_amount or 0)
    )


# ── Config / 租户 ─────────────────────────────────────────

@router.get("/config/sxw-tenant")
def sxw_tenant_info(supp_key: Optional[str] = Depends(sxw_supp_code_dep)):
    return responses.ok({
        "mysql_database": resolve_sxw_mysql_database(supp_key),
        "mysql_host": SXW_MYSQL_HOST,
    })


@router.get("/amap-config")
def get_amap_config():
    return responses.ok({
        "key": os.getenv("AMAP_JSAPI_KEY", ""),
        "securityJsCode": os.getenv("AMAP_SECURITY_JSCODE", ""),
    })


# ── 车辆列表（分页可选）───────────────────────────────────

@router.get("/vehicles")
def list_vehicles(
    plateno: Optional[str] = Query(default=None),
    page: Optional[int] = Query(default=None, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1, le=500),
    sxw_db: Session = Depends(get_sxw_db),
):
    q = sxw_db.query(SxwVehicle)
    if plateno:
        q = q.filter(SxwVehicle.plateno.contains(plateno))
    q = q.order_by(SxwVehicle.id)
    total = q.count()

    if page is not None and page_size is not None:
        rows = q.offset((page - 1) * page_size).limit(page_size).all()
    else:
        rows = q.all()

    beidou_map, camera_map = mysql_bind_count_maps(sxw_db)
    dup_mac_vehicles = vehicle_ids_with_duplicate_beidou_macid(sxw_db) | vehicle_ids_with_duplicate_vehicle_imei(
        sxw_db
    )
    result = []
    for v in rows:
        plateno_str = v.plateno or ""
        plateno_short, driver_name = plateno_parts(plateno_str)
        b_count = int(beidou_map.get(v.id, 0))
        c_count = int(camera_map.get(v.id, 0))
        imei_s = (v.imei or "").strip()
        has_bind = b_count > 0
        has_imei_field = bool(imei_s)
        locatable = has_bind or has_imei_field
        result.append({
            "id": v.id,
            "plateno": plateno_short,
            "plateno_raw": plateno_str,
            "car_type": v.car_type,
            "shipper_type": shipper_label(v.shipper_type or 1),
            "driver_name": driver_name,
            "driver_phone": None,
            "imei": v.imei or "",
            "has_beidou_bind": has_bind,
            "has_imei_field": has_imei_field,
            "has_beidou": locatable,
            "beidou_count": 1 if has_bind else 0,
            "beidou_bind_rows": b_count,
            "beidou_mds": resolve_mds(sxw_db, v) or imei_s or None,
            "beidou_macid_conflict": int(v.id) in dup_mac_vehicles,
            "camera_count": c_count,
        })

    if page is not None and page_size is not None:
        return responses.ok({
            "items": result,
            "total": total,
            "page": page,
            "page_size": page_size,
        })
    return responses.ok(result)


@router.get("/vehicles/{vehicle_id}")
def get_vehicle(vehicle_id: int, sxw_db: Session = Depends(get_sxw_db)):
    v = vehicle_or_404(vehicle_id, sxw_db)
    plateno_str = v.plateno or ""
    plateno_short, driver_name = plateno_parts(plateno_str)
    return responses.ok({
        "id": v.id,
        "plateno": plateno_short,
        "plateno_raw": plateno_str,
        "car_type": v.car_type,
        "shipper_type": shipper_label(v.shipper_type or 1),
        "driver_name": driver_name,
        "driver_phone": None,
        "imei": v.imei or "",
    })


# ── 北斗绑定 ─────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/beidou")
def get_beidou_bind(vehicle_id: int, sxw_db: Session = Depends(get_sxw_db), db: Session = Depends(get_db)):
    v = vehicle_or_404(vehicle_id, sxw_db)
    row = bind_beidou_row(sxw_db, vehicle_id)
    local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
    login_name = (local.login_name if local else None) or os.getenv("GPS18_LOGIN_NAME", "")
    if row and (row.macid or "").strip():
        return responses.ok({
            "id": row.id,
            "bind_id": row.id,
            "mds": row.macid,
            "macid": row.macid,
            "unit_id": row.user_id or "",
            "user_id": row.user_id or "",
            "login_name": login_name,
            "source": "mysql",
        })
    if v.imei and str(v.imei).strip():
        return responses.ok({
            "mds": str(v.imei).strip(),
            "macid": str(v.imei).strip(),
            "unit_id": "",
            "user_id": "",
            "login_name": login_name,
            "source": "imei",
        })
    return responses.ok(None)


@router.post("/vehicles/{vehicle_id}/beidou")
def save_beidou_bind(
    vehicle_id: int,
    payload: BeidouBindCreate,
    sxw_db: Session = Depends(get_sxw_db),
    db: Session = Depends(get_db),
):
    vehicle_or_404(vehicle_id, sxw_db)
    mac = (payload.mds or "").strip()
    uid = (payload.unit_id or "").strip()
    if not mac:
        raise HTTPException(status_code=400, detail="请填写设备号（macid）")

    local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
    login_name = (local.login_name if local and local.login_name else None) or os.getenv("GPS18_LOGIN_NAME", "")
    login_password = (local.login_password if local and local.login_password else None) or os.getenv(
        "GPS18_LOGIN_PASSWORD", ""
    )
    try:
        client = Gps18Client(login_name=login_name, login_password=login_password)
        devices = client.get_device_list()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无法校验北斗设备：{e}")

    if find_device_by_macid_in_list(mac, devices) is None:
        raise HTTPException(
            status_code=400,
            detail="当前北斗账号下设备列表中未找到该设备号；请核对 macid/sim_id 是否与「设备管理 → 北斗定位」列表一致，或确认终端已入网",
        )

    mac_norm = normalize_beidou_macid(mac)
    others = sxw_db.execute(
        text("SELECT id, vehicle_id FROM sl_vehicle_bind_beidou WHERE macid=:m"),
        {"m": mac},
    ).mappings().all()
    for r in others:
        if int(r["vehicle_id"]) != int(vehicle_id):
            raise HTTPException(status_code=400, detail="该北斗设备号已绑定其他车辆")

    now = int(time.time())
    ex = sxw_db.execute(
        text("SELECT id FROM sl_vehicle_bind_beidou WHERE vehicle_id=:vid LIMIT 1"),
        {"vid": vehicle_id},
    ).fetchone()
    if ex:
        sxw_db.execute(
            text(
                "UPDATE sl_vehicle_bind_beidou SET macid=:m, user_id=:u, update_user=:uu, update_time=:t "
                "WHERE vehicle_id=:vid"
            ),
            {"m": mac, "u": uid, "uu": "ai-agent", "t": now, "vid": vehicle_id},
        )
    else:
        sxw_db.execute(
            text(
                "INSERT INTO sl_vehicle_bind_beidou(vehicle_id,macid,user_id,update_user,update_time,create_time) "
                "VALUES (:vid,:m,:u,:uu,:t,:t2)"
            ),
            {"vid": vehicle_id, "m": mac, "u": uid, "uu": "ai-agent", "t": now, "t2": now},
        )
    sxw_db.commit()

    if payload.login_name is not None or payload.login_password is not None:
        loc2 = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
        if loc2:
            if payload.login_name is not None:
                loc2.login_name = payload.login_name
            if payload.login_password:
                loc2.login_password = payload.login_password
        else:
            db.add(SlVehicleBindBeidou(
                vehicle_id=vehicle_id,
                mds="",
                unit_id=payload.unit_id,
                login_name=payload.login_name or "",
                login_password=payload.login_password or "",
            ))
        db.commit()
    return responses.ok("保存成功")


@router.delete("/vehicles/{vehicle_id}/beidou")
def detach_beidou(
    vehicle_id: int,
    sxw_db: Session = Depends(get_sxw_db),
    db: Session = Depends(get_db),
):
    sxw_db.execute(text("DELETE FROM sl_vehicle_bind_beidou WHERE vehicle_id=:vid"), {"vid": vehicle_id})
    sxw_db.commit()
    local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
    if local:
        db.delete(local)
        db.commit()
    return responses.ok("解绑成功")


# ── 实时位置（兼容 + 食迅载荷）──────────────────────────

@router.get("/vehicles/{vehicle_id}/location")
def get_realtime_location(
    vehicle_id: int,
    sxw_db: Session = Depends(get_sxw_db),
    db: Session = Depends(get_db),
):
    v = vehicle_or_404(vehicle_id, sxw_db)
    mds = resolve_mds(sxw_db, v)
    if not mds:
        raise HTTPException(status_code=400, detail="该车辆无北斗设备号(未绑定且 vehicle.imei 为空)")
    local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
    login_name = (local.login_name if local and local.login_name else None) or os.getenv("GPS18_LOGIN_NAME", "")
    login_password = (local.login_password if local and local.login_password else None) or os.getenv(
        "GPS18_LOGIN_PASSWORD", ""
    )
    try:
        client = Gps18Client(login_name=login_name, login_password=login_password)
        point = client.get_realtime(mds)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"北斗API调用失败: {e}")
    row_bind = bind_beidou_row(sxw_db, vehicle_id)
    mac_bind = (row_bind.macid or "").strip() if row_bind else ""
    sxw_card = None
    if mac_bind:
        try:
            sxw_card = client.build_realtime_sxw_payload(mac_bind)
        except Exception:
            sxw_card = None
    if isinstance(point, dict) and not point.get("error"):
        point["sxw_realtime"] = sxw_card
    return responses.ok(point)


@router.get("/vehicles/{vehicle_id}/realtime-sxw")
def get_realtime_sxw(
    vehicle_id: int,
    sxw_db: Session = Depends(get_sxw_db),
    db: Session = Depends(get_db),
):
    """与 ajax.php#get_realtime_data 一致：仅绑定 macid，data 为单元素数组。"""
    vehicle_or_404(vehicle_id, sxw_db)
    row = bind_beidou_row(sxw_db, vehicle_id)
    mac = (row.macid or "").strip() if row else ""
    if not mac:
        return responses.err("该车辆未绑定北斗设备", 40001)

    local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
    login_name = (local.login_name if local and local.login_name else None) or os.getenv("GPS18_LOGIN_NAME", "")
    login_password = (local.login_password if local and local.login_password else None) or os.getenv(
        "GPS18_LOGIN_PASSWORD", ""
    )
    try:
        client = Gps18Client(login_name=login_name, login_password=login_password)
        card = client.build_realtime_sxw_payload(mac)
    except Exception as e:
        return responses.err(f"北斗API调用失败: {e}", 40001)
    if not card:
        return responses.err("北斗定位批量列表中未找到该设备号，请核对 macid 或稍后刷新", 40001)
    return responses.ok([card])


# ── 历史轨迹 ─────────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/track")
def get_history_track(
    vehicle_id: int,
    start_time: str = Query(..., description="YYYY-MM-DD HH:MM:SS 北京时间"),
    end_time: str = Query(...),
    sxw_db: Session = Depends(get_sxw_db),
    db: Session = Depends(get_db),
):
    v = vehicle_or_404(vehicle_id, sxw_db)
    mac, uid_bound = resolve_beidou_mac_and_user_id(sxw_db, v)
    if not mac and not uid_bound:
        raise HTTPException(status_code=400, detail="该车辆无北斗设备号(未绑定且 vehicle.imei 为空)")
    tz_name = os.getenv("GPS18_HISTORY_TZ", "Asia/Shanghai")
    try:
        tz = ZoneInfo(tz_name)
        st = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        et = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式应为 YYYY-MM-DD HH:MM:SS")
    if et <= st:
        raise HTTPException(status_code=400, detail="结束时间须大于开始时间")
    max_days = int(os.getenv("GPS18_HISTORY_MAX_DAYS", "90"))
    if (et - st).total_seconds() > max_days * 86400:
        raise HTTPException(status_code=400, detail=f"查询时间跨度不能超过{max_days}天，请缩短区间")

    local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
    login_name = (local.login_name if local and local.login_name else None) or os.getenv("GPS18_LOGIN_NAME", "")
    login_password = (local.login_password if local and local.login_password else None) or os.getenv(
        "GPS18_LOGIN_PASSWORD", ""
    )
    chunk_sec = int(os.getenv("GPS18_HISTORY_CHUNK_SECONDS", str(5 * 86400)))
    try:
        client = Gps18Client(login_name=login_name, login_password=login_password)
        all_points = []
        cur = st
        while cur < et:
            chunk_end = min(cur + timedelta(seconds=chunk_sec), et)
            from_ms = int(cur.timestamp() * 1000)
            to_ms = int(chunk_end.timestamp() * 1000)
            if to_ms > from_ms:
                all_points.extend(client.get_history_track_ms(mac, from_ms, to_ms, uid_bound))
            cur = chunk_end
        all_points = [p for p in all_points if isinstance(p, dict)]
        seen_ms = set()
        merged = []
        for p in sorted(all_points, key=lambda x: int(x.get("time_ms") or 0)):
            tms = int(p.get("time_ms") or 0)
            if tms in seen_ms:
                continue
            seen_ms.add(tms)
            merged.append(p)
        sxw_pts = raw_points_to_sxw_points(merged)
        sxw_pts = apply_history_post_chain(sxw_pts)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"北斗API调用失败: {e}")
    return responses.ok(sxw_pts)


@router.post("/vehicles/{vehicle_id}/track-sxw")
def post_history_track_sxw(
    vehicle_id: int,
    body: TrackSxwBody,
    sxw_db: Session = Depends(get_sxw_db),
    db: Session = Depends(get_db),
):
    """与 ajax.php#get_history_track：Unix 秒、force_demo、PHP 信封。"""
    vehicle_or_404(vehicle_id, sxw_db)
    mac, uid = bind_mac_uid_strict(sxw_db, vehicle_id)
    st, et = body.start_time, body.end_time

    def _debug():
        return {
            "vehicle_id": vehicle_id,
            "macid": mac,
            "user_id": uid,
            "start_time": st,
            "end_time": et,
            "force_demo": "1" if body.force_demo else "0",
        }

    if st <= 0 or et <= 0 or et < st:
        return {**responses.err("参数错误", 40001), "content": _debug()}
    if (et - st) > HISTORY_MAX_SPAN_SEC:
        return {**responses.err("查询跨度不能超过 10 天，请缩短时间段", 40001), "content": _debug()}
    if not mac and not uid:
        return {**responses.err("该车辆未绑定北斗设备", 40001), "content": _debug()}

    if body.force_demo:
        demo = history_demo_points(st, et)
        return {
            **responses.ok({
                "points": demo,
                "is_demo": True,
                "demo_forced": True,
                "message": "已勾选「仅演示」：未请求北斗定位服务，以下为演示轨迹（非真实数据）。查真实轨迹请取消勾选后重试。",
                "notice": "",
            }),
            "content": _debug(),
        }

    local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == vehicle_id).first()
    login_name = (local.login_name if local and local.login_name else None) or os.getenv("GPS18_LOGIN_NAME", "")
    login_password = (local.login_password if local and local.login_password else None) or os.getenv(
        "GPS18_LOGIN_PASSWORD", ""
    )
    chunk_sec = int(os.getenv("GPS18_HISTORY_CHUNK_SECONDS", str(5 * 86400)))
    try:
        client = Gps18Client(login_name=login_name, login_password=login_password)
        from_ms = int(st) * 1000
        to_ms = int(et) * 1000
        all_points = []
        cur_ms = from_ms
        while cur_ms < to_ms:
            chunk_end_ms = min(cur_ms + chunk_sec * 1000, to_ms)
            if chunk_end_ms > cur_ms:
                all_points.extend(client.fetch_history_track_ms(mac, uid, cur_ms, chunk_end_ms))
            cur_ms = chunk_end_ms
        all_points = [p for p in all_points if isinstance(p, dict)]
        seen_ms = set()
        merged = []
        for p in sorted(all_points, key=lambda x: int(x.get("time_ms") or 0)):
            tms = int(p.get("time_ms") or 0)
            if tms in seen_ms:
                continue
            seen_ms.add(tms)
            merged.append(p)
        sxw_pts = raw_points_to_sxw_points(merged)
        sxw_pts = apply_history_post_chain(sxw_pts)
    except Exception as e:
        return {**responses.err(str(e), 40001), "content": _debug(), "raw": None}

    if not sxw_pts:
        return {
            **responses.ok({
                "points": [],
                "is_demo": False,
                "message": "",
                "notice": "所选时段内暂无北斗定位轨迹数据，可更换时间范围后重试。",
            }),
            "content": _debug(),
        }
    return {
        **responses.ok({
            "points": sxw_pts,
            "is_demo": False,
            "message": "",
            "notice": "",
        }),
        "content": _debug(),
    }


# ── 摄像头设备库 ────────────────────────────────────────

@router.get("/devices/cameras")
def list_camera_devices(sxw_db: Session = Depends(get_sxw_db)):
    q = sxw_db.query(SxwSlCameraDevice).filter(SxwSlCameraDevice.status == 1).order_by(SxwSlCameraDevice.id.desc())
    cameras = q.all()
    return responses.ok([
        {
            "id": c.id,
            "name": c.device_name or "",
            "brand": (c.camera_source or "ys7").lower(),
            "device_serial": c.device_guid or "",
            "channel_no": int(c.channel_id or 1),
            "remark": "",
        }
        for c in cameras
    ])


@router.post("/devices/cameras")
def create_camera_device(payload: CameraDeviceCreate, sxw_db: Session = Depends(get_sxw_db)):
    now = int(time.time())
    src = "ys7" if payload.brand == "ys7" else "imou"
    sxw_db.execute(
        text(
            "INSERT INTO sl_camera_device(device_name,device_guid,channel_id,device_sn,device_model,"
            "status,camera_source,update_user,update_time,create_time) "
            "VALUES (:n,:g,:ch,:sn,:model,1,:src,:uu,:t,:t2)"
        ),
        {
            "n": payload.name,
            "g": payload.device_serial,
            "ch": payload.channel_no,
            "sn": "",
            "model": "",
            "src": src,
            "uu": "ai-agent",
            "t": now,
            "t2": now,
        },
    )
    sxw_db.commit()
    rid = sxw_db.execute(text("SELECT LAST_INSERT_ID() AS id")).scalar()
    return responses.ok({"id": int(rid or 0)})


@router.delete("/devices/cameras/{camera_id}")
def delete_camera_device(camera_id: int, sxw_db: Session = Depends(get_sxw_db)):
    n = sxw_db.execute(
        text("SELECT COUNT(*) FROM sl_vehicle_bind_camera WHERE camera_device_id=:cid"),
        {"cid": camera_id},
    ).scalar()
    if int(n or 0) > 0:
        raise HTTPException(status_code=400, detail="该摄像头已绑定车辆，请先解绑")
    sxw_db.execute(text("DELETE FROM sl_camera_device WHERE id=:id"), {"id": camera_id})
    sxw_db.commit()
    return responses.ok("ok")


# ── 摄像头绑定 ───────────────────────────────────────────

@router.get("/vehicles/{vehicle_id}/cameras")
def list_vehicle_cameras(vehicle_id: int, sxw_db: Session = Depends(get_sxw_db)):
    vehicle_or_404(vehicle_id, sxw_db)
    binds = (
        sxw_db.query(SxwSlVehicleBindCamera)
        .filter(SxwSlVehicleBindCamera.vehicle_id == vehicle_id)
        .order_by(SxwSlVehicleBindCamera.id.desc())
        .all()
    )
    result = []
    for b in binds:
        cam = sxw_db.query(SxwSlCameraDevice).filter(SxwSlCameraDevice.id == b.camera_device_id).first()
        if not cam:
            continue
        brand = (cam.camera_source or "ys7").lower()
        result.append({
            "bind_id": b.id,
            "camera_id": cam.id,
            "camera_device_id": cam.id,
            "name": cam.device_name or "",
            "device_name": cam.device_name or "",
            "brand": brand,
            "device_serial": cam.device_guid or "",
            "device_guid": cam.device_guid or "",
            "channel_id": int(cam.channel_id or 1),
            "channel_no": int(cam.channel_id or 1),
            "device_model": "",
            "position_label": "",
        })
    return responses.ok(result)


@router.post("/vehicles/{vehicle_id}/cameras")
def attach_camera(vehicle_id: int, payload: CameraBindCreate, sxw_db: Session = Depends(get_sxw_db)):
    vehicle_or_404(vehicle_id, sxw_db)
    cid = payload.resolved_camera_row_id()
    cam = sxw_db.query(SxwSlCameraDevice).filter(SxwSlCameraDevice.id == cid).first()
    if not cam:
        raise HTTPException(status_code=404, detail="设备不存在")
    ex = sxw_db.execute(
        text("SELECT id FROM sl_vehicle_bind_camera WHERE camera_device_id=:c LIMIT 1"),
        {"c": cid},
    ).fetchone()
    if ex:
        raise HTTPException(status_code=400, detail="该设备已绑定其他车辆，请先解绑后再操作")
    now = int(time.time())
    sxw_db.execute(
        text(
            "INSERT INTO sl_vehicle_bind_camera(vehicle_id,camera_device_id,update_user,update_time,create_time) "
            "VALUES (:vid,:cid,:uu,:t,:t2)"
        ),
        {"vid": vehicle_id, "cid": cid, "uu": "ai-agent", "t": now, "t2": now},
    )
    sxw_db.commit()
    return responses.ok("绑定成功")


@router.delete("/vehicles/{vehicle_id}/cameras/{bind_id}")
def detach_camera(vehicle_id: int, bind_id: int, sxw_db: Session = Depends(get_sxw_db)):
    sxw_db.execute(
        text("DELETE FROM sl_vehicle_bind_camera WHERE id=:bid AND vehicle_id=:vid"),
        {"bid": bind_id, "vid": vehicle_id},
    )
    sxw_db.commit()
    return responses.ok("解绑成功")


@router.get("/vehicles/{vehicle_id}/cameras/live")
def get_cameras_live(vehicle_id: int, sxw_db: Session = Depends(get_sxw_db)):
    vehicle_or_404(vehicle_id, sxw_db)
    rows = build_cameras_live_payload(sxw_db, vehicle_id)
    return responses.ok(rows)


# ── 云台 / 镜像（食迅 POST 语义 + 旧 REST）───────────────

def _ys7_bound_row(sxw_db: Session, vehicle_id: int, camera_device_id: int):
    return sxw_db.execute(
        text(
            "SELECT d.device_guid, d.channel_id, d.camera_source, d.status "
            "FROM sl_vehicle_bind_camera b "
            "INNER JOIN sl_camera_device d ON b.camera_device_id = d.id "
            "WHERE b.vehicle_id = :vid AND b.camera_device_id = :cid "
            "LIMIT 1"
        ),
        {"vid": vehicle_id, "cid": camera_device_id},
    ).mappings().first()


@router.post("/sxw/cameras/ptz")
def sxw_camera_ptz(body: SxwPtzBody, sxw_db: Session = Depends(get_sxw_db)):
    row = _ys7_bound_row(sxw_db, body.vehicle_id, body.camera_device_id)
    if not row or int(row.get("status") or 0) != 1:
        return responses.err("未绑定该摄像头或设备已禁用", 40003)
    if (str(row.get("camera_source") or "").strip().lower() != "ys7"):
        return responses.err("仅萤石设备支持云台", 40004)
    serial = (str(row.get("device_guid") or "").strip())
    if not serial:
        return responses.err("设备序列号为空", 40005)
    ch = int(row.get("channel_id") or 1)
    if ch < 1:
        ch = 1
    client = Ys7Client(app_key=os.getenv("YS7_APP_KEY", ""), app_secret=os.getenv("YS7_APP_SECRET", ""))
    if body.op == "stop":
        r = requests_post_ptz_stop(client, serial, ch)
    else:
        direction = int(body.direction)
        if direction < 0 or direction > 16 or (direction > 11 and direction < 16):
            return responses.err("direction 无效", 40001)
        speed = int(body.speed)
        if speed < 1:
            speed = 1
        if speed > 2:
            speed = 2
        r = requests_post_ptz_start(client, serial, ch, direction, speed)
    code = str(r.get("code", ""))
    if code != "200":
        return responses.err(r.get("msg", "萤石错误"), 500)
    return responses.ok("ok")


def requests_post_ptz_start(client: Ys7Client, serial: str, ch: int, direction: int, speed: int) -> dict:
    tok = client._get_token()
    r = requests.post(
        "https://open.ys7.com/api/lapp/device/ptz/start",
        data={
            "accessToken": tok,
            "deviceSerial": serial,
            "channelNo": ch,
            "direction": direction,
            "speed": speed,
        },
        timeout=10,
    )
    return r.json()


def requests_post_ptz_stop(client: Ys7Client, serial: str, ch: int) -> dict:
    tok = client._get_token()
    r = requests.post(
        "https://open.ys7.com/api/lapp/device/ptz/stop",
        data={"accessToken": tok, "deviceSerial": serial, "channelNo": ch},
        timeout=10,
    )
    return r.json()


@router.post("/sxw/cameras/mirror")
def sxw_camera_mirror(body: SxwMirrorBody, sxw_db: Session = Depends(get_sxw_db)):
    if body.command < 0 or body.command > 3:
        return responses.err("command 应为 0–3", 40001)
    row = _ys7_bound_row(sxw_db, body.vehicle_id, body.camera_device_id)
    if not row or int(row.get("status") or 0) != 1:
        return responses.err("未绑定该摄像头或设备已禁用", 40003)
    if (str(row.get("camera_source") or "").strip().lower() != "ys7"):
        return responses.err("仅萤石设备支持画面镜像", 40004)
    serial = (str(row.get("device_guid") or "").strip())
    if not serial:
        return responses.err("设备序列号为空", 40005)
    ch = int(row.get("channel_id") or 1)
    if ch < 1:
        ch = 1
    client = Ys7Client(app_key=os.getenv("YS7_APP_KEY", ""), app_secret=os.getenv("YS7_APP_SECRET", ""))
    r = client.ptz_mirror_command(serial, ch, body.command)
    if str(r.get("code", "")) != "200":
        return responses.err(r.get("msg", "萤石错误"), 500)
    return responses.ok("ok")


@router.post("/cameras/{camera_id}/ptz")
def ptz_control(camera_id: int, payload: PtzRequest, sxw_db: Session = Depends(get_sxw_db)):
    cam = sxw_db.query(SxwSlCameraDevice).filter(SxwSlCameraDevice.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="摄像头设备不存在")
    if (cam.camera_source or "").lower() != "ys7":
        raise HTTPException(status_code=400, detail="仅萤石设备支持云台控制")
    client = Ys7Client(app_key=os.getenv("YS7_APP_KEY", ""), app_secret=os.getenv("YS7_APP_SECRET", ""))
    result = client.ptz_control(
        cam.device_guid or "", int(cam.channel_id or 1),
        payload.direction, payload.speed, payload.action,
    )
    return responses.ok(result)


@router.post("/cameras/{camera_id}/mirror")
def set_mirror(camera_id: int, payload: MirrorRequest, sxw_db: Session = Depends(get_sxw_db)):
    cam = sxw_db.query(SxwSlCameraDevice).filter(SxwSlCameraDevice.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="摄像头设备不存在")
    if (cam.camera_source or "").lower() != "ys7":
        raise HTTPException(status_code=400, detail="仅萤石设备支持画面翻转")
    client = Ys7Client(app_key=os.getenv("YS7_APP_KEY", ""), app_secret=os.getenv("YS7_APP_SECRET", ""))
    r = client.ptz_mirror_command(cam.device_guid or "", int(cam.channel_id or 1), payload.mirror_type)
    return responses.ok({"code": r.get("code"), "msg": r.get("msg")})


# ── 同步 / 费用 ─────────────────────────────────────────

@router.post("/cameras/sync/ys7")
def sync_ys7_cameras(db: Session = Depends(get_db)):
    client = Ys7Client()
    try:
        rows = client.fetch_device_list()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"萤石同步失败: {e}")
    inserted, updated = 0, 0
    for row in rows:
        existing = db.query(SlCameraDevice).filter(
            SlCameraDevice.device_serial == row["device_serial"],
            SlCameraDevice.channel_no == row["channel_no"],
            SlCameraDevice.brand == "ys7",
        ).first()
        if existing:
            existing.name = row["name"]
            updated += 1
        else:
            db.add(SlCameraDevice(**row))
            inserted += 1
    db.commit()
    return responses.ok({"inserted": inserted, "updated": updated, "total": len(rows)})


@router.post("/cameras/sync/imou")
def sync_imou_cameras(db: Session = Depends(get_db)):
    client = ImouClient()
    try:
        rows = client.fetch_device_list()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"乐橙同步失败: {e}")
    inserted, updated = 0, 0
    for row in rows:
        existing = db.query(SlCameraDevice).filter(
            SlCameraDevice.device_serial == row["device_serial"],
            SlCameraDevice.channel_no == row["channel_no"],
            SlCameraDevice.brand == "imou",
        ).first()
        if existing:
            existing.name = row["name"]
            updated += 1
        else:
            db.add(SlCameraDevice(**row))
            inserted += 1
    db.commit()
    return responses.ok({"inserted": inserted, "updated": updated, "total": len(rows)})


@router.post("/sync/sxw-bindings")
def sync_sxw_bindings_to_sqlite(sxw_db: Session = Depends(get_sxw_db), db: Session = Depends(get_db)):
    stats = {"cameras_upserted": 0, "beidou_upserted": 0, "camera_binds": 0}
    for cam in sxw_db.query(SxwSlCameraDevice).all():
        brand = (cam.camera_source or "ys7").lower()
        ch = int(cam.channel_id or 1)
        guid = cam.device_guid or ""
        existing = db.query(SlCameraDevice).filter(
            SlCameraDevice.brand == brand,
            SlCameraDevice.device_serial == guid,
            SlCameraDevice.channel_no == ch,
        ).first()
        if existing:
            existing.name = cam.device_name or existing.name
        else:
            db.add(SlCameraDevice(
                name=cam.device_name or guid,
                brand=brand,
                device_serial=guid,
                channel_no=ch,
            ))
            stats["cameras_upserted"] += 1
    db.commit()

    key_to_local_id = {}
    for lc in db.query(SlCameraDevice).all():
        key_to_local_id[(lc.brand, lc.device_serial, lc.channel_no)] = lc.id

    for row in sxw_db.query(SxwSlVehicleBindBeidou).all():
        local = db.query(SlVehicleBindBeidou).filter(SlVehicleBindBeidou.vehicle_id == row.vehicle_id).first()
        mac = (row.macid or "").strip()
        uid = (row.user_id or "") or None
        if local:
            local.mds = mac
            local.unit_id = uid
        else:
            db.add(SlVehicleBindBeidou(vehicle_id=row.vehicle_id, mds=mac, unit_id=uid))
            stats["beidou_upserted"] += 1
    db.commit()

    for bind in sxw_db.query(SxwSlVehicleBindCamera).all():
        cam = sxw_db.query(SxwSlCameraDevice).filter(SxwSlCameraDevice.id == bind.camera_device_id).first()
        if not cam:
            continue
        brand = (cam.camera_source or "ys7").lower()
        key = (brand, cam.device_guid or "", int(cam.channel_id or 1))
        local_cam_id = key_to_local_id.get(key)
        if not local_cam_id:
            continue
        ex = db.query(SlVehicleBindCamera).filter(
            SlVehicleBindCamera.vehicle_id == bind.vehicle_id,
            SlVehicleBindCamera.camera_id == local_cam_id,
        ).first()
        if not ex:
            db.add(SlVehicleBindCamera(
                vehicle_id=bind.vehicle_id,
                camera_id=local_cam_id,
                position_label="",
            ))
            stats["camera_binds"] += 1
    db.commit()
    return responses.ok(stats)


@router.get("/fees")
def list_fees(
    plateno: Optional[str] = None,
    driver_name: Optional[str] = None,
    fee_date_start: Optional[str] = None,
    fee_date_end: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(LogisticsFee)
    if plateno:
        q = q.filter(LogisticsFee.plateno.contains(plateno))
    if driver_name:
        q = q.filter(LogisticsFee.driver_name.contains(driver_name))
    if fee_date_start:
        q = q.filter(LogisticsFee.fee_date >= fee_date_start)
    if fee_date_end:
        q = q.filter(LogisticsFee.fee_date <= fee_date_end)
    rows = q.order_by(LogisticsFee.id.desc()).all()
    return responses.ok([
        {
            "id": f.id,
            "fee_date": f.fee_date,
            "plateno": f.plateno,
            "driver_name": f.driver_name,
            "follow_fee": f.follow_fee,
            "follow_fee2": f.follow_fee2,
            "freight": f.freight,
            "staff_cost": f.staff_cost,
            "toll_fee": f.toll_fee,
            "parking_fee": f.parking_fee,
            "fixed_cost": f.fixed_cost,
            "kilo": f.kilo,
            "fuel_economy": f.fuel_economy,
            "fine_amount": f.fine_amount,
            "total": f.total,
            "remark": f.remark,
        }
        for f in rows
    ])


@router.post("/fees")
def create_fee(payload: FeeCreate, db: Session = Depends(get_db)):
    total = _fee_compute_total(payload)
    db.add(LogisticsFee(
        fee_date=payload.fee_date,
        plateno=payload.plateno,
        driver_name=payload.driver_name,
        follow_fee=payload.follow_fee,
        follow_fee2=payload.follow_fee2,
        freight=payload.freight,
        staff_cost=payload.staff_cost,
        toll_fee=payload.toll_fee,
        parking_fee=payload.parking_fee,
        fixed_cost=payload.fixed_cost,
        kilo=payload.kilo,
        fuel_economy=payload.fuel_economy,
        fine_amount=payload.fine_amount,
        total=total,
        remark=payload.remark,
    ))
    db.commit()
    return responses.ok("ok")


@router.delete("/fees/{fee_id}")
def delete_fee(fee_id: int, db: Session = Depends(get_db)):
    f = db.query(LogisticsFee).filter(LogisticsFee.id == fee_id).first()
    if f:
        db.delete(f)
        db.commit()
    return responses.ok("ok")
