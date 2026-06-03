# TROUBLESHOOTING QUICK REFERENCE

## Problem: PDF Processing Fails Silently

### Check These First
```bash
# 1. View the last error
tail -50 logs/app.log | grep -i error

# 2. Check enrollment extraction
grep "\[ENROLLMENT\]" logs/app.log | tail -5

# 3. Check Excel lookup
grep "\[EXCEL\]" logs/app.log | tail -5

# 4. Check if PDF exists
ls -la data/uploads/

# 5. Check output folders
ls -la data/corrected/
ls -la data/ocr_texts/
ls -la data/reports/
```

---

## Problem: Excel Record NOT Found

### Debug Steps
```bash
1. Get the enrollment that was extracted:
   grep "\[ENROLLMENT\]" logs/app.log | grep "Filename:"

2. Look up in Excel file manually
   - Is the enrollment number exact match? (case-sensitive for value lookup)
   - Check Excel column: "Enrollment Number" (exact name & case)

3. Verify Excel columns exist:
   - "Enrollment Number"
   - "Student Name"
   - "Course Name"
   - "OJT Period"
   - "Year"

4. Check for hidden rows/columns in Excel

5. If still not found:
   grep "\[EXCEL\]" logs/app.log
   Verify the enrollment shown is the one in your Excel file
```

### Common Cause
- Excel column name doesn't match exactly: `"Enrollment Number"` (check spaces, case)
- Enrollment number format in Excel is different (e.g., has leading zeros)
- Excel file is not saved or is corrupted

---

## Problem: Validation FAILS But Should PASS

### Check Field Scores
```bash
# View all field scores for a PDF
grep "\[FIELD\]" logs/app.log | grep "YOUR_PDF_NAME"

# Expected output:
[FIELD] student_name: PASS (score=92)
[FIELD] course_name: FAIL (score=45) → Corrected to '...'
```

### Scoring Rules
```
Score ≥ 80  → PASS ✓
Score 50-79 → FAIL (but no auto-correct)
Score < 50  → FAIL + AUTO CORRECT
```

### If Score is Low
1. **Check OCR quality**
   - View: `data/ocr_texts/{filename}_ocr.txt`
   - Is the OCR value badly corrupted?

2. **Check Excel value**
   - Is it correct in Excel?
   - Does it match what's in the PDF?

3. **Adjust threshold if needed**
   - Edit: `config.py`
   - Find: `FIELD_PASS_THRESHOLD`
   - Lower the threshold by 5-10% and retry

---

## Problem: Corrected PDF Not Generated

### Check These
```bash
1. Was validation FAIL or PASS?
   grep "\[VALIDATION\]" logs/app.log | tail -1
   
   If PASS: ✓ Correct! PDF is copied (no corrections needed)
   If FAIL: Check below

2. Were corrections built?
   grep "\[CORRECTOR\]" logs/app.log | grep "YOUR_PDF"
   
   If empty: No field failed enough to trigger correction
   If has content: Corrections were attempted

3. Was PDF actually saved?
   grep "\[PDF_CORRECTOR\]" logs/app.log | grep "YOUR_PDF"
   
   If "saved": ✓ Check data/corrected/ folder
   If "Failed": See error message

4. Check folder permissions
   ls -ld data/corrected/
   chmod 755 data/corrected/
```

### If Still Not Generated
```bash
# Try with test PDF manually
python app.py

# Check if ANY PDFs are corrected
ls -la data/corrected/

# If completely empty:
1. Check uploads folder exists: ls -la data/uploads/
2. Check PDF is valid: pdfinfo data/uploads/YOUR_FILE.pdf
3. Check PDF has ≥7 pages
4. Check PDF is not already corrupted
```

---

## Problem: Validation Report Not Generated

### Check This
```bash
1. Was processing completed?
   grep "Generating Excel report" logs/app.log
   
   If not found: Processing was cancelled or crashed

2. Check report file exists
   ls -la data/reports/
   
   If empty: Report generation failed

3. View report save logs
   grep "\[REPORT\]" logs/app.log
   
   Should see: "Excel report saved: /path/..."

4. Check folder permissions
   ls -ld data/reports/
   chmod 755 data/reports/
```

### If Report is Empty
```bash
1. Check if ANY PDFs were processed
   grep "\[PDF\] Loaded" logs/app.log | wc -l
   
   If 0: No PDFs were loaded

2. Check for processing errors
   grep "\[ERROR\]" logs/app.log

3. Check Excel file was loaded
   grep "Loading Excel" logs/app.log
```

---

## Problem: Enrollment Mismatch (Filename vs OCR)

### Debug Steps
```bash
# Find the mismatch
grep "\[ENROLLMENT\] Mismatch" logs/app.log

# Output will show:
[ENROLLMENT] Mismatch: Filename=DMCFSJU17090 vs OCR=DepartmentandJob
[ENROLLMENT] USING FILENAME (Priority 1)

# ✓ This is CORRECT behavior - filename is always used
```

### If This Happens Frequently
- OCR quality is poor
- PDF forms have unusual layouts
- Increase OCR image scaling: `config.py` → `OCR_IMAGE_SCALE = 3.0`

---

## Problem: Logs Are Hard to Read

