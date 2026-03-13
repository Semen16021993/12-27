from pypdf import PdfReader


def read_pdf(file_path):

    text = ""

    try:
        reader = PdfReader(file_path)

        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text

    except Exception:
        return ""

    return text