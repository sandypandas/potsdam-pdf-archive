#!/usr/bin/env python3
"""Step 1: profile every PDF with Poppler tools.

Usage: python3 01_profile.py RAW_DIR SAMPLE_JSON OUT_JSONL

For each PDF records: SHA-256, byte size, all pdfinfo fields, XMP presence,
font count (pdffonts), embedded image count (pdfimages -list),
and per-page character counts from pdftotext (used to judge the text layer).
Tools: Poppler 24.02 (pdfinfo, pdffonts, pdfimages, pdftotext), qpdf 11.
"""
import hashlib, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

RAW, SAMPLE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
sample = set(json.load(open(SAMPLE))["sample"])

def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"

def profile(name):
    path = os.path.join(RAW, name)
    num = int(name[:-4])
    rec = {"file_no": num, "filename": name, "in_sample": num in sample,
           "bytes": os.path.getsize(path)}
    with open(path, "rb") as f:
        data = f.read()
    rec["sha256"] = hashlib.sha256(data).hexdigest()
    rec["header"] = data[:8].decode("latin-1", "replace").strip()
    rec["has_eof"] = b"%%EOF" in data[-2048:]

    rc, out, err = run(["pdfinfo", "-isodates", path])
    rec["pdfinfo_rc"] = rc
    rec["pdfinfo_err"] = err.strip()[:500]
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    rec["info"] = info
    rc, out, _ = run(["pdfinfo", "-meta", path])
    rec["has_xmp"] = "<x:xmpmeta" in out or "<rdf:RDF" in out
    rec["xmp_pdfa"] = "pdfaid" in out.lower()

    rc, out, _ = run(["pdffonts", path])
    lines = out.splitlines()[2:] if rc == 0 else []
    rec["font_count"] = len(lines)
    rec["fonts_embedded"] = sum(1 for l in lines if len(l.split()) > 4 and l.split()[-5] == "yes")
    rec["font_names"] = sorted({l.split()[0] for l in lines})[:15]

    rc, out, _ = run(["pdfimages", "-list", path])
    imgs = out.splitlines()[2:] if rc == 0 else []
    rec["image_count"] = len(imgs)
    dpis = []
    for l in imgs:
        p = l.split()
        try:
            dpis.append(int(p[12]))
        except (IndexError, ValueError):
            pass
    rec["image_xppi_max"] = max(dpis) if dpis else None

    pages = int(info.get("Pages", "0") or 0)
    per_page = []
    rc, out, _ = run(["pdftotext", "-layout", "-enc", "UTF-8", path, "-"], timeout=300)
    if rc == 0:
        per_page = [len("".join(pg.split())) for pg in out.split("\f")][:pages or None]
    rec["chars_per_page"] = per_page
    rec["text_chars"] = sum(per_page)
    rec["first_text"] = " ".join(out.split())[:300] if rc == 0 else ""
    return rec

files = sorted(os.listdir(RAW), key=lambda n: int(n[:-4]))
with ThreadPoolExecutor(8) as ex, open(OUT, "w") as fo:
    for rec in ex.map(profile, files):
        fo.write(json.dumps(rec) + "\n")
print("profiled", len(files))
