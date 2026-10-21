"""
Two fixes for the Arabic bot, both found by a live run that produced no post.

1. THE QC REJECTED THE SOURCE'S OWN NAME.
   The run picked a post by @BillAckman. The writer produced a good Arabic
   draft, and the QC killed it with "unlisted Latin words (['Ackman',
   'Bill'])" - because the allowlist was built from the post title and
   summary, and the author's name lives in the FEED LABEL, not the text.
   A draft that names the source's own author is faithful, not slop. The
   feed label now feeds the allowlist, and an X handle is split on
   camelCase so "@BillAckman" allows both "Bill" and "Ackman".

2. THE WRITER CHAIN LEADS WITH DEAD MODELS.
   nvidia/nemotron-3-super-120b-a12b returns HTTP 404 ("Function not
   found") - the endpoint is gone. It sat in both the NVIDIA default and
   the OpenRouter default list, so every run burned a retry on it. It is
   removed from both.

The chain still ends on a working model: Gemini first (it works, it just
failed QC on a draft shape), then Groq gpt-oss-20b/120b, then the
OpenRouter free models.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(r"C:\Users\Abdelli\Documents\soq-alyoum-fb-bot")
bot = REPO / "post_bot.py"
src = bot.read_text(encoding="utf-8")
orig = len(src.split("\n"))
applied = []


def sub(old, new, label, count=1):
    global src
    if old not in src:
        print(f"  !! ANCHOR MISSING: {label}")
        return False
    src = src.replace(old, new, count)
    applied.append(label)
    return True


# ---------------------------------------------------------------- 1. the feed
# words the source's own feed label is allowed to use
helper = '''
def _feed_words(feed: str) -> set:
    """Words the source's own feed label is allowed to use.

    An X handle like "@BillAckman" is one token, but a post names the
    person as two words. Split on camelCase so both are allowed - the
    draft is quoting the source, not inventing a name.
    """
    out = set()
    for tok in re.findall(r"[A-Za-z]{2,}", feed or ""):
        out.add(tok.lower())
        for part in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]+|[a-z]+", tok):
            if len(part) >= 2:
                out.add(part.lower())
    return out


def quality_check('''
sub("\ndef quality_check(", helper, "the feed-label allowlist helper")

# the signature gains the feed
sub("def quality_check(post: str, source_title: str,\n"
    "                  source_extra: str = \"\") -> list[str]:",
    "def quality_check(post: str, source_title: str,\n"
    "                  source_extra: str = \"\",\n"
    "                  source_feed: str = \"\") -> list[str]:",
    "quality_check takes the feed label")

# ...and the allowlist uses it
sub("    _allow |= {t.lower() for t in\n"
    "               re.findall(r\"[A-Za-z]{2,}\", source_title + \" \" + source_extra)}",
    "    _allow |= {t.lower() for t in\n"
    "               re.findall(r\"[A-Za-z]{2,}\", source_title + \" \" + source_extra)}\n"
    "    # The source's own author name lives in the feed label, not the\n"
    "    # text. Naming them is faithful, not slop.\n"
    "    _allow |= _feed_words(source_feed)",
    "the allowlist includes the feed label")

# the call sites pass the feed
sub("quality_check(post, pick[\"title\"], pick.get(\"summary\", \"\")))",
    "quality_check(post, pick[\"title\"], pick.get(\"summary\", \"\"),\n"
    "                             pick.get(\"feed\", \"\")))",
    "the text-post QC call passes the feed")
sub("vprobs = quality_check(vpost, vpick[\"title\"],",
    "vprobs = quality_check(vpost, vpick[\"title\"], vpick.get(\"summary\", \"\"),\n"
    "                             vpick.get(\"feed\", \"\")),",
    "the video QC call passes the feed")

# ---------------------------------------------------------------- 2. dead model
sub('NVIDIA_MODELS_DEFAULT = ("openai/gpt-oss-20b,"\n'
    '                         "nvidia/nemotron-3-super-120b-a12b")',
    '# nvidia/nemotron-3-super-120b-a12b is GONE: the endpoint returns HTTP 404\n'
    '# ("Function not found") and every run wasted a retry on it.\n'
    'NVIDIA_MODELS_DEFAULT = ("openai/gpt-oss-20b,"\n'
    '                         "openai/gpt-oss-120b")',
    "the dead NVIDIA model is out of the default chain")
sub('OPENROUTER_MODELS_DEFAULT = ("google/gemma-4-31b-it:free,"\n'
    '                              "google/gemma-4-26b-a4b-it:free,"\n'
    '                              "nvidia/nemotron-3-super-120b-a12b:free")',
    'OPENROUTER_MODELS_DEFAULT = ("google/gemma-4-31b-it:free,"\n'
    '                              "google/gemma-4-26b-a4b-it:free,"\n'
    '                              "openai/gpt-oss-120b:free")',
    "the dead NVIDIA model is out of the OpenRouter chain")

# ---------------------------------------------------------------- guards
out_lines = src.split("\n")
if '__name__ == "__main__":' not in src:
    print("!! the __main__ guard is missing - REFUSING TO WRITE")
    raise SystemExit(1)
if len(out_lines) < orig:
    print(f"!! the file shrank ({orig} -> {len(out_lines)}) - REFUSING TO WRITE")
    raise SystemExit(1)
for must in ("_feed_words", "source_feed", "NVIDIA_MODELS_DEFAULT"):
    if must not in src:
        print(f"!! {must} missing after the patch - REFUSING TO WRITE")
        raise SystemExit(1)

bot.write_text(src, encoding="utf-8")
print(f"applied {len(applied)} changes ({orig} -> {len(out_lines)} lines):")
for a in applied:
    print("  -", a)
