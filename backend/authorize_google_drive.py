"""Run locally to authorize a dedicated Google test account for MOTO TECH.

Requires Google OAuth Desktop client JSON downloaded from Google Cloud Console.
Never upload client JSON or tokens to GitHub or ChatGPT.
"""
import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]
CLIENT_FILE = Path("client_secret.json")
if not CLIENT_FILE.is_file():
    raise SystemExit("Place the Google OAuth Desktop client JSON beside this script as client_secret.json")
flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
credentials = flow.run_local_server(host="127.0.0.1", port=0, access_type="offline", prompt="consent")
if not credentials.refresh_token:
    raise SystemExit("Google did not return a refresh token. Revoke this app grant and retry with offline consent.")
print("OAuth successful. Configure the following Render variables through the Render Dashboard.")
print("MOTOTECH_GOOGLE_CLIENT_ID =", credentials.client_id)
print("MOTOTECH_GOOGLE_CLIENT_SECRET =", credentials.client_secret)
print("MOTOTECH_GOOGLE_REFRESH_TOKEN =", credentials.refresh_token)
print("MOTOTECH_GOOGLE_DRIVE_FOLDER_ID = 1USvydygqLpFR4B349XQ40zn1yAIuZVja")
print("Do not save the printed secrets in source code or send them through chat.")
