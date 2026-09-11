# -*- coding: utf-8 -*-

import os
import re
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Cm

from config import CASES_FOLDER


BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

TEMPLATE = TEMPLATES_DIR / "dogovor_template_new.docx"
LOGO = TEMPLATES_DIR / "logo.png"
STAMP = TEMPLATES_DIR / "podpis_pechat.png"

LOGO_WIDTH_CM = 3.5
STAMP_WIDTH_CM = 4.5

MONTHS = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


_UNITS_M = [
    "",
    "один",
    "два",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
]

_UNITS_F = [
    "",
    "одна",
    "две",
    "три",
    "четыре",
    "пять",
    "шесть",
    "семь",
    "восемь",
    "девять",
]

_TEENS = [
    "десять",
    "одиннадцать",
    "двенадцать",
    "тринадцать",
    "четырнадцать",
    "пятнадцать",
    "шестнадцать",
    "семнадцать",
    "восемнадцать",
    "девятнадцать",
]

_TENS = [
    "",
    "",
    "двадцать",
    "тридцать",
    "сорок",
    "пятьдесят",
    "шестьдесят",
    "семьдесят",
    "восемьдесят",
    "девяносто",
]

_HUNDREDS = [
    "",
    "сто",
    "двести",
    "триста",
    "четыреста",
    "пятьсот",
    "шестьсот",
    "семьсот",
    "восемьсот",
    "девятьсот",
]


def _triad(n, feminine=False):
    units = _UNITS_F if feminine else _UNITS_M

    h = n // 100
    t = (n % 100) // 10
    u = n % 10

    words = []

    if h:
        words.append(_HUNDREDS[h])

    if t == 1:
        words.append(_TEENS[u])
    else:
        if t:
            words.append(_TENS[t])

        if u:
            words.append(units[u])

    return " ".join(words)


def _plural(n, forms):
    n = n % 100

    if 11 <= n <= 19:
        return forms[2]

    n %= 10

    if n == 1:
        return forms[0]

    if 2 <= n <= 4:
        return forms[1]

    return forms[2]


def amount_in_words(value):
    n = int(re.sub(r"[^\d]", "", str(value)) or 0)

    if n == 0:
        return "ноль"

    parts = []

    millions, rest = divmod(n, 1_000_000)
    thousands, units = divmod(rest, 1000)

    if millions:
        parts.append(
            _triad(millions)
            + " "
            + _plural(
                millions,
                ("миллион", "миллиона", "миллионов"),
            )
        )

    if thousands:
        parts.append(
            _triad(thousands, feminine=True)
            + " "
            + _plural(
                thousands,
                ("тысяча", "тысячи", "тысяч"),
            )
        )

    if units:
        parts.append(_triad(units))

    return " ".join(parts)


def format_amount(value):
    n = int(re.sub(r"[^\d]", "", str(value)) or 0)
    return f"{n:,}".replace(",", " ")


def parse_client_data(case):
    path = Path(CASES_FOLDER) / case / "passport" / "client_data.txt"

    data = {}

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()

    return data


def make_signature(fio):
    parts = fio.split()

    if len(parts) < 3:
        return fio

    return f"{parts[0]} {parts[1][0]}.{parts[2][0]}."


PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")


def _replace_in_paragraph(paragraph, replacements, images):
    full_text = "".join(run.text for run in paragraph.runs)

    if "{{" not in full_text:
        return

    stripped = full_text.strip()

    if stripped in images:
        path, width_cm = images[stripped]

        if not paragraph.runs:
            return

        for run in paragraph.runs:
            run.text = ""

        if path.exists():
            paragraph.runs[0].add_picture(
                str(path),
                width=Cm(width_cm),
            )

        return

    new_text = full_text

    for key, value in replacements.items():
        new_text = new_text.replace(key, str(value))

    if new_text == full_text:
        return

    if not paragraph.runs:
        return

    first_run = paragraph.runs[0]

    for run in paragraph.runs[1:]:
        run.text = ""

    lines = new_text.split("\n")

    first_run.text = lines[0]

    for line in lines[1:]:
        first_run.add_break()
        first_run.add_text(line)


