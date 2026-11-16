#!/usr/bin/env python3
"""Step 4: estimate how many scanned pages need full human correction.

Usage: python3 11_estimate_correction.py OCR_PAGES_JSONL VERIFICATION_CSV
Each verified Tesseract page was drawn from one OCR-confidence band. The share of pages in a band
that came out 'major errors' or 'unusable' is applied to that band's share of all 1,008 scanned
sample pages. Bands hold only 2-3 verified pages each, so the result is a rough estimate.
"""
import csv, json, sys
pages = [json.loads(l) for l in open(sys.argv[1])]
band = lambda c: ">=90" if c >= 90 else "80-90" if c >= 80 else "60-80" if c >= 60 else "<60"
conf = {(p["file_no"], p["page"]): p["mean_conf"] for p in pages}
share = {}
for p in pages:
    share[band(p["mean_conf"])] = share.get(band(p["mean_conf"]), 0) + 1 / len(pages)
fail, n = {}, {}
for r in csv.DictReader(open(sys.argv[2])):
    if r["method"] != "tesseract 300ppi psm3":
        continue
    b = band(conf[(int(r["file"].split(".")[0]), int(r["page"]))])
    n[b] = n.get(b, 0) + 1
    fail[b] = fail.get(b, 0) + (r["result"] in ("major errors", "unusable"))
est = 0
for b in (">=90", "80-90", "60-80", "<60"):
    rate = fail.get(b, 0) / n[b]
    est += rate * share[b]
    print(f"{b:6} share of pages {share[b]:.3f}  verified {n[b]}  failed {fail.get(b,0)}  rate {rate:.2f}")
print(f"estimated share needing full correction: {est:.3f}  (archive-wide: about {est*2424:.0f} of 2,424 scanned pages)")
