#!/usr/bin/env python3
"""Step 1b: derive document type, content date and metadata-quality flags.

Usage: python3 02_classify.py PROFILE_JSONL OUT_JSONL
Rule-based and transparent on purpose: every flag can be traced to a rule below.
"""
import collections, json, re, sys
from datetime import date

MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE_RE = re.compile(rf"\b({MONTHS})\.?\s*-?\s*(\d{{1,2}}),?\s*(\d{{4}})", re.I)
MNUM = {m.lower(): i for i, m in enumerate(MONTHS.split("|"), 1)}

def doc_type(t):
    t = re.sub(r"^[^A-Za-z0-9]+", "", t)
    u = t.upper()[:400]
    if not t.strip():
        return "unknown (no text layer)"
    if u.startswith("AGENDA") and "PUBLIC HEARING" in u[:40]:
        return "agenda - public hearing"
    if u.startswith("AGENDA"):
        return "agenda - board meeting"
    if "EXECUTIVE SESSION" in u[:120] and "WAS HELD" in u[:200]:
        return "minutes - executive session"
    if "PUBLIC HEARING" in u[:120] and "WAS HELD" in u[:200]:
        return "minutes - public hearing"
    if "MEETING" in u[:120] and "WAS HELD" in u[:200]:
        return "minutes - board meeting"
    if "APPLICATION" in u[:200] or "FORM" in u[:80]:
        return "application / form"
    if "NOTICE" in u[:150]:
        return "public notice"
    if any(k in u for k in ("REPORT", "PLAN", "TABLE OF CONTENTS", "STUDY")):
        return "report / plan"
    return "other"

def content_date(t):
    m = DATE_RE.search(t[:600])
    if not m:
        return None
    try:
        return date(int(m.group(3)), MNUM[m.group(1).lower()], int(m.group(2))).isoformat()
    except ValueError:
        return None

recs = [json.loads(l) for l in open(sys.argv[1])]
hash_groups = collections.defaultdict(list)
for r in recs:
    hash_groups[r["sha256"]].append(r["file_no"])
title_counts = collections.Counter((r["info"].get("Title") or "").strip() for r in recs)

out = []
for r in recs:
    info, t = r["info"], r["first_text"]
    title = (info.get("Title") or "").strip()
    r["doc_type"] = doc_type(t)
    r["content_date"] = content_date(t)
    cd = (info.get("CreationDate") or "")[:10]
    r["creation_date"] = cd or None
    r["mod_date"] = (info.get("ModDate") or "")[:10] or None
    lag = None
    if r["content_date"] and cd:
        lag = (date.fromisoformat(cd) - date.fromisoformat(r["content_date"])).days
    r["creation_lag_days"] = lag
    # title quality
    if not title:
        tq = "missing"
    elif re.search(r"\.(pub|docx?|xlsx?|pdf)$", title, re.I) or title.lower().startswith("microsoft"):
        tq = "filename or software string"
    elif title_counts[title] >= 5:
        tq = "reused across many files (template carry-over)"
    elif title.split()[:4] == t.split()[:4]:
        tq = "auto-filled from first line"
    else:
        tq = "descriptive"
    r["title_quality"] = tq
    pages = int(info.get("Pages", "0") or 0)
    cpp = r["chars_per_page"]
    empty_pages = sum(1 for c in cpp if c < 20)
    if r["text_chars"] == 0:
        tl = "none (image only)"
    elif empty_pages and empty_pages >= max(1, pages // 2):
        tl = "partial (some pages image only)"
    else:
        tl = "full"
    r["text_layer"] = tl
    r["empty_text_pages"] = empty_pages
    r["dup_group"] = hash_groups[r["sha256"]] if len(hash_groups[r["sha256"]]) > 1 else None
    out.append(r)

with open(sys.argv[2], "w") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
print("classified", len(out))
