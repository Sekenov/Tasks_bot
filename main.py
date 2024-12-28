import asyncio
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
        "/complete - Завершить задачу.\n\n"
        "Чтобы узнать свой ID, используйте команду /myid."
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

@router.message(Command("complete"))
async def choose_task_to_complete(message: Message):
    """Позволяет пользователю выбрать задачу для завершения"""
    logging.info(f"Команда /complete от {message.from_user.id}")
    user_id = message.from_user.id
    task_buttons = generate_task_buttons(user_id)

    if not task_buttons:
        await message.reply("У вас нет активных задач для завершения.")
        return

    await message.reply("Выберите задачу, чтобы отметить её как выполненную:", reply_markup=task_buttons)

@router.callback_query(lambda call: call.data.startswith("complete:"))
async def complete_task(call: CallbackQuery):
    """Отмечает задачу как завершённую"""
    user_id = call.from_user.id
    task_index = int(call.data.split(":")[1])

    user_tasks = [task for task in tasks if task["recipient"] == user_id and not task.get("completed")]

    if task_index < 0 or task_index >= len(user_tasks):
        await call.answer("Некорректный выбор задачи.", show_alert=True)
        return

    task = user_tasks[task_index]
    task["completed"] = True
    task["reminders"] = None  # Удаляем напоминания

    # Уведомление администратора
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

@router.message(lambda message: message.text.isdigit())
async def handle_task_detail_request(message: Message):
    """Отправляет полную информацию по задаче на основе номера"""
    user_id = message.from_user.id
    user_tasks = [task for task in tasks if task["recipient"] == user_id and not task.get("completed")]

    task_number = int(message.text) - 1
    if task_number < 0 or task_number >= len(user_tasks):
        await message.reply("Некорректный номер задачи.")
        return

    task = user_tasks[task_number]
    created_by_username = next((username for username, user_id in user_database.items() if user_id == task['created_by']), "Неизвестный")

    await message.reply(
        f"Полная информация о задаче:\n\n"
        f"Название: {task['title']}\n"
        f"Описание: {task['description']}\n"
        f"Дедлайн: {task['deadline'].strftime('%d.%m.%Y %H:%M')}\n"
        f"Отправитель: @{created_by_username}\n"
        f"Статус: {'Завершена' if task.get('completed') else 'Активна'}",
        parse_mode=ParseMode.HTML
    )

@router.message(Command("send"))
async def start_task_creation(message: Message):
    """Начинает процесс создания задачи (доступно только администратору)"""
    logging.info(f"Команда /send от {message.from_user.id}")
    if message.from_user.id != ADMIN_ID:
        await message.reply("У вас нет прав для выполнения этой команды.")
        return

    user_states[message.from_user.id] = {
        "step": "waiting_for_task_title",
        "task": {},
    }
    await message.reply("Введите название задачи:", reply_markup=generate_navigation_buttons())

