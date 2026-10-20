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
from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File, Form, Response
from starlette.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.api.storage_rules import normalize_vin, validate_transition
from backend.api import supabase_storage

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
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
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


@app.get("/storage/{contract_id}/photos/{photo_id}")
async def view_storage_photo(
    contract_id: uuid.UUID, photo_id: uuid.UUID,
    person=Depends(require_roles(*ROLES)), db=Depends(database)
):
    """Serve private photo bytes only after checking employee authorization and ownership."""
    async with db.acquire() as c:
        key = await c.fetchval(
            """SELECT object_key FROM storage_photos
               WHERE id=$1 AND contract_id=$2 AND deleted_at IS NULL""",
            photo_id, contract_id
        )
    if key is None:
        raise HTTPException(404, "Photo not found")
    if not key.startswith("supabase:"):
        raise HTTPException(409, "Legacy photo storage is not accessible through this endpoint")
    if not supabase_storage.configured():
        raise HTTPException(503, "Private photo storage unavailable")
    try:
        data = await run_in_threadpool(supabase_storage.download_private_image, key)
    except Exception:
        raise HTTPException(502, "Photo could not be retrieved from private storage")
    return Response(
        content=data, media_type="image/jpeg",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    )



class StorageEdit(BaseModel):
    version: int = Field(ge=1)
    owner_name: str = Field(min_length=1,max_length=250)
    owner_phone: str | None = Field(default=None,max_length=80)
    brand_model: str = Field(min_length=1,max_length=200)
    plate: str | None = Field(default=None,max_length=30)
    location_label: str | None = Field(default=None,max_length=100)
    monthly_rate_rub: Decimal = Field(ge=0,le=100000000)
    body_condition: str = Field(min_length=1,max_length=10000)
    damage_description: str | None = Field(default=None,max_length=10000)

@app.patch("/storage/{contract_id}")
async def edit_storage(
    contract_id: uuid.UUID, payload: StorageEdit,
    person=Depends(require_roles("owner_manager","manager","administrator")),
    db=Depends(database)
):
    async with db.acquire() as c:
        async with c.transaction():
            existing = await c.fetchrow("SELECT status,version FROM storage_contracts WHERE id=$1 FOR UPDATE",contract_id)
            if not existing:
                raise HTTPException(404,"Contract not found")
            if existing["status"] == "returned":
                raise HTTPException(409,"Returned contracts are read-only")
            if existing["version"] != payload.version:
                raise HTTPException(409,"Card changed: reload before editing")
            updated = await c.fetchrow("""UPDATE storage_contracts SET
              owner_name=$2,owner_phone=$3,brand_model=$4,plate=$5,location_label=$6,
              monthly_rate_rub=$7,body_condition=$8,damage_description=$9,
              updated_by=$10,updated_at=now(),version=version+1 WHERE id=$1
              RETURNING id,version,status""",contract_id,payload.owner_name.strip(),
              payload.owner_phone,payload.brand_model.strip(),payload.plate,
              payload.location_label,payload.monthly_rate_rub,payload.body_condition.strip(),
              payload.damage_description,person["id"])
            await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id)
                               VALUES($1,'updated',$2)""",contract_id,person["id"])
    return dict(updated)

@app.delete("/storage/{contract_id}/photos/{photo_id}")
async def remove_storage_photo(
    contract_id: uuid.UUID, photo_id: uuid.UUID,
    person=Depends(require_roles("owner_manager","manager","administrator")),
    db=Depends(database)
):
    async with db.acquire() as c:
        async with c.transaction():
            record = await c.fetchrow("SELECT status FROM storage_contracts WHERE id=$1 FOR UPDATE",contract_id)
            if not record:
                raise HTTPException(404,"Contract not found")
            if record["status"] != "draft":
                raise HTTPException(409,"Photos from accepted storage cannot be removed; retain audit evidence")
            photo = await c.fetchrow("""SELECT id FROM storage_photos
                          WHERE id=$1 AND contract_id=$2 AND deleted_at IS NULL
                          FOR UPDATE""",photo_id,contract_id)
            if not photo:
                raise HTTPException(404,"Photo not found")
            await c.execute("UPDATE storage_photos SET deleted_at=now(),deleted_by=$2 WHERE id=$1",photo_id,person["id"])
            await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id,payload)
                 VALUES($1,'photo_removed',$2,$3::jsonb)""",contract_id,person["id"],
                 json.dumps({"photo_id":str(photo_id)}))
    return {"removed":True,"photo_id":photo_id,"message":"Photo hidden from draft, audit retained"}


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
    if not supabase_storage.configured():
        raise HTTPException(503, 'Supabase test storage not configured')
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
    # Keep network-bound Drive operations outside SQL transaction, with cleanup on failure.
    object_key = None
    try:
        object_key = await run_in_threadpool(
            supabase_storage.upload_private_image,
            data, f"{contract_id}-{photo_id}.jpg"
        )
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
                     photo_id, contract_id, kind, object_key,
                     hashlib.sha256(data).hexdigest(), len(data), note.strip(), person["id"])
                await c.execute("""INSERT INTO storage_events(contract_id,event_type,actor_id,payload)
                    VALUES($1,'photo_added',$2,$3::jsonb)""",contract_id,person["id"],
                    json.dumps({"photo_id":str(photo_id),"kind":kind}))
    except Exception:
        if object_key:
            try:
                await run_in_threadpool(supabase_storage.remove_private_image, object_key)
            except Exception:
                pass  # Cleanup failure is logged for later orphan-file reconciliation.
        raise
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
            if not supabase_storage.configured():
                raise HTTPException(503, "Supabase Storage not configured")
            checks = await run_in_threadpool(lambda: all(supabase_storage.photo_exists(row["object_key"]) for row in photos))
            if not checks:
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

