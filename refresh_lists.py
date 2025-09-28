import os
import requests

# Load API token from environment variable
API_TOKEN = os.getenv("TODOIST_API_KEY")

def get_project_id(project_name):
    url = "https://api.todoist.com/rest/v2/projects"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }

    try:
        res = requests.get(url, headers=headers)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

    try:
        projects = res.json()
    except ValueError:
        print("Failed to decode JSON. Response was:")
        print(res.text)
        return None

    for project in projects:
        if project["name"] == project_name:
            return project["id"]

    print(f"Project '{project_name}' not found.")
    return None

# Example usage
if __name__ == "__main__":
    project_name = "Daily Tasks"
    project_id = get_project_id(project_name)
    if project_id:
        print(f"Project ID for '{project_name}': {project_id}")