def _iter_paragraphs(doc):
    for paragraph in doc.paragraphs:
        yield paragraph

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    yield paragraph

    for section in doc.sections:
        parts = (
            section.header,
            section.footer,
            section.first_page_header,
            section.first_page_footer,
        )

        for part in parts:
            for paragraph in part.paragraphs:
                yield paragraph

            for table in part.tables:
                for row in table.rows:
                    for cell in row.cells:
                        for paragraph in cell.paragraphs:
                            yield paragraph


def fill_template(template_path, out_path, replacements, images):
    doc = Document(str(template_path))

    for paragraph in _iter_paragraphs(doc):
        _replace_in_paragraph(
            paragraph,
            replacements,
            images,
        )

    doc.save(str(out_path))

    leftover = set()

    check_doc = Document(str(out_path))

    for paragraph in _iter_paragraphs(check_doc):
        text = "".join(run.text for run in paragraph.runs)
        leftover.update(PLACEHOLDER_RE.findall(text))

    return leftover


def _find_soffice():
    soffice = shutil.which("soffice")

    if soffice:
        return soffice

    fallback_paths = [
        "/usr/local/bin/soffice",
        "/usr/bin/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]

    for path in fallback_paths:
        if os.path.exists(path):
            return path

    raise FileNotFoundError("LibreOffice / soffice не найден")


def generate_contract(case, services_text, price, spec_number=1):
    data = parse_client_data(case)

    now = datetime.now()

    case_folder = Path(CASES_FOLDER) / case
    case_folder.mkdir(parents=True, exist_ok=True)

    number_file = case_folder / "contract_number.txt"

    if number_file.exists():
        number = number_file.read_text(
            encoding="utf-8"
        ).strip()
    else:
        number = str(random.randint(10000, 99999))

        number_file.write_text(
            number,
            encoding="utf-8",
        )

    replacements = {
        "{{Номер_договора}}": number,
        "{{Номер_спецификации}}": str(spec_number),
        "{{День}}": str(now.day),
        "{{Месяц}}": MONTHS[now.month],
        "{{Год}}": str(now.year),

        "{{ФИО}}": data["ФИО"],
        "{{Пол}}": data.get("Пол", ""),
        "{{Дата_рождения}}": data["Дата рождения"],
        "{{Место_рождения}}": data.get("Место рождения", ""),

        "{{Серия}}": data["Серия"],
        "{{Номер}}": data["Номер"],

        "{{Дата_выдачи}}": data["Дата выдачи"],
        "{{Кем_выдан}}": data["Кем выдан"],

        "{{Код_подразделения}}": data["Код подразделения"],
        "{{Адрес_регистрации}}": data["Адрес регистрации"],

        "{{Email}}": data["Email"],
        "{{Телефон}}": data["Телефон"],

        "{{Перечень_услуг}}": services_text.strip(),

        "{{Стоимость}}": format_amount(price),
        "{{Стоимость_прописью}}": amount_in_words(price),

        "{{ФИО_подпись}}": make_signature(data["ФИО"]),
    }

    images = {
        "{{Логотип}}": (
            LOGO,
            LOGO_WIDTH_CM,
        ),

        "{{Подпись_печать}}": (
            STAMP,
            STAMP_WIDTH_CM,
        ),
    }

    if not TEMPLATE.exists():
        raise FileNotFoundError(
            f"Шаблон договора не найден: {TEMPLATE}"
        )

    docx_path = case_folder / f"договор {case}.docx"

    leftover = fill_template(
        TEMPLATE,
        docx_path,
        replacements,
        images,
    )

    if leftover:
        raise ValueError(
            f"В договоре остались незаполненные поля: {sorted(leftover)}"
        )

    soffice = _find_soffice()

    subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(case_folder),
            str(docx_path),
        ],
        check=True,
    )

    pdf_path = case_folder / f"договор {case}.pdf"

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF не был создан: {pdf_path}"
        )

    return str(docx_path), str(pdf_path)