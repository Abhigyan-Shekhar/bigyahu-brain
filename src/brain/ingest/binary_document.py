"""Bounded PDF/DOCX text extraction. Original bytes and extraction snapshots stay distinct."""

import io
import json
import sys
import zipfile
from pathlib import Path


def extract(raw, suffix):
    if not raw or len(raw) > 1_400_000:
        raise ValueError("Document must be under 1.4 MB")
    if suffix == ".pdf":
        from pypdf import PdfReader

        if not raw.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF header")
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or not 1 <= len(reader.pages) <= 50:
            raise ValueError("Use an unencrypted PDF with 1–50 pages")
        pages, total = [], 0
        for i, page in enumerate(reader.pages, 1):
            contents = page.get_contents()
            if contents:
                total += len(contents.get_data())
                if total > 10_000_000:
                    raise ValueError("PDF decoded content exceeds 10 MB")
            text = page.extract_text() or ""
            if not text.strip():
                raise ValueError("PDF has a page without extractable text; OCR is not supported")
            pages.append(f"# Page {i}\n{text}\n")
        text = "\n".join(pages)
        units = len(pages)
    elif suffix == ".docx":
        from docx import Document

        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(e.file_size for e in entries) > 10_000_000:
                raise ValueError("DOCX expanded archive exceeds bounds")
            if any(e.flag_bits & 1 or "vbaProject" in e.filename for e in entries):
                raise ValueError("Encrypted or macro-bearing Word files are unsupported")
        document = Document(io.BytesIO(raw))
        # iter_inner_content preserves paragraph/table order; cells remain explicit rows.
        from docx.text.paragraph import Paragraph

        lines = []
        for item in document.iter_inner_content():
            if isinstance(item, Paragraph):
                lines.append(item.text)
            else:
                lines.extend(" | ".join(cell.text for cell in row.cells) for row in item.rows)
        text, units = "\n".join(lines) + "\n", len(lines)
    else:
        raise ValueError("Only PDF and DOCX binary uploads are supported")
    if not text.strip() or len(text.encode()) > 500000 or "\0" in text:
        raise ValueError("Extracted text is empty or exceeds 500 KB")
    return {
        "text": text,
        "format": suffix[1:],
        "units": units,
        "extractor": "pypdf" if suffix == ".pdf" else "python-docx",
        "limitations": "Extracted text only; no OCR, images, layout fidelity, headers/footers or embedded attachments",
    }


def main():
    source, suffix, output = sys.argv[1:]
    Path(output).write_text(
        json.dumps(extract(Path(source).read_bytes(), suffix)), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
