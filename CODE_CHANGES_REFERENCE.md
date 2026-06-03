# EXACT CODE CHANGES - Line-by-Line Reference

## Quick Navigation

| File | Method | Lines | Change Type |
|------|--------|-------|------------|
| ocr_engine.py | `_extract_enrollment()` | 211-253 | CRITICAL: Reverse priority |
| processor.py | `_process_single_pdf()` | 267-374 | HIGH: Add logging |
| validator.py | `validate()` | 66-117 | HIGH: Add logging |
| pdf_corrector.py | `build_corrections_dict()` | 208-213 | MEDIUM: Add logging |
| pdf_corrector.py | `correct_pdf()` | 114-127 | MEDIUM: Add logging |
| report_generator.py | `add()` | 68 | MEDIUM: Add logging |
| report_generator.py | `save()` | 70-95 | MEDIUM: Add logging |

---

## 1. core/ocr_engine.py - Lines 211-253

### Method: `_extract_enrollment()`

**BEFORE:**
```python
def _extract_enrollment(self, lines: list[str], full_text: str, filename_enrollment: str = None) -> str:
    """
    Extract enrollment number from OCR.
    
    Validation:
    - Must match pattern DMCFSJU\\d+
    - Reject keywords: Name, Student, StudentName, Course, Skill, Year, 
      Period, Department, DepartmentandJob, JobRole
    
    Falls back to regex only if filename_enrollment not provided.
    """
    # Keywords to reject (common OCR errors)
    REJECTION_KEYWORDS = {
        "name", "student", "studentname", "course", "skill", 
        "year", "period", "department", "departmentandjob", "jobrole"
    }

    # Try keyword anchor first
    by_keyword = self._extract_near_keyword(
        lines, config.FIELD_KEYWORDS["enrollment_no"]
    )
    
    if by_keyword:
        # Check if it matches a rejection keyword
        if by_keyword.lower() in REJECTION_KEYWORDS:
            logger.debug(f"Rejected OCR enrollment '{by_keyword}' (matches keyword)")
        else:
            # Validate against DMCFSJU\\d+ pattern
            match = re.search(r"DMCFSJU\d+", by_keyword, re.IGNORECASE)
            if match:
                return match.group(0).upper()

    # Regex fallback: DMCFSJU\\d+ pattern only
    match = re.search(r"DMCFSJU\d+", full_text, re.IGNORECASE)
    if match:
        return match.group(0).upper()

    # If filename_enrollment provided, it's already validated
    if filename_enrollment:
        return filename_enrollment

    return ""
```

**AFTER:**
```python
def _extract_enrollment(self, lines: list[str], full_text: str, filename_enrollment: str = None) -> str:
    """
    Extract enrollment number from OCR.
    
    Priority 1: Use filename enrollment if provided (already validated)
    Priority 2: Extract from OCR if filename enrollment not available
    
    Validation:
    - Must match pattern DMCFSJU\\d+
    - Reject keywords: Name, Student, StudentName, Course, Skill, Year, 
      Period, Department, DepartmentandJob, JobRole, designation, etc.
    """
    # PRIORITY 1: Filename enrollment is most reliable
    if filename_enrollment:
        logger.debug(f"[ENROLLMENT] Priority 1 - Using filename enrollment: {filename_enrollment}")
        return filename_enrollment

    # PRIORITY 2: OCR extraction (fallback)
    logger.debug(f"[ENROLLMENT] Priority 2 - Extracting from OCR (filename not provided)")
    
    # Keywords to reject (common OCR errors and label keywords)
    REJECTION_KEYWORDS = {
        "name", "student", "studentname", "course", "skill", 
        "year", "period", "department", "departmentandjob", "jobrole",
        "designation", "role", "job", "title", "position"
    }

    # Try keyword anchor first
    by_keyword = self._extract_near_keyword(
        lines, config.FIELD_KEYWORDS["enrollment_no"]
    )
    
    if by_keyword:
        # Check if it matches a rejection keyword (exact or contains)
        by_keyword_lower = by_keyword.lower()
        is_rejection = False
        
        # Exact match check
        if by_keyword_lower in REJECTION_KEYWORDS:
            is_rejection = True
            logger.debug(f"[ENROLLMENT] Rejected OCR value '{by_keyword}' (exact match with rejection keyword)")
        # Partial match check for multi-word OCR errors
        else:
            for reject_kw in REJECTION_KEYWORDS:
                if reject_kw in by_keyword_lower:
                    is_rejection = True
                    logger.debug(f"[ENROLLMENT] Rejected OCR value '{by_keyword}' (contains '{reject_kw}')")
                    break
        
        if not is_rejection:
            # Validate against DMCFSJU\\d+ pattern
            match = re.search(r"DMCFSJU\d+", by_keyword, re.IGNORECASE)
            if match:
                extracted = match.group(0).upper()
                logger.debug(f"[ENROLLMENT] Extracted from OCR keyword: {extracted}")
                return extracted

    # Regex fallback: DMCFSJU\\d+ pattern only
    match = re.search(r"DMCFSJU\d+", full_text, re.IGNORECASE)
    if match:
        extracted = match.group(0).upper()
        logger.debug(f"[ENROLLMENT] Extracted from regex fallback: {extracted}")
        return extracted

    logger.debug(f"[ENROLLMENT] No valid enrollment found in OCR")
    return ""
```

