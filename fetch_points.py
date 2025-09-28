import os
import json
import time
from datetime import datetime, timezone
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

SYNC_COMPLETED_URL = "https://api.todoist.com/sync/v9/completed/get_all"
REST_PROJECTS_URL  = "https://api.todoist.com/rest/v2/projects"


# === Helpers ===
def iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def parse_iso_utc(s: str) -> datetime:
    # Accept both ...Z and ...+00:00
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {
            "points": {"Julia": 0, "Chris": 0},
            "last_sync": "2000-01-01T00:00:00Z",
            "tie_break_ids": [],
        }
    with open(path, "r") as f:
        return json.load(f)

def save_state(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def fetch_projects() -> dict:
    """Return {project_id: project_name} and {name: id} maps."""
    r = requests.get(REST_PROJECTS_URL, headers=HEADERS)
    r.raise_for_status()
    projects = r.json()
    id_to_name = {p["id"]: p["name"] for p in projects}
    name_to_id = {p["name"]: p["id"] for p in projects}
    return id_to_name, name_to_id

def fetch_completed_since(since_dt: datetime, project_id: str | None = None) -> list[dict]:
    """
    Pull completed items since 'since_dt'. We page using limit/offset.
    If 'project_id' is provided, we ask the server to filter; if not supported
    in your tenant, we still filter client-side below (defensive).
    """
    since_iso = since_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    items = []
    offset = 0

    while True:
        params = {
            "since": since_iso,
            "limit": PAGE_SIZE,
            "offset": offset,
            "annotate_items": "true",  # includes more fields if you need them later
        }
        if project_id:
            params["project_id"] = project_id

        r = requests.get(SYNC_COMPLETED_URL, headers=HEADERS, params=params)
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            # If project-level filter errors, fallback to no project filter this page
            if project_id:
                params.pop("project_id", None)
                r = requests.get(SYNC_COMPLETED_URL, headers=HEADERS, params=params)
                r.raise_for_status()
            else:
                raise

        payload = r.json()
        batch = payload.get("items", [])
        items.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return items

def poll_once(state: dict) -> dict:
    """
    Poll both projects, count new completions > last_sync (with tiebreak),
    add points, and advance last_sync/tie_break_ids safely.
    """
    # Ensure keys exist
    state.setdefault("points", {})
    state["points"].setdefault("Julia", 0)
    state["points"].setdefault("Chris", 0)
    state.setdefault("last_sync", "2000-01-01T00:00:00Z")
    state.setdefault("tie_break_ids", [])

    last_sync_dt = parse_iso_utc(state["last_sync"])
    tie_break_ids = set(state["tie_break_ids"])

    # Resolve project IDs for Julia/Chris
    id_to_name, name_to_id = fetch_projects()
    missing = [n for n in PROJECT_NAMES if n not in name_to_id]
    if missing:
        raise RuntimeError(f"Projects not found in Todoist: {', '.join(missing)}")

    julia_id = name_to_id["Julia"]
    chris_id = name_to_id["Chris"]

    # Fetch completed items for both projects (server-filtered if supported)
    items = []
    items += fetch_completed_since(last_sync_dt, project_id=julia_id)
    items += fetch_completed_since(last_sync_dt, project_id=chris_id)

    # If server filtering not supported, also filter client-side by project_id.
    # (We dedupe by item['id'] across the combined list.)
    wanted_ids = {julia_id, chris_id}
    uniq = {}
    for it in items:
        iid = it.get("id")
        pid = it.get("project_id")
        if iid and pid in wanted_ids:
            uniq[iid] = it  # overwrite duplicates from two fetches if any

    # Count only items strictly after last_sync
    max_seen_time = last_sync_dt
    ids_at_max_time = set()

    new_points = {"Julia": 0, "Chris": 0}

    for it in uniq.values():
        completed_raw = it.get("completed_at") or it.get("completed_date")
        if not completed_raw:
            continue
        completed_dt = parse_iso_utc(completed_raw)

        # Strictly greater than last_sync, OR equal but not yet seen (tie-break)
        if completed_dt > last_sync_dt or (completed_dt == last_sync_dt and it["id"] not in tie_break_ids):
            # Identify child by project_id
            child = "Julia" if it.get("project_id") == julia_id else ("Chris" if it.get("project_id") == chris_id else None)
            if child:
                state["points"][child] += 1
                new_points[child] += 1

            # Track max time and tiebreak IDs
            if completed_dt > max_seen_time:
                max_seen_time = completed_dt
                ids_at_max_time = {it["id"]}
            elif completed_dt == max_seen_time:
                ids_at_max_time.add(it["id"])

    # Advance last_sync to the latest completed_at we saw,
    # and store only the IDs at that exact timestamp for tie-breaking next run.
    state["last_sync"] = max_seen_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    state["tie_break_ids"] = sorted(ids_at_max_time)

    print(
        f"[poll] Added points — Julia: {new_points['Julia']} | Chris: {new_points['Chris']} "
        f"| new last_sync: {state['last_sync']} | tracked_ties: {len(state['tie_break_ids'])}"
    )

    return state


# === Main loop (every ~2 minutes) ===
if __name__ == "__main__":
    # If you will run it under a scheduler (cron/GitHub Actions), you can
    # call poll_once(state) once and exit instead of a forever loop.
    while True:
        try:
            state = load_state(LEADERBOARD_PATH)
            state = poll_once(state)
            save_state(LEADERBOARD_PATH, state)
        except Exception as e:
            # Log the error but keep the loop alive
            print("Error during poll:", e)

        time.sleep(POLL_INTERVAL_SECONDS)
