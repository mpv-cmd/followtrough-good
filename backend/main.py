# --- SAFETY GUARD: prevent HTML/UI code in backend files ---
import pathlib, sys

BACKEND_DIR = pathlib.Path(__file__).parent
# Build strings without embedding literal HTML tags in source (avoid self-triggering)
_lt = "<"
_gt = ">"
BAD_MARKERS = [
    _lt + "html" + _gt,
    "<!" + "doctype html",
    _lt + "button" + _gt,
    _lt + "body" + _gt,
    _lt + "head" + _gt,
    _lt + "/html" + _gt,
]

for py in BACKEND_DIR.glob("*.py"):
    try:
        txt = py.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        continue

    if any(m in txt for m in BAD_MARKERS):
        print(f"❌ SAFETY GUARD: HTML detected in backend file: {py.name}")
        sys.exit(1)
# --- END SAFETY GUARD ---

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import os, json, uuid, shutil

from transcribe import transcribe_file
from extract_action import extract_actions

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5500","http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
LATEST_JSON_PATH = os.path.join(UPLOAD_DIR, "latest.json")

@app.post("/upload")
async def upload_meeting(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    transcript = transcribe_file(file_path)
    actions = extract_actions(transcript)

    payload = {
        "file_id": file_id,
        "filename": file.filename,
        "actions": actions,
    }
    with open(LATEST_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {"status": "ok", **payload}

@app.get("/latest")
def latest():
    if not os.path.exists(LATEST_JSON_PATH):
        return {"status": "empty"}
    with open(LATEST_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"status": "ok", "data": data}