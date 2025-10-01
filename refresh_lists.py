import os
import sys
import requests
from datetime import datetime, timedelta, timezone

API_TOKEN = os.getenv("TODOIST_API_KEY")
if not API_TOKEN:
    print("ERROR: TODOIST_API_KEY env var is not set.")
    sys.exit(1)

PROJECT_NAMES = ["Julia", "Chris"]

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# === Helpers ===
RFC3339_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f%z",  # e.g., 2025-09-28T10:30:00.000000+00:00
    "%Y-%m-%dT%H:%M:%S%z",     # e.g., 2025-09-28T10:30:00+00:00
]

def parse_due_to_datetime(due: dict) -> datetime | None:
    """
    Return a timezone-aware datetime if possible, else a date at local midnight.
    """
    if not due:
        return None

    # Prefer exact datetime if present
    dt = due.get("datetime")
    if dt:
        # Handle trailing 'Z' (UTC) by replacing with +00:00
        if dt.endswith("Z"):
            dt = dt.replace("Z", "+00:00")
        # Try parsing RFC3339-like strings
        for fmt in RFC3339_FORMATS:
            try:
                return datetime.strptime(dt, fmt)
            except ValueError:
                pass
        # Fallback: attempt fromisoformat (Py 3.11 handles +00:00 well)
        try:
            return datetime.fromisoformat(dt)
        except Exception:
            return None

    # Fall back to date-only
    d = due.get("date")
    if d:
        try:
            # Interpret as local date at midnight; make it naive
            return datetime.fromisoformat(d)
        except ValueError:
            return None

    return None

def infer_period(due_string: str) -> str | None:
    """
    Very simple inference: 'daily'/'every day' -> daily
                          'weekly'/weekday names -> weekly
                          'monthly' -> monthly
    """
    if not due_string:
        return None
    s = due_string.lower()
    if "every day" in s or "daily" in s or "every weekday" in s:
        return "daily"
    # Heuristic: if it mentions 'week' or a weekday name, treat as weekly
    weekdays = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    if "week" in s or any(wd in s for wd in weekdays):
        return "weekly"
    if "month" in s:
        return "monthly"
    return None

def advance_to_next_period(start: datetime, period: str, today: datetime) -> datetime:
    """
    Advance start forward in whole period increments until >= today (date-wise).
    For monthly we approximate by 30 days (good enough for chores).
    """
    next_dt = start
    # Only compare dates (ignore time for all-day recurrences)
    while next_dt.date() < today.date():
        if period == "daily":
            next_dt += timedelta(days=1)
        elif period == "weekly":
            next_dt += timedelta(weeks=1)
        elif period == "monthly":
            next_dt += timedelta(days=30)  # simple approximation
        else:
            break
    return next_dt

# === Todoist REST calls ===
def get_project_id(name):
    res = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers)
    res.raise_for_status()
    for project in res.json():
        if project["name"] == name:
            return project["id"]
    return None

def get_tasks(project_id):
    url = f"https://api.todoist.com/rest/v2/tasks?project_id={project_id}"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json()

def update_due_date(task_id, new_date: datetime, due_string: str) -> bool:
    """
    Reschedule the task's next occurrence to an absolute date (YYYY-MM-DD)
    without changing its recurrence pattern.
    """
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    payload = {"due_date": new_date.strftime("%Y-%m-%d"), "due_string": due_string}
    # Todoist expects POST for updates; success returns 204 No Content.
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code not in (204, 200):
        print(f"Failed to update task {task_id}: {res.status_code} - {res.text}")
        return False
    return True

# === Core logic ===
def get_next_due_datetime(task) -> datetime | None:
    """
    If task is recurring & overdue, compute the next occurrence date we want to set.
    Otherwise return None.
    """
    due_info = task.get("due")
    if not due_info:
        return None

    # Must use 'is_recurring' (not 'recurring')
    if not due_info.get("is_recurring"):
        return None

    current_due = parse_due_to_datetime(due_info)
    if not current_due:
        return None

    # Not overdue → skip
    now = datetime.now(tz=current_due.tzinfo) if current_due.tzinfo else datetime.now()
    if current_due.date() >= now.date():
        return None

    # Infer the period from due.string (e.g., "every day", "every Monday", etc.)
    period = infer_period(due_info.get("string", ""))
    if not period:
        return None

    # Advance to today or next future date
    return advance_to_next_period(current_due, period, now)

def reset_tasks():
    grand_total = 0
    for project_name in PROJECT_NAMES:
        project_id = get_project_id(project_name)
        if not project_id:
            print(f"Project '{project_name}' not found.")
            continue

        tasks = get_tasks(project_id)
        reset_count = 0

        for task in tasks:
            next_due = get_next_due_datetime(task)
            due_string = task.get("due", {}).get("string", "")
            if next_due and due_string:
                print(f"{task['content']}-> due: {next_due}, recurrence: {due_string}")
                if update_due_date(task["id"], next_due, due_string):
                    reset_count += 1
                    print(f"[{project_name}] Rescheduled: {task['content']} → {next_due.date()}")

        print(f"[{project_name}] Total tasks rescheduled: {reset_count}")
        grand_total += reset_count

    print(f"Grand total rescheduled: {grand_total}")

if __name__ == "__main__":
    reset_tasks()
