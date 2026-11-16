-- Potsdam PDF archive: preservation inventory schema (SQLite 3)
-- One row per sampled document in `documents`; fixity covers the whole archive (718 files).
PRAGMA foreign_keys = ON;

-- Controlled vocabulary for document types found in the sample
CREATE TABLE doc_types (
    doc_type      TEXT PRIMARY KEY,
    series        TEXT NOT NULL,          -- records series the type belongs to
    description   TEXT
);

-- Controlled vocabulary for preservation / metadata issues
CREATE TABLE issue_types (
    issue_code    TEXT PRIMARY KEY,
    category      TEXT NOT NULL CHECK (category IN ('metadata','text','format','integrity','identity')),
    severity      TEXT NOT NULL CHECK (severity IN ('high','medium','low')),
    description   TEXT NOT NULL
);

-- Core inventory: the 251 sampled documents
CREATE TABLE documents (
    file_no             INTEGER PRIMARY KEY,         -- number in the original filename
    filename            TEXT NOT NULL UNIQUE,        -- as received, e.g. 544.pdf
    proposed_filename   TEXT,                        -- standardized name (see plan)
    doc_type            TEXT REFERENCES doc_types(doc_type),
    content_date        TEXT,                        -- ISO date read from the document text
    content_date_source TEXT CHECK (content_date_source IN ('text','none')),
    -- embedded metadata as found (pdfinfo)
    title_raw           TEXT,
    title_quality       TEXT,
    author_raw          TEXT,
    author_normalized   TEXT,
    creator_app         TEXT,
    producer_app        TEXT,
    creation_date       TEXT,                        -- PDF CreationDate (ISO)
    mod_date            TEXT,                        -- PDF ModDate (ISO)
    creation_lag_days   INTEGER,                     -- creation_date minus content_date
    -- structure
    pdf_version         TEXT,
    pages               INTEGER NOT NULL,
    page_size_pts       TEXT,
    orientation         TEXT CHECK (orientation IN ('portrait','landscape','mixed/other')),
    tagged              INTEGER CHECK (tagged IN (0,1)),
    has_xmp             INTEGER CHECK (has_xmp IN (0,1)),
    is_pdfa             INTEGER CHECK (is_pdfa IN (0,1)),
    encrypted           INTEGER CHECK (encrypted IN (0,1)),
    font_count          INTEGER,
    fonts_embedded      INTEGER,
    image_count         INTEGER,
    image_ppi_max       INTEGER,
    -- text layer
    text_chars          INTEGER,
    text_layer          TEXT CHECK (text_layer IN ('full','partial','none')),
    ocr_needed          INTEGER CHECK (ocr_needed IN (0,1)),
    -- file
    bytes               INTEGER NOT NULL,
    sha256              TEXT NOT NULL,
    dup_group_id        INTEGER REFERENCES duplicate_groups(group_id),
    notes               TEXT
);

-- Issues found per document (many per document)
CREATE TABLE document_issues (
    file_no     INTEGER NOT NULL REFERENCES documents(file_no),
    issue_code  TEXT NOT NULL REFERENCES issue_types(issue_code),
    detail      TEXT,
    PRIMARY KEY (file_no, issue_code)
);

-- Fixity for every file in the archive (not just the sample)
CREATE TABLE fixity (
    file_no     INTEGER PRIMARY KEY,
    filename    TEXT NOT NULL UNIQUE,
    sha256      TEXT NOT NULL,
    bytes       INTEGER NOT NULL,
    in_sample   INTEGER NOT NULL CHECK (in_sample IN (0,1)),
    computed_at TEXT NOT NULL,
    tool        TEXT NOT NULL
);

-- Byte-identical duplicates across the whole archive
CREATE TABLE duplicate_groups (
    group_id        INTEGER PRIMARY KEY,
    sha256          TEXT NOT NULL UNIQUE,
    copies          INTEGER NOT NULL,
    keep_file_no    INTEGER NOT NULL           -- lowest number kept as the original
);
CREATE TABLE duplicate_members (
    group_id    INTEGER NOT NULL REFERENCES duplicate_groups(group_id),
    file_no     INTEGER NOT NULL REFERENCES fixity(file_no),
    PRIMARY KEY (group_id, file_no)
);

-- Filled in Steps 3 and 4
CREATE TABLE extraction_tests (
    test_id         INTEGER PRIMARY KEY,
    file_no         INTEGER NOT NULL REFERENCES documents(file_no),
    page            INTEGER NOT NULL,
    method          TEXT NOT NULL,             -- e.g. pdftotext, tesseract-300ppi
    tool_version    TEXT,
    chars           INTEGER,
    mean_word_conf  REAL,                      -- Tesseract only
    cer             REAL,                      -- character error rate vs reference
    word_miss_rate  REAL,
    output_path     TEXT,
    run_at          TEXT
);
CREATE TABLE verification (
    verify_id       INTEGER PRIMARY KEY,
    file_no         INTEGER NOT NULL REFERENCES documents(file_no),
    page            INTEGER NOT NULL,
    method          TEXT NOT NULL,
    verified_by     TEXT,
    verified_at     TEXT,
    result          TEXT CHECK (result IN ('accurate','minor errors','major errors','unusable')),
    error_count     INTEGER,
    error_notes     TEXT
);

-- Convenience views
CREATE VIEW v_ocr_queue AS
    SELECT file_no, filename, doc_type, pages, image_ppi_max, bytes
    FROM documents WHERE ocr_needed = 1 ORDER BY pages DESC;

CREATE VIEW v_issue_summary AS
    SELECT it.category, it.issue_code, it.severity, COUNT(di.file_no) AS documents
    FROM issue_types it LEFT JOIN document_issues di USING (issue_code)
    GROUP BY it.issue_code ORDER BY documents DESC;

CREATE VIEW v_type_summary AS
    SELECT doc_type, COUNT(*) AS documents, SUM(pages) AS pages,
           SUM(ocr_needed) AS need_ocr,
           MIN(content_date) AS earliest, MAX(content_date) AS latest
    FROM documents GROUP BY doc_type ORDER BY documents DESC;
