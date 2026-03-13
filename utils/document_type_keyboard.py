from telegram import ReplyKeyboardMarkup

def document_type_keyboard():

    keyboard = [

        ["Ходатайство", "Другое"],

        ["Назад"]

    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )