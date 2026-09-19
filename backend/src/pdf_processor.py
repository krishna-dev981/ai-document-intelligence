from pypdf import PdfReader


def extract_text(pdf_file):
    reader = PdfReader(pdf_file)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": page_number, "text": text})

    return pages


def create_chunks(pages, filename, chunk_size=800, overlap=150):
    chunks = []
    step = max(1, chunk_size - overlap)

    for page in pages:
        text = page["text"]

        for start in range(0, len(text), step):
            chunk = text[start:start + chunk_size].strip()

            if chunk:
                chunks.append({
                    "filename": filename,
                    "page": page["page"],
                    "text": chunk,
                })

    return chunks
