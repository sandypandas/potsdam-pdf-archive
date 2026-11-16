# Important errors and uncertainties

This file lists the errors we found in the archive's text, the errors and limits in our own method, and what is still uncertain. Full numbers are in `results/verification/step4_verification_results.csv`.

## A. Errors found in the extracted text

### Text layers (pdftotext)

* **885.pdf has a silently broken text layer.** In italic headings it drops every digit and the letters t, r and s. On the verified page, 22 of 22 numbers were missing ("founded in 1806" becomes "founded in"). The file looks fine and is searchable, so the only way to catch it is an OCR cross-check. Our audit of one page per text file found it.
* **Text that only exists as an image is invisible to pdftotext.** Logos and headers on 3.pdf and 916.pdf (including 916's date) are missing. The survey charts in 889.pdf carry their labels only as images. Map pages in 43, 47 and 863 have no text at all.
* Born-digital layers were otherwise exact: 4 of 6 verified pages had zero errors, and the other two missed only image text.

### OCR (Tesseract 5.3.4)

| Page | Problem | Example |
|---|---|---|
| 611 p17 (budget table) | 15 of 190 numbers wrong | 1.4% read as 14% |
| 977 p11 (payables table) | Columns read in the wrong order; 3 of 29 numbers wrong | Amounts separated from the payees |
| 232 p35 (form with handwriting) | Handwriting unreadable; 4 of 4 numbers wrong | $42.13 read as 472,13 |
| 615 p1 (text on grey halftone) | 95% of words lost | 870 of 912 words missing |
| 292 p49 (stored sideways) | Unreadable until rotated; still 13 of 38 numbers wrong after rotation | $184,480.77 read as $384,480.77 |
| 190 p21 (sideways spreadsheet, psm 1 auto-rotate) | 33 of 91 numbers wrong | |
| 982 p1 (colour-coded calendar) | Colour meaning lost; the whole B-week street column dropped | |
| 209 p69 (colour map) | Fragments only | Not word-scored |

On plain typed pages OCR was very good: 1 error in 671 words across 249 p8, 249 p12 and 960 p1. The 40-page benchmark against known-correct layers missed 0.87% of words at 300 ppi and 0.94% at 200 ppi.

### LLM transcription (Claude)

On the two hardest pages (190 p21 and 982 p1), the LLM transcription had 0 errors in 436 words and 145 numbers. See the uncertainties below for why this needs care.

## B. Errors in our own method (found and fixed)

* **Rotation was under-counted at first.** Tesseract's orientation check with a confidence cut-off of 2 found 19 rotated pages. Verification then turned up a sideways page (292 p49) that it had detected at confidence 0.46. A best-of-four test (OCR at 0/90/180/270 degrees) raised the count to **55 rotated pages in 9 files**.
* **The type rules missed 6 agendas** that start with a hidden glyph. We fixed this by stripping leading symbols, which gives 46 agendas in the sample.
* **The first benchmark metric counted dot leaders ("......") as words.** It was changed to count only tokens with a letter or digit, and the benchmark was re-run.
* **The scoring rule misclassified two pages.** 3 p1 and 916 p1 came out as "major errors" only because logo text inside images was missing. We overrode them to "minor errors" by hand. The override is written in `10_score_verification.py`.
* Re-saved files: an early count said 13 sampled files were batch re-saved; the correct figure is 12 (30 archive-wide whose CreationDate was overwritten in October 2023, plus 2.pdf, re-saved but with its original CreationDate kept).

## C. Uncertainties

* **Verification was done by Claude, not a person.** Each page was proofread word by word against the page image. For the LLM pages the same model both extracted and checked, so every value was re-checked in zoomed crops, with extra attention where the LLM and Tesseract disagreed. A human reviewer should still confirm at least the three side-by-side sheets in `results/verification/step4_side_by_side_sheets.html`.
* **Small verified sample.** 18 pages (21 extractions) were fully verified. Each OCR-confidence band has only 2 or 3 pages. The estimate that about 24% of scanned pages (roughly 590 of 2,424 archive-wide) need full correction comes from `scripts/11_estimate_correction.py`. It assumes every page under confidence 90 fails, and every page at 90 or above passes, as happened in the sample. It should be treated as a rough guide.
* **Confidence is not a safe filter on its own.** In the sample, every page under 90 failed, but no table page at 90 or above was verified, and 611 p17 at 86.9 looked readable while carrying 15 wrong numbers. The plan therefore routes by page type, not by confidence.
* **Layer audit covered one page per file.** A defect on other pages of a born-digital file could be missed. 885's defect spans pages 5 to 25 and was caught. Shorter defects might not be.
* **Content dates and types are rule-based.** A rule can pick up the wrong date (for example a date quoted in the text). The 140 scanned files have no type until OCR.
* **Archive-wide figures for scans** (140 files, 2,424 pages) come from the full profile of all 718 files. Everything about OCR quality comes from the 50 sampled scans.
* **Retention periods** in the plan are marked "confirm in LGS-1". We didn't look up each record type in the schedule.
* **Personal data in derived text.** The source PDFs are public records, and our extracted text repeats what they contain. In this repository, email addresses at personal webmail domains and the private owners' phone numbers in the rental listings 1078.pdf and 1079.pdf are replaced with `[redacted]` (see the README).
