# 9Bot

一个面向个人使用的 A 股本地分析工作台，当前采用前后端分离目录结构：
- `frontend/`：React + TypeScript + Vite 前端
- `backend/`：FastAPI + SQLite + AkShare + Anthropic SDK 后端

9Bot 提供自选股管理、行情刷新、技术指标计算、K 线图查看，以及基于本地缓存数据生成 AI 日报的能力。项目仍然保持“本地优先、单用户、轻量可维护”的目标，但代码组织已经调整为更清晰的 monorepo 结构。

## 功能特性

- 自选股管理：添加、删除 A 股 6 位代码自选股
- 本地行情缓存：从 AkShare 拉取实时快照与历史日线，并写入 SQLite
- 技术指标分析：计算 MA5/10/20/60、MACD、RSI14，并生成简洁信号摘要
- 图表展示：前端展示 K 线、均线、成交量、MACD、RSI
- AI 日报生成：基于本地缓存数据生成中文自选股日报，并保存到本地数据库

## 技术栈

- Backend: FastAPI, Uvicorn, SQLite, pandas, AkShare, Anthropic Python SDK
- Frontend: React, TypeScript, Vite, React Router, ECharts

## 项目结构

```text
9Bot/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # FastAPI 入口
│  │  ├─ config.py               # 环境变量与配置加载
│  │  ├─ db.py                   # SQLite 持久化层
│  │  ├─ routers/
│  │  │  └─ api.py               # JSON API 路由
│  │  └─ services/
│  │     ├─ market_data.py       # AkShare 行情拉取与看板数据组装
│  │     ├─ indicators.py        # 技术指标与图表数据生成
│  │     ├─ report_generator.py  # AI 日报生成与落库
│  │     └─ prompt_builder.py    # 日报提示词构造
│  ├─ tests/                     # 后端测试
│  ├─ pyproject.toml             # pytest 配置
│  ├─ requirements.txt
│  └─ requirements-dev.txt
├─ conf/
│  └─ .env.example               # 环境变量示例
├─ frontend/
│  ├─ src/
│  │  ├─ api/                    # 前端 API client 和类型
│  │  ├─ pages/                  # Dashboard / Stock / Report 页面
│  │  ├─ App.tsx                 # 前端路由入口
│  │  └─ main.tsx                # React 挂载入口
│  ├─ package.json
│  └─ vite.config.ts
├─ data/                         # 本地数据库与运行时文件
├─ start.bat                     # Windows 全栈开发启动脚本
├─ start.sh                      # Linux/macOS 全栈开发启动脚本
├─ README.md
└─ CLAUDE.md
```

## 快速开始

### 1. 配置后端环境变量

复制 `conf/.env.example` 为 `conf/.env`，至少补充 Anthropic API Key：

```bash
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_MODEL=claude-opus-4-6
ANTHROPIC_MAX_TOKENS=16000
NINEBOT_DATA_DIR=data
NINEBOT_DB_PATH=data/9bot.db
NINEBOT_HISTORY_DAYS=365
NINEBOT_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
NINEBOT_FRONTEND_DIST=../frontend/dist
```

说明：
- `ANTHROPIC_API_KEY`：生成 AI 日报时必填
- `NINEBOT_DB_PATH`：后端 SQLite 数据库路径，默认相对仓库根目录
- `NINEBOT_HISTORY_DAYS`：刷新历史行情时回看的天数
- `NINEBOT_CORS_ORIGINS`：允许访问后端 API 的前端来源
- `NINEBOT_FRONTEND_DIST`：如果后续要让后端托管打包产物，可指向 `../frontend/dist`（这个路径仍相对 `backend/` 解析）

### 2. 启动开发环境

#### Windows

```bat
start.bat
```

#### Linux / macOS

```bash
./start.sh
```

启动脚本位于项目根目录，会自动：
1. 在 `backend/` 下创建 `.venv`（如果不存在）
2. 安装 `backend/requirements.txt`
3. 安装 `frontend/package.json` 依赖
4. 同时启动后端 API 和前端开发服务器

默认地址：
- Frontend: `http://127.0.0.1:5173`
- Backend API: `http://127.0.0.1:8000`

可通过环境变量覆盖监听地址：
- `NINEBOT_HOST`
- `NINEBOT_PORT`
- `NINEBOT_FRONTEND_HOST`
- `NINEBOT_FRONTEND_PORT`

