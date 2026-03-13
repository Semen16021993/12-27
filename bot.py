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
from services.knowledge_loader import load_knowledge
from services.legal_analysis_prompt import LEGAL_ANALYSIS_PROMPT
from services.passport_pipeline import process_passport

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
knowledge_base = load_knowledge()

print("База знаний загружена")
print(len(knowledge_base))


# регистрируем шрифт один раз
pdfmetrics.registerFont(
    TTFont(
        "TimesNewRoman",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf"
    )
)

pdfmetrics.registerFont(
    TTFont(
        "TimesNewRomanBold",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf"
    )
)


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
    # выбрать клиента
    # -----------------------------------

    if user_text == "выбрать клиента":

        cases_dir = "cases"

        if not os.path.exists(cases_dir):

            await update.message.reply_text(
                "Папка клиентов не найдена."
            )
            return

        clients = [
            name for name in os.listdir(cases_dir)
            if os.path.isdir(os.path.join(cases_dir, name))
        ]

        if not clients:

            await update.message.reply_text(
                "Клиенты не найдены."
            )
            return

        clients_list = "\n".join(clients)

        context.user_data["state"] = "WAIT_CLIENT_SELECT"

        await update.message.reply_text(clients_list)

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
    # выбор клиента из списка
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_CLIENT_SELECT":

        client_name = update.message.text.strip()

        path = f"cases/{client_name}"

        if not os.path.exists(path):

            await update.message.reply_text(
                "Такого клиента нет. Попробуйте снова."
            )
            return

        context.user_data["case"] = client_name
        context.user_data["state"] = None

        await update.message.reply_text(
            f"Выбран клиент: {client_name}",
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
        context.user_data["passport_files"] = []

        await update.message.reply_text(
            "Пришлите 2 фотографии паспорта:\n"
            "1️⃣ главная страница\n"
            "2️⃣ страница с пропиской"
        )

        return


    # -----------------------------------
    # загрузка материалов дела
    # -----------------------------------

    if user_text == "материалы дела":

        context.user_data["state"] = "WAIT_MATERIALS"

        await update.message.reply_text(
            "Прикрепите материалы дела.\n\n"
            "Можно отправить несколько файлов подряд:\n"
            "Когда закончите — напишите 'готово'."
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

    if user_text == "анализ материалов":

        await update.message.reply_text(
            "Приступаю к анализу материалов дела.\n"
            "Пожалуйста подождите, это может занять до 30–60 секунд."
        )

        materials_folder = f"cases/{case}/materials"
        questionnaire_path = f"cases/{case}/materials/questionnaire.txt"
        if not os.path.exists(questionnaire_path):

            await update.message.reply_text(
                "Опросник не найден. Сначала загрузите файл опросника."
            )
            return

        with open(questionnaire_path, "r", encoding="utf-8") as f:

            questionnaire_text = f.read()

        if not questionnaire_text.strip():

            await update.message.reply_text(
                "Файл опросника пуст. Проверьте загрузку."
            )
            return

        if not os.path.exists(materials_folder):
            await update.message.reply_text("Материалы дела отсутствуют.")
            return

        materials_text_path = f"cases/{case}/materials_text.txt"

        if not os.path.exists(materials_text_path):

            await update.message.reply_text(
                "Материалы дела не обработаны. Сначала загрузите материалы."
            )
            return

        with open(materials_text_path, "r", encoding="utf-8") as f:

            full_text = f.read()

        if not full_text.strip():

            await update.message.reply_text(
                "Файл материалов пуст. Проверьте загрузку документов."
            )
            return
        
        analysis_text = full_text

        final_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": f"""
        {LEGAL_ANALYSIS_PROMPT}

        Дополнительно используй профессиональный опыт из базы знаний:

        {knowledge_base}
        """
                },
                {
                    "role": "user",
                    "content": f"""
        questionnaire:

        {questionnaire_text}

        materials_text:

        {analysis_text}
        """
                }
            ]
        )

        analysis_result = final_response.choices[0].message.content


        defense_folder = f"cases/{case}/defense"
        os.makedirs(defense_folder, exist_ok=True)

        analysis_txt_path = f"{defense_folder}/analysis.txt"

        with open(analysis_txt_path, "w", encoding="utf-8") as f:
            f.write(analysis_result)


        # создаем PDF анализа
        # создаем нормальный PDF анализа
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.styles import getSampleStyleSheet

        analysis_pdf_path = f"{defense_folder}/analysis.pdf"

        styles = getSampleStyleSheet()

        normal_style = ParagraphStyle(
            "Normal",
            parent=styles["Normal"],
            fontName="TimesNewRoman",
            fontSize=11,
            leading=16
        )

        title_style = ParagraphStyle(
            "Title",
            parent=styles["Normal"],
            fontName="TimesNewRomanBold",
            fontSize=14,
            leading=20,
            spaceAfter=10
        )

        elements = []

        for line in analysis_result.split("\n"):

            text = line.strip()

            if not text:
                elements.append(Spacer(1, 6))
                continue

            # заголовки
            if text.startswith("#") or text.endswith(":"):

                clean = text.replace("#", "").strip()

                elements.append(Paragraph(clean, title_style))

            else:

                elements.append(Paragraph(text, normal_style))


        doc = SimpleDocTemplate(
            analysis_pdf_path,
            pagesize=A4,
            leftMargin=25 * mm,
            rightMargin=25 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm
        )

        doc.build(elements)


        await update.message.reply_text("Анализ материалов завершен.")

        with open(analysis_pdf_path, "rb") as f:
            await update.message.reply_document(f)

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
    # завершение загрузки материалов
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_MATERIALS" and user_text == "готово":

        context.user_data["state"] = None

        build_case_context(case)

        materials_folder = f"cases/{case}/materials"
        files_count = len(os.listdir(materials_folder))

        await update.message.reply_text(
            f"Загрузка материалов завершена.\n"
            f"Распознано документов: {files_count}",
            reply_markup=main_keyboard()
        )

        return
    
    # -----------------------------------
    # кнопка назад
    # -----------------------------------

    if user_text == "назад":

        context.user_data["state"] = None

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
                    "content": """
        Ты юрист по делам ст.12.27 ч.2 КоАП РФ.

        Проанализируй представленный фрагмент материалов дела.

        Выдели:
        — фактические обстоятельства
        — важные детали ДТП
        — возможные противоречия
        — доказательства, подтверждающие или опровергающие версию событий
        """
                },
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

        files = context.user_data.get("passport_files", [])

        # если пользователь отправил фото
        if update.message.photo:

            photo = update.message.photo[-1]

            file = await photo.get_file()

            file_name = f"passport_{len(files)+1}.jpg"

            path = f"{folder}/{file_name}"

            await file.download_to_drive(path)

            files.append(path)

        # если отправлен файл (pdf / jpg / png)
        elif update.message.document:

            file = await update.message.document.get_file()

            file_name = update.message.document.file_name

            path = f"{folder}/{file_name}"

            await file.download_to_drive(path)

            files.append(path)

        context.user_data["passport_files"] = files

        # если пока только 1 фото
        if len(files) == 1 and not files[0].lower().endswith(".pdf"):

            await update.message.reply_text(
                "Фото получено. Пришлите вторую страницу паспорта."
            )

            return

        await update.message.reply_text(
            "Паспорт получен. Начинаю распознавание..."
        )

        case_folder = f"cases/{case}"

        passport_data = process_passport(files, case_folder)

        context.user_data["passport_data"] = passport_data
        context.user_data["state"] = "WAIT_PASSPORT_CONFIRM"

        await update.message.reply_text(
            f"Проверьте данные паспорта:\n\n{passport_data}",
            reply_markup=passport_confirm_keyboard()
        )

        return

    # -----------------------------------
    # принимаем материалы дела
    # -----------------------------------

    if context.user_data.get("state") == "WAIT_MATERIALS":

        folder = f"cases/{case}/materials"
        os.makedirs(folder, exist_ok=True)

        # документ
        if update.message.document:

            file = await update.message.document.get_file()

            file_name = os.path.basename(
                update.message.document.file_name or "document"
            )

            path = f"{folder}/{file_name}"

            await file.download_to_drive(path)

            case_folder = f"cases/{case}"

            process_material(path, case_folder)
            
            return

        # фото

        if update.message.photo:

            photo = update.message.photo[-1]

            file = await photo.get_file()

            file_name = f"material_{uuid.uuid4().hex}.jpg"

            path = f"{folder}/{file_name}"

            await file.download_to_drive(path)

            case_folder = f"cases/{case}"

            process_material(path, case_folder)
            
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
