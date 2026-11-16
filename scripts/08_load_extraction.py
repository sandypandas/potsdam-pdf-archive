#!/usr/bin/env python3
"""Step 3e: record extraction tests and text-usability findings in the inventory.

Usage: python3 08_load_extraction.py DB OUT_DIR
Reads: OUT_DIR/ocr/ocr_pages.jsonl, ocr_benchmark.jsonl, layer_audit.jsonl, orientation.jsonl
Adds: extraction_tests rows, new issue types, final text-usability class per document.
"""
import json, os, sqlite3, sys
from datetime import datetime, timezone

DB, OUT = sys.argv[1], sys.argv[2]
con = sqlite3.connect(DB)
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
load = lambda p: [json.loads(l) for l in open(os.path.join(OUT, p))]
TESS, POPPLER = "tesseract 5.3.4 (eng, LSTM)", "poppler 24.02 pdftotext"

cols = [r[1] for r in con.execute("PRAGMA table_info(documents)")]
if "text_usability" not in cols:
    con.execute("ALTER TABLE documents ADD COLUMN text_usability TEXT")
    con.execute("ALTER TABLE documents ADD COLUMN rotated_pages INTEGER DEFAULT 0")
    con.execute("ALTER TABLE extraction_tests ADD COLUMN notes TEXT")
con.execute("DELETE FROM extraction_tests")

con.executemany("INSERT OR IGNORE INTO issue_types VALUES (?,?,?,?)", [
    ("TEXT_LAYER_DEFECTIVE", "text", "high", "Text layer exists but drops characters (e.g. all digits); fails OCR cross-check"),
    ("IMAGE_ONLY_PAGES", "text", "medium", "Born-digital file contains pages that are images only (maps, inserts)"),
    ("TEXT_IN_IMAGES", "text", "low", "Charts or graphics carry text only as images"),
    ("ROTATED_PAGES", "format", "medium", "Scanned pages stored sideways/upside down; OCR fails unless auto-rotated"),
    ("OCR_HARD_CONTENT", "text", "medium", "Tables, maps, colour-coded or graphic content; OCR text incomplete or scrambled"),
])

# 1) full OCR of image-only files
rows = []
for o in load("ocr/ocr_pages.jsonl"):
    rows.append((o["file_no"], o["page"], "tesseract-300ppi-psm3", TESS, o["chars"], o["mean_conf"], None, None,
                 f'out/ocr/{o["file_no"]}_p{o["page"]}.txt', now, None))
# 2) benchmark on born-digital pages (reference = verified text layer)
for b in load("ocr_benchmark.jsonl"):
    for d in (300, 200):
        rows.append((b["file_no"], b["page"], f"tesseract-{d}ppi-psm3 vs layer", TESS, None, None,
                     b[f"cer_{d}"], b[f"word_miss_{d}"], f'out/bench_text/{b["file_no"]}_p{b["page"]}_tess{d}.txt', now,
                     f'benchmark; extra-word rate {b[f"word_extra_{d}"]}'))
# 3) layer audit (pdftotext cross-checked against OCR)
audit = load("layer_audit.jsonl")
for a in audit:
    rows.append((a["file_no"], a["page"], "pdftotext layer vs tesseract-300ppi", POPPLER + " + " + TESS,
                 None, None, None, a["layer_gap"], f'out/layer_audit_text/{a["file_no"]}_p{a["page"]}_layer.txt', now,
                 f'layer audit; OCR words missing from layer={a["layer_gap"]}, digits layer/ocr={a["digits_layer"]}/{a["digits_ocr"]}, flag={a["flag"]}'))
# 4) rotation fix and LLM tests (manual, recorded individually)
rows += [
    (190, 21, "tesseract-300ppi-psm1 (auto-rotate)", TESS, None, 81.2, None, None, "verify/s3/tess190_p21_psm1.txt", now,
     "same page psm3 = 53.6 conf, unreadable text; psm1 readable but digit errors in amounts and dates"),
    (190, 21, "LLM vision transcription", "claude-opus-5-5 via page image (150 ppi, rotated)", None, None, None, None,
     "verify/s3/llm190_p21.md", now, "top half of page; table structure and all figures captured; verified in Step 4"),
    (982, 1, "LLM vision transcription", "claude-opus-5-5 via page image (130 ppi)", None, None, None, None,
     "verify/s3/llm982_p1.md", now, "captures colour-coded dates and B-week street column that Tesseract dropped; verified in Step 4"),
]
con.executemany("INSERT INTO extraction_tests (file_no,page,method,tool_version,chars,mean_word_conf,cer,"
                "word_miss_rate,output_path,run_at,notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)

# document-level findings
rot = {}
for o in load("orientation.jsonl"):
    if o["rotated"]:
        rot[o["file_no"]] = rot.get(o["file_no"], 0) + 1
for f, n in rot.items():
    con.execute("UPDATE documents SET rotated_pages=? WHERE file_no=?", (n, f))
    con.execute("INSERT OR IGNORE INTO document_issues VALUES (?,?,?)", (f, "ROTATED_PAGES", f"{n} page(s)"))

DEFECTIVE = {885: "pages 5-25 contain no digits in layer; OCR recovers them (e.g. 'founded in 1806')"}
IMAGE_PAGES = {43: "pages 65, 73-77 image only (maps)", 47: "exact copy of 43.pdf; same image-only pages",
               863: "pages 5-7 image only"}
TEXT_IN_IMG = {889: "survey charts: labels exist only as images (p17)"}
HARD = {44: "street map", 982: "colour-coded calendar; B-week column dropped by OCR",
        190: "rotated financial spreadsheet", 209: "tables/charts on low-confidence pages"}
for f, d in DEFECTIVE.items():
    con.execute("INSERT OR IGNORE INTO document_issues VALUES (?,?,?)", (f, "TEXT_LAYER_DEFECTIVE", d))
for f, d in IMAGE_PAGES.items():
    con.execute("INSERT OR IGNORE INTO document_issues VALUES (?,?,?)", (f, "IMAGE_ONLY_PAGES", d))
    con.execute("UPDATE documents SET text_layer='partial' WHERE file_no=?", (f,))
for f, d in TEXT_IN_IMG.items():
    con.execute("INSERT OR IGNORE INTO document_issues VALUES (?,?,?)", (f, "TEXT_IN_IMAGES", d))
for f, d in HARD.items():
    con.execute("INSERT OR IGNORE INTO document_issues VALUES (?,?,?)", (f, "OCR_HARD_CONTENT", d))

# final usability class
con.execute("""UPDATE documents SET text_usability = CASE
    WHEN file_no IN (SELECT file_no FROM document_issues WHERE issue_code='TEXT_LAYER_DEFECTIVE') THEN 'layer defective: re-OCR'
    WHEN text_layer='none' THEN 'no layer: OCR required'
    WHEN text_layer='partial' THEN 'usable layer + OCR image pages'
    ELSE 'usable layer as-is' END""")
con.execute("UPDATE documents SET ocr_needed = CASE WHEN text_usability='usable layer as-is' THEN 0 ELSE 1 END")
con.commit()
for r in con.execute("SELECT text_usability, COUNT(*), SUM(pages) FROM documents GROUP BY 1 ORDER BY 2 DESC"):
    print(r)
print("extraction_tests rows", con.execute("SELECT COUNT(*) FROM extraction_tests").fetchone()[0])
