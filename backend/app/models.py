# SQLite ORM 模型（created_at 使用北京时间 UTC+8）
from datetime import datetime, timezone, timedelta

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base

_BEIJING_TZ = timezone(timedelta(hours=8))


def _beijing_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)
    except Exception:
        return datetime.now(_BEIJING_TZ).replace(tzinfo=None)


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), default="mysql")  # mysql, postgres, ...
    host = Column(String(255), nullable=False)
    port = Column(Integer, default=3306)
    database = Column(String(100), nullable=False)
    username = Column(String(100), nullable=False)
    password_encrypted = Column(String(500))  # base64 或加密存储
    created_at = Column(DateTime, default=_beijing_now)


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    source_type = Column(String(20), default="upload")  # upload, from_source
    source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    config_json = Column(Text)  # 表名、字段、条件等
    row_count = Column(Integer, default=0)
    local_path = Column(String(500))  # 本地路径
    created_at = Column(DateTime, default=_beijing_now)


class TrainTask(Base):
    __tablename__ = "train_tasks"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, running, done, error, cancelled
    params_json = Column(Text)  # epochs, batch_size, model_type
    metrics_json = Column(Text)  # loss, acc 等
    model_path = Column(String(500))
    status_file = Column(String(500))
    created_at = Column(DateTime, default=_beijing_now)
    updated_at = Column(DateTime, default=_beijing_now, onupdate=_beijing_now)


class Model(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("train_tasks.id"), nullable=False)
    name = Column(String(200), nullable=False)
    metrics_json = Column(Text)
    path = Column(String(500))
    deployed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_beijing_now)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    time = Column(String(50), nullable=False)
    action = Column(String(50), nullable=False)
    detail = Column(Text)
    created_at = Column(DateTime, default=_beijing_now)
