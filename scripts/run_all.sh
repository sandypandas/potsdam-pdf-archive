#!/usr/bin/env bash
# Re-run the whole assessment from the original PDFs.
# Put the 718 PDFs in ./raw (named 2.pdf ... 1164.pdf), then run from the repository root:
#   bash scripts/run_all.sh
# Outputs go to ./out and ./work; compare them with the copies under results/.
# Needs: poppler-utils 24.02, tesseract 5.3 (eng), python3 with rapidfuzz, pillow, openpyxl.
set -euo pipefail
mkdir -p out work
cp data/sample/sample.json out/sample.json            # seed 20261111, s = 251
python3 scripts/01_profile.py raw out/sample.json out/profile.jsonl
python3 scripts/02_classify.py out/profile.jsonl out/classified.jsonl
python3 scripts/03_ocr_scans.py out/classified.jsonl raw out/ocr          # about 45 min on 4 cores
python3 scripts/04_ocr_benchmark.py out/classified.jsonl raw out/ocr_benchmark.jsonl 40
python3 scripts/06_layer_audit.py out/classified.jsonl raw out/layer_audit.jsonl
python3 scripts/07_orientation_check.py out/classified.jsonl raw out/orientation.jsonl
python3 scripts/05_build_inventory.py sql/schema.sql out/classified.jsonl work/potsdam_inventory.db
python3 scripts/08_load_extraction.py work/potsdam_inventory.db out
python3 scripts/09_rotation_bestof4.py out/orientation.jsonl raw out/rotation_bestof4.jsonl
python3 scripts/09b_apply_rotation_and_findings.py work/potsdam_inventory.db out/orientation.jsonl out/rotation_bestof4.jsonl
# Verification scoring and the correction estimate run on files already in this repository:
python3 scripts/10_score_verification.py results/verification work/potsdam_inventory.db work/step4_verification_results.csv
python3 scripts/11_estimate_correction.py results/extraction/ocr_scans/ocr_pages.jsonl results/verification/step4_verification_results.csv
