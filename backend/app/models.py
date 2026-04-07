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


# ── 智能物流模块 ──────────────────────────────────────────

class Vehicle(Base):
    """车辆基础信息"""
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plateno = Column(String(20), nullable=False, unique=True, comment="车牌号")
    car_type = Column(String(50), comment="车辆类型")
    shipper_type = Column(String(10), default="自有", comment="自有/外部")
    driver_name = Column(String(50), comment="司机姓名")
    driver_phone = Column(String(20), comment="司机电话")
    remark = Column(Text, comment="备注")
    created_at = Column(DateTime, default=_beijing_now)

    th_binds = relationship("SlVehicleBindTh", back_populates="vehicle", cascade="all, delete-orphan")


class SlCameraDevice(Base):
    """摄像头设备库"""
    __tablename__ = "sl_camera_devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="设备名称")
    brand = Column(String(20), default="ys7", comment="品牌: ys7=萤石, imou=乐橙")
    device_serial = Column(String(100), nullable=False, comment="设备序列号/DeviceId")
    channel_no = Column(Integer, default=1, comment="通道号")
    app_key = Column(String(200), comment="AppKey / AppId")
    app_secret = Column(String(200), comment="AppSecret")
    remark = Column(String(200))
    created_at = Column(DateTime, default=_beijing_now)


class SlThDevice(Base):
    """温湿度传感器设备"""
    __tablename__ = "sl_th_devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    device_serial = Column(String(100), nullable=False)
    remark = Column(String(200))
    created_at = Column(DateTime, default=_beijing_now)

    th_binds = relationship("SlVehicleBindTh", back_populates="th_device")


class SlVehicleBindBeidou(Base):
    """本地 SQLite：北斗绑定镜像或 GPS18 账号覆盖（vehicle_id 与 SXW MySQL vehicle.id 对齐，不设外键）"""
    __tablename__ = "sl_vehicle_bind_beidou"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, nullable=False, unique=True)
    mds = Column(String(100), comment="北斗MDS/终端号")
    unit_id = Column(String(100), comment="UnitId")
    login_name = Column(String(100), comment="GPS18登录账号（可覆盖全局）")
    login_password = Column(String(200), comment="GPS18登录密码")
    created_at = Column(DateTime, default=_beijing_now)


class SlVehicleBindCamera(Base):
    """本地 SQLite：摄像头绑定镜像（vehicle_id / camera_id 与业务 id 对齐，不设外键）"""
    __tablename__ = "sl_vehicle_bind_camera"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, nullable=False)
    camera_id = Column(Integer, nullable=False)
    position_label = Column(String(50), comment="安装位置，如：车头、车厢、车尾")
    created_at = Column(DateTime, default=_beijing_now)


class SlVehicleBindTh(Base):
    """车辆↔温湿度传感器绑定（1:N）"""
    __tablename__ = "sl_vehicle_bind_th"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    th_device_id = Column(Integer, ForeignKey("sl_th_devices.id"), nullable=False)
    position_label = Column(String(50))
    created_at = Column(DateTime, default=_beijing_now)

    vehicle = relationship("Vehicle", back_populates="th_binds")
    th_device = relationship("SlThDevice", back_populates="th_binds")


class LogisticsFee(Base):
    """物流费用主表"""
    __tablename__ = "logistics_fees"

    id = Column(Integer, primary_key=True, index=True)
    fee_date = Column(String(10), nullable=False, comment="费用日期 YYYY-MM-DD")
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)
    plateno = Column(String(20), comment="车牌（冗余，方便查询）")
    driver_name = Column(String(50))
    follow_fee = Column(Float, default=0, comment="跟车费")
    follow_fee2 = Column(Float, default=0, comment="跟车费2")
    freight = Column(Float, default=0, comment="运费")
    staff_cost = Column(Float, default=0, comment="人工费")
    toll_fee = Column(Float, default=0, comment="路桥费")
    parking_fee = Column(Float, default=0, comment="停车费")
    fixed_cost = Column(Float, default=0, comment="固定成本")
    kilo = Column(Float, default=0, comment="行驶里程(km)")
    fuel_economy = Column(Float, default=0, comment="油耗(元/km)")
    fine_amount = Column(Float, default=0, comment="罚款总额")
    total = Column(Float, default=0, comment="合计")
    remark = Column(Text)
    created_at = Column(DateTime, default=_beijing_now)

    items = relationship("LogisticsFeeItem", back_populates="fee", cascade="all, delete-orphan")


class LogisticsFeeItem(Base):
    """物流费用明细子表"""
    __tablename__ = "logistics_fee_items"

    id = Column(Integer, primary_key=True, index=True)
    fee_id = Column(Integer, ForeignKey("logistics_fees.id"), nullable=False)
    item_type = Column(String(50), comment="费用类型名称")
    amount = Column(Float, default=0)
    note = Column(String(200))
    created_at = Column(DateTime, default=_beijing_now)

    fee = relationship("LogisticsFee", back_populates="items")
