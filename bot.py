from dotenv import load_dotenv
load_dotenv()
from services.contract_generator import generate_contract
from services.document_generator import generate_document
from services.document_registry import DOCUMENTS
from services.questionnaire_parser import parse_questionnaire
from services.instances_parser import update_instances
from services.case_context_builder import build_case_context
from services.materials_ocr import ocr_image
from services.materials_processor import process_material
from services.pdf_reader import read_pdf

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from utils.document_type_keyboard import document_type_keyboard
from utils.motion_keyboard import motion_keyboard
from utils.other_documents_keyboard import other_documents_keyboard
from config import TELEGRAM_TOKEN, OPENAI_API_KEY
from utils.keyboard import main_keyboard
from utils.passport_keyboard import passport_confirm_keyboard
from openai import OpenAI
from pypdf import PdfReader

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import os
import base64
import uuid


client = OpenAI(api_key=OPENAI_API_KEY)


# регистрируем шрифт один раз
pdfmetrics.registerFont(
    TTFont(
        "TimesNewRoman",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
    )
)


# -----------------------------------
# чтение PDF
# -----------------------------------

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


# -----------------------------------
# создание PDF
# -----------------------------------

def create_pdf(text, case_name):

    file_name = f"document_{uuid.uuid4().hex}.pdf"

    folder = f"cases/{case_name}"

    os.makedirs(folder, exist_ok=True)

    path = f"{folder}/{file_name}"

    c = canvas.Canvas(path)

    c.setFont("TimesNewRoman", 12)

    y = 800

    for line in text.split("\n"):

        c.drawString(50, y, line)

        y -= 20

        if y < 50:

            c.showPage()
            c.setFont("TimesNewRoman", 12)
            y = 800

    c.save()

    return path


# -----------------------------------
# OCR через GPT Vision
# -----------------------------------

def parse_passport_from_images(image_paths):

    images = []

    for path in image_paths:

        with open(path, "rb") as img:

            base64_image = base64.b64encode(img.read()).decode("utf-8")

        images.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "high"
                }
            }
        )

    response = client.chat.completions.create(

        model="gpt-4o-mini",
        temperature=0,


        messages=[
            {
                "role": "system",
                "content": """
            Ты система распознавания российских паспортов.

            Из изображений извлеки данные и верни строго в формате:

            ФИО:
            Пол:
            Дата рождения:
            Место рождения:
            Серия:
            Номер:
            Кем выдан:
            Дата выдачи:
            Код подразделения:
            Адрес регистрации:

            ВАЖНО:

            Не используй капслок.

            Форматируй текст нормально:

            ФИО — Каждое слово с большой буквы
            пример: Псов Алексей Олегович

            Пол — Муж / Жен

            Адрес — обычный текст
            пример: ул. Мира, дом 10, кв. 5, г. Москва

            Органы выдачи — обычный регистр
            пример: Управлением внутренних дел г. Южно-Сахалинска
            """
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Извлеки данные паспорта"},
                    *images
                ]
            }
        ]
    )

    return response.choices[0].message.content



# -----------------------------------
# обработка сообщений
# -----------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "AI Lawyer запущен. Выберите действие:",
        reply_markup=main_keyboard()
    )

# -----------------------------------
# нормализация контактов
# -----------------------------------

