"""Private Supabase Storage backend; secret key must remain server-side."""
import os
from urllib.parse import quote

import httpx

BUCKET = "moto-tech-test-photos"

def configured() -> bool:
    return bool(os.getenv("MOTOTECH_SUPABASE_URL") and os.getenv("MOTOTECH_SUPABASE_SECRET_KEY"))

def _base():
    url = os.environ["MOTOTECH_SUPABASE_URL"].rstrip("/")
    if not url.startswith("https://"):
        raise RuntimeError("Supabase must use HTTPS")
    return url + "/storage/v1/object/" + BUCKET + "/"

def _headers(mimetype=None):
    key = os.environ["MOTOTECH_SUPABASE_SECRET_KEY"]
    h = {"apikey": key}
    # Legacy JWT service_role keys also accept Authorization: Bearer. Modern sb_secret keys are API keys, not JWTs.
    if not key.startswith("sb_secret_"):
        h["Authorization"] = "Bearer " + key
    if mimetype:
        h["Content-Type"] = mimetype
    return h

def _path(key):
    if not key.startswith("supabase:"):
        raise ValueError("Not a Supabase object key")
    name = key[len("supabase:"):]
    if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/." for c in name) or ".." in name:
        raise ValueError("Invalid object key")
    return quote(name, safe="/")

def upload_private_image(data: bytes, filename: str) -> str:
    with httpx.Client(timeout=35) as client:
        response = client.post(_base() + quote(filename, safe="/"), headers=_headers("image/jpeg"),content=data)
        response.raise_for_status()
    return "supabase:" + filename

def photo_exists(key: str) -> bool:
    with httpx.Client(timeout=15) as client:
        response = client.get(_base() + _path(key), headers=_headers())
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

def remove_private_image(key: str):
    with httpx.Client(timeout=15) as client:
        response = client.delete(_base() + _path(key), headers=_headers())
        response.raise_for_status()
