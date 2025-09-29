import json
import hashlib
from pathlib import Path
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

# ====== Config ======
PACKAGES_DIR = Path("packages")
METADATA_FILE = Path("metadata.json")
PRIVATE_KEY_FILE = Path("keys/private.pem")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ====== Load private key ======
with open(PRIVATE_KEY_FILE, "rb") as f:
    private_key = serialization.load_pem_private_key(
        f.read(), password=None, backend=default_backend()
    )

# ====== FastAPI App ======
app = FastAPI(title="OTA Update Server")

class UpdateRequest(BaseModel):
    device_id: str
    build_id: str

def sign_data(data: bytes) -> str:
    """Sign data using private key and return hex signature."""
    signature = private_key.sign(
        data,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    return signature.hex()

def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA256 checksum for a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def load_metadata() -> dict:
    if METADATA_FILE.exists():
        return json.loads(METADATA_FILE.read_text())
    return {}

def find_next_build(metadata: dict, current_build: str) -> str:
    """Find the next build ID in sequence based on release date ordering."""
    from datetime import datetime
    
    # Get current build's release date
    current_entry = metadata.get(current_build)
    if not current_entry or 'release_date' not in current_entry:
        return None
    
    try:
        current_date = datetime.strptime(current_entry['release_date'], '%Y-%m-%d')
    except ValueError:
        return None
    
    # Find all builds with release dates after current build
    next_builds = []
    for build_id, entry in metadata.items():
        if 'release_date' not in entry:
            continue
        try:
            release_date = datetime.strptime(entry['release_date'], '%Y-%m-%d')
            if release_date > current_date:
                next_builds.append((release_date, build_id))
        except ValueError:
            continue
    
    # Sort by release date and return the earliest next build
    if next_builds:
        next_builds.sort(key=lambda x: x[0])
        return next_builds[0][1]
    
    return None  # No next build found

@app.post("/check-update")
def check_update(req: UpdateRequest):
    metadata = load_metadata()
    current_build = req.build_id

    # Check if current build exists in metadata
    if current_build not in metadata:
        return {"status": "device-not-found", "message": "Current build ID not found"}

    # Find the next build in sequence
    next_build = find_next_build(metadata, current_build)
    
    if not next_build:
        return {"status": "up-to-date"}

    update_info = metadata[next_build]
    package_file = PACKAGES_DIR / update_info["filename"]

    if not package_file.exists():
        raise HTTPException(status_code=404, detail="Update package not found")

    checksum = calculate_checksum(package_file)
    signed_checksum = sign_data(checksum.encode())

    return {
        "status": "update-available",
        "version": update_info["version"],
        "build_id": next_build,
        "url": f"/packages/{update_info['filename']}",
        "checksum": checksum,
        "signature": signed_checksum,
    }

@app.get("/checksum/{filename}")
def get_checksum(filename: str):
    file_path = PACKAGES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    checksum = calculate_checksum(file_path)
    signed_checksum = sign_data(checksum.encode())
    return {"filename": filename, "checksum": checksum, "signature": signed_checksum}

@app.get("/packages/{filename}")
def get_package(filename: str):
    file_path = PACKAGES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Package not found")
    return FileResponse(file_path)

# Load metadata.json
def load_metadata():
    if not METADATA_FILE.exists():
        return {}
    with open(METADATA_FILE, "r") as f:
        return json.load(f)

# Save metadata.json
def save_metadata(data):
    with open(METADATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# --- API Endpoints (device-facing) ---
@app.get("/metadata")
def get_metadata():
    return load_metadata()


@app.get("/update")
def get_update(build_id: str):
    metadata = load_metadata()
    return metadata.get(build_id, {"error": "No update found"})


# --- Admin Web UI ---
@app.get("/admin/metadata", response_class=HTMLResponse)
def admin_metadata(request: Request):
    metadata = load_metadata()
    return templates.TemplateResponse(
        "metadata.html", {"request": request, "metadata": metadata}
    )


@app.post("/admin/metadata/add")
def add_metadata(build_id: str = Form(...), version: str = Form(...), filename: str = Form(...), release_date: str = Form(...)):
    metadata = load_metadata()
    metadata[build_id] = {"version": version, "filename": filename, "release_date": release_date}
    save_metadata(metadata)
    return RedirectResponse(url="/admin/metadata", status_code=303)


@app.post("/admin/metadata/delete")
def delete_metadata(build_id: str = Form(...)):
    metadata = load_metadata()
    if build_id in metadata:
        del metadata[build_id]
        save_metadata(metadata)
    return RedirectResponse(url="/admin/metadata", status_code=303)