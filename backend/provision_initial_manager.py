"""Provision the initial manager from Render secret environment variables.

One-time command, never part of normal API startup.
Refuses to reset existing credentials.
"""
import asyncio
import os
import asyncpg
from pwdlib import PasswordHash

async def main():
    dsn = os.getenv("DATABASE_URL")
    password = os.getenv("MOTOTECH_INITIAL_MANAGER_PASSWORD", "")
    if not dsn or len(password) < 14 or password.strip() != password:
        raise SystemExit("Missing DATABASE_URL or manager password (minimum 14 characters)")
    conn = await asyncpg.connect(dsn, ssl="require" if "localhost" not in dsn and "127.0.0.1" not in dsn else None)
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(7251092027)")
            existing = await conn.fetchrow("SELECT id,role,active FROM service_employees WHERE username='maximov'")
            if existing:
                print("Employee maximov already exists; no password or role changes made.")
                return
            password_hash = PasswordHash.recommended().hash(password)
            await conn.execute("""
                INSERT INTO service_employees (username,password_hash,full_name,role,active)
                VALUES ('maximov',$1,'Павел Анатольевич','owner_manager',true)
            """, password_hash)
            print("Initial manager created: maximov (owner_manager). Password not printed.")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
