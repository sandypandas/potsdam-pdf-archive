#!/usr/bin/env python3
"""Step 3d: detect rotated pages in the image-only PDFs (Tesseract OSD).

Usage: python3 07_orientation_check.py CLASSIFIED_JSONL RAW_DIR OUT_JSONL
Each scanned page is rendered at 150 ppi and passed to `tesseract --psm 0` (orientation and
script detection only). A page counts as rotated when OSD says Rotate != 0 with
orientation confidence >= 2 (Tesseract's documented rule of thumb for a reliable call).
"""
import json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

recs = [json.loads(l) for l in open(sys.argv[1])]
RAW, OUT = sys.argv[2], sys.argv[3]
jobs = [(r["file_no"], p) for r in recs if r["in_sample"] and r["text_chars"] == 0
        for p in range(1, int(r["info"]["Pages"]) + 1)]

def osd(job):
    fno, p = job
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "pg")
        subprocess.run(["pdftoppm", "-r", "150", "-gray", "-f", str(p), "-l", str(p), "-singlefile",
                        "-png", os.path.join(RAW, f"{fno}.pdf"), base], check=True, capture_output=True)
        r = subprocess.run(["tesseract", base + ".png", "-", "--psm", "0"], capture_output=True)
    out = r.stdout.decode() + r.stderr.decode()
    rot = re.search(r"Rotate: (\d+)", out)
    conf = re.search(r"Orientation confidence: ([\d.]+)", out)
    rot = int(rot.group(1)) if rot else None
    conf = float(conf.group(1)) if conf else None
    return {"file_no": fno, "page": p, "rotate": rot, "osd_conf": conf,
            "rotated": bool(rot and conf is not None and conf >= 2)}

with ThreadPoolExecutor(os.cpu_count() or 4) as ex, open(OUT, "w") as fo:
    for res in ex.map(osd, jobs):
        fo.write(json.dumps(res) + "\n")
print("osd pages", len(jobs))
