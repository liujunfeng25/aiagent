# MySQL 连接与查询
import base64
import pymysql
from typing import Optional


def decode_password(encrypted: str) -> str:
    if not encrypted:
        return ""
    try:
        return base64.b64decode(encrypted).decode("utf-8")
    except Exception:
        return encrypted


def encode_password(password: str) -> str:
    return base64.b64encode(password.encode("utf-8")).decode("utf-8")


def get_connection(host: str, port: int, database: str, user: str, password: str):
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        read_timeout=10,
    )


def test_connection(host: str, port: int, database: str, user: str, password: str) -> tuple[bool, str]:
    try:
        conn = get_connection(host, port, database, user, password)
        conn.ping()
        conn.close()
        return True, "连接成功"
    except Exception as e:
        return False, str(e)


def list_tables(host: str, port: int, database: str, user: str, password: str) -> list[dict]:
    conn = get_connection(host, port, database, user, password)
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            rows = cur.fetchall()
            key = f"Tables_in_{database}"
            return [{"name": r[key]} for r in rows]
    finally:
        conn.close()


def execute_query(host: str, port: int, database: str, user: str, password: str, sql: str, limit: int = 1000) -> tuple[list, list]:
    conn = get_connection(host, port, database, user, password)
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchmany(limit)
            columns = [d[0] for d in cur.description] if cur.description else []
            return rows, columns
    finally:
        conn.close()


def fetch_table_preview(host: str, port: int, database: str, user: str, password: str, table: str, limit: int = 100) -> tuple[list, list]:
    sql = f"SELECT * FROM `{table}` LIMIT {limit}"
    return execute_query(host, port, database, user, password, sql, limit)
