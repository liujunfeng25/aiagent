# SQLite 数据库连接
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.models import DataSource, Dataset, TrainTask, Model, OperationLog
    from config import CATEGORIES_DIR

    Base.metadata.create_all(bind=engine)

    # 确保「类别训练数据」存在并指向 CATEGORIES_DIR（若当前路径无效或为空则更新）
    db = SessionLocal()
    try:
        from pathlib import Path
        ds = db.query(Dataset).filter(Dataset.name == "类别训练数据").first()
        cats_path = str(CATEGORIES_DIR.resolve())
        if ds:
            p = Path(ds.local_path) if ds.local_path else None
            if not p or not p.exists() or not any(p.iterdir()):
                ds.local_path = cats_path
                db.commit()
        else:
            ds = Dataset(name="类别训练数据", source_type="upload", row_count=0, local_path=cats_path)
            db.add(ds)
            db.commit()

        # 旧数据同步：更新图片分类数据集的 row_count（确保历史数据显示正确）
        _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff", ".tif"}
        for d in db.query(Dataset).all():
            if not d.local_path:
                continue
            p = Path(d.local_path)
            if not p.exists() or not p.is_dir():
                continue
            subdirs = [x for x in p.iterdir() if x.is_dir() and not x.name.startswith(".")]
            if not subdirs:
                continue
            cnt = sum(
                sum(1 for f in sd.iterdir() if f.is_file() and f.suffix.lower() in _IMAGE_EXTS)
                for sd in subdirs
            )
            if d.row_count != cnt:
                d.row_count = cnt
        db.commit()
    finally:
        db.close()
