import sys
import os
from fastapi import FastAPI
from contextlib import asynccontextmanager

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from routers import register_routers
from lifecycle.startup_events import on_startup
from lifecycle.shutdown_events import on_shutdown

@asynccontextmanager
async def lifespan(app: FastAPI):
    on_startup()
    yield
    on_shutdown()

def create_app() -> FastAPI:
    app = FastAPI(
        title="AD Tracker & Rendszerközpont",
        lifespan=lifespan
    )
    register_routers(app)
    return app
