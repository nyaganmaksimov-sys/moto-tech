"""Create missing MOTO TECH employee accounts in a private PostgreSQL database.

Run once after migrations 001-004. Requires DATABASE_URL and six individual
MOTOTECH_PASSWORD_<USERNAME> secrets. Does not reset existing passwords or roles.
Never store the secrets in the repository or log them.
"""
import asyncio
import os
import secrets
import asyncpg
from pwdlib import PasswordHash

STAFF = [
    ("maximov", "Павел Анатольевич", "owner_manager", "Управляющий"),
    ("nikita", "Никита", "owner_manager", "Руководитель"),
    ("alexandr", "Александр", "owner_manager", "Руководитель"),
    ("pavel", "Павел", "mechanic", "Механик"),
    ("alexey", "Алексей", "mechanic", "Механик"),
    ("andrey", "Андрей", "mechanic", "Механик"),
]

async def main():
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        raise SystemExit("DATABASE_URL is required")
    passwords = {}
    for username, *_ in STAFF:
        password = os.environ.get("MOTOTECH_PASSWORD_" + username.upper(), "")
        if len(password) < 16 or password != password.strip():
            raise SystemExit("Missing or invalid secret for " + username + " (minimum 16 characters)")
        passwords[username] = password
    if len(set(passwords.values())) != len(passwords):
        raise SystemExit("Passwords must be unique")
    con = await asyncpg.connect(dsn, ssl="require" if not any(x in dsn for x in ("@localhost", "@127.0.0.1", "@db:")) else None)
    try:
        async with con.transaction():
            await con.execute("SELECT pg_advisory_xact_lock(7251092027)")
            has_position = await con.fetchval("""SELECT EXISTS(
                SELECT 1 FROM information_schema.columns
                WHERE table_name='service_employees' AND column_name='position')""")
            if not has_position:
                raise SystemExit("Migration 004_employee_positions.sql is required")
            for username, full_name, role, position in STAFF:
                exists = await con.fetchval("SELECT EXISTS(SELECT 1 FROM service_employees WHERE username=$1)", username)
                if exists:
                    print(username + ": exists, unchanged (verify role manually)")
                    continue
                hash_value = PasswordHash.recommended().hash(passwords[username])
                await con.execute("""INSERT INTO service_employees
                    (username,password_hash,full_name,role,position,active)
                    VALUES ($1,$2,$3,$4,$5,true)""",
                    username, hash_value, full_name, role, position)
                print(username + ": created, role=" + role)
    finally:
        await con.close()

if __name__ == "__main__":
    asyncio.run(main())