**Key Changes:**
- ✅ `if filename_enrollment:` moved to **beginning** (Priority 1)
- ✅ Returns immediately if filename enrollment provided
- ✅ Expanded REJECTION_KEYWORDS: added `designation`, `role`, `job`, `title`, `position`
- ✅ Added partial-match checking for multi-word OCR errors
- ✅ All debug logs prefixed with `[ENROLLMENT]`

---

## 2. core/processor.py - Lines 267-374

### Method: `_process_single_pdf()`

**Key sections changed:**

### Section A: Enrollment Extraction (Lines 267-280)
```python
# BEFORE:
if enrollment_from_filename:
    self._log(f"Filename Enrollment: {enrollment_from_filename}")
else:
    self._log(f"No enrollment found in filename: {pdf_path.name}")

# AFTER:
if enrollment_from_filename:
    self._log(f"[ENROLLMENT] Filename: {enrollment_from_filename}")
else:
    self._log(f"[ENROLLMENT] Filename: NOT FOUND in {pdf_path.name}")
```

### Section B: Excel Lookup (Lines 281-291)
```python
# BEFORE:
if excel_record:
    self._log(f"Excel Match: Found")
    report.enrollment_no = enrollment_from_filename
    report.student_record = excel_record
else:
    self._log(f"Excel Match: Not found")

# AFTER:
if excel_record:
    self._log(f"[EXCEL] Match: FOUND for enrollment {enrollment_from_filename}")
    report.enrollment_no = enrollment_from_filename
    report.student_record = excel_record
else:
    self._log(f"[EXCEL] Match: NOT FOUND for enrollment {enrollment_from_filename}")
```

### Section C: PDF Loading (Lines 293-300)
```python
# BEFORE:
with PDFReader(pdf_path) as reader:
    self._log(f"PDF loaded: {pdf_path.name}")

# AFTER:
with PDFReader(pdf_path) as reader:
    self._log(f"[PDF] Loaded: {pdf_path.name}")
```

### Section D: OCR Extraction (Lines 308-318)
```python
# BEFORE:
self._log(f"OCR completed: {pdf_path.name}")
ocr_enroll = ocr_fields.get("enrollment_no", "")
self._log(f"OCR Enrollment: {ocr_enroll if ocr_enroll else 'NOT FOUND'}")

# AFTER:
self._log(f"[OCR] Extraction completed for {pdf_path.name}")
ocr_enroll = ocr_fields.get("enrollment_no", "")
self._log(f"[OCR] Enrollment extracted: {ocr_enroll if ocr_enroll else 'NOT FOUND'}")

# Debug: Compare filename vs OCR enrollment
if enrollment_from_filename and ocr_enroll and enrollment_from_filename != ocr_enroll:
    self._log(f"[ENROLLMENT] Mismatch: Filename={enrollment_from_filename} vs OCR={ocr_enroll}")
    self._log(f"[ENROLLMENT] USING FILENAME (Priority 1)")
```

### Section E: Validation Start (Lines 323-324)
```python
# BEFORE:
val_report = self.validator.validate(

# AFTER:
self._log(f"[VALIDATION] Starting validation...")
val_report = self.validator.validate(
```

### Section F: Field Validation Logging (Lines 333-337)
```python
# BEFORE:
for field_name, field_result in val_report.field_results.items():
    status_str = field_result.status
    if field_result.correction_text and field_result.status == "FAIL":
        self._log(f"  {field_name}: {status_str} → Corrected to '{field_result.correction_text}'")
    else:
        self._log(f"  {field_name}: {status_str}")

# AFTER:
for field_name, field_result in val_report.field_results.items():
    status_str = field_result.status
    if field_result.correction_text and field_result.status == "FAIL":
        self._log(f"[FIELD] {field_name}: {status_str} (score={field_result.score:.0f}) → Corrected to '{field_result.correction_text}'")
    else:
        self._log(f"[FIELD] {field_name}: {status_str} (score={field_result.score:.0f})")
```

