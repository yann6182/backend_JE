from __future__ import annotations
from pathlib import Path
import msal, requests, shutil, tempfile, os, logging
from app.core.config import Settings

settings = Settings()          # charge vos env (.env)

AUTHORITY = f"https://login.microsoftonline.com/{settings.TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

app = msal.ConfidentialClientApplication(
    client_id=settings.CLIENT_ID,
    client_credential=settings.CLIENT_SECRET,
    authority=AUTHORITY,
)

log = logging.getLogger(__name__)

def _token() -> str:
    tok = app.acquire_token_silent(SCOPES, account=None)
    if not tok:
        tok = app.acquire_token_for_client(SCOPES)
    if "access_token" not in tok:
        raise RuntimeError(f"OAuth error: {tok.get('error_description')}")
    return tok["access_token"]

def list_xlsx() -> list[dict]:
    hdr = {"Authorization": f"Bearer {_token()}"}
    folder = settings.GRAPH_DPFG_FOLDER.strip("/")
    url = (
        f"https://graph.microsoft.com/v1.0/drives/{settings.GRAPH_DRIVE_ID}/root"
        f":/{folder}:/children" if folder else
        f"https://graph.microsoft.com/v1.0/drives/{settings.GRAPH_DRIVE_ID}/root/children"
    )
    items = requests.get(url, headers=hdr).json()["value"]
    return [i for i in items if i.get("file", {}).get("mimeType", "").endswith("spreadsheetml.sheet")]

def download_item(item_id: str, filename: str) -> Path:
    hdr = {"Authorization": f"Bearer {_token()}"}
    url = f"https://graph.microsoft.com/v1.0/drives/{settings.GRAPH_DRIVE_ID}/items/{item_id}/content"
    temp = Path(settings.DPGF_UPLOAD_DIR) / filename
    temp.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=hdr, stream=True) as r:
        r.raise_for_status()
        with temp.open("wb") as f:
            shutil.copyfileobj(r.raw, f)
    return temp
