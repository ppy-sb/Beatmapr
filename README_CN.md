# Beatmapr

Beatmapr 是一个由 FastAPI 后端和 Vue 3 前端组成的两端项目，为 osu! 包与用户提供索引、同步和排行榜功能。

## 目录

- [概览](#概览)
- [仓库结构](#仓库结构)
- [先决条件](#先决条件)
- [后端（FastAPI）](#后端fastapi)
	- [环境变量](#环境变量)
	- [维护脚本](#维护脚本)
- [前端（Vite + Vue 3）](#前端vite--vue-3)
- [数据库](#数据库)
- [常见问题](#常见问题)
- [贡献](#贡献)

## 概览

仓库主要包括以下两部分：

- `beatmapr/`：FastAPI 应用及 Typer 维护脚本。
- `web/`：基于 Vite + Vue 3 的单页前端。

## 仓库结构

- `beatmapr/` — 后端源码（配置、路由、模型、Schema、数据同步逻辑）。
- `web/` — 前端源码（Vue 组件、Pinia store、API 工具）。
- `etc/` — 辅助文件：
	- `.env.example` — 示例环境变量文件，可复制为根目录 `.env`。
	- `beatmapr.app.db.example` — 示例 SQLite 数据库，可用于快速体验。
- `beatmapr.app.db` — 默认在运行时生成的 SQLite 数据库（可安全删除以重建）。
- `.env` — 可选的本地环境变量覆盖文件（已加入 .gitignore）。

## 先决条件

- Python >= 3.13
- Node.js（遵循 `web/package.json` 中的 engines：`^20.19.0 || >=22.12.0`）
- 前端包管理器（推荐使用 `pnpm`，也可使用 `npm` / `yarn`）
- Poetry（推荐）或其他方式安装 Python 依赖

> 文中命令均以 Windows PowerShell 语法为例，其他 shell 请自行调整。

## 后端（FastAPI）

后端位于 `beatmapr` 包，默认使用仓库根目录的 SQLite 文件 `beatmapr.app.db`。

使用 Poetry 安装依赖：

```powershell
# 在仓库根目录执行
poetry install
```

运行开发服务器（启用自动重载）：

```powershell
poetry run uvicorn beatmapr.main:app --reload --host 127.0.0.1 --port 8000
```

或者在已激活的虚拟环境中直接使用 Python：

```powershell
python -m uvicorn beatmapr.main:app --reload --host 127.0.0.1 --port 8000
```

启动后可访问交互式 API 文档：

- OpenAPI UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 环境变量

配置从 `BEATMAPR_` 前缀的环境变量读取（详见 `beatmapr/app/config.py`）。常见选项包括：

- `BEATMAPR_DATABASE_URL` — 覆盖默认数据库（默认：`sqlite:///beatmapr.app.db`）
- `BEATMAPR_OSU_CLIENT_ID` — osu! 官方 API client id（可选）
- `BEATMAPR_OSU_CLIENT_SECRET` — osu! 官方 API client secret（可选）
- `BEATMAPR_AKATSUKI_BASE_URL` — Akatsuki API 基础地址（默认：`https://akatsuki.gg/api/v1`）
- `BEATMAPR_REQUEST_TIMEOUT_SECONDS` — 外部请求超时（秒）

示例（PowerShell）：

```powershell
$env:BEATMAPR_DATABASE_URL = 'sqlite:///C:/path/to/beatmapr.app.db'
$env:BEATMAPR_OSU_CLIENT_ID = '12345'
$env:BEATMAPR_OSU_CLIENT_SECRET = 'secret'
poetry run uvicorn beatmapr.main:app --reload
```

### 维护脚本

项目提供基于 Typer 的 CLI（目录 `beatmapr/scripts.py`）。若通过 Poetry 安装，可直接使用 `scripts` 入口。

示例：

```powershell
# 从 osu! 官方 API 更新包数据
poetry run scripts packs update

# 从本地 JSON 文件导入包数据
poetry run scripts packs import --path ./data --recursive

# 从 Akatsuki 同步用户
poetry run scripts users sync
```

也可直接运行模块：

```powershell
python -m beatmapr.scripts packs update
```

## 前端（Vite + Vue 3）

前端 SPA 位于 `web/` 目录。

安装并运行（建议使用 pnpm）：

```powershell
cd .\web
pnpm install
pnpm run dev
```

使用 npm：

```powershell
cd .\web
npm install
npm run dev
```

开发服务器默认运行在 5173 端口，后端已允许 `http://localhost:5173` 与 `http://127.0.0.1:5173` 的跨域请求。

生产构建：

```powershell
cd .\web
pnpm run build
pnpm run preview
```

## 数据库

默认使用 SQLite（文件 `beatmapr.app.db`）。后端启动时会通过 SQLAlchemy 的 `Base.metadata.create_all` 自动构建表结构，无需额外迁移即可开始开发。

若需改用其他数据库，请设置 `BEATMAPR_DATABASE_URL` 为兼容 SQLAlchemy 的连接字符串（例如 PostgreSQL），并确保服务可访问。

## 常见问题

- Python 版本低于 3.13 可能触发依赖冲突，建议严格遵循版本要求。
- 如果前端无法访问后端，请确认 uvicorn 服务器在 8000 端口运行，并使用允许的来源地址。
- 如 `poetry run scripts` 执行失败，可退回使用 `python -m beatmapr.scripts`。

## 贡献

请在 `main` 分支提 issue 或 PR，保持提交小而明确。若修改 API 合约，请同步更新文档和前端页面。

---

作者: Syneergy, Murmur Twins, TuRou