### Section G: Validation Summary (Lines 338-340)
```python
# BEFORE:
self._log(f"Validation completed: {pdf_path.name} → {val_report.final_status}")

# AFTER:
self._log(f"[VALIDATION] Completed: {pdf_path.name} → {val_report.final_status}")
```

### Section H: Stamp Detection (Lines 342-346)
```python
# BEFORE:
if stamp_result["failed_pages"]:
    logger.debug(...)

# AFTER:
if stamp_result["failed_pages"]:
    logger.debug(...)
else:
    self._log(f"[STAMP] Detection: {stamp_result['status']}")
```

### Section I: PDF Correction (Lines 349-365)
```python
# BEFORE:
corrections = self.corrector.build_corrections_dict(val_report)
if corrections:
    out_path = self.corrected_dir / pdf_path.name
    success, n_applied, msg = self.corrector.correct_pdf(...)
    if success:
        self._log(f"Corrected PDF Saved: {out_path}")

# AFTER:
corrections = self.corrector.build_corrections_dict(val_report)
if corrections:
    self._log(f"[CORRECTION] {len(corrections)} fields need correction")
    out_path = self.corrected_dir / pdf_path.name
    success, n_applied, msg = self.corrector.correct_pdf(...)
    if success:
        self._log(f"[CORRECTION] Corrected PDF saved: {out_path.name} ({n_applied} corrections applied)")
    else:
        self._log(f"[CORRECTION] FAILED: {msg}")
```

### Section J: No Corrections Path (Lines 366-375)
```python
# BEFORE:
else:
    import shutil
    out_path = self.corrected_dir / pdf_path.name
    try:
        shutil.copy2(str(pdf_path), str(out_path))
        self._log(f"Corrected PDF Saved: {out_path}")

# AFTER:
else:
    import shutil
    out_path = self.corrected_dir / pdf_path.name
    try:
        shutil.copy2(str(pdf_path), str(out_path))
        self._log(f"[CORRECTION] No corrections needed - PDF copied to output")
```

### Section K: Error Handling (Lines 376-379)
```python
# BEFORE:
except Exception as exc:
    logger.exception(f"Pipeline error for {pdf_path.name}")
    report.error = str(exc)

# AFTER:
except Exception as exc:
    logger.exception(f"Pipeline error for {pdf_path.name}")
    report.error = str(exc)
    self._log(f"[ERROR] Pipeline error: {exc}")
```

---

## 3. core/validator.py - Lines 66-117

### Method: `validate()`

**Key additions:**

### After `if excel_enrollment:` block (Lines 95-99)
```python
# ADDED:
if excel_enrollment:
    report.enrollment_no = excel_enrollment
    logger.debug(f"[VALIDATOR] Enrollment source: FILENAME (Priority 1) = {excel_enrollment}")
else:
    logger.debug(f"[VALIDATOR] Enrollment source: No filename enrollment provided, will try OCR fallback")
```

### Enhanced logging in fallback section (Lines 102-110)
```python
# BEFORE:
if excel_record:
    report.student_record = excel_record
else:
    student_record = self._find_student_record(ocr_fields)
    report.student_record = student_record
    if not excel_enrollment:
        report.enrollment_no = ocr_fields.get("enrollment_no", "")

# AFTER:
if excel_record:
    report.student_record = excel_record
    logger.debug(f"[VALIDATOR] Excel record: FOUND (pre-matched)")
else:
    student_record = self._find_student_record(ocr_fields)
    report.student_record = student_record
    if not excel_enrollment:
        report.enrollment_no = ocr_fields.get("enrollment_no", "")
        logger.debug(f"[VALIDATOR] Enrollment source: OCR (fallback) = {report.enrollment_no}")

    if not student_record:
        report.error = "No matching student record found in Excel"
        logger.warning(f"[VALIDATOR] No Excel record found for {pdf_name}")
        self._validate_fields_without_record(report, ocr_fields)
        return report
    excel_record = student_record
    logger.debug(f"[VALIDATOR] Excel record: FOUND (via fuzzy match)")
```

### Enhanced debug logging (Lines 114-120)
```python
# BEFORE:
logger.debug(
    f"{pdf_name}: {report.final_status} "
    f"(failed: {report.failed_fields})"
)

# AFTER:
logger.debug(
    f"[VALIDATOR] {pdf_name}: {report.final_status} "
    f"(fields: {[k for k, v in report.field_results.items() if not v.is_pass]})"
)
```

---

## 4. core/pdf_corrector.py - Multiple Sections

### Section A: Lines 208-213 - `build_corrections_dict()`

