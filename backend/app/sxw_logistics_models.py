"""
SXW 业务库（MySQL）智能物流相关表 — 与 PHP 后台 edu_std_supp 一致，只映射本模块用到的列。
"""
from sqlalchemy import Column, Integer, String, Numeric
from sqlalchemy.orm import declarative_base

SxwBase = declarative_base()


class SxwVehicle(SxwBase):
    __tablename__ = "vehicle"

    id = Column(Integer, primary_key=True)
    plateno = Column(String(15))
    car_type = Column(String(10))
    shipper_type = Column(Integer)
    imei = Column(String(20))
    fuel_economy = Column(Numeric(10, 2))
    depreciation = Column(Numeric(10, 2))
    insure = Column(Numeric(10, 2))
    maintain = Column(Numeric(10, 2))
    other = Column(Numeric(10, 2))


class SxwSlVehicleBindBeidou(SxwBase):
    __tablename__ = "sl_vehicle_bind_beidou"

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, index=True, unique=True)
    macid = Column(String(255))
    user_id = Column(String(255))


class SxwSlVehicleBindCamera(SxwBase):
    __tablename__ = "sl_vehicle_bind_camera"

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, index=True)
    camera_device_id = Column(Integer, index=True)


class SxwSlCameraDevice(SxwBase):
    __tablename__ = "sl_camera_device"

    id = Column(Integer, primary_key=True)
    device_name = Column(String(255))
    device_guid = Column(String(128))
    channel_id = Column(Integer)
    camera_source = Column(String(32))
    status = Column(Integer, default=1)
