#!/usr/bin/env python3
"""Step 3a: OCR every page of every image-only sampled PDF.

Usage: python3 03_ocr_scans.py CLASSIFIED_JSONL RAW_DIR OUT_DIR
Procedure per page: pdftoppm -r 300 -gray -> PNG; tesseract 5.3.4 (eng, --oem 1 LSTM,
--psm 3 auto layout) -> plain text plus TSV word confidences.
Writes OUT_DIR/<file>_p<page>.txt and ocr_pages.jsonl with mean word confidence.
"""
import json, os, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

recs = [json.loads(l) for l in open(sys.argv[1])]
RAW, OUT = sys.argv[2], sys.argv[3]
os.makedirs(OUT, exist_ok=True)
jobs = [(r["file_no"], p) for r in recs if r["in_sample"] and r["text_chars"] == 0
        for p in range(1, int(r["info"]["Pages"]) + 1)]

def ocr(job):
    fno, p = job
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "pg")
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-f", str(p), "-l", str(p), "-singlefile",
                        "-png", os.path.join(RAW, f"{fno}.pdf"), base], check=True, capture_output=True)
        png = base + ".png"
        txt = subprocess.run(["tesseract", png, "-", "-l", "eng", "--oem", "1", "--psm", "3"],
                             capture_output=True).stdout.decode("utf-8", "replace")
        tsv = subprocess.run(["tesseract", png, "-", "-l", "eng", "--oem", "1", "--psm", "3", "tsv"],
                             capture_output=True).stdout.decode("utf-8", "replace")
    confs = []
    for line in tsv.splitlines()[1:]:
        f = line.split("\t")
        if len(f) == 12 and f[11].strip():
            try:
                c = float(f[10])
                if c >= 0:
                    confs.append(c)
            except ValueError:
                pass
    open(os.path.join(OUT, f"{fno}_p{p}.txt"), "w").write(txt)
    return {"file_no": fno, "page": p, "words": len(confs),
            "mean_conf": round(sum(confs) / len(confs), 1) if confs else None,
            "low_conf_share": round(sum(c < 60 for c in confs) / len(confs), 3) if confs else None,
            "chars": len("".join(txt.split()))}

with ThreadPoolExecutor(os.cpu_count() or 4) as ex, open(os.path.join(OUT, "ocr_pages.jsonl"), "w") as fo:
    for res in ex.map(ocr, jobs):
        fo.write(json.dumps(res) + "\n")
print("ocr pages", len(jobs))
