import os
import base64
import binascii
import uuid
import sqlite3
from contextlib import contextmanager
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).parent
DB = Path(os.environ.get("MOTO_DB", str(ROOT / "moto.db")))
PHOTO_DIR = Path(os.environ.get("MOTO_PHOTOS_DIR", str(ROOT / "intake_photos"))).resolve()
MAX_PHOTO_BYTES = 8 * 1024 * 1024
REQUIRED_ANGLES = ("front", "rear", "left", "right")
app = FastAPI(title="MOTO TECH Service", version="0.1.0")

@contextmanager
def db():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

@app.on_event("startup")
def initialize():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS vehicles(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), kind TEXT NOT NULL, brand TEXT NOT NULL DEFAULT '', model TEXT NOT NULL DEFAULT '', vin TEXT NOT NULL DEFAULT '', mileage TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY, category TEXT NOT NULL, name TEXT NOT NULL, price_kopecks INTEGER NOT NULL CHECK(price_kopecks >= 0));
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), vehicle_id INTEGER NOT NULL REFERENCES vehicles(id), complaint TEXT NOT NULL DEFAULT '', mechanic TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Принят', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS order_items(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), kind TEXT NOT NULL, description TEXT NOT NULL, qty TEXT NOT NULL, price_kopecks INTEGER NOT NULL, cost_kopecks INTEGER NOT NULL DEFAULT 0, approved INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), amount_kopecks INTEGER NOT NULL CHECK(amount_kopecks > 0), method TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), action TEXT NOT NULL, at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS intakes(id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), vehicle_id INTEGER NOT NULL REFERENCES vehicles(id), purpose TEXT NOT NULL CHECK(purpose IN (\'repair\',\'storage\')), condition_notes TEXT NOT NULL DEFAULT \'\', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS intake_photos(id INTEGER PRIMARY KEY, intake_id INTEGER NOT NULL REFERENCES intakes(id), angle TEXT NOT NULL, filename TEXT NOT NULL UNIQUE);
        """)
        if c.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
            c.executemany("INSERT INTO services(category,name,price_kopecks) VALUES(?,?,?)", [
                ("ТО", "Замена моторного масла", 150000),
                ("Диагностика", "Первичная диагностика", 200000),
                ("Тормоза", "Замена тормозных колодок", 150000),
                ("Шиномонтаж", "Снятие и установка колеса", 120000)
            ])

def rows(c, query, params=()):
    return [dict(x) for x in c.execute(query, params).fetchall()]

def kopecks(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("Сумма должна быть неотрицательной")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def audit(c, oid, event):
    c.execute("INSERT INTO audit(order_id,action) VALUES(?,?)", (oid, event))

class Customer(BaseModel):
    name: str = Field(min_length=1)
    phone: str = ""

class Vehicle(BaseModel):
    customer_id: int
    kind: str = Field(min_length=1)
    brand: str = ""
    model: str = ""
    vin: str = ""
    mileage: str = ""

class Service(BaseModel):
    category: str = Field(min_length=1)
    name: str = Field(min_length=1)
    price: Decimal = Field(ge=0)

class Order(BaseModel):
    customer_id: int
    vehicle_id: int
    complaint: str = ""

class Item(BaseModel):
    kind: str = Field(pattern="^(work|part)$")
    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    unit_cost: Decimal = Field(default=0, ge=0)

class Payment(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(min_length=1)

class Status(BaseModel):
    status: str = Field(min_length=1)
    mechanic: str = ""

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/customers")
def customers():
    with db() as c: return rows(c, "SELECT * FROM customers ORDER BY id DESC")

@app.post("/api/customers")
def add_customer(x: Customer):
    with db() as c:
        cur=c.execute("INSERT INTO customers(name,phone) VALUES(?,?)", (x.name,x.phone))
        return {"id":cur.lastrowid}

@app.get("/api/vehicles")
def vehicles():
    with db() as c: return rows(c, "SELECT * FROM vehicles ORDER BY id DESC")

@app.post("/api/vehicles")
def add_vehicle(x: Vehicle):
    with db() as c:
        if not c.execute("SELECT id FROM customers WHERE id=?", (x.customer_id,)).fetchone(): raise HTTPException(404,"Клиент не найден")
        cur=c.execute("INSERT INTO vehicles(customer_id,kind,brand,model,vin,mileage) VALUES(?,?,?,?,?,?)",(x.customer_id,x.kind,x.brand,x.model,x.vin,x.mileage))
        return {"id":cur.lastrowid}

@app.get("/api/services")
def services():
    with db() as c: return rows(c, "SELECT * FROM services ORDER BY category,name")

@app.post("/api/services")
def add_service(x: Service):
    with db() as c:
        cur=c.execute("INSERT INTO services(category,name,price_kopecks) VALUES(?,?,?)",(x.category,x.name,kopecks(x.price)))
        return {"id":cur.lastrowid}

@app.put("/api/services/{sid}")
def update_service(sid:int,x:Service):
    with db() as c:
        cur=c.execute("UPDATE services SET category=?,name=?,price_kopecks=? WHERE id=?",(x.category,x.name,kopecks(x.price),sid))
        if not cur.rowcount: raise HTTPException(404,"Услуга не найдена")
        return {"ok":True}

@app.get("/api/orders")
def orders():
    with db() as c:
        return rows(c, """SELECT o.*, cu.name customer_name, (v.brand||' '||v.model) vehicle_name,
        COALESCE((SELECT SUM(CAST(i.qty AS REAL)*i.price_kopecks) FROM order_items i WHERE i.order_id=o.id AND i.approved=1),0) total_kopecks,
        COALESCE((SELECT SUM(p.amount_kopecks) FROM payments p WHERE p.order_id=o.id),0) paid_kopecks
        FROM orders o JOIN customers cu ON cu.id=o.customer_id JOIN vehicles v ON v.id=o.vehicle_id ORDER BY o.id DESC""")

@app.post("/api/orders")
def add_order(x: Order):
    with db() as c:
        if not c.execute("SELECT id FROM vehicles WHERE id=? AND customer_id=?", (x.vehicle_id,x.customer_id)).fetchone(): raise HTTPException(400,"Техника не принадлежит клиенту")
        cur=c.execute("INSERT INTO orders(customer_id,vehicle_id,complaint) VALUES(?,?,?)",(x.customer_id,x.vehicle_id,x.complaint))
        audit(c,cur.lastrowid,"Создан заказ")
        return {"id":cur.lastrowid,"number":f"MT-{cur.lastrowid:06d}"}

@app.patch("/api/orders/{oid}")
def change_order(oid:int,x:Status):
    with db() as c:
        cur=c.execute("UPDATE orders SET status=?,mechanic=? WHERE id=?",(x.status,x.mechanic,oid))
        if not cur.rowcount:raise HTTPException(404,"Заказ не найден")
        audit(c,oid,"Изменён статус: "+x.status)
        return {"ok":True}

@app.get("/api/orders/{oid}")
def order(oid:int):
    with db() as c:
        data=c.execute("SELECT * FROM orders WHERE id=?",(oid,)).fetchone()
        if not data:raise HTTPException(404,"Заказ не найден")
        return {"order":dict(data),"items":rows(c,"SELECT * FROM order_items WHERE order_id=?",(oid,)),
        "payments":rows(c,"SELECT * FROM payments WHERE order_id=?",(oid,)),
        "history":rows(c,"SELECT * FROM audit WHERE order_id=? ORDER BY id DESC",(oid,))}

@app.post("/api/orders/{oid}/items")
def add_item(oid:int,x:Item):
    with db() as c:
        if not c.execute("SELECT id FROM orders WHERE id=?",(oid,)).fetchone():raise HTTPException(404,"Заказ не найден")
        qty=str(x.quantity)
        price=kopecks(x.unit_price)
        cost=kopecks(x.unit_cost)
        cur=c.execute("INSERT INTO order_items(order_id,kind,description,qty,price_kopecks,cost_kopecks) VALUES(?,?,?,?,?,?)",(oid,x.kind,x.description,qty,price,cost))
        audit(c,oid,"Добавлена позиция: "+x.description+" (ожидает согласования)")
        return {"id":cur.lastrowid}

@app.post("/api/orders/{oid}/approve/{item_id}")
def approve(oid:int,item_id:int):
    with db() as c:
        cur=c.execute("UPDATE order_items SET approved=1 WHERE id=? AND order_id=?",(item_id,oid))
        if not cur.rowcount: raise HTTPException(404,"Позиция не найдена")
        audit(c,oid,"Согласована позиция "+str(item_id)+" (отметка оператора)")
        return {"ok":True}

@app.post("/api/orders/{oid}/payments")
def pay(oid:int,x:Payment):
    with db() as c:
        if not c.execute("SELECT id FROM orders WHERE id=?",(oid,)).fetchone():raise HTTPException(404,"Заказ не найден")
        amount=kopecks(x.amount)
        cur=c.execute("INSERT INTO payments(order_id,amount_kopecks,method) VALUES(?,?,?)",(oid,amount,x.method))
        audit(c,oid,"Принята оплата "+str(x.amount)+" руб.; "+x.method)
        return {"id":cur.lastrowid}

@app.get("/api/dashboard")
def dashboard():
    with db() as c:
        counts=rows(c,"SELECT status,COUNT(*) count FROM orders GROUP BY status")
        income=c.execute("SELECT COALESCE(SUM(amount_kopecks),0) FROM payments").fetchone()[0]
        return {"statuses":counts,"payments_kopecks":income,"total_orders":c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]}


# Приёмка: VIN всегда необязательный. Четыре ракурса обязательны для ремонта и хранения.
class IntakePhoto(BaseModel):
    angle: str
    data: str  # base64 JPEG/PNG без data URI

class Intake(BaseModel):
    customer_id: int
    vehicle_id: int
    purpose: str = Field(pattern="^(repair|storage)$")
    condition_notes: str = ""
    photos: list[IntakePhoto] = Field(min_length=4, max_length=20)

def decode_photo(encoded: str):
    if len(encoded) > (MAX_PHOTO_BYTES * 4 // 3) + 16:
        raise HTTPException(413, "Фото превышает 8 МБ")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(422, "Неверный формат фотографии")
    if not raw or len(raw) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "Фото пустое или превышает 8 МБ")
    if raw.startswith(b"\\xff\\xd8\\xff") and raw.endswith(b"\\xff\\xd9"):
        return raw, ".jpg"
    if raw.startswith(b"\\x89PNG\\r\\n\\x1a\\n") and b"IEND" in raw[-20:]:
        return raw, ".png"
    raise HTTPException(422, "Допускаются только JPEG и PNG")

@app.post("/api/intakes", status_code=201)
def create_intake(x: Intake):
    angles = [p.angle for p in x.photos]
    if any(angles.count(a) != 1 for a in REQUIRED_ANGLES):
        raise HTTPException(422, "Нужны ровно четыре обязательных фото: спереди, сзади, слева, справа")
    if any(a not in (*REQUIRED_ANGLES, "damage", "pts", "other") for a in angles):
        raise HTTPException(422, "Неизвестный ракурс")
    decoded = [(p.angle, *decode_photo(p.data)) for p in x.photos]
    PHOTO_DIR.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        with db() as c:
            if not c.execute("SELECT id FROM vehicles WHERE id=? AND customer_id=?", (x.vehicle_id, x.customer_id)).fetchone():
                raise HTTPException(400, "Техника не принадлежит клиенту")
            cur = c.execute("INSERT INTO intakes(customer_id,vehicle_id,purpose,condition_notes) VALUES(?,?,?,?)",
                            (x.customer_id, x.vehicle_id, x.purpose, x.condition_notes))
            intake_id = cur.lastrowid
            for angle, raw, ext in decoded:
                filename = uuid.uuid4().hex + ext
                dest = PHOTO_DIR / filename
                with dest.open("xb") as f:
                    f.write(raw)
                created.append(dest)
                c.execute("INSERT INTO intake_photos(intake_id,angle,filename) VALUES(?,?,?)",
                          (intake_id, angle, filename))
            return {"id": intake_id, "number": f"MT-IN-{intake_id:06d}", "photo_count": len(decoded)}
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise

@app.get("/api/intakes")
def list_intakes():
    with db() as c:
        return rows(c, """SELECT i.*,cu.name AS customer_name,v.kind,v.brand,v.model,v.vin,
                       (SELECT COUNT(*) FROM intake_photos p WHERE p.intake_id=i.id) AS photo_count
                       FROM intakes i JOIN customers cu ON cu.id=i.customer_id
                       JOIN vehicles v ON v.id=i.vehicle_id ORDER BY i.id DESC""")

@app.get("/api/intakes/{intake_id}")
def get_intake(intake_id: int):
    with db() as c:
        intake = c.execute("SELECT * FROM intakes WHERE id=?", (intake_id,)).fetchone()
        if not intake:
            raise HTTPException(404, "Приёмка не найдена")
        photos = rows(c, "SELECT id,angle FROM intake_photos WHERE intake_id=? ORDER BY id", (intake_id,))
        return {"intake": dict(intake), "photos": photos}

@app.get("/api/intakes/{intake_id}/photos/{photo_id}")
def get_intake_photo(intake_id: int, photo_id: int):
    with db() as c:
        row = c.execute("SELECT filename FROM intake_photos WHERE id=? AND intake_id=?", (photo_id,intake_id)).fetchone()
        if not row:
            raise HTTPException(404, "Фото не найдено")
        path = PHOTO_DIR / row["filename"]
        if not path.is_file():
            raise HTTPException(404, "Файл фото не найден")
        return FileResponse(path, media_type="image/png" if path.suffix == ".png" else "image/jpeg")
