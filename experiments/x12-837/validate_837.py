"""Validate X12 files with pyx12 (005010X222A1 map shipped with pyx12) and print errors.

  <venv>/bin/python validate_837.py out/*.x12
The x12valid CLI in pyx12 2.3.3 crashes on Python 3.9 while writing its 999 output (str vs bytes),
so this calls the library with no 999/HTML output. pyx12 checks segment syntax, loop structure,
required elements, element lengths and some code lists. It does not check whether an ICD-10-CM
or CPT code exists, so a SNOMED number in HI passes (see the control files)."""
import io
import logging
import sys

import pyx12.params
import pyx12.x12n_document

for path in sys.argv[1:]:
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setLevel(logging.ERROR)
    log = logging.getLogger("pyx12")
    log.handlers = [h]
    log.setLevel(logging.ERROR)
    ok = pyx12.x12n_document.x12n_document(pyx12.params.params(), path, None, None)
    errs = [l for l in buf.getvalue().splitlines() if l.strip()]
    print(f"{path}: {'OK' if ok else 'FAILURE'} ({len(errs)} error lines)")
    for l in errs[:10]:
        print("   ", l[:200])
