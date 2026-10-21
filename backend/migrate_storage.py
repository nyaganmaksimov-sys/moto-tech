"""Explicit one-time MOTO TECH database schema migration.

Usage from a secured server with DATABASE_URL:
    python -m backend.migrate_storage

No migrations run during the normal API startup.
"""
import asyncio
import os
from pathlib import Path

import asyncpg

FILES = (
    "001_storage_foundation.sql",
    "002_staff_auth.sql",
)

async def run():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL is missing")
    base = Path(__file__).resolve().parent / "migrations"
    connection = await asyncpg.connect(url, ssl="require" if "localhost" not in url and "127.0.0.1" not in url else None)
    try:
        await connection.execute("SELECT pg_advisory_lock(7251092026)")
        try:
            existing = await connection.fetch("SELECT to_regclass('public.storage_contracts') AS contracts, to_regclass('public.service_employees') AS employees")
            if bool(existing[0]["contracts"]) != bool(existing[0]["employees"]):
                raise RuntimeError("Partial schema detected; inspect database manually before migrating")
            if existing[0]["contracts"] and existing[0]["employees"]:
                print("Storage tables already exist; verifying table structure instead of reapplying migrations.")
            else:
                for name in FILES:
                    sql = (base / name).read_text(encoding="utf-8")
                    await connection.execute(sql)
                    print("Applied:", name)
            for table in ("storage_contracts", "storage_photos", "storage_events", "service_employees"):
                exists = await connection.fetchval("SELECT to_regclass($1)", "public." + table)
                if not exists:
                    raise RuntimeError("Missing required table: " + table)
            required_columns = {
                "storage_contracts": ("id", "contract_number", "owner_name", "vin", "status", "version"),
                "storage_photos": ("contract_id", "kind", "object_key", "sha256"),
                "storage_events": ("contract_id", "event_type", "actor_id"),
                "service_employees": ("username", "password_hash", "role", "active"),
            }
            for table, columns in required_columns.items():
                present = {
                    row["column_name"] for row in await connection.fetch(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=$1", table
                    )
                }
                missing = set(columns) - present
                if missing:
                    raise RuntimeError(f"Table {table} missing columns: {sorted(missing)}")
            print("Storage migration schema checks passed")
            repairs_exists = await connection.fetchval("SELECT to_regclass('public.repair_orders')")
            if not repairs_exists:
                await connection.execute((base / "003_repair_orders.sql").read_text(encoding="utf-8"))
                print("Applied: 003_repair_orders.sql")
            for table in ("repair_orders", "repair_order_events"):
                exists = await connection.fetchval("SELECT to_regclass($1)", "public." + table)
                if not exists:
                    raise RuntimeError("Missing required table: " + table)
            print("Repair order schema checks passed")
            has_position = await connection.fetchval("""SELECT EXISTS(
              SELECT 1 FROM information_schema.columns
              WHERE table_schema='public' AND table_name='service_employees' AND column_name='position')""")
            if not has_position:
                await connection.execute((base / "004_employee_positions.sql").read_text(encoding="utf-8"))
                print("Applied: 004_employee_positions.sql")
            print("Employee schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.service_clients')"):
                await connection.execute((base / "005_clients_vehicles.sql").read_text(encoding="utf-8"))
                print("Applied: 005_clients_vehicles.sql")
            for table in ("service_clients","service_vehicles"):
                if not await connection.fetchval("SELECT to_regclass($1)","public."+table):
                    raise RuntimeError("Missing table: "+table)
            print("Clients and vehicles schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.staff_pin_devices')"):
                await connection.execute((base / "006_staff_pin_devices.sql").read_text(encoding="utf-8"))
                print("Applied: 006_staff_pin_devices.sql")
            print("PIN devices schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.inventory_parts')"):
                await connection.execute((base / "007_inventory.sql").read_text(encoding="utf-8"))
                print("Applied: 007_inventory.sql")
            for table in ("inventory_parts","inventory_movements"):
                if not await connection.fetchval("SELECT to_regclass($1)", "public."+table):
                    raise RuntimeError("Missing inventory table: "+table)
            print("Inventory schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.inventory_suppliers')"):
                await connection.execute((base / "008_suppliers_requests.sql").read_text(encoding="utf-8"))
                print("Applied: 008_suppliers_requests.sql")
            for table in ("inventory_suppliers","inventory_requests"):
                if not await connection.fetchval("SELECT to_regclass($1)","public."+table):
                    raise RuntimeError("Missing procurement table: "+table)
            print("Procurement schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.service_appointments')"):
                await connection.execute((base / "009_appointments_warranties.sql").read_text(encoding="utf-8"))
                print("Applied: 009_appointments_warranties.sql")
            for table in ("service_appointments","service_warranties"):
                if not await connection.fetchval("SELECT to_regclass($1)","public."+table):
                    raise RuntimeError("Missing bookings/warranty table: "+table)
            print("Appointments and warranties schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.service_price_items')"):
                await connection.execute((base / "010_finance_pricing.sql").read_text(encoding="utf-8"))
                print("Applied: 010_finance_pricing.sql")
            for table in ("service_price_items", "service_finance_entries"):
                if not await connection.fetchval("SELECT to_regclass($1)", "public."+table):
                    raise RuntimeError("Missing finance table: "+table)
            print("Finance and pricing schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.integration_1c_settings')"):
                await connection.execute((base / "011_1c_integration.sql").read_text(encoding="utf-8"))
                print("Applied: 011_1c_integration.sql")
            for table in ("integration_1c_settings","integration_1c_mappings","integration_1c_events"):
                if not await connection.fetchval("SELECT to_regclass($1)","public."+table):
                    raise RuntimeError("Missing 1C integration table: "+table)
            print("1C integration schema checks passed")
            if not await connection.fetchval("""SELECT EXISTS(
                SELECT 1 FROM information_schema.columns WHERE table_name='repair_orders'
                AND column_name='mechanic_id')"""):
                await connection.execute((base / "012_repair_assignment.sql").read_text(encoding="utf-8"))
                print("Applied: 012_repair_assignment.sql")
            print("Repair assignment schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.repair_work_items')"):
                await connection.execute((base / "013_repair_work_items.sql").read_text(encoding="utf-8"))
                print("Applied: 013_repair_work_items.sql")
            print("Repair work items schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.equipment_assets')"):
                await connection.execute((base / "014_equipment_assets.sql").read_text(encoding="utf-8"))
                print("Applied: 014_equipment_assets.sql")
            print("Equipment inventory schema checks passed")
            if not await connection.fetchval("""SELECT EXISTS(SELECT 1 FROM information_schema.columns
                   WHERE table_name='equipment_assets' AND column_name='estimated_value_rub')"""):
                await connection.execute((base / "015_equipment_valuation.sql").read_text(encoding="utf-8"))
                print("Applied: 015_equipment_valuation.sql")
            print("Equipment valuation schema checks passed")
            if not await connection.fetchval("SELECT to_regclass('public.equipment_maintenance')"):
                await connection.execute((base / "016_equipment_maintenance.sql").read_text(encoding="utf-8"))
                print("Applied: 016_equipment_maintenance.sql")
            print("Equipment maintenance schema checks passed")
            if not await connection.fetchval("SELECT to_regclass($1)", "public.crm_tasks"):
                await connection.execute((base / "017_crm_tasks.sql").read_text(encoding="utf-8"))
                print("Applied: 017_crm_tasks.sql")
            print("CRM task schema checks passed")
            if not await connection.fetchval("SELECT to_regclass($1)", "public.crm_task_comments"):
                await connection.execute((base / "018_crm_task_threads.sql").read_text(encoding="utf-8"))
                print("Applied: 018_crm_task_threads.sql")
            print("CRM discussion schema checks passed")
            if not await connection.fetchval("SELECT to_regclass($1)", "public.crm_task_events"):
                await connection.execute((base / "019_crm_task_events.sql").read_text(encoding="utf-8"))
                print("Applied: 019_crm_task_events.sql")
            print("CRM history schema checks passed")
        finally:
            await connection.execute("SELECT pg_advisory_unlock(7251092026)")
    finally:
        await connection.close()

if __name__ == "__main__":
    asyncio.run(run())
