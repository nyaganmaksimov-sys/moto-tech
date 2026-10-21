#!/usr/bin/env python3
"""MOTO TECH: local-only, one-time provisioning for existing Supabase staff rows.

Run on a trusted workstation or server with SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
set as private environment variables. Never commit the service-role key or output file.
Passwords generated locally; no password is printed to stdout. Existing Auth accounts
are NOT modified. On partial failure rerun safely after investigating.
"""
import json
import os
import secrets
import stat
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

STAFF = ["nikita", "alexandr", "pavel", "alexey", "andrey"]
OUT = Path("staff_credentials_PRIVATE.json")
URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

def call(path, method="GET", body=None):
    request = Request(URL + path,
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "apikey": KEY,
            "Authorization": "Bearer " + KEY,
            "Content-Type": "application/json",
        })
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b"{}")
    except HTTPError as exc:
        raise RuntimeError(f"{method} {path} failed ({exc.code}): {exc.read().decode()[:300]}") from exc

def save(records):
    tmp = OUT.with_suffix(".tmp")
    with os.fdopen(os.open(tmp, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600), "w", encoding="utf-8") as file:
        json.dump(records, file, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)
    if os.name == "posix":
        OUT.chmod(stat.S_IRUSR|stat.S_IWUSR)

def main():
    if not URL.startswith("https://") or not KEY:
        sys.exit("Missing secure SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    if OUT.exists():
        sys.exit("Private credentials file already exists. Move it securely before retry.")
    people = call("/rest/v1/staff?select=id,login,role,auth_user_id&login=in.(nikita,alexandr,pavel,alexey,andrey)")
    if len(people) != len(STAFF):
        sys.exit("Staff rows missing. No changes made.")
    indexed = {x["login"]: x for x in people}
    if any(indexed[n]["auth_user_id"] for n in STAFF):
        sys.exit("Some staff already linked; stop and review before rerun.")
    if indexed["nikita"]["role"] != "owner_manager" or indexed["alexandr"]["role"] != "owner_manager":
        sys.exit("Manager roles not configured.")
    records = []
    for login in STAFF:
        password = secrets.token_urlsafe(24)
        email = login + "@staff.moto-tech.example"
        result = call("/auth/v1/admin/users", "POST", {
            "email": email, "password": password, "email_confirm": True,
            "user_metadata": {"staff_login": login}
        })
        auth_id = result.get("id")
        if not auth_id:
            raise RuntimeError("No Auth user ID returned for " + login)
        # Only update the existing unlinked matching staff row.
        updated = call(
            "/rest/v1/staff?login=eq." + login + "&auth_user_id=is.null",
            "PATCH", {"auth_user_id": auth_id}
        )
        records.append({"login": login, "password": password, "auth_user_id": auth_id})
        save(records) if not OUT.exists() else save_replace(records)
        print(login + ": Auth created and staff linkage requested")
    print("Credentials written to local PRIVATE JSON. Deliver individually; delete after handover.")

def save_replace(records):
    OUT.unlink()
    save(records)

if __name__ == "__main__":
    main()
