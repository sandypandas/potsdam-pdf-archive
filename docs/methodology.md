# Potsdam PDF archive: assessment procedure (Steps 1 to 4)

All commands were run on Linux in November 2026. Every script takes its inputs as arguments and uses a fixed random seed, so a second run on the same files gives the same results.

## Tools and versions

| Tool | Version | Used for |
|---|---|---|
| Poppler `pdfinfo` | 24.02.0 | Document metadata (`-isodates`), XMP (`-meta`) |
| Poppler `pdffonts` | 24.02.0 | Font list and embedding |
| Poppler `pdfimages -list` | 24.02.0 | Embedded images and scan resolution (ppi) |
| Poppler `pdftotext` | 24.02.0 | Text-layer extraction (`-layout`, `-enc UTF-8`, per page with `-f/-l`) |
| Poppler `pdftoppm` | 24.02.0 | Rendering pages to PNG for OCR and visual checks |
| Tesseract | 5.3.4 | OCR (`-l eng --oem 1` LSTM engine), orientation detection (`--psm 0`) |
| Python | 3 (standard library + `rapidfuzz` 3.14, `openpyxl` 3.1) | Orchestration, SHA-256, edit distance, SQLite, Excel export |
| SQLite | 3 (via Python `sqlite3`) | Inventory database |
| Claude (claude-opus-5-5) | Nov 2026 | LLM transcription test on two difficult pages |

## Sample

* Population: 718 PDFs in the shared `pdf-archive` folder (N after removing two listing duplicates).
* Sample size: Krejcie & Morgan (1970), 95% confidence, d = .05, P = .50, which gives s = 251.
* Selection: simple random sampling without replacement, Python `random.sample`, seed 20261111 (`out/sample.json`).

## Step 1: metadata and structure (`01_profile.py`, `02_classify.py`)

1. `01_profile.py raw out/sample.json out/profile.jsonl` runs `pdfinfo`, `pdfinfo -meta`, `pdffonts`, `pdfimages -list` and `pdftotext -layout` on every file, counts characters per page, and computes SHA-256.
2. `02_classify.py out/profile.jsonl out/classified.jsonl` applies transparent rules:
   * document type from the opening text (e.g. starts with "AGENDA", contains "EXECUTIVE SESSION ... WAS HELD");
   * content date = first "Month D, YYYY" in the first 600 characters;
   * title quality: missing / filename / reused in 5 or more files (template carry-over) / auto-filled / descriptive;
   * text layer: none if the whole file has 0 extractable characters;
   * exact duplicates = identical SHA-256.

## Step 2: inventory (`schema.sql`, `05_build_inventory.py`)

`05_build_inventory.py sql/schema.sql out/classified.jsonl potsdam_inventory.db` creates the tables and loads 251 documents, 718 fixity rows, duplicate groups and issue records.

## Step 3: text extraction tests

Decision rule used to sort files: **a text layer counts as usable only if it exists and survives the OCR cross-check (3c).**

### 3a. OCR of every image-only page (`03_ocr_scans.py`)
For each of the 50 files with no text layer, every page (1,008 pages) was processed as follows:

```
pdftoppm -r 300 -gray -f P -l P -singlefile -png FILE.pdf page
tesseract page.png - -l eng --oem 1 --psm 3          # text
tesseract page.png - -l eng --oem 1 --psm 3 tsv      # word confidences
```
Output: `out/ocr/<file>_p<page>.txt` and `out/ocr/ocr_pages.jsonl` (mean word confidence, share of words under 60).

### 3b. OCR accuracy benchmark (`04_ocr_benchmark.py`, seed 20261111, 40 pages)
Born-digital pages (at least 200 characters) have a known-correct text layer. Six of these layers were checked by eye against the rendered page (Step 4). Each benchmark page was rendered at **300 and 200 ppi** (the two scan resolutions in the archive) and OCR'd. Tesseract output was then compared with the layer:

* **CER**: Levenshtein distance divided by reference length (sensitive to reading order and layout);
* **word miss rate**: share of reference words (tokens with a letter or digit, punctuation stripped, order-insensitive) absent from the OCR. This is the main accuracy measure.

### 3c. Text-layer audit (`06_layer_audit.py`, seed 20261116)
For **every** one of the 201 files with a text layer, one random page (at least 200 characters) was extracted with `pdftotext` and also OCR'd at 300 ppi. A page was flagged when more than 5% of OCR words were missing from the layer, or when the OCR had more than 2 x (layer digits) + 3 numeric tokens. All 4 flagged files were then inspected by eye.

### 3d. Orientation check (`07_orientation_check.py`)
Every scanned page was rendered at 150 ppi and checked with `tesseract --psm 0`. A page counts as rotated when Rotate != 0 with orientation confidence of at least 2. A rotated page was then re-OCR'd with `--psm 1` (automatic orientation and layout).