@router.message(lambda message: message.from_user.id in user_states)
async def handle_task_creation(message: Message):
    """Обрабатывает этапы создания задачи"""
    user_id = message.from_user.id
    state = user_states[user_id]

    if state["step"] == "waiting_for_task_title":
        state["task"]["title"] = message.text
        state["step"] = "waiting_for_task_description"
        await message.reply("Введите описание задачи:", reply_markup=generate_navigation_buttons())

    elif state["step"] == "waiting_for_task_description":
        state["task"]["description"] = message.text
        state["step"] = "waiting_for_task_recipient"
        await message.reply("Введите ID пользователя или @username, которому адресована задача:", reply_markup=generate_navigation_buttons())

    elif state["step"] == "waiting_for_task_recipient":
        recipient_id = None

        if message.text.startswith("@"):
            username = message.text.lstrip("@")
            recipient_id = user_database.get(username)
            if not recipient_id:
                await message.reply("Этот пользователь не зарегистрирован. Попросите его отправить команду /start.")
                return
        else:
            try:
                recipient_id = int(message.text)
            except ValueError:
                await message.reply("Укажите корректный ID или @username.")
                return

        state["task"]["recipient"] = recipient_id
        state["step"] = "waiting_for_task_deadline_date"
        await message.reply("Введите дедлайн задачи (день.месяц.год ЧЧ:ММ):", reply_markup=generate_navigation_buttons())

    elif state["step"] == "waiting_for_task_deadline_date":
        try:
            deadline = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
            state["task"]["deadline"] = LOCAL_TZ.localize(deadline)

            task = state["task"]
            task["created_by"] = message.from_user.id
            task["reminders"] = {
                "24_hours": False,
                "12_hours": False,
                "6_hours": False,
                "3_hours": False,
                "1_hour": False,
            }
            tasks.append(task)

            await bot.send_message(
                task["recipient"],
                f"Вам добавлена новая задача:\n\n<b>{task['title']}</b>\n"
                f"Описание: {task['description']}\n"
                f"Дедлайн: <i>{task['deadline'].strftime('%d.%m.%Y %H:%M')}</i>",
                parse_mode=ParseMode.HTML,
            )
            await message.reply("Задача успешно добавлена!")
            del user_states[user_id]
        except ValueError:
            await message.reply("Укажите корректный формат даты (день.месяц.год ЧЧ:ММ).", reply_markup=generate_navigation_buttons())

@router.callback_query()
async def handle_navigation(call: CallbackQuery):
    """Обрабатывает кнопки навигации"""
    user_id = call.from_user.id

    if user_id not in user_states:
        await call.answer("Вы не находитесь в процессе создания задачи.", show_alert=True)
        return

    state = user_states[user_id]

    if call.data == "back":
        if state["step"] == "waiting_for_task_description":
            state["step"] = "waiting_for_task_title"
            await call.message.edit_text("Введите название задачи:", reply_markup=generate_navigation_buttons())
        elif state["step"] == "waiting_for_task_recipient":
            state["step"] = "waiting_for_task_description"
            await call.message.edit_text("Введите описание задачи:", reply_markup=generate_navigation_buttons())
        elif state["step"] == "waiting_for_task_deadline_date":
            state["step"] = "waiting_for_task_recipient"
            await call.message.edit_text("Введите ID пользователя или @username, которому адресована задача:", reply_markup=generate_navigation_buttons())

    elif call.data == "cancel":
        del user_states[user_id]
        await call.message.edit_text("Создание задачи отменено.")

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










@router.message(Command("ask"))
async def ask_admin_start(message: Message):
    """Начало процесса отправки вопроса админу."""
    user_id = message.from_user.id

    # Сбрасываем предыдущее состояние пользователя
    if user_id in user_states:
        del user_states[user_id]

    # Устанавливаем состояние
    user_states[user_id] = {"step": "waiting_for_question"}

    await message.reply("Пожалуйста, напишите ваш вопрос, который вы хотите отправить администратору.")

@router.message(lambda message: message.from_user.id in user_states and user_states[message.from_user.id]["step"] == "waiting_for_question")
async def handle_question_input(message: Message):
    """Обрабатывает ввод вопроса от пользователя и отправляет админу."""
    user_id = message.from_user.id
    question = message.text

    try:
        # Отправляем вопрос админу
        await bot.send_message(
            ADMIN_ID,
            f"❓ <b>Вопрос от пользователя:</b>\n\n"
            f"👤 @{message.from_user.username} (ID: {user_id})\n\n"
            f"<b>Вопрос:</b> {question}",
            parse_mode=ParseMode.HTML,
        )

        await message.reply("Ваш вопрос успешно отправлен администратору.")
    except Exception as e:
        logging.error(f"Ошибка при отправке вопроса админу: {e}")
        await message.reply("Произошла ошибка при отправке вопроса админу. Попробуйте позже.")
    finally:
        # Удаляем состояние пользователя
        if user_id in user_states:
            del user_states[user_id]
















async def main():
    """Запуск бота"""
    dp.include_router(router)
    asyncio.create_task(send_reminders())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
