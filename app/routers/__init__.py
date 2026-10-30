from fastapi import FastAPI
from routers import (
    web, auth, users, ad_analytics, telemetry,
    sync, history, backups, github, ai, settings, easy_project
)

def register_routers(app: FastAPI) -> None:
    app.include_router(web.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(ad_analytics.router)
    app.include_router(telemetry.router)
    app.include_router(sync.router)
    app.include_router(history.router)
    app.include_router(backups.router)
    app.include_router(github.router)
    app.include_router(ai.router)
    app.include_router(settings.router)
    app.include_router(easy_project.router)
