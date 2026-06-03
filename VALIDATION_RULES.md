# VALIDATION RULES & CONFIGURATION - OJT Checker System

## Validation Field Rules (Per Requirements)

### ✅ Fields to Validate

| Field | Source | Min Similarity | Rule |
|-------|--------|---------------|----|
| Student Name | Excel | 80% | PASS if ≥80, else FAIL/AUTO-CORRECT |
| Course Name | Excel | 75% | PASS if ≥75, else FAIL/AUTO-CORRECT |
| OJT Period | Excel | 80% | PASS if ≥80, else FAIL/AUTO-CORRECT |
| Enrollment Number | Filename (Priority 1) | N/A | Exact match from filename regex |

### ❌ Fields to IGNORE (Do Not Validate)

- Department ← **Ignored completely**
- Job Role ← **Ignored completely**
- Year ← **Not validated** (informational only)
- Designation ← **Ignored** (same as Job Role)

---

## Similarity Scoring Rules

The OJT Checker uses **RapidFuzz WRatio** for fuzzy matching:

```python
Score < 50      → FAIL + AUTO CORRECT (use Excel value)
Score 50-79     → FAIL (manual review needed)
Score ≥ 80      → PASS (field matches well)
```

### Examples

#### Student Name: "Ammulya" vs "AMULYA"
- WRatio Score: ~95%
- Result: **PASS** ✓

#### Course: "Work Integreated Skill Dipoma" vs "Work Integrated Skill Diploma in Automotive Manufacturing"
- WRatio Score: ~65%  
- Result: **FAIL**, triggers AUTO CORRECT ✗
- Corrected Value: "Work Integrated Skill Diploma in Automotive Manufacturing"

#### OJT Period: "I#/b/s5" vs "Jan 2024 – Jun 2024"
- WRatio Score: ~5%
- Result: **FAIL**, triggers AUTO CORRECT ✗
- Corrected Value: "Jan 2024 – Jun 2024"

---

## Enrollment Number Extraction

### Priority System (Strict Order)

#### Priority 1: Filename Extraction (ALWAYS USED IF FOUND)
```
Pattern: DMCFSJU\d+
Examples:
  ✓ AMULYA_DMCFSJU17090 (1).pdf → DMCFSJU17090
  ✓ DMCFSJU17090.pdf → DMCFSJU17090
  ✗ AMULYA_17090.pdf → NOT FOUND (needs DMCFSJU prefix)
```

#### Priority 2: OCR Extraction (Only if filename not found)
- Searches for "enrollment" label in OCR text
- Validates against same pattern: DMCFSJU\d+
- **Rejects** any value that matches OCR label keywords

#### Rejected Keywords (Cannot be enrollment values)
```
name, student, studentname, course, skill, year, period, 
department, departmentandjob, jobrole, designation, role, 
job, title, position
```

Example: If OCR finds "enrollment: DepartmentandJob", it's **rejected** because:
- Value contains "departmentandjob" → in rejection list
- Falls back to regex search

---

## PDF Correction Logic

### When Corrections Are Applied

Corrections are applied when:
1. Field validation score < 50 (auto-correct triggers)
2. Field validation score 50-79 but correction needed (FAIL status)
3. Field is MISSING in OCR (empty string)

### Correction Process

1. **Locate text on PDF**
   - Try PyMuPDF text search for the OCR value
   - If found, cover with white rectangle + padding
   - If not found, use fallback region for the field

2. **Write corrected text**
   - Font: Helvetica (built-in PDF font)
   - Size: 10 points
   - Color: Black (0, 0, 0)
   - Position: Left-aligned, vertically centered in rectangle

3. **Save corrected PDF**
   - Path: `data/corrected/{filename}.pdf`
   - Compression: Yes (garbage collection + deflate)
   - Logged: `[CORRECTION] Corrected PDF saved: {filename} ({n} corrections applied)`

### Fallback Regions (if text not found on page)

| Field | Region (PDF points) | 
|-------|-------------------|
| student_name | (100, 180, 450, 210) |
| course_name | (100, 230, 500, 260) |
| enrollment_no | (100, 280, 400, 310) |
| ojt_period | (100, 330, 450, 360) |
| department | (100, 380, 450, 410) |

---

## Excel Master Data

### Required Columns

```python
EXCEL_COL_ENROLLMENT = "Enrollment Number"
EXCEL_COL_NAME       = "Student Name"
EXCEL_COL_COURSE     = "Course Name"
EXCEL_COL_OJT_PERIOD = "OJT Period"
EXCEL_COL_YEAR       = "Year"
```

### Exact Column Names (must match)

- [ ] "Enrollment Number" - Exact case
- [ ] "Student Name" - Exact case
- [ ] "Course Name" - Exact case
- [ ] "OJT Period" - Exact case
- [ ] "Year" - Exact case

If any column is missing or named differently, Excel load will **fail** with error message.

### Example Excel Format

