# 阶段一：构建前端
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --legacy-peer-deps 2>/dev/null || npm install --legacy-peer-deps
COPY frontend/ ./
RUN npm run build

# 阶段二：运行环境（后端 + 前端静态文件）
# 使用带版本号的 tag 便于镜像站缓存；若拉取失败可改为 python:3.11
FROM python:3.11-slim-bookworm
WORKDIR /app

# 安装运行时依赖（可选，如需 GPU 可改用 nvidia/cuda 基础镜像）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 后端
COPY backend/requirements.txt backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/

# 前端构建产物
COPY --from=frontend-builder /build/dist ./frontend/dist

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
