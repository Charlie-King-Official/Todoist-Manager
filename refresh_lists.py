import requests
from datetime import datetime, timedelta
import os

# === CONFIGURATION ===
API_TOKEN = os.getenv["TODOIST_API_KEY"]  # Stored securely in Replit Secrets
PROJECT_NAMES = ["Julia", "Chris"]

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# === Get Project ID ===
def get_project_id(name):
    res = requests.get("https://api.todoist.com/rest/v2/projects", headers=headers)
    for project in res.json():
        if project["name"] == name:
            return project["id"]
    return None

# === Get Tasks in Project ===
def get_tasks(project_id):
    res = requests.get(f"https://api.todoist.com/rest/v2/tasks?project_id={project_id}", headers=headers)
    return res.json()

# === Determine Next Due Date ===
def get_next_due_date(task):
    due_info = task.get("due", {})
    if not due_info.get("recurring") or not due_info.get("date"):
        return None

    try:
        due_date = datetime.fromisoformat(due_info["date"])
    except ValueError:
        return None

    if due_date.date() >= datetime.now().date():
        return None  # Not overdue

    content = task["content"].lower()
    if "daily" in content:
        return due_date + timedelta(days=1)
    elif "weekly" in content:
        return due_date + timedelta(weeks=1)
    elif "monthly" in content:
        return due_date + timedelta(days=30)
    return None

# === Update Task Due Date ===
def update_due_date(task_id, new_date):
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    data = {"due_date": new_date.strftime("%Y-%m-%d")}
    res = requests.post(url, headers=headers, json=data)
    return res.status_code == 204

# === Main Routine ===
def reset_tasks():
    total_reset = 0
    for project_name in PROJECT_NAMES:
        project_id = get_project_id(project_name)
        if not project_id:
            print(f"Project '{project_name}' not found.")
            continue

        tasks = get_tasks(project_id)
        reset_count = 0

        for task in tasks:
            next_due = get_next_due_date(task)
            if next_due:
                success = update_due_date(task["id"], next_due)
                if success:
                    reset_count += 1
                    print(f"[{project_name}] Reset: {task['content']} → {next_due.date()}")

        print(f"[{project_name}] Total tasks reset: {reset_count}")
        total_reset += reset_count

    print(f"Grand total tasks reset: {total_reset}")

# === Run Script ===
if __name__ == "__main__":
    reset_tasks()