def normalize_contacts(text):

    response = client.chat.completions.create(

        model="gpt-4o-mini",
        temperature=0,

        messages=[
            {
                "role": "system",
                "content": """
Из текста извлеки email и телефон.

Верни строго в формате:

Email:
Телефон:

Телефон приведи к формату:
+7 XXX XXX XXXX
"""
            },
            {
                "role": "user",
                "content": text
            }
        ]
    )

    return response.choices[0].message.content


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not update.message or not update.message.text:
        return

    user_text = update.message.text.lower().strip()


    # -----------------------------------
    # подтверждение паспорта
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_PASSPORT_CONFIRM":

        if user_text.lower() == "подтверждаю":

            context.user_data["state"] = "WAIT_CONTACT"

            await update.message.reply_text(
                "Введите телефон и email клиента\n"
                "Можно в свободной форме",
                reply_markup=ReplyKeyboardRemove()
            )

            return


        if user_text == "исправить":

            context.user_data["state"] = "WAIT_CORRECTION"

            await update.message.reply_text(
                "Напишите что нужно исправить"
            )

            return


    # -----------------------------------
    # исправление данных паспорта
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_CORRECTION":

        correction = update.message.text

        passport_data = context.user_data.get("passport_data", "")

        response = client.chat.completions.create(

            model="gpt-4o-mini",
            temperature=0,
    
            messages=[
                {
                    "role": "system",
                    "content": """
                Ты редактор данных российского паспорта.

                Тебе дан список паспортных данных.
                Пользователь пишет исправление в свободной форме.

                Примеры:
                правильная фамилия Иванов
                номер паспорта 123456
                исправь дату рождения на 12.03.1985

                Твоя задача:
                1. Понять какое поле нужно изменить
                2. Изменить только это поле
                3. Остальные данные оставить без изменений

                Верни строго в формате:

                ФИО:
                Пол:
                Дата рождения:
                Место рождения:
                Серия:
                Номер:
                Кем выдан:
                Дата выдачи:
                Код подразделения:
                Адрес регистрации:
                """
                }
                ,
                {
                    "role": "user",
                    "content": f"""
Данные паспорта:

{passport_data}

Исправление:

{correction}
"""
                }
            ]
        )

        new_data = response.choices[0].message.content

        context.user_data["passport_data"] = new_data
        context.user_data["state"] = "WAIT_PASSPORT_CONFIRM"

        await update.message.reply_text(
            f"Обновленные данные:\n\n{new_data}",
            reply_markup=passport_confirm_keyboard()
        )

        return


    # -----------------------------------
    # получение контактов
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_CONTACT":

        contacts = normalize_contacts(update.message.text)

        passport_data = context.user_data.get("passport_data")

        final_data = f"""
{passport_data}

{contacts}
"""

        case = context.user_data.get("case")

        path = f"cases/{case}/passport/client_data.txt"

        with open(path, "w", encoding="utf-8") as f:
            f.write(final_data)

        context.user_data["state"] = None
        build_case_context(case)

        await update.message.reply_text(
            f"Данные клиента сохранены:\n\n{final_data}",
            reply_markup=main_keyboard()
        )

        return


    # -----------------------------------
    # создать клиента
    # -----------------------------------

    if user_text == "создать клиента":

        context.user_data["state"] = "WAIT_CLIENT_NAME"

        await update.message.reply_text(
            "Введите ФИО клиента\n"
            "(достаточно фамилии)"
        )

        return


    # -----------------------------------
    # ввод имени клиента
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_CLIENT_NAME":

        case_name = update.message.text.strip()

        path = f"cases/{case_name}"

        os.makedirs(path, exist_ok=True)
        os.makedirs(f"{path}/passport", exist_ok=True)
        os.makedirs(f"{path}/materials", exist_ok=True)
        os.makedirs(f"{path}/defense", exist_ok=True)

        context.user_data["case"] = case_name
        context.user_data["state"] = None

        await update.message.reply_text(
            f"Клиент создан: {case_name}",
            reply_markup=main_keyboard()
        )

        return


    # -----------------------------------
    # загрузка паспорта
    # -----------------------------------

    if user_text == "паспорт":

        case = context.user_data.get("case")

        if case is None:

            await update.message.reply_text(
                "Сначала создайте клиента"
            )
            return

        context.user_data["state"] = "WAIT_PASSPORT"
        context.user_data["passport_images"] = []

        await update.message.reply_text(
            "Пришлите 2 фотографии паспорта:\n"
            "1️⃣ главная страница\n"
            "2️⃣ страница с пропиской"
        )

        return

    # -----------------------------------
    # загрузка опросника
    # -----------------------------------

    if user_text == "данные опросника":

        context.user_data["state"] = "WAIT_QUESTIONNAIRE"

        await update.message.reply_text(
            "Пришлите XLSX файл опросника"
        )

        return

    # -----------------------------------
    # данные гибдд и суда
    # -----------------------------------

    if user_text == "данные гибдд и суда":

        context.user_data["state"] = "WAIT_INSTANCES"

        await update.message.reply_text(
            "Введите название и адрес ГИБДД или суда"
        )

        return
    
    # -----------------------------------
    # проверяем выбран ли клиент
    # -----------------------------------

    case = context.user_data.get("case")

    if case is None:

        await update.message.reply_text(
            "Сначала создайте клиента"
        )

        return

    folder = f"cases/{case}"

    os.makedirs(folder, exist_ok=True)


    # -----------------------------------
    # обработка данных гибдд и суда
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_INSTANCES":

        result = update_instances(folder, update.message.text)
        build_case_context(case)    

        await update.message.reply_text(result)

        context.user_data["state"] = None

        return

    # -----------------------------------
    # анализ материалов
    # -----------------------------------

    if "посмотри материалы" in user_text:

        materials_folder = f"cases/{case}/materials"

        if not os.path.exists(materials_folder):
            await update.message.reply_text("Материалы дела отсутствуют.")
            return

        texts = []

        files = os.listdir(materials_folder)

        for file in files:

            path = f"{materials_folder}/{file}"

            if file.lower().endswith(".pdf"):

                text = read_pdf(path)

                if text:
                    texts.append(text)

            if file.lower().endswith((".jpg", ".jpeg", ".png")):

                text = ocr_image(path)

                if text:
                    texts.append(text)

        if not texts:

            await update.message.reply_text("Не удалось извлечь текст из материалов.")
            return


        full_text = "\n\n".join(texts)


        # режем текст на куски
        chunk_size = 12000

        chunks = [
            full_text[i:i+chunk_size]
            for i in range(0, len(full_text), chunk_size)
        ]


        analyses = []


        for chunk in chunks:

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "Ты юрист по делам 12.27 ч.2 КоАП РФ. Проанализируй материалы."
                    },
                    {
                        "role": "user",
                        "content": chunk
                    }
                ]
            )

            analyses.append(response.choices[0].message.content)


        # финальный вывод

        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Сделай итоговый юридический анализ материалов дела."
                },
                {
                    "role": "user",
                    "content": "\n\n".join(analyses)
                }
            ]
        )

        await update.message.reply_text(
            final_response.choices[0].message.content
        )

        return


    # -----------------------------------
    # меню ходатайств
    # -----------------------------------

    if user_text == "ходатайство":

        await update.message.reply_text(
            "Выберите ходатайство:",
            reply_markup=motion_keyboard()
        )

        return
    
    # -----------------------------------
    # меню других документов
    # -----------------------------------

    if user_text == "другое":

        await update.message.reply_text(
            "Выберите документ:",
            reply_markup=other_documents_keyboard()
        )

        return
    

    

    # -----------------------------------
    # кнопка назад
    # -----------------------------------

    if user_text == "назад":

        await update.message.reply_text(
            "Главное меню:",
            reply_markup=main_keyboard()
        )

        return
    

    # -----------------------------------
    # выбор конкретного ходатайства
    # -----------------------------------

    if user_text == "малозначительность":

        await update.message.reply_text(
            "Формирую ходатайство о малозначительности..."
        )

        # здесь позже будет генератор DOCX

        return
    

    # -----------------------------------
    # ходатайство ознакомление
    # -----------------------------------

    if user_text == "ознакомление с материалами":

        await update.message.reply_text(
            "Формирую ходатайство об ознакомлении..."
        )

        return


    # -----------------------------------
    # ходатайство экспертиза
    # -----------------------------------

    if user_text == "экспертиза":

        await update.message.reply_text(
            "Формирую ходатайство о проведении экспертизы..."
        )

        return

    # -----------------------------------
    # подготовить договор
    # -----------------------------------

    if user_text == "сформировать договор":

        case = context.user_data.get("case")

        if case is None:

            await update.message.reply_text(
                "Сначала создайте клиента"
            )
            return

        client_data_path = f"cases/{case}/passport/client_data.txt"

        if not os.path.exists(client_data_path):

            await update.message.reply_text(
                "Нет данных клиента. Сначала загрузите паспорт."
            )
            return

        try:

            docx_path, pdf_path = generate_contract(case)

            await update.message.reply_text("Договор сформирован.")

            with open(docx_path, "rb") as f:
                await update.message.reply_document(f)

            with open(pdf_path, "rb") as f:
                await update.message.reply_document(f)

        except Exception as e:

            print(e)

            await update.message.reply_text(
                "Ошибка генерации договора"
            )

        return

   
    # -----------------------------------
    # универсальная генерация документов
    # -----------------------------------

    if user_text in DOCUMENTS:

        case = context.user_data.get("case")

        if case is None:

            await update.message.reply_text(
                "Сначала создайте клиента"
            )

            return

        await update.message.reply_text(
            f"Формирую документ: {user_text}"
        )

        template = DOCUMENTS[user_text]["template"]

        # пока без подстановок
        replacements = {}

        try:

            docx_path, pdf_path = generate_document(
                case,
                template,
                replacements
            )

            with open(docx_path, "rb") as f:
                await update.message.reply_document(f)

            with open(pdf_path, "rb") as f:
                await update.message.reply_document(f)

        except Exception as e:

            print(e)

            await update.message.reply_text(
                "Ошибка генерации документа"
            )

        return
   
    # -----------------------------------
    # меню подготовки документов
    # -----------------------------------

    if user_text == "подготовить документ":

        await update.message.reply_text(
            "Выберите тип документа:",
            reply_markup=document_type_keyboard()
        )

        return


    # -----------------------------------
    # обычный GPT режим
    # -----------------------------------

    try:

        response = client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[
                {
                    "role": "system",
                    "content": f"Ты юридический помощник по делам 12.27 КоАП РФ. Сейчас рассматривается дело: {case}"
                },
                {
                    "role": "user",
                    "content": user_text
                }
            ]
        )

        answer = response.choices[0].message.content

        await update.message.reply_text(answer)

    except Exception as e:

        print(e)

        await update.message.reply_text("Ошибка обработки запроса.")



