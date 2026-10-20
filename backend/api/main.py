import os
import json
import hashlib
import io
import secrets
from pathlib import Path
from PIL import Image, UnidentifiedImageError
import uuid
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager

import asyncpg
import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form
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


MAX_IMAGE_BYTES = 12 * 1024 * 1024
PHOTO_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
STORAGE_PHOTO_KINDS = {"front", "rear", "left", "right", "vin", "dashboard", "damage", "other", "pts"}

def private_photo_root():
    raw = os.getenv("MOTOTECH_PRIVATE_PHOTO_ROOT", "").strip()
    if not raw:
        raise HTTPException(503, "Private photo storage not configured")
    root = Path(raw).expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise HTTPException(503, "Private photo directory unavailable")
    return root

@app.post("/storage/{contract_id}/photos", status_code=201)
async def upload_storage_photo(
    contract_id: uuid.UUID,
    kind: str = Form(...),
    note: str = Form(""),
    photo: UploadFile = File(...),
    person=Depends(require_roles(*ROLES)),
    db=Depends(database),
):
    if kind not in STORAGE_PHOTO_KINDS:
        raise HTTPException(422, "Unknown photo category")
    if kind == "damage" and not note.strip():
        raise HTTPException(422, "Damage description is required")
    if len(note) > 2000:
        raise HTTPException(422, "Photo note is too long")
    root = private_photo_root()
    raw = await photo.read(MAX_IMAGE_BYTES + 1)
    await photo.close()
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image exceeds 12 MB limit")
    try:
        with Image.open(io.BytesIO(raw)) as source:
            if source.format not in PHOTO_TYPES:
                raise HTTPException(415, "Unsupported image format")
            source.verify()
        with Image.open(io.BytesIO(raw)) as source:
            source.load()
            if source.width * source.height > 35_000_000:
                raise HTTPException(413, "Image dimensions too large")
            clean_image = source.convert("RGB")
            encoded = io.BytesIO()
            clean_image.save(encoded, format="JPEG", quality=88, optimize=True)
            data = encoded.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(415, "Invalid image")
    photo_id = uuid.uuid4()
    relative = f"{contract_id}/{photo_id}.jpg"
    directory = root / str(contract_id)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = directory / f"{photo_id}.jpg"
    temp = directory / f".{photo_id}.{secrets.token_hex(8)}.tmp"
    try:
        with temp.open("xb") as output:
            output.write(data)
        os.chmod(temp, 0o600)
        os.replace(temp, target)
        async with db.acquire() as c:
            async with c.transaction():
                contract = await c.fetchrow("SELECT id,status FROM storage_contracts WHERE id=$1 FOR UPDATE", contract_id)
                if not contract:
                    raise HTTPException(404, "Contract not found")
                if contract["status"] not in ("draft", "stored", "return_requested"):
                    raise HTTPException(409, "Cannot add photos to a closed contract")
                await c.execute("""INSERT INTO storage_photos
                     (id,contract_id,kind,object_key,sha256,mime_type,size_bytes,note,uploaded_by)
                     VALUES($1,$2,$3,$4,$5,'image/jpeg',$6,$7,$8)""",
                     photo_id, contract_id, kind, relative,
                     hashlib.sha256(data).hexdigest(), len(data), note.strip(), person["id"])
                await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id,payload)
                    VALUES($1,'photo_added',$2,$3::jsonb)""",contract_id,person["id"],
                    json.dumps({"photo_id":str(photo_id),"kind":kind}))
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)
    return {"id":photo_id,"kind":kind,"note":note.strip()}

class IntakeConfirmation(BaseModel):
    version: int = Field(ge=1)
    condition_confirmed: bool

@app.post("/storage/{contract_id}/accept")
async def accept_storage(
    contract_id: uuid.UUID, payload: IntakeConfirmation,
    person=Depends(require_roles(*ROLES)), db=Depends(database)
):
    if not payload.condition_confirmed:
        raise HTTPException(422, "Confirm completed motorcycle condition inspection")
    async with db.acquire() as c:
        async with c.transaction():
            contract = await c.fetchrow("""SELECT status,version,body_condition,damage_description
                                          FROM storage_contracts WHERE id=$1 FOR UPDATE""", contract_id)
            if not contract:
                raise HTTPException(404, "Contract not found")
            if contract["version"] != payload.version:
                raise HTTPException(409, "Contract changed; refresh before acceptance")
            if not (contract["body_condition"] or "").strip():
                raise HTTPException(422, "Document the motorcycle body condition")
            photos = await c.fetch("""SELECT kind,note,object_key FROM storage_photos
                WHERE contract_id=$1 AND deleted_at IS NULL""", contract_id)
            root = private_photo_root()
            if not all((root / row["object_key"]).is_file() for row in photos):
                raise HTTPException(409, "One or more uploaded photos are missing")
            try:
                validate_transition(contract["status"], "stored", [dict(row) for row in photos])
            except ValueError as exc:
                raise HTTPException(409, str(exc))
            updated = await c.fetchrow("""UPDATE storage_contracts
                SET status='stored',received_at=now(),updated_at=now(),
                    updated_by=$2,version=version+1 WHERE id=$1
                RETURNING id,status,version,received_at""", contract_id, person["id"])
            await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id)
                               VALUES($1,'accepted',$2)""", contract_id, person["id"])
    return dict(updated)

# Employee provisioning remains an administrator-only offline operation.
