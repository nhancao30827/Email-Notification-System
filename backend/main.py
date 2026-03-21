
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).parent / ".env")

from app.core.config import settings
from app.features.auth.router import router as auth_router
from app.features.campaigns.router import router as campaigns_router
from app.features.email_deliveries.router import router as deliveries_router
from app.features.recipients.router import router as recipients_router
from app.features.tracking.router import router as tracking_router
from app.infrastructure.database.session import engine
from app.infrastructure.redis.client import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="Email Distribution System",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(campaigns_router)
app.include_router(recipients_router)
app.include_router(deliveries_router)
app.include_router(tracking_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "Email Distribution System"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}

def main():
    print("Hello from backend!")


if __name__ == "__main__":
    main()

