#!/usr/bin/env python3
"""Rich failure alert for the market-today bot (Arabic-framed).

Runs ONLY on consecutive failures (the workflow gates single blips).
Reads the failed run's jobs + log via gh, extracts the real cause, and
sends ONE compact Telegram message with: streak count, cause, failed step,
last successful post, today's count, triage hint, log link.
Never crashes the step: any internal error falls back to a plain message.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from notify_telegram import send_telegram
except Exception:
    send_telegram = None

REPO = os.environ.get("GITHUB_REPOSITORY", "")
RUN_ID = os.environ.get("RUN_ID", "")
SERVER = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=120).stdout
    except Exception:
        return ""


def api(path):
    out = sh(["gh", "api", path])
    try:
        return json.loads(out) if out.strip() else {}
    except Exception:
        return {}


def main():
    link = f"{SERVER}/{REPO}/actions/runs/{RUN_ID}"
    try:
        return build(link)
    except Exception as ex:
        plain = (f"🚨 سوق اليوم bot run FAILED (run {RUN_ID}). "
                 f"Log parse failed ({ex}); triage from log: {link}")
        if send_telegram:
            send_telegram(plain)


def build(link):
    # 1. consecutive-failure streak (completed runs before this one)
    d = api("repos/" + REPO +
            "/actions/workflows/fb-post.yml/runs?per_page=10")
    streak = 0
    for r in d.get("workflow_runs", []):
        if str(r.get("id")) == str(RUN_ID):
            continue
        if r.get("status") != "completed":
            continue
        if r.get("conclusion") == "failure":
            streak += 1
        else:
            break
    streak += 1  # include this run

    # 2. failed steps
    jobs = api(f"repos/{REPO}/actions/runs/{RUN_ID}/jobs?per_page=5")
    bad_steps = []
    for j in (jobs.get("jobs") or []):
        for s in j.get("steps", []):
            if (s.get("conclusion") or "") == "failure":
                bad_steps.append(s.get("name", "?"))
    step = ", ".join(bad_steps) or "Run bot"

    # 3. log tail: the real cause
    log = sh(["gh", "run", "view", RUN_ID, "--log"])
    log = ANSI.sub("", log or "")
    cause, hint = classify(log)

    # 4. page health: posts today + minutes since last success
    posts_today, mins_ago = "?", "?"
    try:
        st = json.load(open("posted.json", encoding="utf-8"))
        today = datetime.now(timezone.utc).date().isoformat()
        posts_today = st.get("day_counts", {}).get(today, 0)
        at = (st.get("last_post") or {}).get("at", "")
        if at:
            dt = (datetime.now(timezone.utc)
                  - datetime.fromisoformat(at))
            mins_ago = int(dt.total_seconds() // 60)
    except Exception:
        pass

    msg = (f"🚨 سوق اليوم عطلان — الفشل #{streak} ورا بعض\n"
           f"السبب: {cause}\n"
           f"الخطوة: {step}\n"
           f"آخر بوست ناجح: من {mins_ago} دقيقة | النهاردة: {posts_today}\n"
           f"اعمل إيه: {hint}\n"
           f"🔗 {link}")
    if send_telegram:
        send_telegram(msg)
    else:
        print(msg)


def classify(log):
    """(cause, triage-hint) from log signatures. Order matters."""
    if not log.strip():
        return ("السجل مش متاح", "افتح رابط السجل وشوف بنفسك")
    fails = re.findall(r"All LLM providers failed: (.+)", log)
    if fails:
        tail = fails[-1][:600]
        bits = []
        if "429" in tail:
            n = len(re.findall(r"429", tail))
            bits.append(f"زحمة مجانية 429 (×{n})")
        m404 = re.findall(r"(\S+?): \S+ HTTP 404", tail)
        if m404:
            bits.append("موديلات اتشالت: " + ", ".join(
                m.split("/")[-1].split(":")[0] for m in m404[:2]))
        if "failed QC" in tail:
            q = re.findall(r"failed QC: \[(.*?)\]", tail)
            bits.append("مرفوض QC: " + (q[-1][:120] if q else "?"))
        if "parse error" in tail or "no text" in tail or "empty" in tail:
            bits.append("موديل رجع فاضي")
        detail = "; ".join(bits) or "كل الموديلات وقعت"
        if m404:
            return (detail, "حدّث أسماء الموديلات في post_bot.py")
        return (detail, "زحمة مؤقتة غالباً — لو كمل 3+ راجع السجل")
    m = re.search(r"Quality check FAILED: (\[.*?\])", log)
    if m:
        return (f"مرفوض QC: {m.group(1)[:150]}",
                "شوف سبب الرفض — لو متكرر عدّل الـ QC")
    m = re.search(r"(Facebook error: .{0,150}|Publish failed: .{0,150})", log)
    if m:
        return (m.group(1)[:160], "رسالة فيسبوك في السجل")
    if re.search(r"token.*(expir|invalid|190)|invalid.*token", log, re.I):
        return ("توكن فيسبوك ميت", "أعد تثبيت التوكن (README section 3)")
    m = re.search(r"Rewrite failed: (.{0,200})", log)
    if m:
        return (m.group(1), "التفاصيل في السجل")
    return ("خطوة وقعت (شوف السجل)", "التفاصيل في السجل")


if __name__ == "__main__":
    main()
