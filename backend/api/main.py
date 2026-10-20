import os
import json
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import asyncpg
import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.api.storage_rules import normalize_vin, validate_transition

pool = None
password_hash = PasswordHash.recommended()
JWT_SECRET = os.getenv("MOTOTECH_JWT_SECRET", "")
ALGORITHM = "HS256"
ROLES = {"owner_manager", "manager", "administrator", "mechanic"}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=5,
                                         ssl="require" if "localhost" not in dsn and "127.0.0.1" not in dsn else None)
    try:
        yield
    finally:
        if pool:
            await pool.close()
            pool = None

app = FastAPI(title="MOTO TECH Service API", version="0.4.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("MOTOTECH_ALLOWED_ORIGINS", "").split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

async def database():
    if pool is None:
        raise HTTPException(503, "Database not configured")
    return pool

async def actor(authorization: str | None = Header(default=None), db=Depends(database)):
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise HTTPException(503, "Authentication secret not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        data = jwt.decode(authorization[7:], JWT_SECRET, algorithms=[ALGORITHM],
                          options={"require": ["exp", "sub", "iat"]})
        staff_id = uuid.UUID(data["sub"])
    except (InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, "Invalid session")
    async with db.acquire() as c:
        row = await c.fetchrow("SELECT id,username,full_name,role FROM service_employees WHERE id=$1 AND active=true", staff_id)
    if not row:
        raise HTTPException(401, "Employee account disabled or missing")
    return dict(row)

def require_roles(*roles):
    async def check(person=Depends(actor)):
        if person["role"] not in roles:
            raise HTTPException(403, "Insufficient permissions")
        return person
    return check

class Login(BaseModel):
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=1, max_length=256)

class StorageDraft(BaseModel):
    contract_number: str = Field(min_length=1,max_length=80)
    owner_name: str = Field(min_length=1,max_length=250)
    owner_phone: str | None = Field(default=None,max_length=80)
    vin: str = Field(min_length=1,max_length=64)
    brand_model: str = Field(min_length=1,max_length=200)
    plate: str | None = Field(default=None,max_length=30)
    location_label: str | None = Field(default=None,max_length=100)
    monthly_rate_rub: Decimal = Field(default=Decimal('0'),ge=0,le=100000000)
    body_condition: str | None = Field(default=None,max_length=10000)
    damage_description: str | None = Field(default=None,max_length=10000)

@app.get("/")
async def root():
    return {"app": "MOTO TECH Service API", "status": "online", "api_version": "0.4.0"}

@app.get("/health")
async def health(db=Depends(database)):
    try:
        async with db.acquire() as c:
            await c.fetchval("SELECT 1")
    except Exception:
        raise HTTPException(503, "Database unavailable")
    return {"status": "ok", "database": "connected"}