class RepairOrderCreate(BaseModel):
    client_name: str = Field(min_length=2,max_length=250)
    phone: str | None = Field(default=None,max_length=80)
    vehicle_type: str = Field(default="Мотоцикл",max_length=100)
    brand: str = Field(min_length=1,max_length=150)
    model: str = Field(min_length=1,max_length=150)
    vin: str | None = Field(default=None,max_length=64)
    mileage_km: Decimal | None = Field(default=None,ge=0)
    mechanic_name: str | None = Field(default=None,max_length=250)
    complaint: str = Field(default="",max_length=5000)
    intake_condition: str = Field(default="",max_length=5000)
    total_rub: Decimal = Field(default=Decimal("0"),ge=0,le=100000000)

class RepairOrderState(BaseModel):
    status: str
    version: int = Field(ge=1)

@app.get("/repairs")
async def get_repairs(person=Depends(require_roles(*ROLES)),db=Depends(database)):
    async with db.acquire() as c:
        return [dict(row) for row in await c.fetch("""SELECT * FROM repair_orders
                        ORDER BY updated_at DESC LIMIT 300""")]

@app.post("/repairs",status_code=201)
async def create_repair(payload:RepairOrderCreate,person=Depends(require_roles(*ROLES)),db=Depends(database)):
    async with db.acquire() as c:
        async with c.transaction():
            number = await c.fetchval("SELECT nextval('repair_order_number_seq')")
            order_number = "MT-" + str(number).zfill(6)
            row = await c.fetchrow("""INSERT INTO repair_orders
                 (order_number,client_name,phone,vehicle_type,brand,model,vin,mileage_km,
                  mechanic_name,complaint,intake_condition,total_rub,created_by,updated_by)
                 VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$13)
                 RETURNING *""",
                 order_number,payload.client_name.strip(),payload.phone,payload.vehicle_type,
                 payload.brand.strip(),payload.model.strip(),payload.vin,payload.mileage_km,
                 payload.mechanic_name,payload.complaint,payload.intake_condition,
                 payload.total_rub,person["id"])
            await c.execute("""INSERT INTO repair_order_events(order_id,actor_id,event_type)
                                  VALUES($1,$2,'created')""",row["id"],person["id"])
    return dict(row)

@app.patch("/repairs/{repair_id}/status")
async def update_repair_status(repair_id:uuid.UUID,payload:RepairOrderState,
    person=Depends(require_roles(*ROLES)),db=Depends(database)):
    allowed={"accepted":["diagnostics","cancelled"],"diagnostics":["repair","ready","cancelled"],
             "repair":["ready","cancelled"],"ready":["issued","repair"],"issued":[],"cancelled":[]}
    async with db.acquire() as c:
        async with c.transaction():
            old=await c.fetchrow("SELECT status,version FROM repair_orders WHERE id=$1 FOR UPDATE",repair_id)
            if not old:raise HTTPException(404,"Repair order not found")
            if old["version"]!=payload.version:raise HTTPException(409,"Order changed; refresh")
            if payload.status not in allowed[old["status"]]:raise HTTPException(409,"Invalid status change")
            row=await c.fetchrow("""UPDATE repair_orders SET status=$2,version=version+1,
                   updated_at=now(),updated_by=$3 WHERE id=$1 RETURNING id,status,version""",
                   repair_id,payload.status,person["id"])
            await c.execute("""INSERT INTO repair_order_events(order_id,actor_id,event_type,payload)
                     VALUES($1,$2,'status_changed',$3::jsonb)""",repair_id,person["id"],
                     json.dumps({"from":old["status"],"to":payload.status}))
    return dict(row)


