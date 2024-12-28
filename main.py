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
questions = {}  # Для отслеживания вопросов пользователей

# Вспомогательные функции
def generate_navigation_buttons():
    buttons = [
        [InlineKeyboardButton(text="Назад", callback_data="back")],
        [InlineKeyboardButton(text="Отменить", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def calculate_time_left(deadline):
    now = datetime.now(LOCAL_TZ)
    if deadline.tzinfo is None:
        deadline = LOCAL_TZ.localize(deadline)
    remaining = deadline - now

    if remaining.total_seconds() <= 0:
        return "Просрочено"

    days, seconds = divmod(remaining.total_seconds(), 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, _ = divmod(seconds, 60)
    return f"{int(days)} д. {int(hours)} ч. {int(minutes)} мин."

def generate_task_buttons(user_id):
    buttons = []
    user_tasks = [task for task in tasks if task["recipient"] == user_id and not task.get("completed")]
    for i, task in enumerate(user_tasks):
        buttons.append([InlineKeyboardButton(text=f"{i + 1}. {task['title']}", callback_data=f"task:{i}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

# Команды
@router.message(Command("start"))
async def send_welcome(message: Message):
    logging.info(f"Команда /start от {message.from_user.id}")
    user_database[message.from_user.username] = message.from_user.id
    await message.reply(
        "Привет! Я бот для управления задачами.\n\n"
        "Доступные команды:\n"
        "/send - Добавить задачу (для администратора).\n"
        "/tasks - Посмотреть список задач.\n"
        "/complete - Завершить задачу.\n"
        "/ask - Задать вопрос по задаче.\n\n"
        "Чтобы узнать свой ID, используйте команду /myid."
    )

@router.message(Command("myid"))
async def get_my_id(message: Message):
    logging.info(f"Команда /myid от {message.from_user.id}")
    await message.reply(f"Ваш ID: {message.from_user.id}")

@router.message(Command("tasks"))
async def list_tasks(message: Message):
    logging.info(f"Команда /tasks от {message.from_user.id}")
    user_id = message.from_user.id
    user_tasks = [task for task in tasks if task["recipient"] == user_id and not task.get("completed")]

    if not user_tasks:
        await message.reply("У вас нет задач.")
        return

    task_list = "\n".join(
        [
            f"{i + 1}. {task['title']} (Дедлайн: {task['deadline'].strftime('%d.%m.%Y %H:%M')}, Осталось: {calculate_time_left(task['deadline'])})"
            for i, task in enumerate(user_tasks)
        ]
    )

    await message.reply(
        f"Ваши задачи:\n\n{task_list}\n\n"
        "Отправьте номер задачи, чтобы получить полную информацию."
    )

@router.message(Command("complete"))
async def choose_task_to_complete(message: Message):
    logging.info(f"Команда /complete от {message.from_user.id}")
    user_id = message.from_user.id
    task_buttons = generate_task_buttons(user_id)

    if not task_buttons:
        await message.reply("У вас нет активных задач для завершения.")
        return

    await message.reply("Выберите задачу, чтобы отметить её как выполненную:", reply_markup=task_buttons)

@router.callback_query(lambda call: call.data.startswith("complete:"))
async def complete_task(call: CallbackQuery):
    user_id = call.from_user.id
    task_index = int(call.data.split(":")[1])

    user_tasks = [task for task in tasks if task["recipient"] == user_id and not task.get("completed")]

    if task_index < 0 or task_index >= len(user_tasks):
        await call.answer("Некорректный выбор задачи.", show_alert=True)
        return

    task = user_tasks[task_index]
    task["completed"] = True

    completed_by_username = next((username for username, uid in user_database.items() if uid == user_id), "Неизвестный")
    created_by_username = next((username for username, uid in user_database.items() if uid == task['created_by']), "Неизвестный")
    await bot.send_message(
        ADMIN_ID,
        f"Задача завершена:\n\n"
        f"Название: {task['title']}\n"
        f"Описание: {task['description']}\n"
        f"Дедлайн: {task['deadline'].strftime('%d.%m.%Y %H:%M')}\n"
        f"Завершил пользователь: @{completed_by_username}\n"
        f"Отправитель задачи: @{created_by_username}\n"
        f"Статус: Завершена"
    )

    tasks.remove(task)

    await call.message.edit_text(
        f"Задача завершена:\n\n"
        f"Название: {task['title']}\n"
        f"Описание: {task['description']}\n"
        f"Дедлайн: {task['deadline'].strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: Завершена"
    )

@router.message(Command("ask"))
async def start_question(message: Message):
    logging.info(f"Команда /ask от {message.from_user.id}")
    user_id = message.from_user.id
    task_buttons = generate_task_buttons(user_id)

    if not task_buttons:
        await message.reply("У вас нет активных задач, по которым можно задать вопрос.")
        return

    questions[user_id] = {"step": "select_task"}
    await message.reply("Выберите задачу, по которой хотите задать вопрос:", reply_markup=task_buttons)

@router.callback_query(lambda call: call.data.startswith("task:"))
async def select_task_for_question(call: CallbackQuery):
    user_id = call.from_user.id
    if user_id not in questions or questions[user_id]["step"] != "select_task":
        await call.answer("Вы не можете выбрать задачу для вопроса.", show_alert=True)
        return

    task_index = int(call.data.split(":")[1])
    user_tasks = [task for task in tasks if task["recipient"] == user_id and not task.get("completed")]

    if task_index < 0 or task_index >= len(user_tasks):
        await call.answer("Некорректный выбор задачи.", show_alert=True)
        return

    questions[user_id]["task"] = user_tasks[task_index]
    questions[user_id]["step"] = "write_question"

    await call.message.edit_text("Введите ваш вопрос по выбранной задаче:")

@router.message(lambda message: message.from_user.id in questions and questions[message.from_user.id]["step"] == "write_question")
async def handle_question(message: Message):
    user_id = message.from_user.id
    question_text = message.text
    task = questions[user_id]["task"]

    await bot.send_message(
        ADMIN_ID,
        f"Новый вопрос от пользователя @{message.from_user.username} по задаче:\n\n"
        f"Название: {task['title']}\n"
        f"Вопрос: {question_text}"
    )

    await message.reply("Ваш вопрос отправлен администратору. Ожидайте ответа.")
    del questions[user_id]

@router.message(lambda message: message.from_user.id == ADMIN_ID and message.reply_to_message)
async def answer_question(message: Message):
    original_message = message.reply_to_message.text
    lines = original_message.split("\n")
    username_line = next((line for line in lines if line.startswith("Новый вопрос от пользователя")), None)

    if not username_line:
        await message.reply("Не удалось идентифицировать пользователя для ответа.")
        return

    username = username_line.split("@")[1].split()[0]
    user_id = user_database.get(username)

    if not user_id:
        await message.reply("Не удалось найти пользователя в базе данных.")
        return

    await bot.send_message(user_id, f"Ответ на ваш вопрос от администратора:\n\n{message.text}")
    await message.reply("Ответ отправлен пользователю.")

async def send_reminders():
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
    dp.include_router(router)
    asyncio.create_task(send_reminders())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
