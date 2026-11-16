#!/usr/bin/env python3
"""Step 2: load the SQLite inventory.

Usage: python3 05_build_inventory.py SCHEMA_SQL CLASSIFIED_JSONL OUT_DB
Inputs come from 01_profile.py and 02_classify.py. Re-running rebuilds the database.
"""
import json, os, re, sqlite3, sys
from datetime import datetime, timezone

SCHEMA, SRC, DB = sys.argv[1], sys.argv[2], sys.argv[3]
if os.path.exists(DB):
    os.remove(DB)
con = sqlite3.connect(DB)
con.executescript(open(SCHEMA).read())
recs = [json.loads(l) for l in open(SRC)]
now = datetime.now(timezone.utc).isoformat(timespec="seconds")

DOC_TYPES = [
    ("minutes - board meeting", "Board of Trustees minutes", "Regular, special and annual meeting minutes"),
    ("minutes - public hearing", "Board of Trustees minutes", "Minutes of public hearings"),
    ("minutes - executive session", "Board of Trustees minutes", "Minutes of executive sessions"),
    ("agenda - board meeting", "Board of Trustees agendas", "Agendas for regular/special meetings"),
    ("agenda - public hearing", "Board of Trustees agendas", "Agendas for public hearings"),
    ("application / form", "Forms and applications", "Blank or completed applications and forms"),
    ("report / plan", "Reports and plans", "Studies, plans, RFP and planning reports"),
    ("public notice", "Notices", "Legal and public notices"),
    ("other", "Unclassified", "Text present but no rule matched; needs human review"),
    ("unknown (no text layer)", "Unclassified", "Image-only; type cannot be read until OCR"),
]
con.executemany("INSERT INTO doc_types VALUES (?,?,?)", DOC_TYPES)

ISSUES = [
    ("NO_TEXT_LAYER", "text", "high", "Image-only PDF; not searchable, needs OCR"),
    ("TITLE_MISSING", "metadata", "medium", "Title field empty"),
    ("TITLE_TEMPLATE", "metadata", "medium", "Title carried over from a reused template; describes another document"),
    ("TITLE_FILENAME", "metadata", "low", "Title is a source filename or software string"),
    ("AUTHOR_MISSING", "metadata", "low", "Author field empty"),
    ("AUTHOR_INCONSISTENT", "metadata", "low", "Author written in non-standard form (e.g. all caps)"),
    ("NO_CONTENT_DATE", "identity", "medium", "No meeting/document date could be read from the text"),
    ("CREATION_DATE_RESAVED", "metadata", "medium", "CreationDate reflects a later batch re-save, not origin"),
    ("CREATION_DATE_FAR", "metadata", "low", "CreationDate more than 1 year from the document's own date"),
    ("FONTS_NOT_EMBEDDED", "format", "medium", "One or more fonts not embedded; blocks PDF/A conformance"),
    ("NOT_PDFA", "format", "low", "No PDF/A identification in XMP"),
    ("LOW_RES_SCAN", "format", "high", "Scanned image below 200 ppi; OCR quality at risk"),
    ("EXACT_DUPLICATE", "integrity", "medium", "Byte-identical to another file in the archive"),
    ("PDF_SYNTAX_WARNING", "integrity", "low", "pdfinfo reported a syntax error (file still opens)"),
    ("TYPE_UNCLASSIFIED", "identity", "low", "Document type not determined by rules; needs review"),
]
con.executemany("INSERT INTO issue_types VALUES (?,?,?,?)", ISSUES)

# fixity + duplicates for the full archive
for r in recs:
    con.execute("INSERT INTO fixity VALUES (?,?,?,?,?,?,?)",
                (r["file_no"], r["filename"], r["sha256"], r["bytes"], int(r["in_sample"]), now,
                 "Python hashlib SHA-256"))
groups = {}
for r in recs:
    if r["dup_group"]:
        groups.setdefault(r["sha256"], sorted(r["dup_group"]))
gid_by_hash = {}
for gid, (h, members) in enumerate(sorted(groups.items(), key=lambda kv: kv[1][0]), 1):
    gid_by_hash[h] = gid
    con.execute("INSERT INTO duplicate_groups VALUES (?,?,?,?)", (gid, h, len(members), members[0]))
    con.executemany("INSERT INTO duplicate_members VALUES (?,?)", [(gid, m) for m in members])

SLUG = {"minutes - board meeting": "minutes_board", "minutes - public hearing": "minutes_hearing",
        "minutes - executive session": "minutes_exec", "agenda - board meeting": "agenda_board",
        "agenda - public hearing": "agenda_hearing", "application / form": "form",
        "report / plan": "report", "public notice": "notice", "other": "unclassified",
        "unknown (no text layer)": "unclassified"}

def orientation(ps):
    m = re.match(r"([\d.]+) x ([\d.]+)", ps or "")
    if not m:
        return "mixed/other"
    w, h = float(m.group(1)), float(m.group(2))
    return "portrait" if h > w else "landscape"