@app.get("/employees")
async def list_employees(person=Depends(require_roles(*ROLES)), db=Depends(database)):
    """List employees without password hashes or credential material."""
    async with db.acquire() as c:
        rows = await c.fetch("""SELECT id,username,full_name,position,role,active,created_at
                                FROM service_employees ORDER BY full_name""")
    return [dict(row) for row in rows]

class EmployeeCreate(BaseModel):
    username: str = Field(min_length=3,max_length=40,pattern=r"^[a-z][a-z0-9._-]*$")
    password: str = Field(min_length=14,max_length=128)
    full_name: str = Field(min_length=3,max_length=250)
    position: str = Field(min_length=2,max_length=150)
    role: str

@app.post("/employees",status_code=201)
async def create_employee(payload:EmployeeCreate,
    person=Depends(require_roles("owner_manager","administrator")),db=Depends(database)):
    if payload.role not in ROLES:
        raise HTTPException(422,"Invalid employee role")
    if payload.role == "owner_manager" and person["role"] != "owner_manager":
        raise HTTPException(403,"Only owner may grant owner role")
    hashed = await run_in_threadpool(password_hash.hash,payload.password)
    async with db.acquire() as c:
        try:
            employee = await c.fetchrow("""INSERT INTO service_employees
             (username,password_hash,full_name,position,role,active)
             VALUES($1,$2,$3,$4,$5,true)
             RETURNING id,username,full_name,position,role,active,created_at""",
             payload.username,hashed,payload.full_name.strip(),
             payload.position.strip(),payload.role)
        except asyncpg.UniqueViolationError:
            raise HTTPException(409,"Такой логин уже используется")
    return dict(employee)

class ClientCreate(BaseModel):
    full_name: str = Field(min_length=2,max_length=250)
    phone: str | None = Field(default=None,max_length=80)
    email: str | None = Field(default=None,max_length=254)
    notes: str | None = Field(default=None,max_length=3000)

class VehicleCreate(BaseModel):
    client_id: uuid.UUID
    vehicle_type: str = Field(default="Мотоцикл",max_length=100)
    brand: str = Field(min_length=1,max_length=150)
    model: str = Field(min_length=1,max_length=150)
    year: int | None = Field(default=None,ge=1900,le=2200)
    vin: str | None = Field(default=None,max_length=64)
    plate: str | None = Field(default=None,max_length=30)
    notes: str | None = Field(default=None,max_length=3000)

@app.get("/clients")
async def list_clients(person=Depends(require_roles(*ROLES)),db=Depends(database)):
    async with db.acquire() as c:
        return [dict(r) for r in await c.fetch("SELECT * FROM service_clients ORDER BY created_at DESC LIMIT 300")]

@app.post("/clients",status_code=201)
async def add_client(payload:ClientCreate,person=Depends(require_roles(*ROLES)),db=Depends(database)):
    async with db.acquire() as c:
        return dict(await c.fetchrow("""INSERT INTO service_clients(full_name,phone,email,notes)
          VALUES($1,$2,$3,$4) RETURNING *""",payload.full_name.strip(),payload.phone,payload.email,payload.notes))

@app.get("/vehicles")
async def list_vehicles(person=Depends(require_roles(*ROLES)),db=Depends(database)):
    async with db.acquire() as c:
        return [dict(r) for r in await c.fetch("""SELECT v.*,c.full_name AS owner_name FROM service_vehicles v
            JOIN service_clients c ON c.id=v.client_id ORDER BY v.created_at DESC LIMIT 300""")]

@app.post("/vehicles",status_code=201)
async def add_vehicle(payload:VehicleCreate,person=Depends(require_roles(*ROLES)),db=Depends(database)):
    async with db.acquire() as c:
        try:
            return dict(await c.fetchrow("""INSERT INTO service_vehicles
              (client_id,vehicle_type,brand,model,year,vin,plate,notes)
              VALUES($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *""",
              payload.client_id,payload.vehicle_type,payload.brand.strip(),payload.model.strip(),
              payload.year,payload.vin.strip().upper() if payload.vin else None,payload.plate,payload.notes))
        except asyncpg.UniqueViolationError:
            raise HTTPException(409,"Техника с таким VIN уже существует")
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(422,"Владелец не найден")