### 3e. LLM transcription test
Two pages where Tesseract failed were read by Claude from rendered page images: 190.pdf p.21 (a sideways spreadsheet, rotated before reading) and 982.pdf p.1 (a colour-coded calendar). The instruction was to transcribe faithfully, keep table structure, and keep the source's own errors. Outputs: `verify/s3/llm190_p21.md` and `verify/s3/llm982_p1.md`.

### 3f. Recording (`08_load_extraction.py`)
All results are written to `extraction_tests` (1,292 rows), and each document gets a final `text_usability` class.

## Step 4: verification (`09_rotation_bestof4.py`, `10_score_verification.py`)

### Verification set (21 page-extractions from 18 pages)
* **Text layer (pdftotext), 7 pages:** 544 p1, 521 p1, 496 p1, 3 p1, 43 p57, 916 p1 (born-digital, varied types) and 885 p5 (the file flagged in 3c).
* **Tesseract on scans, 9 pages:** drawn at random (seed 20261116) within OCR-confidence bands: 3 pages >= 90, 2 at 80-90, 2 at 60-80, 2 < 60 (pages already known to be rotated were excluded from the draw). Drawn: 249 p8, 249 p12, 960 p1, 611 p17, 977 p11, 232 p35, 615 p1, 292 p49, 209 p69.
* **Rotation fix, 2 extractions:** 292 p49 OCR'd again after rotating upright; 190 p21 with `--psm 1`.
* **LLM, 2 pages:** 190 p21 (top half) and 982 p1 from Step 3e.

### How each page was verified
1. The page was rendered with `pdftoppm` (110-200 ppi; 300 ppi crops for small print).
2. The extracted text was proofread against the image **word by word, for the whole page**, and every error was corrected, giving a reference ("truth") file in `verify/s4/truth/`. Source errors (e.g. "tax roles", "Municpal", "Execution Session") were kept as written. Handwritten signatures are recorded as `[signature]`.
3. For the LLM pages, the extractor and the proofreader would be the same model, so each value was instead re-checked independently in zoomed 300/200 ppi crops of the original, with special attention to every value where the LLM and Tesseract disagreed.
4. `10_score_verification.py` compares each extraction with its reference (order-insensitive):
   * word recall = share of reference words present in the extraction;
   * number recall = share of reference tokens containing a digit that appear exactly in the extraction;
   * result = accurate (recall >= 99.5% and all numbers right), minor errors (>= 97% and numbers >= 95%), major errors (>= 80%), unusable (< 80%). Two pages (3 p1, 916 p1) were manually reclassified from major to minor because their only missing words are logo text inside images; this override is written in the script and noted in the results.
5. The map page 209 p69 was judged unusable by inspection and not word-scored.

### Rotation re-check
Verification found a sideways page (292 p49) that Tesseract OSD had detected only at confidence 0.46, below the cut-off of 2. `09_rotation_bestof4.py` re-tested the 44 pages where OSD was absent or low-confidence by OCR'ing each at 0/90/180/270 degrees and counting words with confidence >= 80. A page counted as rotated when another angle gave at least twice the words of 0 degrees. This raised the count from 19 to **55 rotated pages in 9 files**.

### Limits
Verification was done by Claude, not a person. Three printable side-by-side sheets (`step4_side_by_side_sheets.html`) let a human reviewer confirm a subset. Per-band samples are small (2-3 pages each), so the archive-wide estimates are indicative only.

## Re-running everything

Run `bash scripts/run_all.sh` from the repository root, with the 718 PDFs in `raw/`. It runs scripts 01 to 11 in order, including `09b_apply_rotation_and_findings.py`, which writes the best-of-four rotation results and the halftone and handwriting findings to the database. The output reproduces `data/potsdam_inventory.db`.

Approximate run time on 4 CPU cores: profiling 30 s; full OCR of 1,008 pages about 45 min; benchmark 1 min; layer audit 2.5 min; orientation 9 min.

## Paths in this document and in the database

The work was done in a working folder (`raw/`, `out/`, `verify/`). Paths stored in `extraction_tests.output_path` use that layout. In this repository the same files are here:

| Working path | Repository path |
|---|---|
| `out/profile.jsonl`, `out/classified.jsonl` | `results/metadata/` |
| `out/ocr/` | `results/extraction/ocr_scans/` |
| `out/ocr_benchmark.jsonl`, `out/bench_text/` | `results/extraction/benchmark/` (text in `text/`) |
| `out/layer_audit.jsonl`, `out/layer_audit_text/` | `results/extraction/layer_audit/` (text in `text/`) |
| `out/orientation.jsonl`, `out/rotation_bestof4.jsonl` | `results/extraction/orientation/` |
| `verify/s3/` (LLM test) | `results/extraction/llm/` |
| `verify/s4/` | `results/verification/` |
| `scripts/schema.sql` | `sql/schema.sql` |
