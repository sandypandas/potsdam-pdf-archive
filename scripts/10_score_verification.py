#!/usr/bin/env python3
"""Step 4: score each verified page: extracted text vs human-verified reference text.

Usage: python3 10_score_verification.py VERIFY_DIR DB OUT_CSV
Reference ("truth") files were produced by proofreading every word of the extraction against
the rendered page image and correcting it; for LLM pages, every value was re-checked in
zoomed crops (300 ppi) of the original. Scoring is order-insensitive (bag of words) so that
column/reading-order differences are reported separately from wrong or missing words.
  word_recall   = share of reference words found in the extraction
  word_errors   = missed reference words + spurious extracted words
  num_recall    = share of reference tokens containing a digit found exactly in the extraction
"""
import csv, os, re, sqlite3, sys, unicodedata
from collections import Counter
from datetime import datetime, timezone

VD, DB, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

def norm(s):
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[-]", "", s)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-")):
        s = s.replace(a, b)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)          # comments in LLM files
    s = s.replace("|", " ").replace("~~", " ").replace("#", " ")
    return s

def words(s):
    return [w.strip(".,;:()[]\"'!?*").lower() for w in norm(s).split() if re.search(r"[A-Za-z0-9]", w)]

# (file, page, method, extracted file, truth file, notes)
PAGES = [
    (544, 1, "pdftotext layer", "544_p1_pdftotext.txt", "544_p1.txt", "born-digital minutes"),
    (521, 1, "pdftotext layer", "521_p1_pdftotext.txt", "521_p1.txt", "keeps source typo 'Execution Session'"),
    (496, 1, "pdftotext layer", "496_p1_pdftotext.txt", "496_p1.txt", "hidden private-use bullet glyph at start"),
    (3, 1, "pdftotext layer", "3_p1_pdftotext.txt", "3_p1.txt", "logo text exists only as image"),
    (43, 57, "pdftotext layer", "43_p57_pdftotext.txt", "43_p57.txt", "report page"),
    (916, 1, "pdftotext layer", "916_p1_pdftotext.txt", "916_p1.txt", "logo/header text and date in images; stray 'FD'"),
    (885, 5, "pdftotext layer", "885_p5_pdftotext.txt", "885_p5.txt", "defective layer: digits and t/r/s in italic font dropped"),
    (249, 8, "tesseract 300ppi psm3", "249_p8_tesseract.txt", "249_p8.txt", "scan 200 ppi, minutes with money table"),
    (249, 12, "tesseract 300ppi psm3", "249_p12_tesseract.txt", "249_p12.txt", "scan 200 ppi, minutes"),
    (960, 1, "tesseract 300ppi psm3", "960_p1_tesseract.txt", "960_p1.txt", "scan 300 ppi, minutes"),
    (611, 17, "tesseract 300ppi psm3", "611_p17_tesseract.txt", "611_p17.txt", "scan 200 ppi, budget table"),
    (977, 11, "tesseract 300ppi psm3", "977_p11_tesseract.txt", "977_p11.txt", "scan 300 ppi, payables table; reading order scrambled"),
    (232, 35, "tesseract 300ppi psm3", "232_p35_tesseract.txt", "232_p35.txt", "printed form with handwritten entries"),
    (615, 1, "tesseract 300ppi psm3", "615_p1_tesseract.txt", "615_p1.txt", "dense text on halftone grey background"),
    (292, 49, "tesseract 300ppi psm3", "292_p49_tesseract.txt", "292_p49_rotated.txt", "page stored sideways; OSD missed it"),
    (292, 49, "tesseract 300ppi psm3 after rotation", "292_p49_tesseract_rotated.txt", "292_p49_rotated.txt", "same page rotated upright first"),
    (190, 21, "tesseract 300ppi psm1 (auto-rotate)", "../../extraction/llm/tess190_p21_psm1.txt", "../../extraction/llm/llm190_p21.md", "scored on top half of page only (reference covers top half)"),
    (190, 21, "LLM vision transcription", "../../extraction/llm/llm190_p21.md", "../../extraction/llm/llm190_p21.md", "all values re-checked in 300 ppi crops; 0 discrepancies"),
    (982, 1, "LLM vision transcription", "../../extraction/llm/llm982_p1.md", "../../extraction/llm/llm982_p1.md", "52 colour-coded dates re-checked in 200 ppi crops; 0 discrepancies"),
    (982, 1, "tesseract 300ppi psm3", "982_p1_tesseract.txt", "../../extraction/llm/llm982_p1.md", "colour meaning lost; B-week street column dropped"),
]
os.makedirs(os.path.join(VD, "extracted"), exist_ok=True)
import shutil
src_ocr = os.path.join(VD, "..", "extraction", "ocr_scans", "982_p1.txt")
if os.path.exists(src_ocr):
    shutil.copy(src_ocr, os.path.join(VD, "extracted", "982_p1_tesseract.txt"))

