"""
Mark the Arabic product post as used, in the state the bot reads.

The run that published it crashed before save_state (a NameError on the
dedup hash, fixed in a9e42b5), so posted.json on the remote never learned
that today's product post had gone out. Without this the next run would
publish the same product post again and the daily cap would read 0/1.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(r"C:\Users\Abdelli\Documents\soq-alyoum-fb-bot")
state_file = REPO / "posted.json"
state = json.loads(state_file.read_text(encoding="utf-8"))

today = datetime.now(timezone.utc).date().isoformat()
used = state.setdefault("product_posts_used", [])
if "ar-01-cot-index-extremes" in used:
    used.remove("ar-01-cot-index-extremes")
used.append("ar-01-cot-index-extremes")
state["product_posts_used"] = used[-30:]

day = state.setdefault("product_posts_day", {})
day[today] = max(day.get(today, 0), 1)
state["product_posts_day"] = {k: v for k, v in day.items() if k >= today}

state_file.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                      encoding="utf-8")
print(f"posted.json: product_posts_day[{today}] = {day[today]}")
print(f"  used tail: {state['product_posts_used'][-4:]}")
