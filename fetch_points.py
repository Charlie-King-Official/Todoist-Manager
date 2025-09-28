import os
import json
import requests
from datetime import datetime, timedelta

# Load API token from environment variable
API_TOKEN = os.getenv("TODOIST_API_KEY")

# Load leaderboard data
with open("leaderboard.json", "r") as f:
    leaderboard = json.load(f)

# Get last sync time
last_sync_str = leaderboard.get("last_sync", leaderboard.get("last_reset", "2000-01-01"))
last_sync = datetime.strptime(last_sync_str, "%Y-%m-%d")

# Prepare headers for Todoist API
headers = {
    "Authorization": f"Bearer {API_TOKEN}"
}

# Fetch completed tasks from Todoist
response = requests.get("https://api.todoist.com/sync/v9/completed/get_all", headers=headers)
completed_tasks = response.json().get("items", [])

# Assign points based on task labels or project names
def assign_points(task):
    # Example logic: 1 point per task
    return 1

# Identify child based on project name or label
def identify_child(task):
    project_name = task.get("project_id", "")
    content = task.get("content", "").lower()
    if "julia" in content:
        return "Julia"
    elif "chris" in content:
        return "Chris"
    return None

# Update points for tasks completed since last sync
for task in completed_tasks:
    completed_date = datetime.strptime(task["completed_date"], "%Y-%m-%dT%H:%M:%SZ")
    if completed_date > last_sync:
        child = identify_child(task)
        if child:
            points = assign_points(task)
            leaderboard["current_week"][child] += points

# Update last sync time
leaderboard["last_sync"] = datetime.utcnow().strftime("%Y-%m-%d")

# Save updated leaderboard
with open("leaderboard.json", "w") as f:
    json.dump(leaderboard, f, indent=2)

print("Leaderboard updated successfully.")

