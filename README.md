# AI Agent 平台

AI 训练与数据智能平台，支持数据源管理、数据集管理、模型训练、模型库、分析中心、系统管理。

## 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite + PyMySQL + PyTorch
- **前端**: Vue3 + Element Plus + ECharts + Vite

## 目录结构

```
ai-agent/
├── backend/         # FastAPI 后端
├── frontend/        # Vue3 前端
└── README.md
```

## 快速开始

### 1. 后端

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

「报价抓取 / 新发地」模块的进度与缓存保存在进程内存中，开发时请使用**单 worker**（不要加 `uvicorn --workers N`，`N>1` 时各进程状态不一致）。

### 2. 前端（开发模式）

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，前端会代理 `/api`、`/admin` 到后端 **8000** 端口（与 `vite.config.js` 中 `target` 一致）。

### 3. 生产部署

```bash
cd frontend
npm run build
cd ../backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 ，后端会挂载前端构建产物。

## 功能模块

- **工作台**: 指标卡片、训练趋势图、Top 模型、最近任务
- **数据源**: 配置 MySQL 等数据源连接，测试连接，获取表列表
- **数据集**: 创建数据集（上传文件或从数据源选择），预览
- **训练管理**: 创建训练任务，查看状态，删除任务
- **模型库**: 模型列表，部署
- **分析中心**: SQL 查询，结果表格
- **系统管理**: 操作日志

## 数据集格式（图像分类）

训练支持的目录结构：按类别分文件夹存放图片

```
datasets/{id}/
├── 类别A/
│   ├── 1.jpg
│   └── ...
├── 类别B/
│   └── ...
└── ...
```

至少需要 2 个类别，每类至少几张图片。

## 新发地报价抓取

- 默认请求 `http://www.xinfadi.com.cn/getPriceData.html`（可在环境变量 `XINFADI_PRICE_API` 中改为其它可用地址）。
- 爬虫会话使用 `requests.Session(trust_env=False)`，避免本机错误 HTTP 代理导致长时间卡在 0%。

## API 文档

启动后端后访问 http://localhost:8000/docs（若使用其它端口请相应修改）。