async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):

    case = context.user_data.get("case")

    if case is None:

        await update.message.reply_text(
            "Сначала создайте клиента"
        )
        return


    # -----------------------------------
    # обработка XLSX опросника
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_QUESTIONNAIRE":

        if not update.message.document:
            return

        folder = f"cases/{case}/materials"

        os.makedirs(folder, exist_ok=True)

        file = await update.message.document.get_file()

        path = f"{folder}/questionnaire.xlsx"

        await file.download_to_drive(path)

        lastname = case.split()[0]

        text = parse_questionnaire(path, lastname)

        if not text:

            await update.message.reply_text(
                "Не удалось найти клиента в таблице."
            )

            return

        txt_path = f"{folder}/questionnaire.txt"

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)

        context.user_data["state"] = None

        build_case_context(case)

        await update.message.reply_text(
            "Опросник успешно обработан."
        )

        return


    # -----------------------------------
    # загрузка паспорта
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_PASSPORT":

        folder = f"cases/{case}/passport"

        os.makedirs(folder, exist_ok=True)

        photos = context.user_data.get("passport_images", [])

        photo = update.message.photo[-1]

        file = await photo.get_file()

        file_name = f"passport_{len(photos)+1}.jpg"

        path = f"{folder}/{file_name}"

        await file.download_to_drive(path)

        photos.append(path)

        context.user_data["passport_images"] = photos

        if len(photos) < 2:

            await update.message.reply_text(
                "Фото получено. Пришлите вторую страницу паспорта."
            )

            return

        context.user_data["state"] = None

        await update.message.reply_text(
            "Паспорт получен. Начинаю распознавание..."
        )

        passport_data = parse_passport_from_images(photos)

        context.user_data["passport_data"] = passport_data
        context.user_data["state"] = "WAIT_PASSPORT_CONFIRM"

        await update.message.reply_text(
            f"Проверьте данные паспорта:\n\n{passport_data}",
            reply_markup=passport_confirm_keyboard()
        )

        return


    # -----------------------------------
    # загрузка материалов (документы)
    # -----------------------------------

    folder = f"cases/{case}/materials"

    os.makedirs(folder, exist_ok=True)


    if update.message.document:

        file = await update.message.document.get_file()

        file_name = os.path.basename(
            update.message.document.file_name or "document"
        )

        path = f"{folder}/{file_name}"

        await file.download_to_drive(path)


        # OCR материалов

        case_folder = f"cases/{case}"

        process_material(path, case_folder)

        build_case_context(case)


        await update.message.reply_text(
            f"Файл сохранен и распознан: {file_name}"
        )

        return


    # -----------------------------------
    # загрузка материалов (фото)
    # -----------------------------------

    if update.message.photo:

        photo = update.message.photo[-1]

        file = await photo.get_file()

        file_name = f"material_{uuid.uuid4().hex}.jpg"

        path = f"{folder}/{file_name}"

        await file.download_to_drive(path)


        case_folder = f"cases/{case}"

        process_material(path, case_folder)

        build_case_context(case)


        await update.message.reply_text(
            "Фото материала сохранено и распознано."
        )

        return



# -----------------------------------
# запуск
# -----------------------------------

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

from telegram.ext import CommandHandler

app.add_handler(CommandHandler("start", start))

app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
app.add_handler(MessageHandler(filters.PHOTO, handle_file))

print("AI Lawyer запущен...")

app.run_polling()