```python
# BEFORE:
def build_corrections_dict(self, validation_report) -> dict[str, str]:
    """Build corrections dict from a ValidationReport."""
    corrections = {}
    for field_name, field_result in validation_report.field_results.items():
        if field_result.needs_correction and field_result.correction_text:
            corrections[field_name] = field_result.correction_text
    return corrections

# AFTER:
def build_corrections_dict(self, validation_report) -> dict[str, str]:
    """Build corrections dict from a ValidationReport."""
    corrections = {}
    for field_name, field_result in validation_report.field_results.items():
        if field_result.needs_correction and field_result.correction_text:
            corrections[field_name] = field_result.correction_text
            logger.debug(f"[CORRECTOR] Will correct {field_name}: '{field_result.ocr_value}' → '{field_result.correction_text}'")
    return corrections
```

### Section B: Lines 114-127 - `correct_pdf()` save block

```python
# BEFORE:
try:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()
    logger.info(
        f"Corrected PDF saved: {output_path.name} "
        f"({corrections_applied} corrections)"
    )
    return True, corrections_applied, "OK"
except Exception as exc:
    doc.close()
    return False, corrections_applied, f"Save failed: {exc}"

# AFTER:
try:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path), garbage=4, deflate=True)
    doc.close()
    logger.info(
        f"[PDF_CORRECTOR] Corrected PDF saved: {output_path.name} "
        f"({corrections_applied} corrections applied)"
    )
    return True, corrections_applied, "OK"
except Exception as exc:
    doc.close()
    logger.error(f"[PDF_CORRECTOR] Failed to save corrected PDF: {exc}")
    return False, corrections_applied, f"Save failed: {exc}"
```

---

## 5. core/report_generator.py - Two Sections

### Section A: Line 68 - `add()` method

```python
# BEFORE:
def add(self, report) -> None:
    """Add one ValidationReport to the report."""
    row = self._report_to_row(report)
    self._rows.append(row)
    self._update_stats(report)

# AFTER:
def add(self, report) -> None:
    """Add one ValidationReport to the report."""
    row = self._report_to_row(report)
    self._rows.append(row)
    self._update_stats(report)
    logger.debug(f"[REPORT] Added: {report.pdf_name} → {report.final_status}")
```

### Section B: Lines 70-95 - `save()` method

```python
# BEFORE:
def save(self, output_dir: Path, filename: Optional[str] = None) -> Path:
    """Save the Excel report to output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = config.REPORT_FILENAME_TEMPLATE.format(timestamp=ts)

    output_path = output_dir / filename

    wb = openpyxl.Workbook()
    ws_detail = wb.active
    ws_detail.title = "Validation Results"

    self._write_detail_sheet(ws_detail)

    ws_summary = wb.create_sheet("Summary")
    self._write_summary_sheet(ws_summary)

    try:
        wb.save(str(output_path))
        logger.info(f"Report saved: {output_path}")
        return output_path
    except Exception as exc:
        logger.error(f"Failed to save report: {exc}")
        raise

# AFTER:
def save(self, output_dir: Path, filename: Optional[str] = None) -> Path:
    """Save the Excel report to output_dir."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = config.REPORT_FILENAME_TEMPLATE.format(timestamp=ts)

    output_path = output_dir / filename

    logger.debug(f"[REPORT] Generating Excel report with {len(self._rows)} records...")

    wb = openpyxl.Workbook()
    ws_detail = wb.active
    ws_detail.title = "Validation Results"

    self._write_detail_sheet(ws_detail)

    ws_summary = wb.create_sheet("Summary")
    self._write_summary_sheet(ws_summary)

    try:
        wb.save(str(output_path))
        logger.info(f"[REPORT] Excel report saved: {output_path}")
        logger.info(f"[REPORT] Summary: {self._stats['total']} total | {self._stats['pass']} pass | {self._stats['fail']} fail | {self._stats['error']} errors")
        return output_path
    except Exception as exc:
        logger.error(f"[REPORT] Failed to save report: {exc}")
        raise
```

---

## Summary of Changes

| Location | Type | Impact |
|----------|------|--------|
| ocr_engine.py line 211-253 | Priority reversal + keywords | Critical bug fix |
| processor.py line 267-374 | Debug logging | High visibility |
| validator.py line 66-117 | Enrollment tracking | High visibility |
| pdf_corrector.py line 208-213 | Correction logging | Medium visibility |
| pdf_corrector.py line 114-127 | Save logging | Medium visibility |
| report_generator.py line 68 | Add logging | Medium visibility |
| report_generator.py line 70-95 | Save logging | Medium visibility |

**Total lines changed:** ~120 lines across 5 files
**New logging statements:** 35+
**Breaking changes:** 0 (fully backwards compatible)

