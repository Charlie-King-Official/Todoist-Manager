# file: generate_scoreboard.py
import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ModuleNotFoundError:
    raise RuntimeError("This script requires Python 3.9+ (zoneinfo). Please upgrade Python.")

LEADERBOARD_PATH = Path("leaderboard.json")
OUTPUT_PATH = Path("index.html")
NY_TZ = ZoneInfo("America/New_York")

def safe_get(d, path, default=0):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

def fmt_dt_et(iso_utc: str) -> str:
    """Format an ISO UTC string as ET (e.g., 'Fri, Sep 26 11:59 PM ET')."""
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(NY_TZ)
        return dt.strftime("%a, %b %-d %I:%M %p ET") if hasattr(dt, "strftime") else dt.strftime("%a, %b %d %I:%M %p ET")
    except Exception:
        return iso_utc

def fmt_timeago_utc(iso_utc: str) -> str:
    """Human-ish relative time from now UTC."""
    try:
        now = datetime.now(timezone.utc)
        then = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        delta = now - then
        secs = int(delta.total_seconds())
        if secs < 60: return "just now"
        mins = secs // 60
        if mins < 60: return f"{mins} min ago"
        hrs = mins // 60
        if hrs < 24: return f"{hrs} hr ago"
        days = hrs // 24
        return f"{days} day{'s' if days!=1 else ''} ago"
    except Exception:
        return iso_utc

def main():
    if not LEADERBOARD_PATH.exists():
        # Create a minimal placeholder page if leaderboard.json is missing
        html = """<!doctype html><html><head><meta charset="utf-8">
<title>Chore Leaderboard</title>
<meta http-equiv="refresh" content="120">
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#111;color:#eee;margin:0}
  .wrap{padding:24px}
</style></head><body>
<div class="wrap"><h1>Chore Leaderboard</h1><p>No leaderboard.json found yet.</p></div>
</body></html>"""
        OUTPUT_PATH.write_text(html, encoding="utf-8")
        print("scoreboard.html written (placeholder).")
        return

    data = json.loads(LEADERBOARD_PATH.read_text(encoding="utf-8"))

    julia = safe_get(data, ["points", "Julia"], 0)
    chris = safe_get(data, ["points", "Chris"], 0)
    prev_julia = safe_get(data, ["previous_points", "Julia"], 0)
    prev_chris = safe_get(data, ["previous_points", "Chris"], 0)

    last_sync = data.get("last_sync", "")
    next_reset = data.get("next_reset_utc", "")

    # A tiny, responsive layout with dark theme
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Chore Leaderboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120"> <!-- auto-refresh every 2 minutes -->
<style>
    :root {
      --card-bg: rgba(23, 26, 33, 0.85);
      --text-color: #eaeef5;
      --muted-color: #a8b3c7;
      --accent-julia: #7dd3fc;
      --accent-chris: #f472b6;
    }
    html, body {
      margin: 0;
      padding: 0;
      background: transparent;
      width: 100%;
      height: 100%;
      overflow: hidden;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      color: var(--text-color);
    }
    .wrap {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: flex-start;
      padding: 2vh 2vw;
      width: 100%;
      height: 100%;
    }
    h1 {
      font-size: 4vw;
      margin-bottom: 2vh;
      text-align: center;
    }
    .meta {
      font-size: 1.8vw;
      color: var(--muted-color);
      margin-bottom: 2vh;
      text-align: center;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(40vw, 1fr));
      gap: 2vw;
      width: 100%;
    }
    .card {
      background: var(--card-bg);
      border-radius: 1vw;
      padding: 2vh 2vw;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .name {
      font-size: 2.5vw;
      font-weight: 700;
      margin-bottom: 1vh;
    }
    .score {
      font-size: 6vw;
      font-weight: 800;
    }
    .julia .score {
      color: var(--accent-julia);
    }
    .chris .score {
      color: var(--accent-chris);
    }
    .sub {
      font-size: 1.8vw;
      color: var(--muted-color);
      margin-top: 1vh;
    }
    .footer {
      margin-top: 3vh;
      font-size: 1.6vw;
      color: var(--muted-color);
      display: flex;
      flex-wrap: wrap;
      gap: 1vw;
      justify-content: center;
    }
    .pill {
      background: rgba(14, 16, 21, 0.7);
      padding: 0.5vh 1vw;
      border-radius: 999px;
    }
    .bar-wrap {
      margin-top: 2vh;
      height: 1vh;
      width: 80%;
      background: rgba(14, 16, 21, 0.7);
      border-radius: 99px;
      overflow: hidden;
    }
    .bar {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--accent-julia), var(--accent-chris));
      transition: width .5s ease;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Weekly Chore Leaderboard</h1>
    <div class="meta">Updated 5 hr ago • Next reset: Fri, Oct 3 11:59 PM ET</div>
    <div class="grid">
      <div class="card julia">
        <div class="name">Julia</div>
        <div class="score">{julia}</div>
        <div class="sub">Previous week: {prev_julia}</div>
      </div>
      <div class="card chris">
        <div class="name">Chris</div>
        <div class="score">{chris}</div>
        <div class="sub">Previous week: {prev_chris}</div>
      </div>
    </div>
    <div class="bar-wrap"><div class="bar"></div></div>
    <div class="footer">
      <span class="pill">Today is {datetime.now(NY_TZ).strftime("%a, %b %-d") if hasattr(datetime.now(NY_TZ), "strftime") else datetime.now(NY_TZ).strftime("%a, %b %d")}</span>
      <span class="pill">Times are shown in ET</span>
      <span class="pill">Page auto-refreshes every 5 minutes</span>
    </div>
  </div>
  <script>
    (function() {
      const julia = {julia};
      const chris = {chris};
      const total = Math.max(julia + chris, 1);
      const pct = Math.round((julia / total) * 100);
      document.querySelector('.bar').style.width = pct + '%';
    })();
  </script>
</body>
</html>
"""
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print("index.html written.")

if __name__ == "__main__":
    main()
