# Google Drive storage — MOTO TECH test pilot

Google Drive folder created for this pilot:
https://drive.google.com/drive/folders/1USvydygqLpFR4B349XQ40zn1yAIuZVja

Folder is private (not publicly shared) as verified at creation. No real customer PTS or personal details until security and data-processing requirements have been reviewed.

The server now supports uploading validated photos to this folder. PostgreSQL stores `gdrive:<file-id>` as the `object_key`. The React-free server pilot UI has not been publicly deployed.

## Separate authorization needed on the Render server
The ChatGPT Google Drive connector **does not** authorize Render to access Google Drive.
Configure a Google Cloud OAuth application and obtain an offline refresh token for
a dedicated test Google account that has been explicitly given permission to access
this folder. Store these only in Render secret environment variables:

- `MOTOTECH_GOOGLE_DRIVE_FOLDER_ID=1USvydygqLpFR4B349XQ40zn1yAIuZVja`
- `MOTOTECH_GOOGLE_CLIENT_ID`
- `MOTOTECH_GOOGLE_CLIENT_SECRET`
- `MOTOTECH_GOOGLE_REFRESH_TOKEN`

The adapter currently requests the Google Drive scope to reach the already-existing
folder; this has broad access to the authorized Google account's Drive. For a production
service, migrate to least-privilege authorization and dedicated restricted storage.
**Do not commit OAuth secrets, refresh tokens, or downloaded credentials.**

Until the four environment variables are set, photo uploads return 503; they
must not silently fall back to ephemeral disk. Uploaded files are never made
public or returned as direct URLs by the API.

For testing: use only fictitious motorcycle/customer information, verify uploads
in the Drive folder, test acceptance, then test an API restart and re-open the record.
Service deploy from integration branch and DB migrations are still separate tasks.

Important: this is a temporary prototype. Google Drive is not a substitute for
backup verification, access revocation, privacy controls, retention policies,
audit trails, or production object storage.
