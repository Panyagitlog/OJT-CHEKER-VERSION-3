# ROOT CAUSE ANALYSIS: OJT Checker Validation & Correction Failures

## Executive Summary

**Root Cause:** The `ocr_engine.py._extract_enrollment()` method treats filename enrollment as a fallback instead of the primary source. This causes corrupted OCR values (e.g., "DepartmentandJob", "DMcFs-ul090") to override the correct filename enrollment during validation.

---

## Problem Flow

### Current Broken Flow:
```
PDF: AMULYA_DMCFSJU17090 (1).pdf
        ↓
Step 1: Extract from filename → DMCFSJU17090 ✓
Step 2: OCR page 1 → finds label "enrollment"
Step 3: OCR reads value as "DepartmentandJob" (misread) ✗
Step 4: _extract_enrollment() runs rejection keywords check
Step 5: Falls back to regex → finds DMCFSJU17090 in full text ✓ 
Step 6: But validator receives CORRUPTED OCR value ✗
Step 7: Excel lookup fails → "Excel record NOT found"
Step 8: Validation FAILS → no corrected PDF
Step 9: No report generated
```

### Expected Flow (After Fix):
```
PDF: AMULYA_DMCFSJU17090 (1).pdf
        ↓
Step 1: Extract from filename → DMCFSJU17090 (Priority 1) ✓
Step 2: OCR page 1 → corrupted value (Priority 2, unused) 
Step 3: Validator uses filename enrollment STRICTLY ✓
Step 4: Excel record found ✓
Step 5: Validate fields against Excel ✓
Step 6: Auto-correct failed fields ✓
Step 7: Generate corrected PDF ✓
Step 8: Generate validation report ✓
```

---

## Exact Root Causes

### 1. **ocr_engine.py Line 227-253: Fallback Logic is Backwards**

**Issue:** `filename_enrollment` is only used as a last resort fallback, not as the primary source.

**Current Code:**
```python
def _extract_enrollment(self, lines, full_text, filename_enrollment=None):
    # ... keyword extraction → may return "DepartmentandJob"
    # ... regex fallback
    # ... ONLY THEN use filename_enrollment
    if filename_enrollment:
        return filename_enrollment
    return ""
```

**Why it fails:**
- When keyword extraction finds "enrollment:" label, it extracts whatever follows (including OCR errors)
- The rejection keywords check is insufficient for labels containing multiple words
- Even if regex finds the correct value, the OCR keyword value has already corrupted the flow

### 2. **ocr_engine.py Line 217: Incomplete Rejection Keywords**

**Issue:** Some label keywords that should be rejected are not in the REJECTION_KEYWORDS set.

**Missing rejections:**
- "DepartmentandJob" (exact OCR error seen)
- "JobRole"
- Multi-word confusion like "Department and Job"

### 3. **processor.py Line 252-254: Validator Receives Both Values**

**Issue:** Validator is passed both `ocr_fields` (which may be corrupted) AND `excel_enrollment` (correct).

**Problem:** Validator validates OCR enrollment against Excel even though we already have the filename enrollment.

### 4. **processor.py Line 328-340: Corrected PDF Logic**

**Issue:** Corrected PDF is only saved if `corrections` dict is non-empty. But:
- If validation PASSES, no corrections dict is built
- Even passing PDFs should be copied to output for consistency
- This is already handled in the code but report generation might be skipped

### 5. **validator.py Line 189-195: Missing Debug Logs**

**Issue:** No tracking of which enrollment value is actually used in validation.

**Current:** Only logs "Excel Match: Found/Not found"

**Missing:** Logs for:
- Final enrollment used
- Whether it came from filename or OCR
- Why OCR enrollment was rejected

---

## Affected Files

1. **core/ocr_engine.py** (CRITICAL)
   - `_extract_enrollment()` method (lines 211-253)
   - Priority logic needs reversal
   - Rejection keywords incomplete

2. **core/processor.py** (CRITICAL)
   - `_process_single_pdf()` method (lines 267-338)
   - Debug logging insufficient
   - Enrollment tracking not comprehensive

3. **core/validator.py** (IMPORTANT)
   - `validate()` method (lines 66-117)
   - Add enrollment source tracking
   - Add debug logs

4. **core/pdf_corrector.py** (MINOR)
   - `build_corrections_dict()` already correct
   - But no logging for missing correction scenarios

5. **core/report_generator.py** (MINOR)
   - Report generation skipped if validation passes?
   - Need to verify report is always generated

---

## Validation Rules Summary (Per Requirements)

✅ **Validate Only:**
- Student Name
- Course Name  
- OJT Period
- Year

❌ **Ignore (Don't Validate):**
- Department
- Job Role

✅ **Similarity Rules:**
- ≥ 80: PASS
- 50-79: FAIL  
- < 50: AUTO CORRECT

✅ **Enrollment Priority:**
1. Filename extraction (DMCFSJU\d+)
2. OCR (fallback only)
3. Never accept OCR labels as values

---

## Fixes Required

### Fix 1: Reverse Enrollment Extraction Priority (ocr_engine.py)
- Check `filename_enrollment` first
- Only run OCR extraction if filename enrollment not provided
- Add validation to reject OCR label keywords

### Fix 2: Add Comprehensive Debug Logging (processor.py)
- Log enrollment at each stage
- Track transformations
- Log final enrollment used

### Fix 3: Strengthen Rejection Keywords (ocr_engine.py)
- Expand rejection set to catch more OCR label keywords
- Add case-insensitive partial matching

### Fix 4: Add Enrollment Source Tracking (validator.py)
- Log which enrollment value is used
- Log why OCR enrollment is rejected
- Ensure Excel values always override OCR

### Fix 5: Verify Report Generation (report_generator.py)
- Ensure reports are generated even for PASS status
- Add logging to verify report save

---

## Logging Enhancements Required

### OCR Enrollment:
```
[DEBUG] OCR Enrollment Source: DMCFSJU17090 (from filename)
[DEBUG] OCR Enrollment Extracted: DepartmentandJob (from OCR keyword)
[DEBUG] OCR Rejection: DepartmentandJob (matches rejection keyword)
[DEBUG] Final Enrollment Used: DMCFSJU17090 (from filename - priority)
```

### Validation:
```
[DEBUG] Enrollment extracted from filename: DMCFSJU17090
[DEBUG] Excel lookup using enrollment: DMCFSJU17090
[DEBUG] Excel Match: Found - Record ID: xxxxx
[DEBUG] Validating: student_name ≥ 80 threshold → PASS
[DEBUG] Validating: course_name ≥ 75 threshold → FAIL, AUTO CORRECT
```

### PDF Correction:
```
[INFO] Field Corrected: student_name (OCR: "Ammulya" → Excel: "AMULYA")
[INFO] Corrected PDF Saved: corrected/AMULYA_DMCFSJU17090_corrected.pdf
```

### Report Generation:
```
[INFO] Validation Report Generated: reports/validation_report_20240603_120000.xlsx
```

---

## Verification Checklist

After applying fixes:

- [ ] OCR enrollment correctly identifies DMCFSJU17090 from filename
- [ ] Debug logs show "OCR Enrollment Source: DMCFSJU17090"
- [ ] Validator uses filename enrollment, not OCR value
- [ ] Excel record is found for DMCFSJU17090
- [ ] Validation shows PASS/FAIL per field rules
- [ ] Corrected PDF is generated with Excel values
- [ ] Corrected PDF is saved to `corrected/` folder
- [ ] OCR text saved to `ocr_texts/` folder
- [ ] Validation report is saved to `reports/` folder
- [ ] All three output files exist for each processed PDF

