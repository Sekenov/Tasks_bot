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
pending_questions = {}  # Хранение вопросов пользователей

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
        "\nЧтобы узнать свой ID, используйте команду /myid."
    )

@router.message(Command("myid"))
async def get_my_id(message: Message):
    """Отправляет ID пользователя"""
    logging.info(f"Команда /myid от {message.from_user.id}")
    await message.reply(f"Ваш ID: {message.from_user.id}")

@router.message(Command("tasks"))
async def list_tasks(message: Message):
    """Показывает список задач для текущего пользователя"""
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

@router.message(Command("ask"))
async def ask_admin(message: Message):
    """Пользователь задаёт вопрос администратору"""
    logging.info(f"Команда /ask от {message.from_user.id}")
    pending_questions[message.from_user.id] = None  # Ожидаем текст вопроса
    await message.reply("Введите ваш вопрос для администратора.")

@router.message(lambda message: message.from_user.id in pending_questions and pending_questions[message.from_user.id] is None)
async def handle_user_question(message: Message):
    """Получение вопроса от пользователя"""
    user_id = message.from_user.id
    pending_questions[user_id] = message.text

    await bot.send_message(
        ADMIN_ID,
        f"Вопрос от пользователя @{message.from_user.username} (ID: {user_id}):\n{message.text}\n\n"
        f"Для ответа используйте команду: /answer {user_id} ваш_ответ"
    )
    await message.reply("Ваш вопрос отправлен администратору.")

@router.message(Command("answer"))
async def answer_user(message: Message):
    """Администратор отвечает на вопрос пользователя"""
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.reply("Используйте формат: /answer user_id ответ")
        return

    try:
        user_id = int(args[1])
        answer = args[2]
    except ValueError:
        await message.reply("Укажите корректный ID пользователя.")
        return

    if user_id not in pending_questions:
        await message.reply("Не найдено вопросов от данного пользователя.")
        return

    del pending_questions[user_id]  # Удаляем вопрос из ожидания

    await bot.send_message(user_id, f"Ответ от администратора:\n{answer}")
    await message.reply("Ответ отправлен пользователю.")

async def main():
    """Запуск бота"""
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
