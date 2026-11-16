#!/usr/bin/env python3
"""Step 4 follow-up: settle page orientation where Tesseract OSD was uncertain.

Usage: python3 09_rotation_bestof4.py ORIENTATION_JSONL RAW_DIR OUT_JSONL
Verification showed OSD at 150 ppi with a confidence cut-off of 2 missed truly rotated pages
(e.g. 292.pdf p.49, OSD conf 0.46). For every page where OSD returned no result or a
low-confidence rotation, the page is rendered at 150 ppi, OCR'd at 0/90/180/270 degrees
(tesseract --psm 3), and the angle with the most words at confidence >= 80 wins.
"""
import json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

A = [json.loads(l) for l in open(sys.argv[1])]
RAW, OUT = sys.argv[2], sys.argv[3]
jobs = [(a["file_no"], a["page"]) for a in A if a["rotate"] is None or (a["rotate"] and not a["rotated"])]

def good_words(png):
    tsv = subprocess.run(["tesseract", png, "-", "--oem", "1", "--psm", "3", "tsv"],
                         capture_output=True).stdout.decode("utf-8", "replace")
    n = 0
    for line in tsv.splitlines()[1:]:
        f = line.split("\t")
        if len(f) == 12 and f[11].strip() and float(f[10]) >= 80:
            n += 1
    return n

def best(job):
    fno, p = job
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "pg")
        subprocess.run(["pdftoppm", "-r", "150", "-gray", "-f", str(p), "-l", str(p), "-singlefile",
                        "-png", os.path.join(RAW, f"{fno}.pdf"), base], check=True, capture_output=True)
        im = Image.open(base + ".png")
        scores = {}
        for ang in (0, 90, 180, 270):
            path = os.path.join(td, f"r{ang}.png")
            im.rotate(-ang, expand=True).save(path)      # rotate clockwise by ang
            scores[ang] = good_words(path)
    win = max(scores, key=scores.get)
    return {"file_no": fno, "page": p, "scores": scores, "best_rotation": win,
            "rotated": win != 0 and scores[win] >= 2 * max(1, scores[0])}

with ThreadPoolExecutor(os.cpu_count() or 4) as ex, open(OUT, "w") as fo:
    for r in ex.map(best, jobs):
        fo.write(json.dumps(r) + "\n")
print("checked", len(jobs))
