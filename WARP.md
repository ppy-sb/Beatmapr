# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Beatmapr is a two-part project consisting of:
- **Backend**: FastAPI application with SQLAlchemy models and Typer CLI scripts
- **Frontend**: Vue 3 + Vite SPA with TypeScript and Pinia for state management

The project indexes osu! song packs with user data and exposes leaderboards and metadata through REST APIs.

## Common Development Commands

### Backend (FastAPI)

```bash
# Install dependencies
poetry install

# Run development server
poetry run uvicorn beatmapr.main:app --host 127.0.0.1 --port 8000 --reload

# Run maintenance scripts
poetry run scripts packs update
poetry run scripts packs import --path ./data --recursive
poetry run scripts users sync
poetry run scripts users totals

# Alternative script execution
python -m beatmapr.scripts packs update
```

### Frontend (Vue 3 + Vite)

```bash
# Install dependencies (recommended: pnpm)
cd web && pnpm install

# Run development server (default port: 5173)
pnpm run dev

# Build for production
pnpm run build
pnpm run preview

# Type checking
pnpm run type-check
```

## Architecture Overview

### Backend Structure

- **`beatmapr/main.py`**: FastAPI application entry point with CORS middleware and router registration
- **`beatmapr/scripts.py`**: Typer CLI for maintenance tasks (pack updates, user syncing)
- **`beatmapr/app/`**: Core application package
  - **`config.py`**: Pydantic settings with environment variable loading (BEATMAPR_ prefix)
  - **`database.py`**: SQLAlchemy engine and session management
  - **`models.py`**: Database models (Pack, Beatmap, User, UserScore with relationships)
  - **`schemas.py`**: Pydantic models for API serialization
  - **`routers/`**: FastAPI route handlers (leaderboard, meta, packs, users)
  - **`updaters/`**: Data synchronization logic for packs and users from external APIs

### Frontend Structure

- **`web/src/App.vue`**: Root Vue component
- **`web/src/components/`**: Reusable Vue components (NavBar, PackGrid, ProfileBanner, etc.)
- **`web/src/views/`**: Page-level components (HomeView, LeaderboardsView)
- **`web/src/stores/`**: Pinia stores for state management

### Database Schema

The application uses SQLAlchemy with these key entities:
- **Pack**: Song pack metadata with many-to-many relationship to beatmaps
- **Beatmap**: Individual map data with osu! API fields (star_rating, ar, od, etc.)
- **User**: Player profiles with completion stats and rankings
- **UserScore**: Individual scores linking users to beatmaps with performance data
- **PackBeatmap**: Junction table for pack-beatmap relationships with position ordering

### Data Flow

1. **Pack Updates**: CLI scripts fetch pack data from osu! official API and store in SQLite
2. **User Sync**: Asynchronous sync from Akatsuki API with batch processing and retry logic
3. **API Layer**: FastAPI routers serve JSON data to the Vue frontend
4. **Frontend**: Axios HTTP client consumes APIs, Pinia manages state, Vue Router handles navigation

## Environment Configuration

Key environment variables (prefix with `BEATMAPR_`):
- `DATABASE_URL`: SQLAlchemy database URL (default: sqlite:///beatmapr.app.db)
- `OSU_CLIENT_ID` / `OSU_CLIENT_SECRET`: osu! API credentials for pack updates
- `AKATSUKI_BASE_URL`: Akatsuki API base URL for user sync
- `REQUEST_TIMEOUT_SECONDS`: HTTP client timeout setting

## Development Notes

- Python >=3.13 required for backend
- Node.js ^20.19.0 || >=22.12.0 required for frontend
- Database migrations are automatic via `Base.metadata.create_all()` on startup
- CORS is pre-configured for localhost:5173 and 127.0.0.1:5173
- The project uses Poetry for Python dependency management
- Frontend uses TypeScript with strict type checking
- No test suite is currently configured

## API Documentation

When the backend is running, interactive API docs are available at:
- OpenAPI UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc