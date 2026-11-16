# Potsdam PDF Archive: Preservation Assessment

This repository assesses a collection of 718 PDF public records from the Village of Potsdam, New York (meeting minutes, agendas, hearings, reports and forms, mostly dated 2014 to 2023). We profiled every file, drew a random sample of 251, built a SQLite inventory, tested text extraction with Poppler, Tesseract and an LLM, verified a set of pages word by word, and wrote a preservation and governance plan based on what the evidence showed.

**Short version:** the files are structurally sound but poorly described, and one fifth of them are not searchable at all. Embedded titles and dates can't be trusted. Born-digital text layers are almost always exact, but one was silently missing every number. OCR is excellent on plain typed pages and unreliable on tables, money figures, handwriting and pages stored sideways. That last group is about 1 in 4 scanned pages, and it needs a person to check every number.

## Contents

* [The collection and the sample](#the-collection-and-the-sample)
* [Methodology](#methodology)
* [Tools](#tools)
* [Repository structure](#repository-structure)
* [Major findings](#major-findings)
* [Recommendations](#recommendations)
* [How to use this repository](#how-to-use-this-repository)
* [Limitations](#limitations)

## The collection and the sample

| | |
|---|---|
| Files | 718 PDFs, named by number only (`2.pdf` to `1164.pdf`) |
| Pages | 6,078 |
| Size | about 505 MB |
| Source | Shared course folder "pdf-archive" (Google Drive) |

**Sample size.** We used Krejcie and Morgan (1970), with 95% confidence, a margin of error of ±5% and P = 0.5:

s = X²NP(1−P) / (d²(N−1) + X²P(1−P)) = 3.841 × 718 × 0.25 / (0.0025 × 717 + 3.841 × 0.25) = **251**

**Selection.** Simple random sampling without replacement, using Python's `random.sample` with seed **20261111**, so anyone can redraw the same sample. The list is in `data/sample/sample_list.csv` and `data/sample/sample.json`.

Checksums, duplicate detection and the basic metadata profile cover **all 718 files**. The inventory, extraction tests and verification cover the **251-file sample**.

## Methodology

The work followed the five assignment steps. Full commands, parameters and seeds are in [`docs/methodology.md`](docs/methodology.md).

1. **Metadata and structure.** For each file we ran `pdfinfo` (with `-isodates` and `-meta`), `pdffonts`, `pdfimages -list` and `pdftotext`, and computed SHA-256 (`01_profile.py`). Simple, transparent rules then assigned a document type, a content date read from the text, a title-quality class and a text-layer class (`02_classify.py`; rules in [`docs/classification_scheme.md`](docs/classification_scheme.md)).
2. **Inventory.** We loaded everything into SQLite (`05_build_inventory.py`, `sql/schema.sql`; described in [`docs/schema.md`](docs/schema.md)).
3. **Text extraction tests** (`03`, `04`, `06`, `07`, `08`):
   * OCR of all 1,008 pages of the 50 image-only sampled files with Tesseract at 300 ppi, recording word confidence;
   * a benchmark of OCR against 40 born-digital pages with known-correct text, at 300 and 200 ppi;
   * an audit of every text layer: one random page per file, extracted with pdftotext and also OCR'd, with mismatches flagged;
   * an orientation check of every scanned page;
   * an LLM transcription test on two pages where Tesseract failed.
4. **Verification** (`09`, `09b`, `10`, `11`). We proofread 21 extractions from 18 pages word by word against the page image: 7 text layers, 9 OCR pages drawn at random within confidence bands, 2 rotation fixes, and 2 LLM transcriptions. Each was scored for word recall and number recall and classed as accurate, minor errors, major errors or unusable. Verification found a rotation problem the earlier check had missed, so we re-tested every uncertain page at all four orientations.
5. **Preservation and governance plan.** Recommendations limited to the problems the evidence showed ([`docs/Potsdam_Preservation_Governance_Plan.pdf`](docs/Potsdam_Preservation_Governance_Plan.pdf)).

## Tools

| Tool | Version | Used for |
|---|---|---|
| Poppler (`pdfinfo`, `pdffonts`, `pdfimages`, `pdftotext`, `pdftoppm`) | 24.02.0 | Metadata, fonts, images, text layers, rendering pages |
| Tesseract | 5.3.4, `eng`, LSTM (`--oem 1`) | OCR (`--psm 3`), orientation (`--psm 0`), auto-rotate (`--psm 1`) |
| Python 3 | with `rapidfuzz` 3.14, `Pillow`, `openpyxl` 3.1 | Scripts, edit distance, rotation test, exports |
| SQLite 3 | via Python `sqlite3` | Inventory |
| Claude (claude-opus-5-5) | November 2026 | LLM transcription test; verification proofreading |

## Repository structure

```
README.md
data/
  potsdam_inventory.db          SQLite inventory (open with DB Browser for SQLite)
  potsdam_inventory.csv         Final CSV export: one row per sampled file, with its issues and verification results
  tables/                       Every table and view as CSV (documents, fixity for all 718, duplicates, extraction_tests, ...)
  sample/                       The 251-file sample list and seed
docs/
  methodology.md                Step-by-step procedure, commands, parameters, path map
  schema.md                     Database schema description
  classification_scheme.md      Rules for document type, content date, title quality, text usability, page routes, issue codes
  errors_and_uncertainties.md   Errors found, errors in our method, and open uncertainties
  Potsdam_Preservation_Governance_Plan.pdf / .docx   Step 5 plan
results/
  metadata/                     Step 1: profile.jsonl and classified.jsonl (all 718 files), step1_metadata_profile.csv (sample)
  extraction/
    ocr_scans/                  OCR text of all 1,008 scanned sample pages + per-page confidence (ocr_pages.jsonl)
    benchmark/                  OCR vs known text on 40 born-digital pages (300 and 200 ppi)
    layer_audit/                pdftotext vs OCR, one page per text file (201 files)
    orientation/                OSD results and the best-of-four rotation test
    llm/                        LLM transcriptions of 190 p21 and 982 p1, with the page images used
  verification/
    step4_verification_results.csv   Scores for all 21 verified extractions
    extracted/  truth/  img/         What each tool produced, the proofread reference text, and the page images
    step4_side_by_side_sheets.html   Printable sheets for a human reviewer (249 p8, 611 p17, 232 p35)
scripts/                        01 to 11 in run order, plus run_all.sh
sql/
  schema.sql                    Table definitions
  queries.sql                   14 ready-to-run queries
```

The original PDFs aren't included because of their size (about 505 MB). They're in the course's shared "pdf-archive" folder, and every file is identified here by its number and SHA-256 (`data/tables/fixity.csv`).

## Major findings

### Metadata: structure is reliable, description is not

* **Reliable:** page counts, page sizes, PDF version, encryption, tagging (534 of 718 tagged), fonts and image resolution. These come straight from the file.
* **Titles:** 460 of 718 files carry a Title copied from a reused Word template, so the title describes a different document. For example, 544.pdf (June 2017 minutes) is titled with a January 2014 resolution. Another 231 titles are blank, and only 19 are descriptive.
* **Dates:** CreationDate records when the PDF was saved, not when the meeting happened. The median gap in the sample is 16 days. In October 2023, 30 files were batch re-saved on macOS 13.4.1, which replaced their original creation dates.
* **Names:** filenames are bare sequence numbers that carry no date or type, and among 187 dated sample files the numbering runs backward in time 40 times. Author is inconsistent, and Subject is empty in every file but one (where it holds a software string).
* **Format:** none of the 718 files is PDF/A, and 513 have fonts that aren't embedded.
* **Duplicates:** 18 sets of byte-identical files, with 20 redundant copies.

### Text extraction

| Group | Sample | What we found |
|---|---|---|
| Usable text layer | 197 files, 1,002 pages | pdftotext output is exact apart from text inside images |
| Image-only scans | 50 files, 1,008 pages (archive: 140 files, 2,424 pages) | Need OCR. 76% of pages had OCR confidence of 90 or above, and 7% were below 60 |
| Partly image-only | 3 files (43, 47, 863) | Maps and inserts with no text |
| Defective layer | 1 file (885) | Every digit and some letters are missing from italic text |

* **OCR on plain text is very good.** It missed under 1% of words at both 300 and 200 ppi on the 40-page benchmark, and made 1 error in 671 words on the verified scans.
* **55 scanned pages in 9 files are stored sideways.** Tesseract can't read them until they're rotated.

### Verification (Step 4)

| Result | Extractions |
|---|---|
| Accurate | 544 p1, 521 p1, 496 p1, 43 p57 (text layers); 249 p8, 960 p1 (OCR); 190 p21, 982 p1 (LLM) |
| Minor errors | 3 p1, 916 p1 (logo text in images); 249 p12 (OCR, 1 word) |
| Major errors | 885 p5 (text layer: 22 of 22 numbers lost); 611 p17 (budget table: 15 numbers wrong, 1.4% read as 14%); 977 p11 (payables table, columns scrambled) |
| Unusable | 232 p35 (handwriting: $42.13 read as 472,13); 615 p1 (grey halftone: 95% of words lost); 292 p49 (sideways, and still 13 of 38 numbers wrong after rotation: $184,480.77 read as $384,480.77); 190 p21 with Tesseract auto-rotate; 982 p1 with Tesseract; 209 p69 (map) |

**Reliability.** Text layers that pass an OCR cross-check can be used as they are. OCR of plain typed pages needs only spot checks. Tables, financial pages, forms, handwriting and rotated pages need every number checked by a person. That's an estimated **24% of scanned pages**, about 590 of the 2,424 in the archive (`scripts/11_estimate_correction.py`). The LLM transcribed the two hardest pages with no errors (436 words, 145 numbers), so it's a good first pass for that group, but its output still needs human checking. Confidence scores can't be used on their own to decide which pages to skip.

More detail is in [`docs/errors_and_uncertainties.md`](docs/errors_and_uncertainties.md).

## Recommendations

The full plan is in [`docs/Potsdam_Preservation_Governance_Plan.pdf`](docs/Potsdam_Preservation_Governance_Plan.pdf). In brief:

* Keep the 718 originals untouched and read-only as preservation masters, each with its SHA-256.
* Build searchable **PDF/A** access copies beside them, with fonts embedded and pages upright, validated with veraPDF.
* Keep descriptive metadata in the inventory, not in the PDFs. Name access copies `potsdam_YYYY-MM-DD_type_NNNN.pdf` using the date read from the content.
* Route each page by type: keep layers that pass the cross-check, spot-check OCR of plain text, verify every number on tables and financial pages, and describe maps instead of OCR'ing them.
* Keep the lowest-numbered file in each duplicate set, and link the others to it.
* Use 3-2-1 backups, a yearly fixity check and a privacy review before publishing anything.
* Assign clear roles, with the person who corrects text never the one who checks it, and follow a review schedule.

## How to use this repository

* **Browse the data without installing anything:** open `data/potsdam_inventory.csv` or any file in `data/tables/` in Excel or Google Sheets.
* **Query the database:** open `data/potsdam_inventory.db` in [DB Browser for SQLite](https://sqlitebrowser.org/), or run `sqlite3 data/potsdam_inventory.db < sql/queries.sql`.
* **Reproduce the verification scores** (no PDFs needed): `python3 scripts/10_score_verification.py results/verification <copy of the db> out.csv`.
* **Re-run everything:** put the 718 PDFs in `raw/` and run `bash scripts/run_all.sh`.

## Limitations

* Verification was carried out by Claude (an AI model), proofreading against page images. A human reviewer should confirm at least the three side-by-side sheets.
* Only 18 pages were fully verified, so the 24% estimate is a rough guide.
* The layer audit checked one page per file.
* Document types and content dates are rule-based, and 140 scanned files can't be typed until they're OCR'd.
* Retention periods in the plan still need to be confirmed against the NYS Archives LGS-1 schedule.
* **Personal data:** the extracted text repeats what the public records contain. In this repository, email addresses at personal webmail domains, and the private owners' phone numbers in the rental listings 1078.pdf and 1079.pdf, are replaced with `[redacted]`. Work and government contact details are left as published.

## Credits

Prepared by Sandipan (Sandy) Das for a course assignment at Iowa State University, November 2026.
