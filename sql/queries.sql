-- Useful queries against data/potsdam_inventory.db
-- Run with:  sqlite3 data/potsdam_inventory.db < sql/queries.sql
-- or paste one query at a time into DB Browser for SQLite ("Execute SQL" tab).
.headers on
.mode column

-- 1. How the sample breaks down by document type
SELECT * FROM v_type_summary;

-- 2. How often each issue appears in the 251 sampled files
SELECT * FROM v_issue_summary;

-- 3. Text usability: which files can be searched as they are, and which need OCR
SELECT text_usability, COUNT(*) AS files, SUM(pages) AS pages
FROM documents GROUP BY text_usability ORDER BY files DESC;

-- 4. Files whose embedded Title describes a different document (template carry-over)
SELECT file_no, doc_type, content_date, title_raw
FROM documents WHERE title_quality LIKE 'reused%' ORDER BY title_raw, file_no LIMIT 20;

-- 5. Gap between the meeting date and the PDF CreationDate
SELECT doc_type, COUNT(*) AS files,
       MIN(creation_lag_days) AS min_lag, MAX(creation_lag_days) AS max_lag,
       ROUND(AVG(creation_lag_days), 1) AS mean_lag
FROM documents WHERE creation_lag_days IS NOT NULL GROUP BY doc_type;

-- 6. Files batch re-saved in October 2023 (origin date lost)
SELECT d.file_no, d.creation_date, d.producer_app
FROM documents d JOIN document_issues i USING (file_no)
WHERE i.issue_code = 'CREATION_DATE_RESAVED';

-- 7. Exact duplicates across the whole archive, with the copy to keep
SELECT g.group_id, g.keep_file_no, group_concat(m.file_no, ', ') AS members
FROM duplicate_groups g JOIN duplicate_members m USING (group_id)
GROUP BY g.group_id ORDER BY g.group_id;

-- 8. OCR work queue (files that need OCR), largest first
SELECT * FROM v_ocr_queue LIMIT 20;

-- 9. Pages stored sideways
SELECT file_no, pages, rotated_pages FROM documents WHERE rotated_pages > 0 ORDER BY rotated_pages DESC;

-- 10. Mean OCR confidence per scanned file (lowest first)
SELECT file_no, COUNT(*) AS pages, ROUND(AVG(mean_word_conf), 1) AS mean_conf,
       SUM(mean_word_conf < 60) AS pages_below_60
FROM extraction_tests WHERE method = 'tesseract-300ppi-psm3'
GROUP BY file_no ORDER BY mean_conf LIMIT 15;

-- 11. Benchmark: OCR word-miss rate at 300 vs 200 ppi on born-digital pages
SELECT method, COUNT(*) AS pages, ROUND(AVG(word_miss_rate), 4) AS mean_word_miss, ROUND(AVG(cer), 4) AS mean_cer
FROM extraction_tests WHERE method LIKE '%vs layer' GROUP BY method;

-- 12. Text layers flagged by the OCR cross-check
SELECT file_no, page, notes FROM extraction_tests
WHERE method LIKE 'pdftotext layer vs%' AND notes LIKE '%flag=True%';

-- 13. Verification results, worst first
SELECT file_no, page, method, result, error_count, error_notes
FROM verification
ORDER BY CASE result WHEN 'unusable' THEN 1 WHEN 'major errors' THEN 2 WHEN 'minor errors' THEN 3 ELSE 4 END;

-- 14. Fixity check list for all 718 files (compare with a fresh sha256sum run)
SELECT filename, sha256, bytes, in_sample FROM fixity ORDER BY file_no LIMIT 10;
