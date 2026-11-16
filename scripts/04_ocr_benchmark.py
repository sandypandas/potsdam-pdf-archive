#!/usr/bin/env python3
"""Step 3b: benchmark Tesseract against verified born-digital text layers.

Usage: python3 04_ocr_benchmark.py CLASSIFIED_JSONL RAW_DIR OUT_JSONL [N_PAGES] [SEED]
Born-digital pages have a text layer written by the authoring software. After spot
verification against the rendered page (step 4), that layer is used as ground truth,
so Tesseract's character and word error rates can be measured on many pages at once.
Each page is rasterized at 300 and 200 ppi (the two scan resolutions found in the archive).
"""
import json, os, random, re, subprocess, sys, tempfile, unicodedata
from concurrent.futures import ThreadPoolExecutor

recs = [json.loads(l) for l in open(sys.argv[1])]
RAW, OUT = sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 40
SEED = int(sys.argv[5]) if len(sys.argv) > 5 else 20261111

pages = [(r["file_no"], i + 1) for r in recs if r["in_sample"] and r["text_layer"] == "full"
         for i, c in enumerate(r["chars_per_page"]) if c >= 200]
random.Random(SEED).shuffle(pages)
pages = sorted(pages[:N])

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[-]", "", s)          # private-use glyphs (Symbol/Wingdings bullets)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-")
    return " ".join(s.split())

from rapidfuzz.distance import Levenshtein   # pip install rapidfuzz (3.14)

def lev(a, b):
    return Levenshtein.distance(a, b)

def run(job):
    fno, p = job
    pdf = os.path.join(RAW, f"{fno}.pdf")
    ref = subprocess.run(["pdftotext", "-f", str(p), "-l", str(p), "-enc", "UTF-8", pdf, "-"],
                         capture_output=True).stdout.decode("utf-8", "replace")
    ref = norm(ref)
    res = {"file_no": fno, "page": p, "ref_chars": len(ref)}
    for dpi in (300, 200):
        with tempfile.TemporaryDirectory() as td:
            base = os.path.join(td, "pg")
            subprocess.run(["pdftoppm", "-r", str(dpi), "-gray", "-f", str(p), "-l", str(p),
                            "-singlefile", "-png", pdf, base], check=True, capture_output=True)
            hyp = subprocess.run(["tesseract", base + ".png", "-", "-l", "eng", "--oem", "1", "--psm", "3"],
                                 capture_output=True).stdout.decode("utf-8", "replace")
        hyp = norm(hyp)
        os.makedirs(os.path.join(os.path.dirname(OUT), "bench_text"), exist_ok=True)
        open(os.path.join(os.path.dirname(OUT), "bench_text", f"{fno}_p{p}_tess{dpi}.txt"), "w").write(hyp)
        # Order-insensitive comparison of real words only (tokens with a letter or digit, punctuation
        # stripped). Guards against column/reading-order differences and dot leaders.
        from collections import Counter
        words = lambda s: [w.strip(".,;:()[]\"'!?").lower() for w in s.split() if re.search(r"[A-Za-z0-9]", w)]
        rw, hw = words(ref), words(hyp)
        miss = sum((Counter(rw) - Counter(hw)).values())
        extra = sum((Counter(hw) - Counter(rw)).values())
        res[f"cer_{dpi}"] = round(lev(ref, hyp) / max(1, len(ref)), 4)
        res[f"word_miss_{dpi}"] = round(miss / max(1, len(rw)), 4)
        res[f"word_extra_{dpi}"] = round(extra / max(1, len(rw)), 4)
        res["ref_words"] = len(rw)
    open(os.path.join(os.path.dirname(OUT), "bench_text", f"{fno}_p{p}_layer.txt"), "w").write(ref)
    return res

with ThreadPoolExecutor(4) as ex, open(OUT, "w") as fo:
    for r in ex.map(run, pages):
        fo.write(json.dumps(r) + "\n")
print("benchmarked", len(pages))
