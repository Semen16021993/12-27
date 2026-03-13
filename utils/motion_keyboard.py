from telegram import ReplyKeyboardMarkup


def motion_keyboard():

    keyboard = [

        ["Ознакомление ГИБДД"],
        ["Ознакомление суд"],

        ["Перенос ГИБДД"],
        ["Перенос суд"],

        ["Прекращение ГИБДД"],
        ["Прекращение суд"],

        ["Малозначительность"],
        ["Крайняя необходимость"],

        ["Проведение экспертизы"],

        ["Назад"]

    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )