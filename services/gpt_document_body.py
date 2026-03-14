import os
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


SYSTEM_PROMPT = """
Ты опытный юрист, который специализируется на защите водителей по делам
об административном правонарушении, предусмотренном ч.2 ст.12.27 КоАП РФ
(оставление места ДТП).

Ты пишешь юридические документы:

— ходатайства
— объяснительные
— правовые позиции
— судебные речи
— жалобы

Требования:

1. Текст должен быть юридически грамотным.
2. Стиль — официальный, судебный.
3. Не использовать разговорные выражения.
4. Аргументы должны выглядеть убедительно.
5. Используй структуру юридического документа.


Если информации мало — аккуратно сформулируй аргументы,
не выдумывая фактов.
"""


def read_file(path):

    if not os.path.exists(path):
        return ""

    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def generate_document_body(case, document_type, user_text):

    base = f"cases/{case}"

    materials = read_file(f"{base}/materials_text.txt")

    context = read_file(f"{base}/case_context.txt")

    example = ""

    example_path = f"knowledge_documents/{document_type}.txt"

    if os.path.exists(example_path):

        example = read_file(example_path)

    prompt = f"""
Тип документа: {document_type}

Специальная информация от юриста:
{user_text}

Контекст дела:
{context}

Материалы дела:
{materials}

Пример аналогичного документа:
{example}

Напиши только основной текст документа,
который должен быть вставлен в шаблон.

Не добавляй заголовков и реквизитов.
Не пиши "ХОДАТАЙСТВО" или "В мировой суд".
Напиши только аргументацию.
"""

    response = client.chat.completions.create(

        model="gpt-4.1",

        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],

        temperature=0.4
    )

    return response.choices[0].message.content.strip()