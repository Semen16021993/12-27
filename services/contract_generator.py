# -*- coding: utf-8 -*-

import os
import re
import random
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from config import CASES_FOLDER


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

TEMPLATE = TEMPLATES_DIR / "dogovor_template_new.docx"
LOGO = TEMPLATES_DIR / "logo.png"
STAMP = TEMPLATES_DIR / "podpis_pechat.png"


# ============================================================
# IMAGE SETTINGS
# ============================================================

# Логотип в шапке.
# Если после теста захочется чуть больше/меньше —
# меняем только эту цифру.
LOGO_WIDTH_CM = 5.2

# Факсимиле / печать.
STAMP_WIDTH_CM = 6.1


# ============================================================
# DATE
# ============================================================

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


# ============================================================
# AMOUNT IN WORDS
# ============================================================

_UNITS_M = [
    "", "один", "два", "три", "четыре",
    "пять", "шесть", "семь", "восемь", "девять",
]

_UNITS_F = [
    "", "одна", "две", "три", "четыре",
    "пять", "шесть", "семь", "восемь", "девять",
]

_TEENS = [
    "десять", "одиннадцать", "двенадцать", "тринадцать",
    "четырнадцать", "пятнадцать", "шестнадцать",
    "семнадцать", "восемнадцать", "девятнадцать",
]

_TENS = [
    "", "", "двадцать", "тридцать", "сорок",
    "пятьдесят", "шестьдесят", "семьдесят",
    "восемьдесят", "девяносто",
]

_HUNDREDS = [
    "", "сто", "двести", "триста", "четыреста",
    "пятьсот", "шестьсот", "семьсот",
    "восемьсот", "девятьсот",
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


# ============================================================
# CLIENT DATA
# ============================================================

def parse_client_data(case):
    path = (
        Path(CASES_FOLDER)
        / case
        / "passport"
        / "client_data.txt"
    )

    if not path.exists():
        raise FileNotFoundError(
            f"Файл данных клиента не найден: {path}"
        )

    data = {}

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()

    return data


# ============================================================
# DOCUMENT ITERATION
# ============================================================

def make_short_name(fio):
    parts = fio.split()

    if len(parts) < 3:
        return fio

    surname = parts[0]
    name_initial = parts[1][0]
    patronymic_initial = parts[2][0]

    return f"{surname} {name_initial}.{patronymic_initial}"

def _iter_paragraphs(doc):
    """
    Возвращает все абзацы:
    - основной текст;
    - таблицы;
    - header/footer.
    """

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


# ============================================================
# TEXT REPLACEMENT
# ============================================================

def _replace_text_in_runs(paragraph, replacements):
    """
    Главная разница со старой функцией:

    НЕ собираем абзац заново.
    НЕ переносим весь текст в первый run.

    Меняем плейсхолдер прямо внутри существующего run,
    поэтому Word сохраняет всё его форматирование.
    """

    for run in paragraph.runs:

        if "{{" not in run.text:
            continue

        text = run.text

        for placeholder, value in replacements.items():

            if placeholder in text:
                text = text.replace(
                    placeholder,
                    str(value),
                )

        run.text = text


# ============================================================
# INLINE LOGO
# ============================================================

def _insert_inline_image(paragraph, image_path, width_cm):
    """
    Для логотипа.

    Логотип находится в header и должен вести себя
    как обычный элемент строки.
    """

    if not image_path.exists():
        raise FileNotFoundError(
            f"Изображение не найдено: {image_path}"
        )

    # очищаем только плейсхолдер
    for run in paragraph.runs:
        run.text = run.text.replace("{{Логотип}}", "")

    if paragraph.runs:
        run = paragraph.runs[0]
    else:
        run = paragraph.add_run()

    run.add_picture(
        str(image_path),
        width=Cm(width_cm),
    )


# ============================================================
# FLOATING IMAGE
# ============================================================

def _inline_to_anchor(inline, x_cm=0.0, y_cm=0.0):
    """
    Превращаем обычную inline-картинку Word
    в плавающую картинку.

    Она перестает раздвигать текст и может лежать
    поверх строки подписи.
    """

    inline_xml = inline._inline

    extent = inline_xml.extent
    doc_pr = inline_xml.docPr
    graphic = inline_xml.graphic

    cx = extent.cx
    cy = extent.cy

    anchor = OxmlElement("wp:anchor")

    anchor.set("distT", "0")
    anchor.set("distB", "0")
    anchor.set("distL", "0")
    anchor.set("distR", "0")

    anchor.set("simplePos", "0")
    anchor.set("relativeHeight", "251659264")
    anchor.set("behindDoc", "1")
    anchor.set("locked", "0")
    anchor.set("layoutInCell", "1")
    anchor.set("allowOverlap", "1")

    simple_pos = OxmlElement("wp:simplePos")
    simple_pos.set("x", "0")
    simple_pos.set("y", "0")
    anchor.append(simple_pos)

    position_h = OxmlElement("wp:positionH")
    position_h.set("relativeFrom", "column")

    pos_h = OxmlElement("wp:posOffset")
    pos_h.text = str(int(Cm(x_cm)))
    position_h.append(pos_h)

    anchor.append(position_h)

    position_v = OxmlElement("wp:positionV")
    position_v.set("relativeFrom", "paragraph")

    pos_v = OxmlElement("wp:posOffset")
    pos_v.text = str(int(Cm(y_cm)))
    position_v.append(pos_v)

    anchor.append(position_v)

    extent_new = OxmlElement("wp:extent")
    extent_new.set("cx", str(cx))
    extent_new.set("cy", str(cy))
    anchor.append(extent_new)

    effect_extent = OxmlElement("wp:effectExtent")
    effect_extent.set("l", "0")
    effect_extent.set("t", "0")
    effect_extent.set("r", "0")
    effect_extent.set("b", "0")
    anchor.append(effect_extent)

    wrap_none = OxmlElement("wp:wrapNone")
    anchor.append(wrap_none)

    anchor.append(doc_pr)

    c_nv_graphic_frame_pr = OxmlElement(
        "wp:cNvGraphicFramePr"
    )

    graphic_frame_locks = OxmlElement(
        "a:graphicFrameLocks"
    )
    graphic_frame_locks.set("noChangeAspect", "1")

    c_nv_graphic_frame_pr.append(
        graphic_frame_locks
    )

    anchor.append(c_nv_graphic_frame_pr)

    anchor.append(graphic)

    parent = inline_xml.getparent()
    parent.replace(inline_xml, anchor)


def _remove_paragraph(paragraph):
    """
    Полностью удаляет технический абзац
    {{Подпись_печать}} из документа.
    """

    element = paragraph._element
    parent = element.getparent()

    if parent is not None:
        parent.remove(element)


def _insert_floating_stamp_on_signature(paragraph):
    """
    Вставляет факсимиле непосредственно в абзац:

    _______________ / Верескунов С.А. /

    Картинка становится плавающей и располагается
    ПОВЕРХ текста, не раздвигая строку подписи.
    """

    if not STAMP.exists():
        raise FileNotFoundError(
            f"Факсимиле не найдено: {STAMP}"
        )

    # Добавляем технический пустой run
    # непосредственно в строку подписи.
    run = paragraph.add_run()

    inline_shape = run.add_picture(
        str(STAMP),
        width=Cm(STAMP_WIDTH_CM),
    )

    # Позиция относительно строки подписи.
    #
    # x_cm — вправо от левого края текстовой области.
    # y_cm — вверх относительно самой строки подписи.
    #
    # Картинка при этом лежит ПОВЕРХ текста.
    _inline_to_anchor(
        inline_shape,
        x_cm=0.55,
        y_cm=-1.75,
    )

# ============================================================
# PLACEHOLDER CHECK
# ============================================================

PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")

def fill_template(
    template_path,
    out_path,
    replacements,
):
    doc = Document(str(template_path))

    # Фиксируем список абзацев заранее.
    # Он нужен в том числе для поиска строки подписи
    # после {{Подпись_печать}}.
    paragraphs = list(_iter_paragraphs(doc))

    stamp_markers = []

    for paragraph in paragraphs:

        full_text = "".join(
            run.text
            for run in paragraph.runs
        )

        # --------------------------------
        # LOGO
        # --------------------------------

        if "{{Логотип}}" in full_text:

            _insert_inline_image(
                paragraph,
                LOGO,
                LOGO_WIDTH_CM,
            )

            continue

        # --------------------------------
        # STAMP MARKER
        # --------------------------------

        if "{{Подпись_печать}}" in full_text:

            # Ничего сюда больше не вставляем.
            # Просто запоминаем положение маркера.
            stamp_markers.append(paragraph)

            continue

        # --------------------------------
        # NORMAL TEXT
        #
        # ВАЖНО:
        # сюда же попадает {{Перечень_услуг}}.
        #
        # Он заменяется ровно тем же способом,
        # каким работал старый генератор.
        # --------------------------------

        _replace_text_in_runs(
            paragraph,
            replacements,
        )

    # ========================================================
    # FACSIMILE
    # ========================================================

    for marker in stamp_markers:

        try:
            marker_index = paragraphs.index(marker)
        except ValueError:
            continue

        signature_paragraph = None

        # Ищем первую строку подписи после конкретного маркера.
        for candidate in paragraphs[marker_index + 1:]:

            candidate_text = "".join(
                run.text
                for run in candidate.runs
            )

            if "Верескунов С.А." in candidate_text:
                signature_paragraph = candidate
                break

        if signature_paragraph is None:
            raise ValueError(
                "После {{Подпись_печать}} "
                "не найдена строка подписи "
                "Верескунов С.А."
            )

        # Вставляем картинку НЕ в marker,
        # а непосредственно в строку подписи.
        _insert_floating_stamp_on_signature(
            signature_paragraph
        )

    # После того как картинки уже привязаны
    # к строкам подписи, полностью удаляем
    # технические абзацы {{Подпись_печать}}.
    for marker in stamp_markers:
        _remove_paragraph(marker)

    # ========================================================
    # SAVE
    # ========================================================

    doc.save(str(out_path))

    # ========================================================
    # LEFTOVER PLACEHOLDERS CHECK
    # ========================================================

    leftover = set()

    check_doc = Document(str(out_path))

    for paragraph in _iter_paragraphs(check_doc):

        text = "".join(
            run.text
            for run in paragraph.runs
        )

        leftover.update(
            PLACEHOLDER_RE.findall(text)
        )

    return leftover


# ============================================================
# LIBREOFFICE
# ============================================================

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

    raise FileNotFoundError(
        "LibreOffice / soffice не найден"
    )


# ============================================================
# MAIN GENERATOR
# ============================================================

def generate_contract(
    case,
    services_text,
    price,
    spec_number=1,
):

    data = parse_client_data(case)
    short_name = make_short_name(data["ФИО"])

    now = datetime.now()

    case_folder = (
        Path(CASES_FOLDER)
        / case
    )

    case_folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -----------------------------
    # CONTRACT NUMBER
    # -----------------------------

    number_file = (
        case_folder
        / "contract_number.txt"
    )

    if number_file.exists():

        number = number_file.read_text(
            encoding="utf-8"
        ).strip()

    else:

        number = str(
            random.randint(
                10000,
                99999,
            )
        )

        number_file.write_text(
            number,
            encoding="utf-8",
        )

    # -----------------------------
    # REPLACEMENTS
    # -----------------------------

    replacements = {

        "{{Номер_договора}}":
            number,

        "{{Номер_спецификации}}":
            str(spec_number),

        "{{День}}":
            str(now.day),

        "{{Месяц}}":
            MONTHS[now.month],

        "{{Год}}":
            str(now.year),

        "{{ФИО}}":
            data["ФИО"],

        "{{Пол}}":
            data.get("Пол", ""),

        "{{Дата_рождения}}":
            data["Дата рождения"],

        "{{Место_рождения}}":
            data.get(
                "Место рождения",
                "",
            ),

        "{{Серия}}":
            data["Серия"],

        "{{Номер}}":
            data["Номер"],

        "{{Дата_выдачи}}":
            data["Дата выдачи"],

        "{{Кем_выдан}}":
            data["Кем выдан"],

        "{{Код_подразделения}}":
            data["Код подразделения"],

        "{{Адрес_регистрации}}":
            data["Адрес регистрации"],

        "{{Email}}":
            data["Email"],

        "{{Телефон}}":
            data["Телефон"],

        "{{Перечень_услуг}}":
            services_text.strip(),

        "{{Стоимость}}":
            format_amount(price),

        "{{Стоимость_прописью}}":
            amount_in_words(price),
    }

    # -----------------------------
    # TEMPLATE
    # -----------------------------

    if not TEMPLATE.exists():
        raise FileNotFoundError(
            f"Шаблон договора не найден: {TEMPLATE}"
        )

    # -----------------------------
    # DOCX
    # -----------------------------

    docx_path = (
        case_folder
        / f"Договор {short_name}.docx"
    )

    leftover = fill_template(
        TEMPLATE,
        docx_path,
        replacements,
    )

    if leftover:
        raise ValueError(
            "В договоре остались "
            f"незаполненные поля: "
            f"{sorted(leftover)}"
        )

    # -----------------------------
    # PDF
    # -----------------------------

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

    pdf_path = (
        case_folder
        / f"Договор {short_name}.pdf"
    )

    if not pdf_path.exists():
        raise FileNotFoundError(
            f"PDF не был создан: "
            f"{pdf_path}"
        )

    return (
        str(docx_path),
        str(pdf_path),
    )