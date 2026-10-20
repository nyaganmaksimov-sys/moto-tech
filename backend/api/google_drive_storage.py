"""Private Google Drive image object adapter for the MOTO TECH pilot.

Use OAuth refresh-token credentials belonging to an explicitly authorized account.
No browser-side Drive tokens. The folder must not be publicly shared.
"""
import io
import os
from functools import lru_cache

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

def configured():
    return all(os.getenv(name) for name in (
        "MOTOTECH_GOOGLE_DRIVE_FOLDER_ID",
        "MOTOTECH_GOOGLE_CLIENT_ID",
        "MOTOTECH_GOOGLE_CLIENT_SECRET",
        "MOTOTECH_GOOGLE_REFRESH_TOKEN",
    ))

def drive():
    if not configured():
        raise RuntimeError("Google Drive backend is not configured")
    credentials = Credentials(
        token=None,
        refresh_token=os.environ["MOTOTECH_GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["MOTOTECH_GOOGLE_CLIENT_ID"],
        client_secret=os.environ["MOTOTECH_GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)

def upload_private_image(data: bytes, filename: str) -> str:
    folder = os.environ["MOTOTECH_GOOGLE_DRIVE_FOLDER_ID"]
    body = {"name": filename, "parents": [folder], "description": "MOTO TECH private test intake"}
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="image/jpeg", resumable=False)
    result = drive().files().create(body=body, media_body=media, fields="id", supportsAllDrives=True).execute()
    return "gdrive:" + result["id"]

def photo_exists(key: str) -> bool:
    if not key.startswith("gdrive:"):
        return False
    try:
        entry = drive().files().get(fileId=key[7:], fields="id,trashed,parents",supportsAllDrives=True).execute()
        return not entry.get("trashed", False) and os.environ["MOTOTECH_GOOGLE_DRIVE_FOLDER_ID"] in entry.get("parents", [])
    except HttpError as error:
        if error.resp.status == 404:
            return False
        raise

def remove_private_image(key: str):
    if not key.startswith("gdrive:"):
        return
    drive().files().delete(fileId=key[7:], supportsAllDrives=True).execute()