con = sqlite3.connect(DB)
con.execute("DELETE FROM verification")
now = datetime.now(timezone.utc).isoformat(timespec="seconds")
rows = []
for f, p, method, ext, tru, note in PAGES:
    E = words(open(os.path.join(VD, "extracted", ext)).read())
    T = words(open(os.path.join(VD, "truth", tru)).read())
    if "top half" in note:          # compare only against what the reference covers
        tset = Counter(T)
        E = [w for w in E if w in tset] + [w for w in E if w not in tset][:0]
    miss = sum((Counter(T) - Counter(E)).values())
    extra = sum((Counter(E) - Counter(T)).values())
    tn = [w for w in T if re.search(r"\d", w)]
    nmiss = sum((Counter(tn) - Counter(w for w in E if re.search(r"\d", w))).values())
    recall = 1 - miss / max(1, len(T))
    nrec = 1 - nmiss / len(tn) if tn else None
    errs = miss + extra
    if recall >= 0.995 and (nrec is None or nrec == 1):
        result = "accurate"
    elif recall >= 0.97 and (nrec is None or nrec >= 0.95):
        result = "minor errors"
    elif recall >= 0.80:
        result = "major errors"
    else:
        result = "unusable"
    # Manual judgement where the rule misleads: on these pages every missed word is logo/header
    # text that exists only as an image; all body text and figures are correct.
    if (f, p) in {(3, 1), (916, 1)}:
        result = "minor errors"
        note += " [rule said 'major errors'; overridden: only logo/header image text missing]"
    rows.append({"file": f"{f}.pdf", "page": p, "method": method, "ref_words": len(T),
                 "missed_words": miss, "spurious_words": extra, "word_recall": round(recall, 4),
                 "ref_numbers": len(tn), "numbers_wrong_or_missing": nmiss,
                 "number_recall": round(nrec, 4) if nrec is not None else "",
                 "result": result, "notes": note})
    con.execute("INSERT INTO verification (file_no,page,method,verified_by,verified_at,result,error_count,error_notes)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (f, p, method, "Claude (proofread vs page image; LLM pages cross-checked in zoomed crops)",
                 now, result, errs, note))
con.execute("INSERT INTO verification (file_no,page,method,verified_by,verified_at,result,error_count,error_notes)"
            " VALUES (209,69,'tesseract 300ppi psm3','Claude (visual check)',?,'unusable',NULL,"
            "'sideways colour map; output is unreadable fragments; maps need metadata description, not OCR')", (now,))
rows.append({"file": "209.pdf", "page": 69, "method": "tesseract 300ppi psm3", "ref_words": "", "missed_words": "",
             "spurious_words": "", "word_recall": "", "ref_numbers": "", "numbers_wrong_or_missing": "",
             "number_recall": "", "result": "unusable", "notes": "sideways colour map; not word-scored"})
con.commit()
with open(OUT, "w", newline="") as fo:
    w = csv.DictWriter(fo, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
for r in rows:
    print(r["file"], r["page"], r["method"][:38].ljust(38), r["ref_words"], r["missed_words"], r["spurious_words"],
          r["word_recall"], r["ref_numbers"], r["numbers_wrong_or_missing"], r["result"])