| Enrollment Number | Student Name | Course Name | OJT Period | Year |
|------------------|--------------|-----------|-----------|------|
| DMCFSJU17090 | Ammulya | Work Integrated Skill Diploma | Jan 2024 – Jun 2024 | I |
| DMCFSJU17091 | Pranav | Diploma in IT | Feb 2024 – Jul 2024 | II |

---

## Validation Report Output

### Report Location
`data/reports/validation_report_{YYYYMMDD_HHMMSS}.xlsx`

### Report Sheets

#### Sheet 1: "Validation Results" (Per-PDF results)

| Column | Contents |
|--------|----------|
| PDF Name | Filename of processed PDF |
| Enrollment Number | Extracted enrollment from filename |
| Student Name | OCR-extracted name |
| Course Match | PASS / FAIL / MISSING |
| Name Match | PASS / FAIL / MISSING |
| OJT Period Match | PASS / FAIL / MISSING |
| Stamp Status | PASS / FAIL / MISSING STAMP / UNCHECKED |
| Corrections Made | Number of fields corrected |
| Final Status | PASS / FAIL / ERROR |
| Error Notes | Any error messages |

#### Sheet 2: "Summary" (Statistics)

| Metric | Value |
|--------|-------|
| Generated | Timestamp |
| Total PDFs Processed | Count |
| PASS | Count |
| FAIL | Count |
| Errors | Count |
| Total Corrections Made | Sum |
| Pass Rate (%) | Percentage |

---

## Debug Logging Filters

### View Only Enrollment Decisions
```bash
grep "\[ENROLLMENT\]" logs/app.log | tail -20
```

### View Only Field Validations
```bash
grep "\[FIELD\]" logs/app.log
```

### View Only Corrections
```bash
grep "\[CORRECTION\]" logs/app.log
```

### View Complete Flow for One PDF
```bash
grep "DMCFSJU17090" logs/app.log
```

### View Only Errors
```bash
grep "\[ERROR\]" logs/app.log
```

### View Final Report Status
```bash
grep "\[REPORT\]" logs/app.log
```

---

## Configuration Parameters

### Thresholds (config.py)

```python
# Fuzzy matching threshold for each field
FIELD_PASS_THRESHOLD = {
    "student_name":   80,    # 80% minimum similarity
    "course_name":    75,    # 75% minimum similarity
    "enrollment_no":  95,    # 95% minimum (very strict)
    "ojt_period":     80,    # 80% minimum similarity
}
```

### PDF Settings

```python
EXPECTED_PAGE_COUNT = 7         # OJT docs must have 7 pages
OCR_PAGE_INDEX = 0              # Extract fields from page 1 (index 0)
STAMP_PAGES = [1, 2, 3, 4, 5, 6]  # Check stamps on pages 2-7 (indices 1-6)
```

### Processing Settings

```python
BATCH_SIZE = 50                 # PDFs per batch
MAX_WORKER_THREADS = 4          # Parallel threads
MEMORY_LIMIT_MB = 2048          # Pause if RAM exceeds this
```

### OCR Settings

```python
OCR_LANGUAGES = ["en"]          # English only
OCR_GPU = False                 # Set True if CUDA available
OCR_MIN_CONFIDENCE = 0.3        # Discard low-confidence text
OCR_DPI = 200                   # Rasterization DPI
OCR_IMAGE_SCALE = 2.0           # Upscale before OCR
```

---

## Common Issues & Solutions

### Issue: "Excel record NOT found"
**Cause:** Enrollment number doesn't match Excel data
**Solution:** 
1. Check Excel has student with that enrollment
2. Check enrollment column name matches exactly: "Enrollment Number"
3. View logs: `grep "\[EXCEL\]" logs/app.log`

### Issue: "No corrections needed - PDF copied to output"
**Cause:** All fields PASSED validation
**Expected:** This is correct! PDF still goes to `data/corrected/` folder
**Action:** None - this is correct behavior

### Issue: Corrected PDF shows no changes
**Cause:** Text couldn't be located on PDF (handwritten/image-based form)
**Solution:**
- Corrections are placed in fallback regions
- Check fallback region coordinates in config.py
- May need manual adjustment of FIELD_FALLBACK_REGIONS

### Issue: "validation_report not generated"
**Cause:** No PDFs were processed successfully
**Solution:**
1. Check PDFs are in correct folder
2. Check PDF page count is 7
3. View logs for processing errors

---

## Expected Processing Output

For each PDF processed:

```
data/
├── uploads/
│   └── AMULYA_DMCFSJU17090 (1).pdf  ← Original (read-only)
├── corrected/
│   └── AMULYA_DMCFSJU17090 (1).pdf  ← Corrected version
├── ocr_texts/
│   └── AMULYA_DMCFSJU17090 (1)_ocr.txt  ← Extracted fields
└── reports/
    └── validation_report_20240603_120000.xlsx  ← Summary
```

Each file signals success:
- ✓ OCR text saved → OCR working
- ✓ Corrected PDF saved → Corrections applied
- ✓ Report generated → Summary created