for r in (x for x in recs if x["in_sample"]):
    i = r["info"]
    author = i.get("Author") or None
    issues = []
    tl = {"full": "full", "none (image only)": "none"}.get(r["text_layer"], "partial")
    if tl == "none":
        issues.append(("NO_TEXT_LAYER", f'{i.get("Pages")} page(s), image only'))
    tq = r["title_quality"]
    if tq == "missing":
        issues.append(("TITLE_MISSING", None))
    elif tq.startswith("reused"):
        issues.append(("TITLE_TEMPLATE", i.get("Title")))
    elif tq.startswith("filename"):
        issues.append(("TITLE_FILENAME", i.get("Title")))
    if not author:
        issues.append(("AUTHOR_MISSING", None))
    elif author.isupper():
        issues.append(("AUTHOR_INCONSISTENT", author))
    if not r["content_date"] and tl != "none":
        issues.append(("NO_CONTENT_DATE", None))
    if (r["creation_date"] or "").startswith("2023-10-0") and "macOS Version 13.4.1" in (i.get("Producer") or ""):
        issues.append(("CREATION_DATE_RESAVED", f'{r["creation_date"]} via {i.get("Producer")}'))
    elif r["creation_lag_days"] is not None and abs(r["creation_lag_days"]) > 365:
        issues.append(("CREATION_DATE_FAR", f'{r["creation_lag_days"]} days'))
    if r["font_count"] and r["fonts_embedded"] < r["font_count"]:
        issues.append(("FONTS_NOT_EMBEDDED", f'{r["font_count"]-r["fonts_embedded"]} of {r["font_count"]} not embedded'))
    if not r["xmp_pdfa"]:
        issues.append(("NOT_PDFA", None))
    if tl == "none" and r["image_xppi_max"] and r["image_xppi_max"] < 200:
        issues.append(("LOW_RES_SCAN", f'{r["image_xppi_max"]} ppi'))
    if r["dup_group"]:
        issues.append(("EXACT_DUPLICATE", "same bytes as " + ", ".join(f"{x}.pdf" for x in r["dup_group"] if x != r["file_no"])))
    if r["pdfinfo_err"]:
        issues.append(("PDF_SYNTAX_WARNING", r["pdfinfo_err"][:120]))
    if r["doc_type"] in ("other", "unknown (no text layer)"):
        issues.append(("TYPE_UNCLASSIFIED", None))

    date_part = r["content_date"] or "undated"
    proposed = f'potsdam_{date_part}_{SLUG[r["doc_type"]]}_{r["file_no"]:04d}.pdf'
    con.execute("""INSERT INTO documents VALUES
        (?,?,?,?,?,?, ?,?,?,?,?,?, ?,?,?, ?,?,?,?,?,?,?,?, ?,?,?,?, ?,?,?, ?,?,?,?)""", (
        r["file_no"], r["filename"], proposed, r["doc_type"], r["content_date"],
        "text" if r["content_date"] else "none",
        i.get("Title") or None, tq, author, author.title() if author else None,
        i.get("Creator") or None, i.get("Producer") or None,
        r["creation_date"], r["mod_date"], r["creation_lag_days"],
        i.get("PDF version"), int(i.get("Pages", 0)), i.get("Page size"), orientation(i.get("Page size")),
        int(i.get("Tagged") == "yes"), int(r["has_xmp"]), int(r["xmp_pdfa"]), int(i.get("Encrypted", "no") != "no"),
        r["font_count"], r["fonts_embedded"], r["image_count"], r["image_xppi_max"],
        r["text_chars"], tl, int(tl != "full"),
        r["bytes"], r["sha256"], gid_by_hash.get(r["sha256"]), None))
    con.executemany("INSERT INTO document_issues VALUES (?,?,?)", [(r["file_no"], c, d) for c, d in issues])

# notes recorded during manual inspection in Step 1
NOTES = {
    43: "Draft corridor study dated April 2003 in page footer; metadata says 2014 and title is a Publisher filename. Exact duplicate of 47.pdf.",
    544: "Minutes of June 19, 2017 meeting; Title field names a January 2014 resolution (template carry-over).",
    521: "Text layer verified against page image; matches, including the original typo 'Execution Session'.",
    3: "Blank planning board application (2006); pdfinfo warns about the form Fields array; logo text exists only as image.",
    916: "NYS Department of Public Service fact sheet, not a Village record; header logo and some bullets are images or symbol glyphs.",
    971: "Single page image at 82 ppi, re-saved Oct 2023; lowest scan resolution in the sample.",
}
con.executemany("UPDATE documents SET notes=? WHERE file_no=?", [(v, k) for k, v in NOTES.items()])
con.commit()
print("documents", con.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
      "fixity", con.execute("SELECT COUNT(*) FROM fixity").fetchone()[0],
      "issues", con.execute("SELECT COUNT(*) FROM document_issues").fetchone()[0])
