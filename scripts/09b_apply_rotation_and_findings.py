#!/usr/bin/env python3
"""Step 4 follow-up: write the best-of-4 rotation results and two verification findings to the db.

Usage: python3 09b_apply_rotation_and_findings.py DB ORIENTATION_JSONL ROTATION_BESTOF4_JSONL
A page counts as rotated if Tesseract OSD flagged it (conf >= 2) or the best-of-4 test did.
"""
import json, sqlite3, sys
DB, OSD, BEST = sys.argv[1:4]
rot = {}
for path, key in ((OSD, "rotated"), (BEST, "rotated")):
    for l in open(path):
        o = json.loads(l)
        if o.get(key):
            rot.setdefault(o["file_no"], set()).add(o["page"])
con = sqlite3.connect(DB)
con.execute("DELETE FROM document_issues WHERE issue_code='ROTATED_PAGES'")
con.execute("UPDATE documents SET rotated_pages=0")
for f, pages in rot.items():
    con.execute("UPDATE documents SET rotated_pages=? WHERE file_no=?", (len(pages), f))
    con.execute("INSERT INTO document_issues VALUES (?,?,?)",
                (f, "ROTATED_PAGES", f"{len(pages)} page(s); confirmed by OSD or best-of-4-rotations OCR test"))
con.executemany("INSERT OR IGNORE INTO issue_types VALUES (?,?,?,?)", [
    ("HALFTONE_BACKGROUND", "text", "high", "Text printed on a grey/dotted background; plain OCR recovers almost nothing"),
    ("HANDWRITING", "text", "high", "Handwritten entries; OCR cannot read them")])
con.executemany("INSERT OR IGNORE INTO document_issues VALUES (?,?,?)", [
    (615, "HALFTONE_BACKGROUND", "p1: 95% of words lost"),
    (232, "HANDWRITING", "p35: all handwritten values misread, incl. amount $42.13 read as 472,13")])
con.commit()
print("rotated pages:", sum(len(p) for p in rot.values()), "in", len(rot), "files")
