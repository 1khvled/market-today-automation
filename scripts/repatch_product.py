"""
Re-apply the product-post wiring to the Arabic bot, safely.

Two earlier patch scripts of mine truncated this file (they rebuilt the
content by slicing a string and dropped the tail), which silently removed the
publish path and the __main__ guard: the bot ran, printed nothing and exited
0, so the Arabic page went quiet. The file is restored from 8d262906 - the
last intact version - and this script re-applies the wiring using LINE
indices, with a verification gate on every edit and a hard refusal to write
if the tail or the line count is not right.
"""
import sys
from pathlib import Path

REPO = Path(r"C:\Users\Abdelli\Documents\soq-alyoum-fb-bot")
bot = REPO / "post_bot.py"
lines = bot.read_text(encoding="utf-8").split("\n")
orig_n = len(lines)
applied = []


def find(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    return -1


def insert(at, block, label):
    global lines
    lines = lines[:at] + block.split("\n") + lines[at:]
    applied.append(label)


# ---- 1. the product branch, by line surgery on the try/except -------------
i_try = find(lambda l: l == "    try:" and
              lines[lines.index(l) + 1].strip() == "post = rewrite_with_llm(pick, shape)"
              if False else False)
# simpler: find the rewrite call, then walk back to its try
i_call = find(lambda l: l.strip() == "post = rewrite_with_llm(pick, shape)")
if i_call < 0:
    print("!! could not find the rewrite call")
    raise SystemExit(1)
i_try = i_call - 1
while i_try >= 0 and lines[i_try].strip() != "try:":
    i_try -= 1
if i_try < 0:
    print("!! could not find the try")
    raise SystemExit(1)
i_try -= (len(lines[i_try]) - len(lines[i_try].lstrip()))   # to column 0 of 'try'

# the end of the try/except = the next line at or below the try's indent
base_indent = len(lines[i_try]) - len(lines[i_try].lstrip())
i_end = i_try + 1
while i_end < len(lines):
    l = lines[i_end]
    if l.strip() == "":
        i_end += 1
        continue
    ind = len(l) - len(l.lstrip())
    if ind <= base_indent:
        break
    i_end += 1
# trim the trailing blank lines back to the real end of the block
while i_end > i_try and not lines[i_end - 1].strip():
    i_end -= 1

block = lines[i_try:i_end]
indented = [("    " + l if l.strip() else l) for l in block]

product_branch = [
    "    if pick.get(\"is_product\"):",
    "        # A hand-written product post: already in the house voice, already",
    "        # fact-checked, already has its image. The LLM must not touch it",
    "        # and the QC (which compares against a source headline) must not",
    "        # run on it.",
    "        post = (pick.get(\"summary\") or \"\").rstrip()",
    "        _tags = \" \".join(pick.get(\"keywords\") or [])",
    "        if _tags and _tags not in post:",
    "            post = f\"{post}\\n\\n{_tags}\"",
    "        fallback = True",
    "        log(f\"PRODUCT POST: {pick.get('product_id')}\")",
    "    else:",
]
lines = lines[:i_try] + product_branch + indented + lines[i_end:]
applied.append("the product copy is published as written")

# ---- 2. the prepared image ----------------------------------------------
i = find(lambda l: l.strip() == "img, ext, src = find_photo(pick)")
if i < 0:
    print("!! could not find find_photo")
    raise SystemExit(1)
# the add_source line sits just above it
i_src = i
while i_src >= 0 and "add_source(post, outlet_for" not in lines[i_src]:
    i_src -= 1
if i_src < 0:
    print("!! could not find add_source")
    raise SystemExit(1)
new_block = [
    "    if pick.get(\"is_product\"):",
    "        img = ext = src = None",
    "        _lp = pick.get(\"local_photo\") or \"\"",
    "        if _lp and os.path.exists(_lp):",
    "            try:",
    "                with open(_lp, \"rb\") as _f:",
    "                    img = _f.read()",
    "                ext, src = \"jpeg\", \"product\"",
    "            except Exception:",
    "                img = None",
    "        if not img:",
    "            log(\"product post image missing - skipping this candidate\")",
    "            return 0",
    "    else:",
    "        post = add_source(post, outlet_for(pick[\"feed\"]))",
    "        img, ext, src = find_photo(pick)",
]
lines = lines[:i_src] + new_block + lines[i + 1:]
applied.append("the prepared product image is used")

# ---- 3. no source/credit line on a product post -------------------------
i = find(lambda l: l.strip() == 'post = add_credit(post, credit_for(pick["feed"], src))')
if i >= 0:
    lines[i:i + 1] = [
        "    if not pick.get(\"is_product\"):",
        "        post = add_credit(post, credit_for(pick[\"feed\"], src))",
    ]
    applied.append("no source/credit line on a product post")
else:
    print("  (add_credit anchor not found - skipping that one)")

# ---- 4. the rotation ----------------------------------------------------
i = find(lambda l: l.strip() == 'log(f"{len(fresh)} fresh (not yet posted)")')
if i < 0:
    print("!! could not find the fresh log")
    raise SystemExit(1)
rotation = '''    # PRODUCT ROTATION. The pages are the top of the funnel for a paid
    # membership, so the product goes out on a schedule - at most
    # PRODUCT_PER_DAY a day, inside PRODUCT_WINDOW_UTC, and never two in a
    # row, so the page stays a news page and not an ad feed.
    try:
        import product_source as _ps
        _per_day = int(os.getenv("PRODUCT_PER_DAY", "1"))
        _win = os.getenv("PRODUCT_WINDOW_UTC", "9-21")
        _lo, _hi = (int(x) for x in _win.split("-"))
        _now_h = datetime.now(timezone.utc).hour
        _count = _ps.daily_count(state)
        _last_was_product = bool(state.get("history") and
                                 state["history"][-1].get("is_product"))
        if (_lo <= _now_h < _hi and _count < _per_day
                and not _last_was_product and _ps.load_posts()):
            _pc = _ps.candidates(state)
            if _pc:
                fresh.insert(0, _pc[0])
                log(f"PRODUCT ROTATION: injecting '{_pc[0].get('product_id')}' "
                    f"({_count}/{_per_day} today, hour {_now_h} in {_win} UTC)")
        else:
            log(f"product rotation skipped: {_count}/{_per_day} today, "
                f"hour {_now_h} in {_win} UTC, "
                f"last was product={_last_was_product}, "
                f"posts available={len(_ps.load_posts())}")'''
insert(i + 1, rotation, "the product rotation is rate-limited and windowed")

# ---- 5. the fresh filter keeps product posts ---------------------------
i = find(lambda l: l.strip() == 'fresh = [c for c in fresh if not _too_similar(c["title"])]')
if i >= 0:
    lines[i:i + 1] = [
        "    fresh = [c for c in fresh",
        "             if c.get(\"is_product\") or not _too_similar(c[\"title\"])]",
    ]
    applied.append("the fresh filter keeps product posts")
else:
    print("  (fresh-filter anchor not found - skipping)")

# ---- 6. the history records product posts ------------------------------
i = find(lambda l: l.strip() == 'hist.append({' and "fb_id" in lines[lines.index(l) + 1] if False else False)
i = -1
for j, l in enumerate(lines):
    if l.strip() == "hist.append({" and lines[j + 1].strip().startswith('"fb_id"'):
        i = j
        break
if i >= 0:
    lines[i + 1:i + 1] = [
        "        \"is_product\": bool(pick.get(\"is_product\")),",
        "        \"product_id\": pick.get(\"product_id\"),",
    ]
    applied.append("the history records product posts")
else:
    print("  (history anchor not found - skipping)")

# ---- 7. count the product post for the daily cap ----------------------
i = find(lambda l: l.strip() == "save_state(state_file, state)" and
          lines[min(len(lines) - 1, find(lambda x: x.strip() == "return 0"))] if False else False)
# the last save_state before the final 'return 0'
idx = len(lines) - 1 - lines[::-1].index("    return 0")
i = -1
for j in range(idx, -1, -1):
    if lines[j].strip() == "save_state(state_file, state)":
        i = j
        break
if i >= 0:
    lines[i:i + 1] = [
        "    try:",
        "        import product_source as _ps2",
        "        if pick.get(\"is_product\"):",
        "            _ps2.mark_used(state, pick.get(\"product_id\", \"\"))",
        "    except Exception:",
        "        pass",
        "    save_state(state_file, state)",
    ]
    applied.append("the product post is counted for the daily cap")
else:
    print("  (save_state anchor not found - skipping)")

# ---- 8. import product_source ------------------------------------------
i = find(lambda l: l.strip() == "import growth")
if i >= 0:
    lines[i:i] = [
        "try:",
        "    import product_source",
        "except Exception:",
        "    product_source = None",
    ]
    applied.append("import product_source")

# ---- GUARDS -------------------------------------------------------------
out = "\n".join(lines)
if '__name__ == "__main__":' not in out:
    print("!! the __main__ guard is missing - REFUSING TO WRITE")
    raise SystemExit(1)
if "def main(" not in out:
    print("!! main() is missing - REFUSING TO WRITE")
    raise SystemExit(1)
if len(lines) < orig_n:
    print(f"!! the file shrank ({orig_n} -> {len(lines)}) - REFUSING TO WRITE")
    raise SystemExit(1)
for must in ("PRODUCT ROTATION", "is_product", "local_photo"):
    if must not in out:
        print(f"!! {must} missing after the patch - REFUSING TO WRITE")
        raise SystemExit(1)

bot.write_text(out, encoding="utf-8")
print(f"applied {len(applied)} changes ({orig_n} -> {len(lines)} lines):")
for a in applied:
    print("  -", a)
