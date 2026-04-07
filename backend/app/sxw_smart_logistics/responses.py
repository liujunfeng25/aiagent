"""与 PHP ajax 一致的 JSON 信封：HTTP 200 + body.status。"""


def ok(data):
    return {"status": 200, "code": 0, "data": data}


def err(msg: str, status: int = 40001, **extra):
    body = {"status": status, "code": status, "data": msg}
    body.update(extra)
    return body