@app.post("/auth/login")
async def login(payload: Login, db=Depends(database)):
    if not JWT_SECRET or len(JWT_SECRET) < 32:
        raise HTTPException(503, "Authentication secret not configured")
    async with db.acquire() as c:
        row = await c.fetchrow("SELECT id,username,password_hash,full_name,role FROM service_employees WHERE username=$1 AND active=true", payload.username.strip().lower())
    # Dummy hash verification for nonexistent accounts to limit account enumeration timing.
    if row is None:
        password_hash.hash("dummy")
        raise HTTPException(401, "Invalid credentials")
    if not password_hash.verify(payload.password, row["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(row["id"]), "iat": now, "exp": now + timedelta(hours=8)}, JWT_SECRET, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer", "expires_in": 28800,
            "profile": {"username": row["username"], "full_name": row["full_name"], "role": row["role"]}}

@app.get("/auth/me")
async def me(person=Depends(actor)):
    return {"id": str(person["id"]), "username": person["username"],
            "full_name": person["full_name"], "role": person["role"]}

@app.get("/storage")
async def list_storage(person=Depends(require_roles(*ROLES)), db=Depends(database)):
    async with db.acquire() as c:
        rows = await c.fetch("""SELECT id,contract_number,status,owner_name,vin,brand_model,
          location_label,updated_at,version FROM storage_contracts ORDER BY updated_at DESC LIMIT 300""")
    return [dict(row) for row in rows]

@app.post("/storage", status_code=201)
async def create_storage(payload: StorageDraft, person=Depends(require_roles(*ROLES)), db=Depends(database)):
    if not normalize_vin(payload.vin):
        raise HTTPException(422, "Invalid VIN/frame identifier")
    try:
        async with db.acquire() as c:
            async with c.transaction():
                row = await c.fetchrow("""INSERT INTO storage_contracts
                  (contract_number,owner_name,owner_phone,vin,brand_model,plate,location_label,
                   monthly_rate_rub,body_condition,damage_description,created_by,updated_by,status)
                  VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$11,'draft')
                  RETURNING id,contract_number,status,version""",
                  payload.contract_number.strip(),payload.owner_name.strip(),payload.owner_phone,
                  normalize_vin(payload.vin),payload.brand_model.strip(),payload.plate,payload.location_label,
                  payload.monthly_rate_rub,payload.body_condition,payload.damage_description,person["id"])
                await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id)
                                   VALUES($1,'created',$2)""",row["id"],person["id"])
        return dict(row)
    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "Contract number or active VIN already exists")

@app.get("/storage/{contract_id}")
async def storage_detail(contract_id: uuid.UUID, person=Depends(require_roles(*ROLES)), db=Depends(database)):
    async with db.acquire() as c:
        contract = await c.fetchrow("SELECT * FROM storage_contracts WHERE id=$1",contract_id)
        if not contract:
            raise HTTPException(404, "Contract not found")
        photos = await c.fetch("""SELECT id,kind,note,uploaded_at,uploaded_by FROM storage_photos
                                  WHERE contract_id=$1 AND deleted_at IS NULL ORDER BY uploaded_at""",contract_id)
        events = await c.fetch("""SELECT event_type,actor_id,happened_at,payload FROM storage_events
                                  WHERE contract_id=$1 ORDER BY happened_at DESC LIMIT 100""",contract_id)
    result = dict(contract)
    result["photos"] = [dict(r) for r in photos]
    result["events"] = [dict(r) for r in events]
    return result


class ReturnRequest(BaseModel):
    version: int = Field(ge=1)
    note: str = Field(default="", max_length=2000)

class ReturnHandover(BaseModel):
    version: int = Field(ge=1)
    received_by: str = Field(min_length=2, max_length=250)
    condition_at_return: str = Field(min_length=3, max_length=5000)
    all_keys_returned: bool
    documents_returned: bool

@app.post("/storage/{contract_id}/request-return")
async def request_storage_return(
    contract_id: uuid.UUID, payload: ReturnRequest,
    person=Depends(require_roles(*ROLES)), db=Depends(database)
):
    async with db.acquire() as c:
        async with c.transaction():
            row = await c.fetchrow("SELECT status,version FROM storage_contracts WHERE id=$1 FOR UPDATE", contract_id)
            if not row:
                raise HTTPException(404, "Contract not found")
            if row["version"] != payload.version:
                raise HTTPException(409, "Contract changed; reload before proceeding")
            try:
                validate_transition(row["status"], "return_requested", [])
            except ValueError as exc:
                raise HTTPException(409, str(exc))
            updated = await c.fetchrow("""UPDATE storage_contracts
                SET status='return_requested',updated_at=now(),updated_by=$2,version=version+1
                WHERE id=$1 RETURNING id,status,version""", contract_id, person["id"])
            await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id,payload)
                VALUES($1,'return_requested',$2,$3::jsonb)""",
                contract_id, person["id"], json.dumps({"note": payload.note}))
    return dict(updated)

@app.post("/storage/{contract_id}/handover")
async def complete_storage_handover(
    contract_id: uuid.UUID, payload: ReturnHandover,
    person=Depends(require_roles(*ROLES)), db=Depends(database)
):
    if not payload.all_keys_returned or not payload.documents_returned:
        raise HTTPException(422, "Confirm return of keys and documents before handover")
    async with db.acquire() as c:
        async with c.transaction():
            row = await c.fetchrow("SELECT status,version FROM storage_contracts WHERE id=$1 FOR UPDATE", contract_id)
            if not row:
                raise HTTPException(404, "Contract not found")
            if row["version"] != payload.version:
                raise HTTPException(409, "Contract changed; reload before proceeding")
            try:
                validate_transition(row["status"], "returned", [])
            except ValueError as exc:
                raise HTTPException(409, str(exc))
            updated = await c.fetchrow("""UPDATE storage_contracts
                SET status='returned',returned_at=now(),updated_at=now(),
                    updated_by=$2,version=version+1
                WHERE id=$1 RETURNING id,status,returned_at,version""",
                contract_id, person["id"])
            await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id,payload)
                VALUES($1,'returned',$2,$3::jsonb)""",
                contract_id, person["id"], json.dumps({
                    "received_by": payload.received_by.strip(),
                    "condition_at_return": payload.condition_at_return.strip(),
                    "all_keys_returned": True, "documents_returned": True
                }))
    return dict(updated)

# Acceptance and photo uploads remain disabled until private object storage is operational.
# Employee provisioning remains an administrator-only offline operation.
