# Classification scheme

We used four classification schemes: document type, title quality, text usability, and issue codes. The rules are simple enough to check by hand and are applied by `scripts/02_classify.py` and `scripts/08_load_extraction.py`. Some files had to be classified by a person, and those are noted in `documents.notes`.

## 1. Document type

The rules read the first few hundred characters of extracted text, after stripping leading symbols (six agendas begin with a hidden private-use glyph). The first matching rule wins:

| Order | Rule (on the upper-cased opening text) | Type | Archive (718) | Sample (251) |
|---|---|---|---|---|
| 0 | No extractable text at all | unknown (no text layer) | 140 | 50 |
| 1 | Starts with AGENDA and has PUBLIC HEARING in the first 40 characters | agenda - public hearing | 56 | 17 |
| 2 | Starts with AGENDA | agenda - board meeting | 135 | 46 |
| 3 | EXECUTIVE SESSION in first 120 and WAS HELD in first 200 | minutes - executive session | 73 | 26 |
| 4 | PUBLIC HEARING in first 120 and WAS HELD in first 200 | minutes - public hearing | 59 | 28 |
| 5 | MEETING in first 120 and WAS HELD in first 200 | minutes - board meeting | 152 | 56 |
| 6 | APPLICATION in first 200 or FORM in first 80 | application / form | 22 | 11 |
| 7 | NOTICE in first 150 | public notice | 5 | 1 |
| 8 | REPORT, PLAN, TABLE OF CONTENTS or STUDY anywhere in the opening | report / plan | 32 | 8 |
| 9 | Nothing matched | other | 44 | 8 |

Each type belongs to a records series (`doc_types.series`): Board of Trustees minutes, Board of Trustees agendas, forms and applications, reports and plans, notices, or unclassified. In the preservation plan these become short codes (`minutes_board`, `agenda_hearing`, ...), and each code still needs to be matched to the NYS Archives LGS-1 retention schedule.

**Known limits.** "unknown" covers 140 scanned files whose type can only be read after OCR. Several of the 50 sampled scans turned out to be minutes, budgets and reports once OCR'd. "other" needs a person to sort. The rules don't separate the Village Board from planning or zoning boards, and 916.pdf (a New York State fact sheet) is typed as a report even though it isn't a Village record.

## 2. Content date

The content date is the first `Month D, YYYY` in the first 600 characters of text, stored as ISO `YYYY-MM-DD`. The embedded CreationDate is **not** used for this, because it records when the PDF was saved (median 16 days after the meeting in the sample, and years later for files re-saved in October 2023). 14 sampled files with text have no readable date.

## 3. Title quality

| Class | Rule | Archive | Sample |
|---|---|---|---|
| missing | Title field empty | 231 | 74 |
| reused across many files (template carry-over) | Same Title appears in 5 or more files | 460 | 167 |
| filename or software string | Ends in .doc/.docx/.pub/.pdf/.xls or starts with "Microsoft" | 5 | 3 |
| auto-filled from first line | Title equals the start of the text | 3 | 2 |
| descriptive | Anything else, checked by eye | 19 | 5 |

## 4. Text usability (Step 3)

| Class | Meaning | Files | Pages |
|---|---|---|---|
| usable layer as-is | Text layer present and passed the OCR cross-check | 197 | 1,002 |
| no layer: OCR required | Image-only scan | 50 | 1,008 |
| usable layer + OCR image pages | Born-digital file with some image-only pages (maps, inserts) | 3 | (43, 47, 863) |
| layer defective: re-OCR | Layer exists but drops characters (885.pdf drops all digits) | 1 | |

## 5. Page routes (Step 4 and the plan)

Accuracy depended on the kind of page, so the plan sends each page down one of six routes:

| Route | Evidence from verification | Method | Human checking |
|---|---|---|---|
| Born-digital, layer passes cross-check | 6 of 6 layers accurate | keep pdftotext layer | none beyond the automated cross-check |
| Born-digital, layer fails cross-check | 885 lost 22 of 22 numbers | replace with OCR | full number check |
| Plain typed scans | 1 error in 671 words | Tesseract 300 ppi | 5% spot check |
| Tables, budgets, forms | 611: 15 of 190 numbers wrong; 977 order scrambled | LLM or OCR | every number checked |
| Handwriting, halftone backgrounds | 232 and 615 unusable | manual or LLM transcription | full proofread |
| Maps and graphics | 209 p69 unusable | no OCR; written description | description reviewed |

Before OCR, every scanned page gets a best-of-four rotation test (`09_rotation_bestof4.py`).

## 6. Issue codes

There are 22 issue codes in `issue_types`, grouped by category with a severity. The counts for the sample are in `data/tables/v_issue_summary.csv`. The most common are NOT_PDFA (251), FONTS_NOT_EMBEDDED (181), TITLE_TEMPLATE (167), TITLE_MISSING (74) and NO_TEXT_LAYER (50).
