"""
document_utils.py — Extract text from uploaded study materials.
"""

from pypdf import PdfReader


def extract_text(uploaded_file):
    """Takes a Streamlit UploadedFile and returns its text content."""
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        return _extract_pdf(uploaded_file)
    if name.endswith((".txt", ".md")):
        return uploaded_file.read().decode("utf-8", errors="ignore")

    raise ValueError(f"Unsupported file type: {name}. Use PDF, TXT, or MD.")


def _extract_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    parts = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text and page_text.strip():
            parts.append(page_text)

    if not parts:
        raise ValueError("No text found in this PDF. It may be scanned/image-based.")
    return "\n\n".join(parts)
