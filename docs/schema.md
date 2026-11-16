# Database schema

The inventory is a single SQLite 3 file, `data/potsdam_inventory.db`. The schema is in `sql/schema.sql`, and three columns were added later by `scripts/08_load_extraction.py` (noted below). Every table is also exported as CSV in `data/tables/`, so you can read the data without SQLite.

The database has two scopes:

* **The sample (251 files).** `documents` and the tables that hang off it describe only the randomly sampled files.
* **The whole archive (718 files).** `fixity`, `duplicate_groups` and `duplicate_members` cover every file, because checksums and duplicate detection are cheap and useful for the entire collection.

## How the tables relate

```
doc_types ──< documents >── duplicate_groups ──< duplicate_members >── fixity (all 718)
                 │
                 ├──< document_issues >── issue_types
                 ├──< extraction_tests
                 └──< verification
```

`file_no` (the number in the original filename, e.g. `544` for `544.pdf`) is the key that links everything.

## Tables

| Table | Rows | One row per | What it holds |
|---|---|---|---|
| `documents` | 251 | sampled file | Embedded metadata as found (pdfinfo), structure (pages, fonts, images, tagging, PDF/A), text layer status, our derived fields (doc type, content date, title quality, proposed filename), SHA-256, notes |
| `doc_types` | 10 | document type | Controlled list of types and the records series each belongs to (see `classification_scheme.md`) |
| `issue_types` | 22 | issue | Controlled list of problems, each with a category (metadata, text, format, integrity, identity) and a severity |
| `document_issues` | 919 | file + issue | Which issues each sampled file has, with a detail note |
| `fixity` | 718 | archive file | SHA-256, size, whether the file is in the sample, when and with what tool the hash was computed |
| `duplicate_groups` | 18 | set of identical files | The shared SHA-256, number of copies, and which copy to keep (lowest number) |
| `duplicate_members` | 38 | file in a duplicate set | Links each file to its group |
| `extraction_tests` | 1,292 | page + method | Every text-extraction test: full OCR of scanned pages, the OCR benchmark, the text-layer audit, rotation and LLM tests. Holds confidence, error rates, the path to the output text and notes |
| `verification` | 21 | page + method | Step 4 results: who verified, when, the result class (accurate, minor errors, major errors, unusable), error count and notes |

## Key fields in `documents`

| Field | Meaning |
|---|---|
| `filename`, `proposed_filename` | Name as received, and the standard name we recommend (`potsdam_YYYY-MM-DD_type_NNNN.pdf`) |
| `doc_type` | Type assigned by the rules in `02_classify.py` |
| `content_date`, `content_date_source` | Date read from the document text (first "Month D, YYYY" in the first 600 characters), or `none` |
| `title_raw`, `title_quality` | Embedded Title, and our judgement of it: missing, filename or software string, reused across many files (template carry-over), auto-filled from first line, or descriptive |
| `author_raw`, `author_normalized` | Embedded Author as found and a cleaned form |
| `creator_app`, `producer_app` | Software that made the PDF |
| `creation_date`, `mod_date`, `creation_lag_days` | Embedded dates and the gap between CreationDate and the content date |
| `tagged`, `has_xmp`, `is_pdfa`, `encrypted` | 0/1 flags |
| `font_count`, `fonts_embedded` | Fonts used and how many are embedded |
| `image_count`, `image_ppi_max` | Embedded images and the highest scan resolution |
| `text_chars`, `text_layer` | Characters extractable by pdftotext; `full`, `partial` or `none` |
| `ocr_needed` | 1 if the file needs OCR before it is searchable |
| `text_usability` *(added in Step 3)* | Final class: usable layer as-is, no layer: OCR required, usable layer + OCR image pages, layer defective: re-OCR |
| `rotated_pages` *(added in Step 3)* | Number of pages stored sideways or upside down |
| `sha256`, `bytes`, `dup_group_id` | Fixity and duplicate membership |

`extraction_tests.notes` was also added in Step 3.

## Views

| View | What it shows |
|---|---|
| `v_type_summary` | Files, pages, OCR need and date range per document type |
| `v_issue_summary` | How many sampled files have each issue |
| `v_ocr_queue` | Files that need OCR, largest first |

Example queries are in `sql/queries.sql`.
