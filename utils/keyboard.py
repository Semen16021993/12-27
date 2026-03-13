from telegram import ReplyKeyboardMarkup


def main_keyboard():

    keyboard = [

        ["Создать клиента", "Выбрать клиента"],

        ["Паспорт", "Сформировать договор"],

        ["Материалы дела", "Данные опросника"],

        ["Данные ГИБДД и суда"],

        ["Анализ материалов"],

        ["Подготовить документ"]

    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )
