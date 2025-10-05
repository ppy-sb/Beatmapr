from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from beatmapr.app.config import get_settings
from beatmapr.app.database import Base, engine
from beatmapr.app.routers import leaderboard, meta, packs, users

Base.metadata.create_all(bind=engine)

settings = get_settings()

app = FastAPI(title="Beatmapr", version="2.0.0")

# Configure CORS origins based on settings
cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if hasattr(settings, 'frontend_origin') and settings.frontend_origin:
    cors_origins.append(settings.frontend_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(packs.router)
app.include_router(users.router)
app.include_router(leaderboard.router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
