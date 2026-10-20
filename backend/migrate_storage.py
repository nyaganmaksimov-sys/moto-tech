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
        finally:
            await connection.execute("SELECT pg_advisory_unlock(7251092026)")
    finally:
        await connection.close()

if __name__ == "__main__":
    asyncio.run(run())
