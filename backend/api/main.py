import os
from contextlib import asynccontextmanager
import asyncpg
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5, ssl="require" if "localhost" not in dsn else None)
    try:
        yield
    finally:
        if pool:
            await pool.close()

app = FastAPI(title="MOTO TECH Service API", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://nyaganmaksimov-sys.github.io"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)

@app.get("/")
async def root():
    return {"app": "MOTO TECH Service API", "status": "online", "api_version": "0.3.0"}

@app.get("/health")
async def health():
    if not pool:
        raise HTTPException(status_code=503, detail="DATABASE_URL not configured")
    try:
        async with pool.acquire() as connection:
            await connection.fetchval("SELECT 1")
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok", "database": "connected"}

# Protected write endpoints will be enabled only after role-based authentication,
# transactional mandatory intake photos and object storage are implemented.
