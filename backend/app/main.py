from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from .database import init_db
from .api.auth import router as auth_router
from .api.accounts import router as accounts_router
from .api.items import router as items_router
from .api.keywords import router as keywords_router
from .api.default_replies import router as default_replies_router
from .api.confirm_receipt import router as confirm_receipt_router
from .api.orders import router as orders_router
from .api.statistics import router as statistics_router
from .api.qr_login import router as qr_login_router
from .api.delivery import router as delivery_router
from .api.internal import router as internal_router
from .api.diagnostics import router as diagnostics_router
from .api.publish import router as publish_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Xianyu Lite", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(items_router, prefix="/api/v1")
app.include_router(keywords_router, prefix="/api/v1")
app.include_router(default_replies_router, prefix="/api/v1")
app.include_router(confirm_receipt_router, prefix="/api/v1")
app.include_router(orders_router, prefix="/api/v1")
app.include_router(statistics_router, prefix="/api/v1")
app.include_router(qr_login_router, prefix="/api/v1")
app.include_router(delivery_router, prefix="/api/v1")
app.include_router(diagnostics_router, prefix="/api/v1")
app.include_router(publish_router, prefix="/api/v1")
app.include_router(internal_router)

uploads_dir = Path("/app/uploads")
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

@app.get("/health")
async def health():
    return {"success": True, "message": "running"}
