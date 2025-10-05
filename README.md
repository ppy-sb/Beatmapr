# Beatmapr

Beatmapr is a two-part project (FastAPI backend + Vue 3 frontend) that indexes osu! packs and users while exposing leaderboards and metadata.

## Table of contents

- [Overview](#overview)
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Backend (FastAPI)](#backend-fastapi)
	- [Environment variables](#environment-variables)
	- [Maintenance scripts](#maintenance-scripts)
- [Frontend (Vite + Vue 3)](#frontend-vite--vue-3)
- [Database](#database)
- [Notes & troubleshooting](#notes--troubleshooting)
- [Contributing](#contributing)

## Overview

The repository is split into:

- `beatmapr/`: Python package powering the FastAPI application and Typer maintenance CLI.
- `web/`: Vite + Vue 3 single-page application that consumes the backend APIs.

## Repository layout

- `beatmapr/` — backend source code (config, routers, models, schemas, updaters).
- `web/` — frontend source code with project-specific Vue components and Pinia stores.
- `etc/` — project artefacts and templates:
	- `.env.example` — starter environment file you can copy to `.env`.
	- `beatmapr.app.db.example` — SQLite database snapshot for quick bootstrapping.
- `beatmapr.app.db` — default local SQLite database created at runtime (safe to delete).
- `.env` — optional runtime overrides (ignored by Git).

## Prerequisites

- Python >= 3.13
- Node.js (`^20.19.0 || >=22.12.0` as declared in `web/package.json`)
- A frontend package manager (recommended: `pnpm`, or use `npm`/`yarn`)
- Poetry for dependency management (or install requirements into a virtual environment manually)

> All command examples target Windows PowerShell. Adjust syntax if you use a different shell.

## Backend (FastAPI)

The backend lives in the `beatmapr` package and defaults to the SQLite file `beatmapr.app.db` in the repository root.

Install dependencies with Poetry:

```powershell
# from repository root
poetry install
```

Run the development server with auto-reload:

```powershell
poetry run uvicorn beatmapr.main:app --reload --host 127.0.0.1 --port 8000
```

Alternatively, run uvicorn directly from an activated environment:

```powershell
python -m uvicorn beatmapr.main:app --reload --host 127.0.0.1 --port 8000
```

FastAPI exposes interactive API docs while the server is running:

- OpenAPI UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### Environment variables

Configuration values are loaded from environment variables prefixed with `BEATMAPR_` (see `beatmapr/app/config.py`). Frequently used options:

- `BEATMAPR_DATABASE_URL` — override default database (default: `sqlite:///beatmapr.app.db`)
- `BEATMAPR_OSU_CLIENT_ID` — osu! official API client id (optional)
- `BEATMAPR_OSU_CLIENT_SECRET` — osu! official API client secret (optional)
- `BEATMAPR_AKATSUKI_BASE_URL` — akatsuki base url (default: `https://akatsuki.gg/api/v1`)
- `BEATMAPR_REQUEST_TIMEOUT_SECONDS` — request timeout for external HTTP calls

Example (PowerShell):

```powershell
$env:BEATMAPR_DATABASE_URL = 'sqlite:///C:/path/to/beatmapr.app.db'
$env:BEATMAPR_OSU_CLIENT_ID = '12345'
$env:BEATMAPR_OSU_CLIENT_SECRET = 'secret'
poetry run uvicorn beatmapr.main:app --reload
```

### Maintenance scripts

A Typer-powered CLI lives in `beatmapr/scripts.py`. When installed via Poetry the entry point is exposed as `scripts`.

Examples:

```powershell
# update packs from the osu! official API
poetry run scripts packs update

# import packs from local JSON files
poetry run scripts packs import --path ./data --recursive

# sync users from Akatsuki
poetry run scripts users sync
```

You can also run the module directly:

```powershell
python -m beatmapr.scripts packs update
```

## Frontend (Vite + Vue 3)

The SPA is located under `web/`.

Install and run (recommended: pnpm):

```powershell
cd .\web
pnpm install
pnpm run dev
```

If you prefer npm or yarn:

```powershell
cd .\web
npm install
npm run dev
```

The dev server defaults to port 5173. The backend CORS policy already allows `http://localhost:5173` and `http://127.0.0.1:5173`.

Build for production:

```powershell
cd .\web
pnpm run build
pnpm run preview
```

## Database

By default the project uses SQLite and the file `beatmapr.app.db` in the repository root. `Base.metadata.create_all` runs on startup so you rarely need manual migrations for local development.

To use another database, set `BEATMAPR_DATABASE_URL` to a SQLAlchemy-compatible URL (for example PostgreSQL) and ensure the target database is reachable.

## Notes & troubleshooting

- Running on Python < 3.13 is unsupported and may raise dependency issues.
- If the frontend cannot reach the backend, confirm uvicorn is serving on port 8000 and that you are using one of the allowed origins.
- Should `poetry run scripts` fail, fall back to `python -m beatmapr.scripts` to ensure the module is importable.

## Contributing

Open issues or PRs against the `main` branch. Keep changes small and focused. If you introduce changes that alter API contracts, update both documentation and the Vue client accordingly.

---

Authors: Syneergy, Murmur Twins, TuRou
