from telegram import ReplyKeyboardMarkup

def passport_confirm_keyboard():

    keyboard = [
        ["Подтверждаю", "Исправить"]
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )
