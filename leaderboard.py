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
  :root {{
    --bg: #0f1115;
    --card: #171a21;
    --text: #eaeef5;
    --muted: #a8b3c7;
    --accent-julia: #7dd3fc;   /* sky-300 */
    --accent-chris: #f472b6;   /* pink-400 */
    --ok: #50fa7b;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; }}
  .wrap {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
  h1 {{ margin: 0 0 16px 0; font-size: 28px; font-weight: 700; letter-spacing: .2px; }}
  .meta {{ color: var(--muted); font-size: 14px; margin-bottom: 18px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }}
  .card {{ background: var(--card); border-radius: 12px; padding: 16px 18px; }}
  .row {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }}
  .name {{ font-weight: 700; font-size: 18px; }}
  .score {{ font-weight: 800; font-size: 44px; line-height: 1; }}
  .julia .score {{ color: var(--accent-julia); }}
  .chris .score {{ color: var(--accent-chris); }}
  .sub {{ color: var(--muted); font-size: 14px; margin-top: 6px; }}
  .bar-wrap {{ margin-top: 12px; height: 10px; background: #0e1015; border-radius: 99px; overflow: hidden; }}
  .bar {{ height: 10px; background: linear-gradient(90deg, var(--accent-julia), var(--accent-chris)); width: 0%; transition: width .5s ease; }}
  .footer {{ margin-top: 16px; color: var(--muted); font-size: 13px; display: flex; gap: 16px; flex-wrap: wrap; }}
  .pill {{ background: #0e1015; padding: 6px 10px; border-radius: 999px; }}
</style>
</head>
<body>
  <div class="wrap">
    <h1>Weekly Chore Leaderboard</h1>
    <div class="meta">
      Updated {fmt_timeago_utc(last_sync)} • Next reset: {fmt_dt_et(next_reset)}
    </div>

    <div class="grid">
      <div class="card julia">
        <div class="row"><div class="name">Julia</div><div class="score">{julia}</div></div>
        <div class="sub">Previous week: {prev_julia}</div>
      </div>
      <div class="card chris">
        <div class="row"><div class="name">Chris</div><div class="score">{chris}</div></div>
        <div class="sub">Previous week: {prev_chris}</div>
      </div>
    </div>

    <div class="footer">
      <span class="pill">Today is {datetime.now(NY_TZ).strftime("%a, %b %-d") if hasattr(datetime.now(NY_TZ), "strftime") else datetime.now(NY_TZ).strftime("%a, %b %d")}</span>
      <span class="pill">Times are shown in ET</span>
      <span class="pill">Page auto-refreshes every 2 minutes</span>
    </div>
  </div>

  <script>
    // Optional tiny progress bar comparing current totals
    (function() {{
      const julia = {julia};
      const chris = {chris};
      const total = Math.max(julia + chris, 1);
      const pct = Math.round((julia / total) * 100);
      const bar = document.createElement('div');
      bar.className = 'bar-wrap';
      bar.innerHTML = '<div class="bar"></div>';
      document.querySelector('.grid').after(bar);
      requestAnimationFrame(() => {{
        bar.querySelector('.bar').style.width = pct + '%';
      }});
    }})();
  </script>
</body>
</html>
"""
    OUTPUT_PATH.write_text(html, encoding="utf-8")
    print("index.html written.")

if __name__ == "__main__":
    main()
