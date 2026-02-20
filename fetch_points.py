import os
import json
from datetime import datetime, timezone, timedelta, time as dt_time
from typing import Tuple, Dict, List

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ModuleNotFoundError:
    raise RuntimeError("This script requires Python 3.9+ (zoneinfo). Please upgrade Python.")

import requests

# === Config ===
API_TOKEN = os.getenv("TODOIST_API_KEY")
if not API_TOKEN:
    raise RuntimeError("TODOIST_API_KEY is not set.")

LEADERBOARD_PATH = "leaderboard.json"
PROJECT_NAMES = ["Julia", "Chris"]
PAGE_SIZE = 200

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Updated endpoint (API v1)
COMPLETED_URL = "https://api.todoist.com/api/v1/tasks/completed"
REST_PROJECTS_URL = "https://api.todoist.com/rest/v2/projects"

NY_TZ = ZoneInfo("America/New_York")


# =========================
# Time Helpers
# =========================

def parse_iso_utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def today_midnight_et_utc(now_utc: datetime) -> datetime:
    now_local = now_utc.astimezone(NY_TZ)
    start_local = datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0, tzinfo=NY_TZ)
    return start_local.astimezone(timezone.utc)

def next_friday_235959_utc(now_utc: datetime) -> datetime:
    now_local = now_utc.astimezone(NY_TZ)
    days_ahead = (4 - now_local.weekday()) % 7  # Mon=0..Fri=4
    tgt_date = now_local.date() + timedelta(days=days_ahead)
    tgt_local = datetime.combine(tgt_date, dt_time(23, 59, 59), NY_TZ)
    if tgt_local <= now_local:
        tgt_local += timedelta(days=7)
    return tgt_local.astimezone(timezone.utc)


# =========================
# State Management
# =========================

def load_state(path: str) -> dict:
    if not os.path.exists(path):
        now_utc = datetime.now(timezone.utc)
        return {
            "points": {"Julia": 0, "Chris": 0},
            "previous_points": {"Julia": 0, "Chris": 0},
            "last_sync": iso_utc(today_midnight_et_utc(now_utc)),
            "next_reset_utc": iso_utc(next_friday_235959_utc(now_utc)),
        }

    with open(path, "r") as f:
        data = json.load(f)

    data.setdefault("points", {"Julia": 0, "Chris": 0})
    data.setdefault("previous_points", {"Julia": 0, "Chris": 0})

    if "last_sync" not in data:
        data["last_sync"] = iso_utc(today_midnight_et_utc(datetime.now(timezone.utc)))

    if "next_reset_utc" not in data:
        data["next_reset_utc"] = iso_utc(next_friday_235959_utc(datetime.now(timezone.utc)))

    for k in ("Julia", "Chris"):
        data["points"].setdefault(k, 0)
        data["previous_points"].setdefault(k, 0)

    return data


def save_state(path: str, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# =========================
# Todoist API Calls
# =========================

def fetch_projects_maps() -> Tuple[Dict[str, str], Dict[str, str]]:
    r = requests.get(REST_PROJECTS_URL, headers=HEADERS)
    r.raise_for_status()
    projs = r.json()
    id_to_name = {str(p["id"]): p["name"] for p in projs}
    name_to_id = {p["name"]: str(p["id"]) for p in projs}
    return id_to_name, name_to_id


def fetch_completed(
    since_dt: datetime,
    until_dt: datetime | None,
    project_id: str | None
) -> List[dict]:
    """
    Pull completed tasks using API v1.
    Uses cursor-based pagination.
    """
    items: List[dict] = []
    cursor = None

    params = {
        "since": iso_utc(since_dt),
        "limit": PAGE_SIZE,
    }

    if until_dt:
        params["until"] = iso_utc(until_dt)

    if project_id:
        params["project_id"] = project_id

    while True:
        if cursor:
            params["cursor"] = cursor

        r = requests.get(COMPLETED_URL, headers=HEADERS, params=params)
        r.raise_for_status()
        payload = r.json()

        batch = payload.get("results", [])
        items.extend(batch)

        cursor = payload.get("next_cursor")
        if not cursor:
            break

    return items


# =========================
# Counting Logic
# =========================

def count_window(state: dict, start_dt: datetime, end_dt: datetime, julia_id: str, chris_id: str) -> dict:
    """
    Count completions in (start_dt, end_dt]
    """
    combined: dict[str, dict] = {}

    for pid in (julia_id, chris_id):
        for it in fetch_completed(start_dt, end_dt, pid):
            iid = it.get("id")
            if iid:
                combined[iid] = it

    max_seen = start_dt
    added = {"Julia": 0, "Chris": 0}

    for it in combined.values():
        raw = it.get("completed_at")
        if not raw:
            continue

        ts = parse_iso_utc(raw)

        if ts <= start_dt or ts > end_dt:
            continue

        if it.get("project_id") == julia_id:
            state["points"]["Julia"] += 1
            added["Julia"] += 1
        elif it.get("project_id") == chris_id:
            state["points"]["Chris"] += 1
            added["Chris"] += 1

        if ts > max_seen:
            max_seen = ts

    state["last_sync"] = iso_utc(max_seen)

    print(f"[window] +Julia:{added['Julia']} +Chris:{added['Chris']} | last_sync={state['last_sync']}")
    return state


def rollover_if_due(state: dict, name_to_id: dict) -> dict:
    now_utc = datetime.now(timezone.utc)
    boundary = parse_iso_utc(state["next_reset_utc"])
    last_sync_dt = parse_iso_utc(state["last_sync"])

    if now_utc < boundary:
        return state

    if last_sync_dt < boundary:
        print(f"[rollover] Closing week at boundary {state['next_reset_utc']}")
        state = count_window(state, last_sync_dt, boundary,
                             name_to_id["Julia"], name_to_id["Chris"])

    state["previous_points"] = {
        "Julia": state["points"]["Julia"],
        "Chris": state["points"]["Chris"],
    }

    state["points"] = {"Julia": 0, "Chris": 0}
    state["last_sync"] = iso_utc(boundary)
    state["next_reset_utc"] = iso_utc(next_friday_235959_utc(now_utc))

    print(
        f"[rollover] Weekly reset. Prev: Julia={state['previous_points']['Julia']} "
        f"Chris={state['previous_points']['Chris']} | next_reset_utc={state['next_reset_utc']}"
    )

    return state


# =========================
# Main
# =========================

def main():
    state = load_state(LEADERBOARD_PATH)
    _, name_to_id = fetch_projects_maps()

    for p in PROJECT_NAMES:
        if p not in name_to_id:
            raise RuntimeError(f"Project '{p}' not found in Todoist.")

    state = rollover_if_due(state, name_to_id)

    last_sync_dt = parse_iso_utc(state["last_sync"])
    now_utc = datetime.now(timezone.utc)

    state = count_window(
        state,
        last_sync_dt,
        now_utc,
        name_to_id["Julia"],
        name_to_id["Chris"],
    )

    save_state(LEADERBOARD_PATH, state)
    print("Leaderboard updated.")


if __name__ == "__main__":
    main()