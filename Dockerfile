# 阶段一：构建前端（与运行阶段同源基础镜像，避免额外拉取 node 官方镜像；Bookworm 自带 Node 18+）
FROM docker.1ms.run/library/python:3.11-slim-bookworm AS frontend-builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    && rm -rf /var/lib/apt/lists/*
COPY frontend/package.json frontend/package-lock.json* ./
# 国内网络优先用 npmmirror；加重试，必要时强制重装 @vueuse 避免截断损坏
RUN npm config set registry https://registry.npmmirror.com \
    && npm config set fetch-retries 10 && npm config set fetch-retry-maxtimeout 120000 \
    && npm ci --legacy-peer-deps --no-audit --no-fund \
    || (rm -rf node_modules && npm install --legacy-peer-deps --no-audit --no-fund) \
    && npm install @vueuse/core@12.0.0 @vueuse/shared@12.0.0 @vueuse/metadata@12.0.0 --legacy-peer-deps --force --no-audit --no-fund
COPY frontend/ ./
# 天枢大屏：子应用静态资源在 frontend/public/tianshu（构建镜像前于宿主机执行
#   ./scripts/sync-beijing-tianshu.sh
# 将 beijing 项目以 base=/tianshu/ 打入 public/tianshu，以下 npm build 会一并拷贝进 dist。
# Cesium ion 影像/地形（构建期注入，勿把真实 Token 写入仓库）
ARG VITE_CESIUM_ION_TOKEN
ENV VITE_CESIUM_ION_TOKEN=$VITE_CESIUM_ION_TOKEN
RUN npm run build

# 阶段二：运行环境（后端 + 前端静态文件）
# 海外网络稳定时可改回 python:3.11-slim-bookworm
FROM docker.1ms.run/library/python:3.11-slim-bookworm
WORKDIR /app

# 安装运行时依赖（可选，如需 GPU 可改用 nvidia/cuda 基础镜像）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 后端
COPY backend/requirements.txt backend/
# torch：aarch64 上 2.11+ 会拉取巨量 CUDA 依赖且易触发 pip 哈希校验失败；固定 2.3.1 + 升级 pip 与实测可用一致
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --timeout 1200 \
    -i https://pypi.org/simple --trusted-host pypi.org \
    torch==2.3.1 torchvision==0.18.1
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ \
    && pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn \
    && pip install --no-cache-dir --timeout 600 -r backend/requirements.txt
COPY backend/ ./backend/

# 前端构建产物
COPY --from=frontend-builder /build/dist ./frontend/dist

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
