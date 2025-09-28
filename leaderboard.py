import json

# Load leaderboard data from JSON file
with open("leaderboard.json", "r") as f:
    data = json.load(f)

# Extract current week points
julia_points = data["current_week"].get("Julia", 0)
chris_points = data["current_week"].get("Chris", 0)

# Generate minimalist HTML content
html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            margin: 0;
            padding: 0;
            width: 480px;
            height: 80px;
            background-color: transparent;
            color: white;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: space-around;
            align-items: center;
        }}
        .column {{
            text-align: center;
            flex: 1;
        }}
        .name {{
            font-size: 16px;
            font-weight: normal;
        }}
        .points {{
            font-size: 36px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="column">
        <div class="name">Julia</div>
        <div class="points">{julia_points}</div>
    </div>
    <div class="column">
        <div class="name">Chris</div>
        <div class="points">{chris_points}</div>
    </div>
</body>
</html>
"""

# Write the HTML content to leaderboard.html
with open("leaderboard.html", "w") as f:
    f.write(html_content)

print("leaderboard.html has been successfully regenerated.")
