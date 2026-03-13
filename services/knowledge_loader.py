from docx import Document


def load_knowledge():

    doc = Document("knowledge/knowledge_base.docx")

    text = []

    for paragraph in doc.paragraphs:

        if paragraph.text.strip():
            text.append(paragraph.text)

    return "\n".join(text)