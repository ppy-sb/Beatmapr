from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from beatmapr.app.config import get_settings
from beatmapr.app.database import Base, engine
from beatmapr.app.routers import leaderboard, meta, packs, users
from beatmapr.app.updaters.packs import PackUpdater

Base.metadata.create_all(bind=engine)

settings = get_settings()

app = FastAPI(title="Beatmapr", version="2.0.0")

# Configure CORS origins based on settings
cors_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
if hasattr(settings, "frontend_origin") and settings.frontend_origin:
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

# 新增：自动更新图包的函数
def update_packs_job():
    PACK_BATCH_SIZE = 10
    print(f"Starting weekly packs update process...(batch_size={PACK_BATCH_SIZE})")
    updater = PackUpdater()
    
    try:
        tag_idx = updater.find_largest_index()
        updater.update_standard(batch_size=PACK_BATCH_SIZE, tag_index=tag_idx)
        updater.update_other(batch_size=PACK_BATCH_SIZE)
        print("Packs update completed successfully.")
    except Exception as exc:
        print(f"An error occurred during the packs update: {exc}")


# 新增：初始化调度器
def init_scheduler():
    scheduler = BackgroundScheduler()
    
    scheduler.add_job(
        update_packs_job,
        trigger=CronTrigger(
            day_of_week=5,  
            hour=0,         
            minute=0,      
            second=0        
        ),
        id="weekly_packs_update",
        name="Weekly packs automatic update",
        replace_existing=True
    )
    
    scheduler.start()
    print("Scheduled task manager is now running: packs will be automatically updated every Saturday at 00:00.")


# 新增：应用启动时初始化调度器
@app.on_event("startup")
async def startup_event():
    init_scheduler()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.bind_host, port=settings.bind_port)
