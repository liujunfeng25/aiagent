# 今日 GMV 增量轮询 + WebSocket 广播（零 DDL）。单进程单循环。
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Any, Optional

import pymysql
from fastapi import WebSocket, WebSocketDisconnect
from zoneinfo import ZoneInfo

from app.business_insights import schema as S
from app.services.business_mysql import resolve_business_mysql
from app.services.db_connector import get_connection

logger = logging.getLogger(__name__)
_TZ = ZoneInfo("Asia/Shanghai")


@dataclass
class _Watermark:
    add_time: int = 0
    order_id: int = 0


def _day_bounds() -> tuple[int, int]:
    day = datetime.now(_TZ).date()
    t0 = int(datetime.combine(day, time.min, tzinfo=_TZ).timestamp())
    t1 = int(datetime.combine(day, time(23, 59, 59), tzinfo=_TZ).timestamp())
    return t0, t1


@dataclass
class LiveGmvHub:
    clients: set[WebSocket] = field(default_factory=set)
    watermark: _Watermark = field(default_factory=_Watermark)
    backorder_watermark_id: int = 0
    cumulative_gmv: float = 0.0
    cumulative_orders: int = 0
    today_t0: int = 0
    initialized: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    task: Optional[asyncio.Task] = None
    started: bool = False

    async def handle(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self.lock:
            self.clients.add(websocket)
        snap = {
            "type": "snapshot",
            "cumulative_gmv": round(self.cumulative_gmv, 2),
            "order_count": self.cumulative_orders,
            "watermark_add_time": self.watermark.add_time,
            "watermark_id": self.watermark.order_id,
            "today_t0": self.today_t0,
            "initialized": self.initialized,
        }
        try:
            await websocket.send_text(json.dumps(snap, ensure_ascii=False))
        except Exception:
            pass
        try:
            while True:
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                except asyncio.TimeoutError:
                    try:
                        await websocket.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        except Exception:
            pass
        finally:
            async with self.lock:
                self.clients.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        txt = json.dumps(payload, ensure_ascii=False)
        dead: list[WebSocket] = []
        async with self.lock:
            snapshot = list(self.clients)
        for ws in snapshot:
            try:
                await ws.send_text(txt)
            except Exception:
                dead.append(ws)
        if dead:
            async with self.lock:
                for ws in dead:
                    self.clients.discard(ws)

    def _sync_init_from_db(self) -> None:
        cfg = resolve_business_mysql()
        if not cfg:
            return
        t0, t1_day = _day_bounds()
        now_ts = min(int(datetime.now(_TZ).timestamp()), t1_day)
        ot, ta, pk = S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL, S.ORDERS_PK_COL
        try:
            conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
        except pymysql.MySQLError as e:
            logger.warning("live_gmv: connect fail %s", e)
            return
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COALESCE(SUM(`{ta}`), 0) AS gmv, COUNT(*) AS cnt
                    FROM `{S.ORDERS_TABLE}`
                    WHERE `{ot}` >= %s AND `{ot}` <= %s
                    """,
                    (t0, now_ts),
                )
                row = dict(cur.fetchone() or {})
                self.cumulative_gmv = float(row.get("gmv") or 0)
                self.cumulative_orders = int(row.get("cnt") or 0)
                self.today_t0 = t0
                cur.execute(
                    f"""
                    SELECT `{ot}` AS add_time, `{pk}` AS oid
                    FROM `{S.ORDERS_TABLE}`
                    WHERE `{ot}` >= %s AND `{ot}` <= %s
                    ORDER BY `{ot}` DESC, `{pk}` DESC
                    LIMIT 1
                    """,
                    (t0, now_ts),
                )
                last = cur.fetchone()
                if last:
                    last = dict(last)
                    self.watermark = _Watermark(
                        int(last["add_time"]),
                        int(last["oid"]),
                    )
                else:
                    self.watermark = _Watermark(t0, 0)
                b_pk, b_t = S.BACKORDER_PK_COL, S.BACKORDER_TIME_COL
                b_tbl = S.BACKORDER_TABLE
                cur.execute(
                    f"""
                    SELECT COALESCE(MAX(`{b_pk}`), 0) AS mid
                    FROM `{b_tbl}`
                    WHERE `{b_t}` >= %s AND `{b_t}` <= %s
                    """,
                    (t0, now_ts),
                )
                self.backorder_watermark_id = int(
                    dict(cur.fetchone() or {}).get("mid") or 0,
                )
                self.initialized = True
        except pymysql.MySQLError as e:
            logger.warning("live_gmv: init query fail %s", e)
        finally:
            conn.close()

    def _sync_poll_batch(self) -> list[dict[str, Any]]:
        cfg = resolve_business_mysql()
        if not cfg:
            return []
        t0, t1_day = _day_bounds()
        now_ts = min(int(datetime.now(_TZ).timestamp()), t1_day)
        ot, ta, pk = S.ORDERS_TIME_COL, S.ORDERS_AMOUNT_COL, S.ORDERS_PK_COL
        wa, wi = self.watermark.add_time, self.watermark.order_id
        try:
            conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
        except pymysql.MySQLError:
            return []
        rows_out: list[dict[str, Any]] = []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT `{pk}` AS oid, `{ot}` AS add_time, `{ta}` AS amount
                    FROM `{S.ORDERS_TABLE}`
                    WHERE `{ot}` >= %s AND `{ot}` <= %s
                      AND (
                        `{ot}` > %s
                        OR (`{ot}` = %s AND `{pk}` > %s)
                      )
                    ORDER BY `{ot}` ASC, `{pk}` ASC
                    LIMIT 200
                    """,
                    (t0, now_ts, wa, wa, wi),
                )
                for r in cur.fetchall():
                    rows_out.append(dict(r))
        except pymysql.MySQLError as e:
            logger.warning("live_gmv: poll fail %s", e)
        finally:
            conn.close()
        return rows_out

    def _sync_poll_backorder_batch(self) -> list[dict[str, Any]]:
        """今日新增退货单（按 id 递增），用于运营台预警 WebSocket 冒泡。"""
        cfg = resolve_business_mysql()
        if not cfg:
            return []
        t0, t1_day = _day_bounds()
        now_ts = min(int(datetime.now(_TZ).timestamp()), t1_day)
        b_tbl = S.BACKORDER_TABLE
        b_pk = S.BACKORDER_PK_COL
        b_t = S.BACKORDER_TIME_COL
        b_sn = S.BACKORDER_SN_COL
        b_oid = S.BACKORDER_ORDER_FK_COL
        b_amt = S.BACKORDER_AMOUNT_COL
        b_bst = S.BACKORDER_BACK_STATUS_COL
        wid = self.backorder_watermark_id
        try:
            conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
        except pymysql.MySQLError:
            return []
        rows_out: list[dict[str, Any]] = []
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT `{b_pk}` AS id, `{b_t}` AS add_time, `{b_sn}` AS backorder_sn,
                           `{b_oid}` AS order_id, `{b_amt}` AS total_amount, `{b_bst}` AS back_status
                    FROM `{b_tbl}`
                    WHERE `{b_t}` >= %s AND `{b_t}` <= %s AND `{b_pk}` > %s
                    ORDER BY `{b_pk}` ASC
                    LIMIT 80
                    """,
                    (t0, now_ts, wid),
                )
                for r in cur.fetchall():
                    rows_out.append(dict(r))
        except pymysql.MySQLError as e:
            logger.warning("live_gmv: backorder poll fail %s", e)
        finally:
            conn.close()
        return rows_out


hub = LiveGmvHub()


def _minute_key(add_time: int, day_t0: int) -> int:
    return day_t0 + ((add_time - day_t0) // 60) * 60


async def _poll_loop() -> None:
    interval = float(os.environ.get("INSIGHTS_LIVE_GMV_POLL_SEC", "3"))
    while True:
        try:
            if not resolve_business_mysql():
                await asyncio.sleep(max(interval, 5.0))
                continue
            # 跨日：重新初始化
            t0, _ = _day_bounds()
            if hub.initialized and hub.today_t0 != t0:
                await asyncio.to_thread(hub._sync_init_from_db)
            if not hub.initialized:
                await asyncio.to_thread(hub._sync_init_from_db)
            batch = await asyncio.to_thread(hub._sync_poll_batch)
            bo_batch = await asyncio.to_thread(hub._sync_poll_backorder_batch)
            if not batch and not bo_batch:
                await asyncio.sleep(interval)
                continue
            if batch:
                rows_payload = []
                for r in batch:
                    oid = int(r["oid"])
                    add_time = int(r["add_time"])
                    amt = float(r["amount"] or 0)
                    hub.watermark = _Watermark(add_time, oid)
                    hub.cumulative_gmv += amt
                    hub.cumulative_orders += 1
                    mk = _minute_key(add_time, hub.today_t0)
                    rows_payload.append(
                        {
                            "id": oid,
                            "add_time": add_time,
                            "amount": round(amt, 2),
                            "minute_start": mk,
                        }
                    )
                avg_ticket = (
                    round(hub.cumulative_gmv / hub.cumulative_orders, 2)
                    if hub.cumulative_orders
                    else 0.0
                )
                await hub.broadcast(
                    {
                        "type": "batch",
                        "rows": rows_payload,
                        "cumulative_gmv": round(hub.cumulative_gmv, 2),
                        "order_count": hub.cumulative_orders,
                        "avg_ticket": avg_ticket,
                    }
                )
                await hub.broadcast({"type": "refresh_hint", "reason": "new_orders"})
            if bo_batch:
                for r in bo_batch:
                    hub.backorder_watermark_id = max(
                        hub.backorder_watermark_id,
                        int(r["id"]),
                    )
                returns_payload = []
                for r in bo_batch:
                    returns_payload.append(
                        {
                            "id": int(r["id"]),
                            "add_time": int(r["add_time"]),
                            "backorder_sn": str(r.get("backorder_sn") or ""),
                            "order_id": int(r.get("order_id") or 0),
                            "total_amount": round(float(r.get("total_amount") or 0), 2),
                            "back_status": int(r.get("back_status") or 0),
                        }
                    )
                await hub.broadcast(
                    {"type": "ops_alert_batch", "returns": returns_payload},
                )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.exception("live_gmv poll loop error: %s", e)
        await asyncio.sleep(interval)


async def start_live_gmv_background() -> None:
    if hub.started:
        return
    hub.started = True
    hub.task = asyncio.create_task(_poll_loop())
