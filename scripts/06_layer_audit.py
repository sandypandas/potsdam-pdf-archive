#!/usr/bin/env python3
"""Step 3c: audit born-digital text layers by cross-checking against OCR.

Usage: python3 06_layer_audit.py CLASSIFIED_JSONL RAW_DIR OUT_JSONL [SEED]
Why: a text layer can exist but be wrong (e.g. broken font Unicode maps drop digits).
Neither pdfinfo nor pdffonts detects this. For every sampled file with a text layer,
one page with >= 200 characters is chosen at random (fixed seed). The page's
pdftotext output is compared with Tesseract OCR of the same page rendered at 300 ppi.
  layer_gap  = share of OCR words absent from the layer  (high -> layer missing content)
  ocr_gap    = share of layer words absent from the OCR  (high -> OCR missing content)
  digits_*   = count of tokens containing a digit in each version
Pages with layer_gap > 0.05 or digits_ocr > 2 * digits_layer + 3 are flagged for visual review.
"""
import json, os, random, re, subprocess, sys, tempfile, unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

recs = [json.loads(l) for l in open(sys.argv[1])]
RAW, OUT = sys.argv[2], sys.argv[3]
rng = random.Random(int(sys.argv[4]) if len(sys.argv) > 4 else 20261116)

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[-]", "", s)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-")):
        s = s.replace(a, b)
    return s

def words(s):
    return [w.strip(".,;:()[]\"'!?").lower() for w in s.split() if re.search(r"[A-Za-z0-9]", w)]

jobs = []
for r in recs:
    if r["in_sample"] and r["text_chars"] > 0:
        cands = [i + 1 for i, c in enumerate(r["chars_per_page"]) if c >= 200] or \
                [i + 1 for i, c in enumerate(r["chars_per_page"]) if c > 0]
        jobs.append((r["file_no"], rng.choice(cands)))

def audit(job):
    fno, p = job
    pdf = os.path.join(RAW, f"{fno}.pdf")
    layer = norm(subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-enc", "UTF-8", pdf, "-"],
                                capture_output=True).stdout.decode("utf-8", "replace"))
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "pg")
        subprocess.run(["pdftoppm", "-r", "300", "-gray", "-f", str(p), "-l", str(p), "-singlefile",
                        "-png", pdf, base], check=True, capture_output=True)
        ocr = norm(subprocess.run(["tesseract", base + ".png", "-", "-l", "eng", "--oem", "1", "--psm", "3"],
                                  capture_output=True).stdout.decode("utf-8", "replace"))
    lw, ow = words(layer), words(ocr)
    layer_gap = sum((Counter(ow) - Counter(lw)).values()) / max(1, len(ow))
    ocr_gap = sum((Counter(lw) - Counter(ow)).values()) / max(1, len(lw))
    dl = sum(1 for w in lw if re.search(r"\d", w))
    do = sum(1 for w in ow if re.search(r"\d", w))
    flag = layer_gap > 0.05 or do > 2 * dl + 3
    d = os.path.join(os.path.dirname(OUT), "layer_audit_text")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, f"{fno}_p{p}_layer.txt"), "w").write(layer)
    open(os.path.join(d, f"{fno}_p{p}_tess300.txt"), "w").write(ocr)
    return {"file_no": fno, "page": p, "layer_words": len(lw), "ocr_words": len(ow),
            "layer_gap": round(layer_gap, 4), "ocr_gap": round(ocr_gap, 4),
            "digits_layer": dl, "digits_ocr": do, "flag": flag}

with ThreadPoolExecutor(os.cpu_count() or 4) as ex, open(OUT, "w") as fo:
    for res in ex.map(audit, jobs):
        fo.write(json.dumps(res) + "\n")
print("audited", len(jobs))
