# -*- coding: utf-8 -*-
"""票据 OCR 结构化结果与业务库订单/采购单对账（仅 SELECT）。"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from app.services.business_mysql import BusinessMysqlConfig
from app.services.db_connector import get_connection

PHONE_RE = re.compile(r"1[3-9]\d{9}")
# 常见订单号：纯数字较长（不用 \\b，避免紧贴中文时匹配失败）
ORDER_SN_DIGITS_RE = re.compile(r"(?<!\d)(\d{12,20})(?!\d)")

DOC_KIND_DELIVERY = "delivery"
DOC_KIND_RECEIPT = "receipt"
DOC_KIND_PROCUREMENT = "procurement"
VALID_DOC_KINDS = frozenset({DOC_KIND_DELIVERY, DOC_KIND_RECEIPT, DOC_KIND_PROCUREMENT})


def _iter_cell_texts(structured: dict) -> list[str]:
    out: list[str] = []
    for kv in structured.get("key_values") or []:
        if isinstance(kv, dict):
            out.append(str(kv.get("key") or ""))
            out.append(str(kv.get("value") or ""))
    for tbl in structured.get("tables") or []:
        if not isinstance(tbl, dict):
            continue
        for row in tbl.get("rows") or []:
            if isinstance(row, (list, tuple)):
                for cell in row:
                    out.append(str(cell) if cell is not None else "")
    return out


def _phones_in_text(s: str) -> set[str]:
    """从一段文字中提取大陆手机号：直接匹配 + 去空格/符号后从连续数字里滑窗。"""
    found: set[str] = set()
    if not s:
        return found
    for m in PHONE_RE.findall(s):
        found.add(m)
    # OCR 可能识别成「185 1930 0547」或拆到相邻单元格，拼接后只保留数字再扫
    digits = re.sub(r"\D", "", s)
    if len(digits) < 11:
        return found
    for i in range(0, len(digits) - 10):
        chunk = digits[i : i + 11]
        if chunk[0] == "1" and chunk[1] in "3456789" and chunk[2:].isdigit():
            found.add(chunk)
    return found


def _phones_from_table_rows(structured: dict) -> set[str]:
    """按行拼接单元格再提手机号（表头「司机电话」与号码分两格时常用）。"""
    found: set[str] = set()
    for tbl in structured.get("tables") or []:
        if not isinstance(tbl, dict):
            continue
        headers = tbl.get("headers") or []
        header_line = " ".join(str(h or "") for h in headers)
        found |= _phones_in_text(header_line)
        for row in tbl.get("rows") or []:
            if not isinstance(row, (list, tuple)):
                continue
            joined = " ".join(str(c) if c is not None else "" for c in row)
            found |= _phones_in_text(joined)
            # 无空格直连（极端拆格）
            joined2 = "".join(str(c) if c is not None else "" for c in row)
            found |= _phones_in_text(joined2)
    return found


def extract_phones_from_structured(structured: dict) -> list[str]:
    found: set[str] = set()
    for s in _iter_cell_texts(structured):
        found |= _phones_in_text(s)
    found |= _phones_from_table_rows(structured)
    return sorted(found)


def extract_order_sn_from_structured(structured: dict) -> Optional[str]:
    for kv in structured.get("key_values") or []:
        if not isinstance(kv, dict):
            continue
        k = str(kv.get("key") or "")
        v = str(kv.get("value") or "").strip()
        if not v:
            continue
        if any(x in k for x in ("单号", "订单号", "订单编号", "Order", "order")):
            return v
    for s in _iter_cell_texts(structured):
        s = s.strip()
        if ORDER_SN_DIGITS_RE.search(s):
            m = ORDER_SN_DIGITS_RE.search(s)
            if m:
                return m.group(1)
    return None


def _parse_date_from_text(text: str) -> Optional[date]:
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    m = re.search(r"(20\d{2})[年/\-.](\d{1,2})[月/\-.](\d{1,2})", text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def extract_send_date_from_structured(structured: dict) -> Optional[date]:
    for kv in structured.get("key_values") or []:
        if not isinstance(kv, dict):
            continue
        k = str(kv.get("key") or "")
        v = str(kv.get("value") or "")
        if ("送货" in k and "日期" in k) or k.strip() in ("送货日期", "配送日期"):
            d = _parse_date_from_text(v)
            if d:
                return d
    # 表格行内「送货日期」与值可能分列
    for tbl in structured.get("tables") or []:
        if not isinstance(tbl, dict):
            continue
        headers = [str(h or "") for h in (tbl.get("headers") or [])]
        for i, h in enumerate(headers):
            if ("送货" in h and "日期" in h) or h.strip() in ("送货日期", "配送日期"):
                for row in tbl.get("rows") or []:
                    if isinstance(row, (list, tuple)) and i < len(row):
                        d = _parse_date_from_text(str(row[i] or ""))
                        if d:
                            return d
        for row in tbl.get("rows") or []:
            if not isinstance(row, (list, tuple)):
                continue
            joined = " ".join(str(c) for c in row if c is not None)
            if "送货" in joined and re.search(r"20\d{2}", joined):
                m = re.search(r"(20\d{2}[年/\-.]\d{1,2}[月/\-.]\d{1,2}|20\d{2}-\d{2}-\d{2})", joined)
                if m:
                    d = _parse_date_from_text(m.group(1))
                    if d:
                        return d
    return None


def merge_order_sn_and_send_date(
    order_sn_raw: Optional[str],
    send_date_override_str: Optional[str],
    structured: dict,
) -> tuple[Optional[str], Optional[date]]:
    """
    送货/收货对账用：用户填的 send_date 优先；订单号框若为标准日期则视为送货日期（避免误把日期当 order_sn）；
    否则沿用识别结果中的送货日期。
    """
    sn = (order_sn_raw or "").strip()
    user_date = (
        _parse_date_from_text((send_date_override_str or "").strip()) if send_date_override_str else None
    )
    from_struct = extract_send_date_from_structured(structured)
    sn_as_date: Optional[date] = None
    if sn:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", sn):
            sn_as_date = _parse_date_from_text(sn)
            sn = ""
        elif re.fullmatch(r"\d{4}/\d{2}/\d{2}", sn):
            sn_as_date = _parse_date_from_text(sn.replace("/", "-")[:10])
            sn = ""
        elif re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", sn):
            sn_as_date = _parse_date_from_text(sn.replace(".", "-")[:10])
            sn = ""
    effective = user_date or sn_as_date or from_struct
    return (sn or None, effective)


def _normalize_goods_name(s: str) -> str:
    return re.sub(r"\s+", "", (s or "").strip())


def goods_names_match(ocr_name: str, db_name: str) -> bool:
    a = _normalize_goods_name(ocr_name)
    b = _normalize_goods_name(db_name)
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


def _parse_decimal(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    s = str(val).strip().replace(",", "").replace("，", "")
    if not s or s in ("-", "—", ""):
        return None
    s = re.sub(r"%\s*$", "", s)
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _dec_eq(a: Optional[Decimal], b: Optional[Decimal], tol: Decimal = Decimal("0.02")) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def _find_col_index(headers: list[str], candidates: list[str]) -> int:
    heads = [str(h or "").strip() for h in headers]
    for cand in candidates:
        for i, h in enumerate(heads):
            if cand == h or cand in h:
                return i
    return -1


_REMARK_HEADER_NOISE = re.compile(
    r"总价|金额|单价|数量|折扣|原价|折后|品名|商品|规格|单位|订货|要货|序号|编号|"
    r"上浮|基准|结算|创价|京东|参考|税率"
)


def _remark_column_index(headers: list[str]) -> int:
    """
    备注列：优先匹配表头含「备注/说明」等；否则最后一列且表头不像金额/数量等业务列时视为备注（与前端高亮逻辑一致）。
    """
    heads = [str(h or "").strip() for h in headers]
    idx = _find_col_index(heads, ["备注", "说明", "附注", "订货备注", "备注信息"])
    if idx >= 0:
        return idx
    if not heads:
        return -1
    last_i = len(heads) - 1
    label = heads[last_i]
    if not label:
        return last_i
    if not _REMARK_HEADER_NOISE.search(label):
        return last_i
    return -1


def _normalize_remark_text(s: str) -> str:
    """统一 Unicode 减号等，避免「−0.2」与「-0.2」被误判为一致以外的重复差异或漏比。"""
    t = (s or "").strip()
    return t.replace("\u2212", "-").replace("\uff0d", "-").replace("﹣", "-").replace("－", "-")


def _normalize_table_row_cells(row: Any, min_header_cols: int) -> list[str]:
    """
    对齐表体与表头：仅补齐短行，绝不截断长行。
    百度等引擎常见「body 列数 > header 列数」，最后一列手写备注若被 [:n] 截掉则永远对不出差异。
    """
    if not isinstance(row, (list, tuple)):
        return [""] * min_header_cols
    cells = [str(c) if c is not None else "" for c in row]
    if len(cells) < min_header_cols:
        cells = cells + [""] * (min_header_cols - len(cells))
    return cells


def _cell_might_be_remark_note(text: str) -> bool:
    """手写备注常见：短中文、小幅度数字调整（-0.5、-.8）；排除正数金额形态。"""
    t = _normalize_remark_text((text or "").strip())
    if not t:
        return False
    if re.search(r"[\u4e00-\u9fff]", t):
        return len(t) <= 80
    if re.match(r"^[-+]?[\d.]+%$", t):
        return False
    if re.match(r"^[-+]?[\d.,]+$", t.replace("，", ",")):
        raw = t.replace(",", "").replace("，", "")
        try:
            v = float(raw)
        except ValueError:
            return len(t) <= 16
        if v < 0:
            return True
        if v == 0 and (t.startswith("-") or t.startswith("+")):
            return True
        if 0 < abs(v) < 1:
            return True
        if v > 0 and v >= 1 and "." in t:
            return False
        if v >= 50:
            return False
        return len(t) <= 5
    return len(t) <= 24


def _ocr_remark_cell(cells: list[str], idx_remark: int, skip_indices: set[int]) -> str:
    """
    读取备注：优先备注列；再取表体多出来的尾列；再在排除业务列后从右向左找「像备注」的格
    （解决手写落在备注格但 OCR 空、或落在邻格、或表头未识别出「备注」等情况）。
    """
    if idx_remark >= 0 and idx_remark < len(cells):
        s = _normalize_remark_text(str(cells[idx_remark] or "").strip())
        if s:
            return s
    if idx_remark >= 0 and cells and len(cells) - 1 > idx_remark:
        tail = _normalize_remark_text(str(cells[-1] or "").strip())
        if tail:
            return tail
    for i in range(len(cells) - 1, -1, -1):
        if i in skip_indices:
            continue
        t = _normalize_remark_text(str(cells[i] or "").strip())
        if not t:
            continue
        if _cell_might_be_remark_note(t):
            return t
    return ""


def _line_detail_table(structured: dict) -> Optional[dict]:
    """
    选取用于明细对账的表格。识别结果里常见首张为小表（抬头/汇总），真正带「品名」的在后续表，
    故遍历全部表，取含品名列且有效数据行数最多的一张。
    """
    tables = structured.get("tables") or []
    best: Optional[dict] = None
    best_key: tuple[int, int] = (-1, -1)
    for t in tables:
        if not isinstance(t, dict):
            continue
        headers = [str(h or "") for h in (t.get("headers") or [])]
        idx_name = _find_col_index(headers, ["品名", "商品名称", "名称", "货品"])
        if idx_name < 0:
            continue
        rows = t.get("rows") or []
        if not isinstance(rows, list):
            continue
        n_data = 0
        for row in rows:
            if not isinstance(row, (list, tuple)) or idx_name >= len(row):
                continue
            cell = str(row[idx_name] or "").strip()
            if cell and not re.match(r"^\d+$", cell):
                n_data += 1
        key = (n_data, len(rows))
        if key > best_key:
            best_key = key
            best = t
    return best


def extract_ocr_goods_names(structured: dict) -> list[str]:
    """从识别结果中带品名列的明细表提取品名（与逐行对账逻辑一致）。"""
    tbl = _line_detail_table(structured)
    if not tbl:
        return []
    headers = [str(h or "") for h in (tbl.get("headers") or [])]
    rows = tbl.get("rows") or []
    if not isinstance(rows, list):
        return []
    idx_name = _find_col_index(headers, ["品名", "商品名称", "名称", "货品"])
    if idx_name < 0:
        return []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or idx_name >= len(row):
            continue
        name = str(row[idx_name] or "").strip()
        if not name or re.match(r"^\d+$", name):
            continue
        out.append(name)
    return out


def _merge_hint_and_ocr_goods_names(
    structured: dict,
    goods_hints: Optional[list[str]],
) -> list[str]:
    """用户填写的品名关键词在前，再并上识别表格品名；按规范化去重。"""
    hints_trim = [str(x or "").strip() for x in (goods_hints or [])[:50] if str(x or "").strip()]
    seen: set[str] = set()
    out: list[str] = []
    for src in (hints_trim, extract_ocr_goods_names(structured)):
        for x in src:
            if len(out) >= 80:
                return out
            s = str(x or "").strip()
            if not s or len(s) > 200:
                continue
            k = _normalize_goods_name(s)
            if not k or k in seen:
                continue
            seen.add(k)
            out.append(s)
    return out


def _order_goods_match_scores(ocr_names: list[str], db_lines: list[dict]) -> tuple[int, int]:
    """
    返回 (识别侧命中行数, 系统侧被命中行数)：
    与 _compare_line_tables 一致，按 goods_names_match 判定。
    """
    if not ocr_names or not db_lines:
        return 0, 0
    db_names = [str(d.get("goods_name") or "") for d in db_lines]
    ocr_hit = 0
    used_db: set[int] = set()
    for o in ocr_names:
        hit = False
        for j, dn in enumerate(db_names):
            if goods_names_match(o, dn):
                hit = True
                used_db.add(j)
        if hit:
            ocr_hit += 1
    return ocr_hit, len(used_db)


def _pick_order_by_line_items(
    cfg: BusinessMysqlConfig,
    candidate_rows: list[dict],
    goods_names: list[str],
) -> tuple[Optional[dict], Optional[str]]:
    """
    多条候选订单时，用品名列表与 orders_items 重合度择优（含用户填写关键词 + 识别表格）。
    返回 (选中行, None) / (None, None) 表示无法用语义收窄（沿用外层提示）/
    (None, str) 表示明细仍并列需填单号。
    """
    if not goods_names:
        return None, None

    ranked: list[tuple[tuple[int, int], dict]] = []
    for r in candidate_rows:
        items = fetch_orders_items(cfg, int(r["id"]))
        oh, dh = _order_goods_match_scores(goods_names, items)
        ranked.append(((oh, dh), r))

    ranked.sort(key=lambda x: x[0], reverse=True)
    best_key, best_row = ranked[0]
    if best_key[0] == 0:
        return None, None

    if len(ranked) == 1:
        return best_row, None

    second_key = ranked[1][0]
    if best_key > second_key:
        return best_row, None

    return None, (
        "根据手机号与送货日期仍有多条订单，且品名（含您填写的关键词）与候选订单明细的重合度相同，无法自动区分，请填写准确订单号。"
    )


def resolve_orders_row(
    cfg: BusinessMysqlConfig,
    structured: dict,
    order_sn_override: Optional[str],
    send_date: Optional[date],
    goods_hints: Optional[list[str]] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """返回 (orders 行 dict 或 None, 错误说明或 None)。"""
    conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
    try:
        with conn.cursor() as cur:
            explicit_sn = (order_sn_override or "").strip()
            if explicit_sn:
                cur.execute(
                    "SELECT id, order_sn, driver_phone, driver_realname, send_date, member_realname, "
                    "total_amount, add_time FROM `orders` WHERE `order_sn` = %s LIMIT 2",
                    (explicit_sn,),
                )
                rows = cur.fetchall()
                if len(rows) == 1:
                    return dict(rows[0]), None
                if len(rows) > 1:
                    return None, "订单号匹配到多条记录，请联系技术核对。"
                return None, f"未找到订单号「{explicit_sn}」，请核对后重试。"

            auto_sn = extract_order_sn_from_structured(structured)
            if auto_sn:
                cur.execute(
                    "SELECT id, order_sn, driver_phone, driver_realname, send_date, member_realname, "
                    "total_amount, add_time FROM `orders` WHERE `order_sn` = %s LIMIT 2",
                    (auto_sn,),
                )
                rows = cur.fetchall()
                if len(rows) == 1:
                    return dict(rows[0]), None
                if len(rows) > 1:
                    return None, "识别到的单号匹配到多条记录，请手动填写准确订单号。"

            phones = extract_phones_from_structured(structured)
            if not phones:
                return None, "未能从识别结果中解析到订单号或司机手机号，请手动填写订单号后再对账。"

            params: list[Any] = []
            placeholders = ",".join(["%s"] * len(phones))
            sql = (
                f"SELECT id, order_sn, driver_phone, driver_realname, send_date, member_realname, "
                f"total_amount, add_time FROM `orders` WHERE `driver_phone` IN ({placeholders})"
            )
            params.extend(phones)
            if send_date:
                sql += " AND `send_date` = %s"
                params.append(send_date)
            sql += " ORDER BY `add_time` DESC LIMIT 10"
            cur.execute(sql, params)
            rows = cur.fetchall()
            if len(rows) == 0:
                return None, "未找到与手机号（及送货日期）匹配的订单，请核对或填写订单号。"
            if len(rows) > 1:
                merged_goods = _merge_hint_and_ocr_goods_names(structured, goods_hints)
                picked, narrow_err = _pick_order_by_line_items(
                    cfg, [dict(r) for r in rows], merged_goods
                )
                if picked is not None:
                    return picked, None
                if narrow_err is not None:
                    return None, narrow_err
                msg = f"根据手机号匹配到 {len(rows)} 条订单，请填写准确订单号以唯一确定。"
                if not send_date:
                    msg += " 若单据上有送货日期，请在页面选择「送货日期」或确保识别到送货日期以帮助收窄。"
                if merged_goods:
                    msg += " 已用品名（含识别表格与「品名关键词」）与系统明细比对，仍无法唯一确定，请填写订单号。"
                else:
                    msg += " 可在「品名关键词」中填写单据上的若干品名，或确保识别表格含品名列，以便与系统明细比对收窄。"
                return None, msg
            return dict(rows[0]), None
    finally:
        conn.close()


def fetch_orders_items(cfg: BusinessMysqlConfig, order_id: int) -> list[dict]:
    conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT goods_name, sendqty, sale_price, remark FROM `orders_items` "
                "WHERE `order_id` = %s ORDER BY `id` ASC",
                (order_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def resolve_procurement_row(
    cfg: BusinessMysqlConfig,
    structured: dict,
    order_sn_override: Optional[str],
) -> tuple[Optional[dict], Optional[str]]:
    conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
    try:
        with conn.cursor() as cur:
            explicit_sn = (order_sn_override or "").strip()
            sn = explicit_sn or extract_order_sn_from_structured(structured) or ""
            if not sn:
                return None, "采购/入库单请填写或识别到采购单号，暂不支持仅用手机号定位。"
            cur.execute(
                "SELECT id, order_sn, member_realname, total_amount, add_time, remark "
                "FROM `procurement_orders` WHERE `order_sn` = %s LIMIT 2",
                (sn,),
            )
            rows = cur.fetchall()
            if len(rows) == 0:
                return None, f"未找到采购单号「{sn}」对应的记录。" + (
                    "" if explicit_sn else " 建议手动填写准确单号。"
                )
            if len(rows) > 1:
                return None, "采购单号匹配异常（多条），请联系技术核对。"
            return dict(rows[0]), None
    finally:
        conn.close()


def fetch_procurement_items(cfg: BusinessMysqlConfig, po_id: int) -> list[dict]:
    conn = get_connection(cfg.host, cfg.port, cfg.database, cfg.user, cfg.password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT goods_name, sendqty, receiveqty, needqty, sale_price, remark "
                "FROM `procurement_orders_items` WHERE `procurement_orders_id` = %s ORDER BY `id` ASC",
                (po_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _kv_map(structured: dict) -> dict[str, str]:
    m: dict[str, str] = {}
    for kv in structured.get("key_values") or []:
        if isinstance(kv, dict):
            k = str(kv.get("key") or "").strip()
            v = str(kv.get("value") or "").strip()
            if k:
                m[k] = v
    return m


def _header_diffs_orders(structured: dict, row: dict) -> list[dict]:
    diffs: list[dict] = []
    kv = _kv_map(structured)
    for key_hint, label, db_key in (
        ("司机电话", "司机电话", "driver_phone"),
        ("司机", "司机", "driver_realname"),
        ("收货单位", "收货单位", "member_realname"),
        ("客户", "客户", "member_realname"),
    ):
        ocr_val = None
        for k, v in kv.items():
            if key_hint in k:
                ocr_val = v
                break
        if ocr_val is None:
            continue
        db_val = row.get(db_key)
        if db_val is None:
            continue
        ds = str(db_val).strip() if not isinstance(db_val, date) else str(db_val)
        os_ = str(ocr_val).strip()
        if db_key == "driver_realname":
            # 单据可能为「陈俊才(121)」
            os_ = re.sub(r"\s*\([^)]*\)\s*$", "", os_).strip()
            ds = re.sub(r"\s*\([^)]*\)\s*$", "", ds).strip()
        if os_ != ds and _normalize_goods_name(os_) != _normalize_goods_name(ds):
            if os_ not in ds and ds not in os_:
                diffs.append({"field": label, "ocr": ocr_val, "db": ds})

    send_d = extract_send_date_from_structured(structured)
    if send_d and row.get("send_date"):
        sd = row["send_date"]
        if isinstance(sd, datetime):
            sd = sd.date()
        if send_d != sd:
            diffs.append({"field": "送货日期", "ocr": str(send_d), "db": str(sd)})

    return diffs


def _compare_line_tables(
    structured: dict,
    db_lines: list[dict],
    qty_key: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    """返回 (line_diffs, only_ocr, only_db)"""
    tbl = _line_detail_table(structured)
    if not tbl:
        return [], [], []

    headers = [str(h or "") for h in (tbl.get("headers") or [])]
    rows = tbl.get("rows") or []
    if not isinstance(rows, list):
        return [], [], []

    idx_name = _find_col_index(headers, ["品名", "商品名称", "名称", "货品"])
    idx_qty = _find_col_index(headers, ["数量", "订货量", "要货数量"])
    idx_settle = _find_col_index(headers, ["结算金额", "金额", "小计", "含税金额"])
    idx_price = _find_col_index(headers, ["基准价", "单价", "销售价", "结算价"])
    idx_remark = _remark_column_index(headers)
    idx_serial = _find_col_index(headers, ["序号", "编号", "行号"])
    idx_spec = _find_col_index(headers, ["规格"])
    idx_unit = _find_col_index(headers, ["单位"])
    idx_markup = _find_col_index(headers, ["上浮", "上浮率", "折扣"])
    idx_ref = _find_col_index(headers, ["创价", "京东", "参考价", "参考"])

    if idx_name < 0:
        return [], [], [{"hint": "未识别到「品名」列，无法逐行对账"}]

    n_cols = len(headers)
    skip_for_remark_scan = {
        i
        for i in (
            idx_name,
            idx_qty,
            idx_settle,
            idx_price,
            idx_serial,
            idx_spec,
            idx_unit,
            idx_markup,
            idx_ref,
        )
        if i >= 0
    }

    used_db_idx: set[int] = set()
    line_diffs: list[dict] = []
    only_ocr: list[dict] = []
    only_db: list[dict] = []

    for row in rows:
        if not isinstance(row, (list, tuple)):
            continue
        cells = _normalize_table_row_cells(row, n_cols)
        if idx_name >= len(cells):
            continue
        ocr_name = str(cells[idx_name] or "").strip()
        if not ocr_name or re.match(r"^\d+$", ocr_name):
            continue

        ocr_qty = _parse_decimal(cells[idx_qty]) if idx_qty >= 0 and idx_qty < len(cells) else None
        ocr_settle = _parse_decimal(cells[idx_settle]) if idx_settle >= 0 and idx_settle < len(cells) else None
        ocr_price = _parse_decimal(cells[idx_price]) if idx_price >= 0 and idx_price < len(cells) else None
        ocr_remark = _ocr_remark_cell(cells, idx_remark, skip_for_remark_scan)

        db_line = None
        db_j = -1
        for j, d in enumerate(db_lines):
            if j in used_db_idx:
                continue
            if goods_names_match(ocr_name, str(d.get("goods_name") or "")):
                db_line = d
                db_j = j
                break

        if db_line is None:
            only_ocr.append({"goods": ocr_name})
            continue
        used_db_idx.add(db_j)

        db_qty = _parse_decimal(db_line.get(qty_key))
        db_price = _parse_decimal(db_line.get("sale_price"))
        db_remark = str(db_line.get("remark") or "").strip()
        db_line_amt = None
        if db_qty is not None and db_price is not None:
            db_line_amt = (db_qty * db_price).quantize(Decimal("0.01"))

        if not _dec_eq(ocr_qty, db_qty):
            line_diffs.append(
                {
                    "goods": ocr_name,
                    "field": "数量",
                    "ocr": str(ocr_qty) if ocr_qty is not None else "",
                    "db": str(db_qty) if db_qty is not None else "",
                }
            )

        if ocr_settle is not None and db_line_amt is not None and not _dec_eq(ocr_settle, db_line_amt):
            line_diffs.append(
                {
                    "goods": ocr_name,
                    "field": "结算金额(≈数量×单价)",
                    "ocr": str(ocr_settle),
                    "db": str(db_line_amt),
                }
            )
        elif ocr_price is not None and db_price is not None and not _dec_eq(ocr_price, db_price):
            line_diffs.append(
                {
                    "goods": ocr_name,
                    "field": "单价",
                    "ocr": str(ocr_price),
                    "db": str(db_price),
                }
            )

        if _normalize_remark_text(ocr_remark) != _normalize_remark_text(db_remark):
            if ocr_remark or db_remark:
                line_diffs.append(
                    {
                        "goods": ocr_name,
                        "field": "备注",
                        "ocr": ocr_remark or "（空）",
                        "db": db_remark or "（空）",
                    }
                )

    for j, d in enumerate(db_lines):
        if j not in used_db_idx:
            only_db.append({"goods": str(d.get("goods_name") or "")})

    return line_diffs, only_ocr, only_db


def run_compare(
    cfg: Optional[BusinessMysqlConfig],
    structured: dict,
    order_sn: Optional[str],
    doc_kind: str,
    send_date_hint: Optional[str] = None,
    goods_hints: Optional[list[str]] = None,
) -> dict[str, Any]:
    kind = (doc_kind or DOC_KIND_DELIVERY).strip().lower()
    if kind not in VALID_DOC_KINDS:
        return {
            "ok": False,
            "reason": f"不支持的 doc_kind：{doc_kind}，可选：delivery / receipt / procurement",
            "doc_kind": kind,
        }

    if not cfg:
        return {"ok": False, "reason": "未配置业务库连接（INSIGHTS_MYSQL_* 或数据源）", "doc_kind": kind}

    if not isinstance(structured, dict):
        return {"ok": False, "reason": "structured 格式无效", "doc_kind": kind}

    if kind == DOC_KIND_PROCUREMENT:
        prow, err = resolve_procurement_row(cfg, structured, order_sn)
        if err:
            return {
                "ok": True,
                "doc_kind": kind,
                "matched": False,
                "message": err,
                "header_diffs": [],
                "line_diffs": [],
                "only_in_ocr": [],
                "only_in_db": [],
            }
        assert prow is not None
        lines = fetch_procurement_items(cfg, int(prow["id"]))
        norm_lines: list[dict] = []
        for d in lines:
            nd = dict(d)
            q = nd.get("sendqty")
            qd = _parse_decimal(q)
            if qd is None or qd == 0:
                q = nd.get("receiveqty") or nd.get("needqty") or 0
            nd["sendqty"] = q
            norm_lines.append(nd)
        line_diffs, only_ocr, only_db = _compare_line_tables(structured, norm_lines, "sendqty")
        header_diffs: list[dict] = []
        ocr_total = None
        for kk, v in _kv_map(structured).items():
            if "合计" in kk or "总额" in kk:
                ocr_total = _parse_decimal(v)
                break
        db_total = _parse_decimal(prow.get("total_amount"))
        if ocr_total is not None and db_total is not None and not _dec_eq(ocr_total, db_total, Decimal("0.05")):
            header_diffs.append({"field": "单据合计", "ocr": str(ocr_total), "db": str(db_total)})

        consistent = not header_diffs and not line_diffs and not only_ocr and not only_db
        return {
            "ok": True,
            "doc_kind": kind,
            "matched": True,
            "order_sn": str(prow.get("order_sn") or ""),
            "order_id": int(prow["id"]),
            "header_diffs": header_diffs,
            "line_diffs": line_diffs,
            "only_in_ocr": only_ocr,
            "only_in_db": only_db,
            "consistent": consistent,
            "message": "数据一致" if consistent else None,
        }

    # delivery / receipt -> orders
    order_sn_eff, send_date_dt = merge_order_sn_and_send_date(order_sn, send_date_hint, structured)
    orow, err = resolve_orders_row(cfg, structured, order_sn_eff, send_date_dt, goods_hints)
    if err:
        return {
            "ok": True,
            "doc_kind": kind,
            "matched": False,
            "message": err,
            "header_diffs": [],
            "line_diffs": [],
            "only_in_ocr": [],
            "only_in_db": [],
        }
    assert orow is not None
    lines = fetch_orders_items(cfg, int(orow["id"]))
    header_diffs = _header_diffs_orders(structured, orow)
    line_diffs, only_ocr, only_db = _compare_line_tables(structured, lines, "sendqty")

    ocr_total = None
    for kk, v in _kv_map(structured).items():
        if "合计" in kk or "总计" in kk or "总额" in kk:
            ocr_total = _parse_decimal(v)
            break
    db_total = _parse_decimal(orow.get("total_amount"))
    if ocr_total is not None and db_total is not None and not _dec_eq(ocr_total, db_total, Decimal("0.05")):
        header_diffs.append({"field": "订单合计", "ocr": str(ocr_total), "db": str(db_total)})

    only_hints = [x for x in only_db if "hint" in x]
    only_db_lines = [x for x in only_db if "hint" not in x]
    only_ocr_lines = [x for x in only_ocr if "hint" not in x]
    line_diffs_final = list(line_diffs)
    if only_hints:
        line_diffs_final.extend([{"goods": "-", "field": h["hint"], "ocr": "-", "db": "-"} for h in only_hints])

    consistent = (
        not header_diffs
        and not line_diffs_final
        and not only_ocr_lines
        and not only_db_lines
    )

    return {
        "ok": True,
        "doc_kind": kind,
        "matched": True,
        "order_sn": str(orow.get("order_sn") or ""),
        "order_id": int(orow["id"]),
        "header_diffs": header_diffs,
        "line_diffs": line_diffs_final,
        "only_in_ocr": only_ocr_lines,
        "only_in_db": only_db_lines,
        "consistent": consistent,
        "message": "数据一致" if consistent else None,
    }