### Filter by Category
```bash
# Only enrollment decisions
tail -100 logs/app.log | grep "\[ENROLLMENT\]"

# Only field validations
tail -100 logs/app.log | grep "\[FIELD\]"

# Only PDF corrections
tail -100 logs/app.log | grep "\[CORRECTION\]"

# Only errors
tail -100 logs/app.log | grep "\[ERROR\]"

# Complete flow for one PDF
tail -500 logs/app.log | grep "DMCFSJU17090"
```

### Save Filtered Logs
```bash
# Extract all corrections to file
grep "\[CORRECTION\]" logs/app.log > corrections.log

# Extract all failures
grep "\[VALIDATION\].*FAIL" logs/app.log > failures.log

# Extract all errors
grep "\[ERROR\]" logs/app.log > errors.log
```

---

## Problem: Processing is Slow

### Check Memory Usage
```bash
# While processing is running in another terminal
while true; do 
    ps aux | grep python
    free -h
    sleep 5
done
```

### If Memory is High
```bash
1. Reduce batch size in config.py
   BATCH_SIZE = 25  (was 50)

2. Reduce worker threads
   MAX_WORKER_THREADS = 2  (was 4)

3. Reduce OCR image scale
   OCR_IMAGE_SCALE = 1.0  (was 2.0)
```

### If CPU is High
- Normal: OCR is CPU-intensive
- Check if other processes are running
- Run on dedicated machine if possible

---

## Problem: PDF Corrections Look Wrong

### Check Generated PDF
```bash
1. Open in Adobe Reader (not browser)
   - Can corrupt display

2. Check corrections were applied
   grep "\[CORRECTOR\]" logs/app.log | grep "YOUR_PDF"
   
   Shows what was supposed to be corrected

3. Check fallback regions
   If correction looks out of place, check:
   config.py → FIELD_FALLBACK_REGIONS
   
   May need to adjust region coordinates

4. Check PDF is not image-based
   pdfimages -list data/corrected/YOUR_FILE.pdf
   
   If only images: Can't correct - use fallback region
```

### If Text Doesn't Show Up
```bash
1. Check font availability
   grep "\[CORRECTOR\]" logs/app.log
   
   Should use "helv" (Helvetica - built-in)

2. Check text color
   config.py → CORRECTION_TEXT_COLOR = (0, 0, 0)  # Black
   
   Should be black RGB values

3. Check PDF wasn't corrupted during save
   Try reopening: pdfinfo data/corrected/YOUR_FILE.pdf
```

---

## Quick Diagnostic Command

### Run This to Check Everything
```bash
#!/bin/bash
echo "=== OJT Checker Diagnostic ==="
echo ""
echo "1. Last errors:"
tail -10 logs/app.log | grep -i error
echo ""
echo "2. Last enrollments:"
tail -10 logs/app.log | grep "\[ENROLLMENT\]" | tail -3
echo ""
echo "3. Files in uploads:"
ls -la data/uploads/ | head -5
echo ""
echo "4. Files in corrected:"
ls -la data/corrected/ | head -5
echo ""
echo "5. Files in reports:"
ls -la data/reports/ | head -5
echo ""
echo "6. Last report generated:"
ls -lt data/reports/ | head -1
echo ""
echo "Done!"
```

---

## When All Else Fails

### Full Reset & Test
```bash
# 1. Backup current logs
cp logs/app.log logs/app.log.backup

# 2. Clear logs
> logs/app.log

# 3. Clear output
rm -f data/corrected/*
rm -f data/ocr_texts/*
rm -f data/reports/*

# 4. Add one test PDF
cp /path/to/test/AMULYA_DMCFSJU17090.pdf data/uploads/

# 5. Run processor
python app.py

# 6. Check logs
tail -100 logs/app.log

# 7. Verify outputs
ls -la data/corrected/
ls -la data/ocr_texts/
ls -la data/reports/
```

### If Still Failing
```bash
# Check Python environment
python --version

# Check dependencies
pip list | grep -E "easyocr|openpyxl|fitz|pandas|rapidfuzz"

# Check PDF is valid
pdfinfo data/uploads/YOUR_FILE.pdf

# Check Excel is valid
python -c "import pandas as pd; df = pd.read_excel('your_excel.xlsx'); print(df.columns.tolist())"
```

---

## Support Information

### When Reporting Issues
Include:
1. Last 50 lines of logs/app.log
2. Output of: `ls -la data/`
3. Output of: `python --version`
4. Output of: `pip list | grep -E "easy|openpyxl|fitz|pandas"`
5. PDF filename that fails
6. Expected vs actual behavior

### Key Logs to Provide
```bash
# Get key logs for issue report
echo "=== ENROLLMENT ===" > issue.log
grep "\[ENROLLMENT\]" logs/app.log >> issue.log
echo "" >> issue.log
echo "=== EXCEL ===" >> issue.log
grep "\[EXCEL\]" logs/app.log >> issue.log
echo "" >> issue.log
echo "=== ERRORS ===" >> issue.log
grep "\[ERROR\]" logs/app.log >> issue.log
echo "" >> issue.log
echo "=== LAST 20 LINES ===" >> issue.log
tail -20 logs/app.log >> issue.log
```

