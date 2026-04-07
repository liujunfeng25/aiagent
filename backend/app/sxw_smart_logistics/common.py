"""智能物流：车辆与绑定查询（SXW MySQL）。"""
from collections import defaultdict
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.sxw_logistics_models import (
    SxwSlVehicleBindBeidou,
    SxwSlVehicleBindCamera,
    SxwVehicle,
)


def vehicle_or_404(vehicle_id: int, sxw_db: Session) -> SxwVehicle:
    v = sxw_db.query(SxwVehicle).filter(SxwVehicle.id == vehicle_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="车辆不存在")
    return v


def shipper_label(t: int) -> str:
    return {1: "自有", 2: "外包"}.get(t, str(t))


def mysql_bind_count_maps(sxw_db: Session) -> Tuple[dict, dict]:
    beidou_rows = (
        sxw_db.query(SxwSlVehicleBindBeidou.vehicle_id, func.count(SxwSlVehicleBindBeidou.id))
        .group_by(SxwSlVehicleBindBeidou.vehicle_id)
        .all()
    )
    camera_rows = (
        sxw_db.query(SxwSlVehicleBindCamera.vehicle_id, func.count(SxwSlVehicleBindCamera.id))
        .group_by(SxwSlVehicleBindCamera.vehicle_id)
        .all()
    )
    return dict(beidou_rows), dict(camera_rows)


def normalize_beidou_macid(mac: Optional[str]) -> str:
    s = (mac or "").strip()
    if not s:
        return ""
    return s.lstrip("0") or s


def vehicle_ids_with_duplicate_vehicle_imei(sxw_db: Session) -> set:
    rows = sxw_db.query(SxwVehicle.id, SxwVehicle.imei).all()
    by_imei: dict = defaultdict(list)
    for vid, imei in rows:
        key = normalize_beidou_macid(str(imei).strip() if imei else "")
        if key:
            by_imei[key].append(int(vid))
    bad: set = set()
    for ids in by_imei.values():
        if len(ids) > 1:
            bad.update(ids)
    return bad


def vehicle_ids_with_duplicate_beidou_macid(sxw_db: Session) -> set:
    rows = (
        sxw_db.query(SxwSlVehicleBindBeidou.vehicle_id, SxwSlVehicleBindBeidou.macid)
        .filter(
            SxwSlVehicleBindBeidou.macid.isnot(None),
            SxwSlVehicleBindBeidou.macid != "",
        )
        .all()
    )
    by_mac: dict = defaultdict(list)
    for vid, mac in rows:
        key = normalize_beidou_macid(mac)
        if key:
            by_mac[key].append(int(vid))
    bad: set = set()
    for ids in by_mac.values():
        if len(ids) > 1:
            bad.update(ids)
    return bad


def plateno_parts(plateno_str: str) -> Tuple[str, str]:
    raw = plateno_str or ""
    if "-" in raw:
        a, b = raw.split("-", 1)
        return a, b
    return raw, ""


def resolve_mds(sxw_db: Session, v: SxwVehicle) -> Optional[str]:
    bind = (
        sxw_db.query(SxwSlVehicleBindBeidou.macid)
        .filter(SxwSlVehicleBindBeidou.vehicle_id == v.id)
        .first()
    )
    if bind and bind[0] and str(bind[0]).strip():
        return str(bind[0]).strip()
    if v.imei and str(v.imei).strip():
        return str(v.imei).strip()
    return None


def bind_beidou_row(sxw_db: Session, vehicle_id: int) -> Optional[SxwSlVehicleBindBeidou]:
    return (
        sxw_db.query(SxwSlVehicleBindBeidou)
        .filter(SxwSlVehicleBindBeidou.vehicle_id == vehicle_id)
        .first()
    )


def bind_mac_uid_strict(sxw_db: Session, vehicle_id: int) -> Tuple[str, str]:
    """仅绑定表，与 PHP get_history_track 一致（不用 vehicle.imei 兜底）。"""
    row = bind_beidou_row(sxw_db, vehicle_id)
    if not row:
        return "", ""
    return (row.macid or "").strip(), (row.user_id or "").strip()


def resolve_beidou_mac_and_user_id(sxw_db: Session, v: SxwVehicle) -> Tuple[str, str]:
    """绑定表 + imei 兜底（历史查询兼容旧数据）。"""
    mac, uid = bind_mac_uid_strict(sxw_db, v.id)
    if not mac and v.imei and str(v.imei).strip():
        mac = str(v.imei).strip()
    return mac, uid
