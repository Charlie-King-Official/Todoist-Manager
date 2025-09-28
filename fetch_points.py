import os
import json
import time as _time
from datetime import datetime, timezone, timedelta, time as dt_time
from zoneinfo import ZoneInfo
import requests

# === Configuration ===
API_TOKEN = os.getenv("TODOIST_API_KEY")
if not API_TOKEN:
    raise RuntimeError("TODOIST_API_KEY environment variable is not set.")

LEADERBOARD_PATH = "leaderboard.json"
PROJECT_NAMES = ["Julia", "Chris"]
POLL_INTERVAL_SECONDS = 120  # ~2 minutes
PAGE_SIZE = 200

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
}

SYNC_COMPLETED_URL = "https://api.todoist.com/sync/v9/completed/get_all"  # completed items (Sync API)
REST_PROJECTS_URL  = "https://api.todoist.com/rest/v2/projects"          # project names/IDs (REST v2)

# === Time helpers ===
NY_TZ = ZoneInfo("America/New_York")

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_iso_utc(s: str) -> datetime:
    # Accept both Z and +00:00 forms
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def next_friday_2359_utc(now_utc: datetime) -> datetime:
    """Compute next Friday 23:59:00 America/New_York as a UTC datetime."""
    now_local = now_utc.astimezone(NY_TZ)
    days_ahead = (4 - now_local.weekday()) % 7  # Monday=0 ... Friday=4
    target_date = now_local.date() + timedelta(days=days_ahead)
    # The requested cutoff is 11:59 PM local time (23:59:00)
    target_local = datetime.combine(target_date, dt_time(23, 59, 0), NY_TZ)
    if target_local <= now_local:
        target_local += timedelta(days=7)
    return target_local.astimezone(timezone.utc)

# === State helpers ===
def load_state(path: str) -> dict:
    if not os.path.exists(path):
        now_utc = datetime.now(timezone.utc)
        return {
            "points": {"Julia": 0, "Chris": 0},
            "previous_points": {"Julia": 0, "Chris": 0},
            "last_sync": "2000-01-01T00:00:00Z",
            "tie_break_ids": [],
            "next_reset_utc": next_friday_2359_utc(now_utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    with open(path, "r") as f:
        data = json.load(f)
    # ensure keys
    data.setdefault("points", {"Julia": 0, "Chris": 0})
    data.setdefault("previous_points", {"Julia": 0, "Chris": 0})
    data.setdefault("last_sync", "2000-01-01T00:00:00Z")
    data.setdefault("tie_break_ids", [])
    data.setdefault("next_reset_utc", next_friday_2359_utc(datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    for key in ("Julia", "Chris"):
        data["points"].setdefault(key, 0)
        data["previous_points"].setdefault(key, 0)
    return data

def save_state(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

# === Todoist fetch ===
def fetch_projects() -> tuple[dict, dict]:
    """Return ({id:name}, {name:id})."""
    r = requests.get(REST_PROJECTS_URL, headers=HEADERS)
    r.raise_for_status()
    projs = r.json()
    id_to_name = {p["id"]: p["name"] for p in projs}
    name_to_id = {p["name"]: p["id"] for p in projs}
    return id_to_name, name_to_id

def fetch_completed_window(since_dt: datetime, until_dt: datetime | None, project_id: str
