import os
from docx import Document


def load_document_examples(document_type):

    folder = f"knowledge_documents/{document_type}"

    if not os.path.exists(folder):
        return ""

    examples = []

    for file in sorted(os.listdir(folder)):

        if not file.endswith(".docx"):
            continue

        path = os.path.join(folder, file)

        try:

            doc = Document(path)

            text = []

            for p in doc.paragraphs:
                if p.text.strip():
                    text.append(p.text)

            examples.append("\n".join(text))

        except Exception as e:
            print("Ошибка чтения примера:", path, e)

    if not examples:
        return ""

    result = ""

    for i, example in enumerate(examples, 1):

        result += f"\n\nПРИМЕР ДОКУМЕНТА {i}\n"
        result += "----------------------\n"
        result += example

    return result