import asyncio
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pytz import timezone

LOCAL_TZ = timezone("Asia/Aqtobe")

# Токен бота
API_TOKEN = "8152580581:AAEYHPMHBe1OnqGwmmBMbmNikboC_iIbtKc"

# Укажите ID администратора
ADMIN_ID = 1313126991  # Замените на ваш Telegram ID

# Инициализация логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота, диспетчера и маршрутизатора
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()

# Состояние для хранения временных данных
tasks = []  # Список всех задач
user_states = {}  # Для отслеживания этапов создания задачи
user_database = {}  # База данных пользователей
questions = {}  # Хранение вопросов и ответов

def generate_navigation_buttons():
    """Генерирует кнопки для навигации между шагами"""
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="back")],
        [InlineKeyboardButton(text="Отменить", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def calculate_time_left(deadline):
    """Вычисляет оставшееся время до дедлайна"""
    now = datetime.now(LOCAL_TZ)  # Локальное время
    if deadline.tzinfo is None:  # Если дедлайн без часового пояса
        deadline = LOCAL_TZ.localize(deadline)
    remaining = deadline - now

    if remaining.total_seconds() <= 0:
        return "Просрочено"

    days, seconds = divmod(remaining.total_seconds(), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    return f"{int(days)} д. {int(hours)} ч. {int(minutes)} мин."

def generate_task_buttons(user_id):
    """Генерирует кнопки задач для завершения"""
    buttons = []
    user_tasks = [task for task in tasks if task["recipient"] == user_id and not task.get("completed")]
    for i, task in enumerate(user_tasks):
        buttons.append([InlineKeyboardButton(text=f"{i + 1}. {task['title']}", callback_data=f"complete:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

@router.message(Command("start"))
async def send_welcome(message: Message):
    """Приветственное сообщение"""
    logging.info(f"Команда /start от {message.from_user.id}")
    user_database[message.from_user.username] = message.from_user.id
    await message.reply(
        "Привет! Я бот для управления задачами.\n\n"
        "Доступные команды:\n"
        "/send - Добавить задачу (для администратора).\n"
        "/tasks - Посмотреть список задач.\n"
        "/complete - Завершить задачу.\n"
        "/ask - Задать вопрос администратору.\n"
        "Чтобы узнать свой ID, используйте команду /myid."
    )

@router.message(Command("myid"))
async def get_my_id(message: Message):
    """Отправляет ID пользователя"""
    logging.info(f"Команда /myid от {message.from_user.id}")
    await message.reply(f"Ваш ID: {message.from_user.id}")

@router.message(Command("ask"))
async def ask_admin(message: Message):
    """Позволяет пользователю задать вопрос администратору"""
    logging.info(f"Команда /ask от {message.from_user.id}")
    user_states[message.from_user.id] = {"step": "waiting_for_question"}
    await message.reply("Введите ваш вопрос для администратора:")

@router.message(lambda message: message.from_user.id in user_states and user_states[message.from_user.id]["step"] == "waiting_for_question")
async def handle_question(message: Message):
    """Обрабатывает вопрос пользователя и отправляет администратору"""
    question = message.text
    user_id = message.from_user.id
    questions[user_id] = {"question": question, "answered": False}

    await bot.send_message(
        ADMIN_ID,
        f"Новый вопрос от @{message.from_user.username} ({user_id}):\n\n{question}\n\n"
        "Для ответа используйте команду: /answer <user_id> <ответ>"
    )
    await message.reply("Ваш вопрос отправлен администратору. Ожидайте ответа.")
    del user_states[user_id]

@router.message(Command("answer"))
async def answer_user(message: Message):
    """Позволяет администратору ответить на вопрос пользователя"""
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Используйте формат: /answer <user_id> <ответ>")
        return

    user_id = int(args[1])
    answer = args[2]

    if user_id not in questions or questions[user_id]["answered"]:
        await message.reply("Этот пользователь не задавал вопросов или на вопрос уже был дан ответ.")
        return

    await bot.send_message(user_id, f"Администратор ответил на ваш вопрос:\n\n{answer}")
    questions[user_id]["answered"] = True
    await message.reply("Ответ отправлен пользователю.")

async def send_reminders():
    """Фоновая задача для отправки напоминаний."""
    while True:
        now = datetime.now(LOCAL_TZ)
        for task in tasks:
            if task.get("completed"):
                continue

            deadline = task["deadline"]
            remaining_time = deadline - now

            if remaining_time <= timedelta(hours=24) and not task["reminders"]["24_hours"]:
                await bot.send_message(task["recipient"], f"Напоминание! До задачи \"{task['title']}\" осталось 24 часа.")
                task["reminders"]["24_hours"] = True
            elif remaining_time <= timedelta(hours=12) and not task["reminders"]["12_hours"]:
                await bot.send_message(task["recipient"], f"Напоминание! До задачи \"{task['title']}\" осталось 12 часов.")
                task["reminders"]["12_hours"] = True
            elif remaining_time <= timedelta(hours=6) and not task["reminders"]["6_hours"]:
                await bot.send_message(task["recipient"], f"Напоминание! До задачи \"{task['title']}\" осталось 6 часов.")
                task["reminders"]["6_hours"] = True
            elif remaining_time <= timedelta(hours=3) and not task["reminders"]["3_hours"]:
                await bot.send_message(task["recipient"], f"Напоминание! До задачи \"{task['title']}\" осталось 3 часа.")
                task["reminders"]["3_hours"] = True
            elif remaining_time <= timedelta(hours=1) and not task["reminders"]["1_hour"]:
                await bot.send_message(task["recipient"], f"Напоминание! До задачи \"{task['title']}\" остался 1 час.")
                task["reminders"]["1_hour"] = True

        await asyncio.sleep(60)

async def main():
    """Запуск бота"""
    dp.include_router(router)
    asyncio.create_task(send_reminders())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
