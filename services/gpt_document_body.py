import os
from openai import OpenAI
from config import OPENAI_API_KEY
from services.document_examples_loader import load_document_examples
from services.document_prompts import DOCUMENT_PROMPTS

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

    example = load_document_examples(document_type)

    document_prompt = DOCUMENT_PROMPTS.get(document_type, "")

    prompt = f"""
Тип документа: {document_type}

Инструкция по написанию документа:
{document_prompt}

Специальная информация от юриста:
{user_text}

Контекст дела:
{context}

Материалы дела:
{materials}

Примеры аналогичных документов:
{example}

Напиши только основной текст документа,
который будет вставлен в шаблон.

Твоя задача выполнить работу в три шага.

ШАГ 1.
Кратко выдели юридически значимые обстоятельства дела
(что произошло, характер ДТП, поведение водителя, последствия).

ШАГ 2.
Определи нашу юридическую позицию защиты по делу
и основные аргументы, которые следует использовать.

ШАГ 3.
На основе этого напиши основной текст документа.

ВАЖНО:

Выведи только результат ШАГА 3 — текст документа

Не добавляй:
— заголовок документа
— реквизиты суда
— реквизиты ГИБДД
— подпись

Пиши только юридическую аргументацию.
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