## 单独运行前后端

### 后端

```bash
cd backend
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m app.main
```

Windows:

```bat
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m app.main
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

常用前端命令：
- `npm run dev`
- `npm run build`
- `npm run lint`
- `npm run preview`

## 前端工作区说明

前端基于官方 `React + TypeScript + Vite` 模板整理而来，并按当前项目做了业务接入：
- 开发环境支持 HMR（热更新）
- Vite 插件使用 `@vitejs/plugin-react`
- ESLint 配置位于 `frontend/eslint.config.js`
- TypeScript 配置位于 `frontend/tsconfig.app.json` 和 `frontend/tsconfig.node.json`
- 如果后续要继续加强前端静态检查，优先在 `frontend/eslint.config.js` 上扩展，而不是再维护一份独立的前端 README

## 使用流程

1. 打开前端看板页
2. 输入 6 位 A 股代码，加入自选股
3. 点击刷新行情，从 AkShare 拉取快照和历史日线
4. 在看板查看最新技术状态
5. 打开个股详情页查看图表和指标
6. 生成 AI 日报，并查看最新日报或历史日报

## 前端路由

- `/`：看板
- `/stocks/:symbol`：个股详情
- `/reports/latest`：最新日报
- `/reports/:reportDate`：指定日期日报

## 后端 API 概览

- `GET /api/dashboard`：获取看板数据和最近日报摘要
- `POST /api/watchlist`：添加自选股
- `DELETE /api/watchlist/{symbol}`：删除自选股
- `POST /api/watchlist/refresh`：刷新自选股行情
- `GET /api/stocks/{symbol}`：获取个股详情摘要
- `GET /api/stocks/{symbol}/chart`：获取图表数据
- `GET /api/reports/latest`：获取最新日报
- `GET /api/reports/{report_date}`：获取指定日期日报
- `POST /api/reports`：生成 AI 日报

## AI 日报说明

AI 日报由 `backend/app/services/report_generator.py` 负责生成，特点如下：
- 使用官方 `anthropic` Python SDK
- 默认模型为 `claude-opus-4-6`
- 使用流式响应
- 开启 adaptive thinking
- 配置 `output_config={"effort": "high"}`
- 系统提示词启用 ephemeral cacheable content
- 日报内容与上下文都会保存到本地 SQLite

为了保证输出稳定性，日报上下文会以确定性顺序序列化，再发送给模型。

## 数据存储

项目当前只持久化三类数据：
- `watchlist`：自选股列表
- `daily_bars`：本地缓存的历史日线
- `daily_reports`：生成后的日报内容与上下文

默认数据库位置是 `data/9bot.db`，韭研公社登录态与抓图等运行时文件也默认保存在 `data/jygs/` 下。

## 测试

先安装后端开发依赖：

### Windows

```bat
cd backend
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

### Linux / macOS

```bash
cd backend
.venv/bin/python -m pip install -r requirements-dev.txt
```

运行全部后端测试：

### Windows

```bat
cd backend
.venv\Scripts\python.exe -m pytest
```

### Linux / macOS

```bash
cd backend
.venv/bin/python -m pytest
```

运行单个测试文件：

```bash
cd backend
pytest tests/test_indicators.py
```

说明：
- 报告生成测试会 mock Anthropic 调用，默认离线运行
- 当前没有 live AkShare 集成测试，若修改行情字段映射，建议手动验证刷新流程

## 开发说明

- 后端业务逻辑集中在 `backend/app/services`
- 持久化逻辑集中在 `backend/app/db.py`
- 前端 API 封装在 `frontend/src/api`
- React 页面在 `frontend/src/pages`
- 图表渲染逻辑在前端完成，依赖 ECharts npm 包

## 注意事项

- 仅支持 6 位 A 股代码输入
- 行情依赖 AkShare 上游接口可用性
- 生成日报前需要先配置 `ANTHROPIC_API_KEY`
- AI 输出仅基于本地缓存的结构化数据，不会自动补充新闻、公告或基本面信息
- 项目定位为个人研究工具，不构成投资建议
- `.venv` 仍位于 `backend/`；本地运行时数据和环境变量文件现在统一放在仓库根目录的 `data/` 与 `conf/` 下
- 如果你之前还在使用 `backend/data` 或 `backend/.env`，请手动迁移到新的根目录位置

## License

当前仓库未声明 License。如需开源，请补充许可证文件。
