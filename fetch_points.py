import os
import json
import requests
from datetime import datetime, timezone

# === Config ===
API_TOKEN = os.getenv("TODOIST_API_KEY")
LEADERBOARD_PATH = "leaderboard.json"
COMPLETED_URL = "https://api.todoist.com/sync/v9/completed/get_all"
PROJECTS_URL  = "https://api.todoist.com/rest/v2/projects"
PAGE_SIZE = 200  # max per page for completed items

if not API_TOKEN:
    raise RuntimeError("TODOIST_API_KEY is not set in the environment.")

HEADERS_JSON = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
}

def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_iso_utc(s: str) -> datetime:
    # Accept both 'Z' and +00:00 forms
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

# === Load leaderboard (with sensible defaults) ===
if not os.path.exists(LEADERBOARD_PATH):
    leaderboard = {
        "current_week": {"Julia": 0, "Chris": 0},
        "previous_week": {"Julia": 0, "Chris": 0},
        "highest_week": {"Julia": 0, "Chris": 0},
        "last_reset": "2000-01-01T00:00:00Z",
        "last_sync": "2000-01-01T00:00:00Z",
    }
else:
    with open(LEADERBOARD_PATH, "r") as f:
        leaderboard = json.load(f)

# Ensure keys exist
leaderboard.setdefault("current_week", {})
leaderboard["current_week"].setdefault("Julia", 0)
leaderboard["current_week"].setdefault("Chris", 0)
leaderboard.setdefault("previous_week", {})
leaderboard["previous_week"].setdefault("Julia", 0)
leaderboard["previous_week"].setdefault("Chris", 0)
leaderboard.setdefault("highest_week", {})
leaderboard["highest_week"].setdefault("Julia", 0)
leaderboard["highest_week"].setdefault("Chris", 0)

last_sync_str = leaderboard.get("last_sync") or leaderboard.get("last_reset") or "2000-01-01T00:00:00Z"
last_sync = parse_iso_utc(last_sync_str)

# === Map project_id -> project name ===
proj_res = requests.get(PROJECTS_URL, headers=HEADERS_JSON)
proj_res.raise_for_status()
projects = proj_res.json()
project_id_to_name = {p["id"]: p["name"] for p in projects}

# === Fetch completed items since last_sync, with pagination ===
def fetch_completed_since(since_dt: datetime):
    items = []
    offset = 0
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    while True:
        params = {
            "since": since_iso,
            "limit": PAGE_SIZE,
            "offset": offset
        }
        res = requests.get(COMPLETED_URL, headers=HEADERS_JSON, params=params)
        if res.status_code != 200:
            raise RuntimeError(f"Completed API error {res.status_code}: {res.text}")
        data = res.json()
        batch = data.get("items", [])
        items.extend(batch)
        # Stop if fewer than a full page returned
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return items

completed_tasks = fetch_completed_since(last_sync)

# === Points assignment ===
def assign_points(task: dict) -> int:
    # Simple rule: 1 point per completed task
    # You can expand this later (e.g., by label or priority)
    return 1

def identify_child(task: dict) -> str | None:
    """
    Determine child based on the project name.
    Completed item has 'project_id'; we map to the name.
    """
    pid = task.get("project_id")
    if not pid:
        return None
    pname = project_id_to_name.get(pid, "")
    if pname == "Julia":
        return "Julia"
    if pname == "Chris":
        return "Chris"
    return None

# === Process tasks strictly after last_sync to avoid duplicates ===
added = {"Julia": 0, "Chris": 0}
for task in completed_tasks:
    # completed_date is RFC3339 with 'Z'
    completed_at = parse_iso_utc(task["completed_date"])
    if completed_at <= last_sync:
        continue  # defense against inclusive 'since' results
    child = identify_child(task)
    if not child:
        continue
    pts = assign_points(task)
    leaderboard["current_week"][child] += pts
    added[child] += pts

# === Update the last_sync timestamp to "now" in UTC ===
leaderboard["last_sync"] = iso_utc_now()

# === Save ===
with open(LEADERBOARD_PATH, "w") as f:
    json.dump(leaderboard, f, indent=2)

print(
    f"Leaderboard updated. Added points — Julia: {added['Julia']}, Chris: {added['Chris']}. "
    f"Last sync: {leaderboard['last_sync']}"
)
