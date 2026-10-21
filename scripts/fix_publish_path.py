"""
Repair the Arabic bot's publish path.

Two defects, both mine, both introduced while re-applying the product
wiring after the truncation accident:

1. `if not pick.get("is_product"):` was placed in front of the add_credit
   call, but the whole publish block that follows it was left indented as
   the body of that if. A product post therefore took the `not is_product`
   path as false, skipped the publish entirely, and the bot fell through
   to save_state and return 0 - a silent no-op. The log stops right after
   "PRODUCT POST:" with nothing after it, which is exactly what happened.

2. `h = item_hash(...)` lived inside the else branch, so a product post
   had no `h` at all - the state update would raise NameError.

The fix: only the add_credit call stays conditional; the publish block
goes back to the function level, and `h` is computed for every candidate.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOT = Path(r"C:\Users\Abdelli\Documents\soq-alyoum-fb-bot\post_bot.py")
lines = BOT.read_text(encoding="utf-8").split("\n")
orig = len(lines)

# ---------------------------------------------------------------- 1 + 2
i = None
for j, l in enumerate(lines):
    if l == "    if not pick.get(\"is_product\"):":
        i = j
        break
if i is None:
    print("!! the conditional add_credit block is not where it should be")
    raise SystemExit(1)

# the block runs to the next line at indent <= 4
end = i + 1
while end < len(lines):
    l = lines[end]
    if l.strip() == "":
        end += 1
        continue
    ind = len(l) - len(l.lstrip())
    if ind <= 4:
        break
    end += 1
while end > i + 1 and not lines[end - 1].strip():
    end -= 1

# the first two lines are the if-body (add_credit + its log); the rest is
# the publish block, which must sit at function level again
body = lines[i + 2:end]
dedented = [(l[4:] if l.startswith("    ") else l) for l in body]
lines = lines[:i + 2] + dedented + lines[end:]

# ---------------------------------------------------------------- 3. h
# `h = item_hash(pick["link"], pick["title"])` must exist for every candidate
k = None
for j, l in enumerate(lines):
    if l.strip() == "h = item_hash(pick[\"link\"], pick[\"title\"])" and j < i:
        k = j
        break
if k is None:
    # it was inside the else branch - move it out, to just before the
    # image block
    k = None
    for j, l in enumerate(lines):
        if l.strip() == "h = item_hash(pick[\"link\"], pick[\"title\"])":
            k = j
            break
    if k is None:
        print("!! item_hash not found")
        raise SystemExit(1)
    lines.pop(k)
    # find the image block and put it above
    m = None
    for j, l in enumerate(lines):
        if l == "    if pick.get(\"is_product\"):" and "local_photo" in lines[j + 2]:
            m = j
            break
    if m is None:
        print("!! the image block not found")
        raise SystemExit(1)
    lines[m:m] = ["    h = item_hash(pick[\"link\"], pick[\"title\"])"]
    moved = True
else:
    moved = False

out = "\n".join(lines)

# ---------------------------------------------------------------- guards
if "    if not pick.get(\"is_product\"):\n        post = add_credit(" not in out:
    print("!! the conditional add_credit is gone")
    raise SystemExit(1)
if out.count('log(f"Published WITH PHOTO ({src})! FB id={post_id}")') != 1:
    print("!! the publish call is not where it should be")
    raise SystemExit(1)
if '__name__ == "__main__":' not in out:
    print("!! the __main__ guard is missing - REFUSING TO WRITE")
    raise SystemExit(1)
if len(lines) < orig:
    print(f"!! the file shrank ({orig} -> {len(lines)}) - REFUSING TO WRITE")
    raise SystemExit(1)

BOT.write_text(out, encoding="utf-8")
print(f"repaired: publish block back at function level ({orig} -> {len(lines)} lines)")
print("  - only the add_credit call stays conditional on the product path")
print("  - item_hash is computed for every candidate" + (" (moved)" if moved else ""))
