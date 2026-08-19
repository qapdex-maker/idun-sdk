"""Document ingest for Idun Matrix (IDEA α / β).

Extracts plain text from uploaded documents so the retrieval layer can chunk it.
Tenant-agnostic, honest about dependencies: PDF parsing needs an optional extra
(`pip install "idun-sdk[pdf]"` -> PyPDF2). .txt/.md need no extra deps.

Functions:
    extract_text(path) -> str          # auto-detect by extension
    load_documents(dir_or_files) -> {name: text}
"""

import os
import glob


def _extract_txt(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_pdf(path):
    # Try PyPDF2 first (common, lightweight), then pdfminer.six (better layout).
    try:
        from PyPDF2 import PdfReader
        r = PdfReader(path)
        return "\n".join((p.extract_text() or "") for p in r.pages)
    except ImportError:
        pass
    try:
        from pdfminer.high_level import extract_text as _pm
        return _pm(path)
    except ImportError:
        raise RuntimeError(
            "PDF ingest requires an optional dependency: "
            "pip install 'idun-sdk[pdf]' (PyPDF2) or 'pdfminer.six'. "
            "Alternatively upload the document as .txt/.md."
        )


def extract_text(path):
    """Extract text from a file by extension. Raises on unsupported type."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md", ".text"):
        return _extract_txt(path)
    if ext == ".pdf":
        return _extract_pdf(path)
    raise ValueError(f"Unsupported document type: {ext} (use .txt/.md/.pdf)")


def load_documents(sources):
    """sources: a directory path, or a list of file paths.
    Returns {filename: text}. Skips unsupported types with a warning."""
    docs = {}
    if isinstance(sources, str):
        paths = sorted(glob.glob(os.path.join(sources, "*")))
    else:
        paths = list(sources)
    for p in paths:
        if not os.path.isfile(p):
            continue
        try:
            docs[os.path.basename(p)] = extract_text(p)
        except (ValueError, RuntimeError) as e:
            print(f"[ingest] skipped {p}: {e}")
    return docs
