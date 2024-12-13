from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
import random
import sqlite3

from aiogram.filters import StateFilter

# Инициализация бота и диспетчера
TOKEN = "6929619724:AAFZDoS7WtuHUNDV6_VCuFXbV5RA56Bgvh0"
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Настройка базы данных
conn = sqlite3.connect("secret_santa.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS rooms (
    room_id TEXT PRIMARY KEY,
    admin_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS participants (
    room_id TEXT,
    user_id INTEGER,
    user_name TEXT,
    PRIMARY KEY (room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS wishes (
    user_id INTEGER,
    wish TEXT,
    PRIMARY KEY (user_id, wish)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS assignments (
    room_id TEXT,
    giver_id INTEGER,
    receiver_id INTEGER,
    PRIMARY KEY (room_id, giver_id),
    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    FOREIGN KEY (giver_id) REFERENCES participants(user_id),
    FOREIGN KEY (receiver_id) REFERENCES participants(user_id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    sender_id INTEGER,
    receiver_id INTEGER,
    room_id TEXT,
    message TEXT,
    FOREIGN KEY (room_id) REFERENCES rooms(room_id),
    FOREIGN KEY (sender_id) REFERENCES participants(user_id),
    FOREIGN KEY (receiver_id) REFERENCES participants(user_id)
)
""")

conn.commit()

class WishStates(StatesGroup):
    adding = State()
    editing = State()

class SetNameState(StatesGroup):
    entering_name = State()

@dp.message(Command("start"))
async def start_command(message: Message):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Мои комнаты", callback_data="my_rooms")
    keyboard.button(text="Создать комнату", callback_data="create_room")
    keyboard.button(text="Присоединиться к комнате", callback_data="join_room")
    keyboard.button(text="Установить имя", callback_data="set_display_name")
    keyboard.adjust(1)
    await message.answer("Добро пожаловать в игру 'Секретный Санта'! Выберите действие:", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data == "set_display_name")
async def set_display_name(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите новое отображаемое имя:")
    await state.set_state(SetNameState.entering_name)

@dp.message(StateFilter(SetNameState.entering_name))
async def handle_new_display_name(message: Message, state: FSMContext):
    new_name = message.text.strip()

    if not new_name or len(new_name) > 50:
        await message.answer("Имя не должно быть пустым и должно содержать не более 50 символов.")
        return

    cursor.execute(
        "UPDATE participants SET user_name = ? WHERE user_id = ?",
        (new_name, message.from_user.id)
    )
    conn.commit()

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="back_to_main")
    keyboard.adjust(1)

    await message.answer(f"Ваше отображаемое имя обновлено на: {new_name}.", reply_markup=keyboard.as_markup())
    await state.clear()

@dp.callback_query(lambda c: c.data == "my_rooms")
async def my_rooms(callback: CallbackQuery):
    cursor.execute(
        """
        SELECT DISTINCT r.room_id, r.admin_id
        FROM rooms r
        INNER JOIN participants p ON r.room_id = p.room_id
        WHERE p.user_id = ?
        """,
        (callback.from_user.id,)
    )
    rooms = cursor.fetchall()

    keyboard = InlineKeyboardBuilder()
    if rooms:
        for room_id, admin_id in rooms:
            admin_label = " (Админ)" if admin_id == callback.from_user.id else ""
            keyboard.button(text=f"Комната {room_id}{admin_label}", callback_data=f"room_menu:{room_id}")
    keyboard.button(text="Назад", callback_data="back_to_main")
    keyboard.adjust(1)

    if rooms:
        await callback.message.edit_text("Ваши комнаты:", reply_markup=keyboard.as_markup())
    else:
        await callback.message.edit_text("У вас нет комнат.", reply_markup=keyboard.as_markup())
@dp.callback_query(lambda c: c.data.startswith("room_menu"))
async def room_menu(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]  # Извлечение room_id из callback.data
    cursor.execute("SELECT admin_id FROM rooms WHERE room_id = ?", (room_id,))
    admin_id = cursor.fetchone()

    if admin_id and admin_id[0] == callback.from_user.id:
        await show_admin_menu(callback.message, room_id)
    else:
        await show_user_menu(callback.message, room_id)

@dp.callback_query(lambda c: c.data == "create_room")
async def create_room(callback: CallbackQuery):
    room_id = str(random.randint(1000, 9999))
    cursor.execute("INSERT INTO rooms (room_id, admin_id) VALUES (?, ?)", (room_id, callback.from_user.id))
    cursor.execute("INSERT INTO participants (room_id, user_id, user_name) VALUES (?, ?, ?)", (room_id, callback.from_user.id, callback.from_user.full_name))
    conn.commit()
    await callback.message.edit_text(f"Комната создана! ID вашей комнаты: {room_id}. Поделитесь этим ID, чтобы участники могли присоединиться.")
    await show_admin_menu(callback.message, room_id)

@dp.callback_query(lambda c: c.data.startswith("join:"))
async def process_join(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="my_rooms")
    keyboard.adjust(1)
    cursor.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,))
    if not cursor.fetchone():
        await callback.answer("Комната с таким ID не найдена.", reply_markup=keyboard.as_markup())
        return

    cursor.execute("SELECT room_id FROM participants WHERE user_id = ? AND room_id = ?", (callback.from_user.id, room_id))
    if cursor.fetchone():
        await callback.answer(f"Вы уже состоите в этой комнате.", reply_markup=keyboard.as_markup())
        return

    cursor.execute("INSERT OR IGNORE INTO participants (room_id, user_id, user_name) VALUES (?, ?, ?)",
                   (room_id, callback.from_user.id, callback.from_user.full_name))
    conn.commit()

    await callback.message.edit_text(f"Вы присоединились к комнате {room_id} как {callback.from_user.full_name}!", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data == "join_room")
async def join_room(callback: CallbackQuery):
    cursor.execute("SELECT room_id FROM rooms")
    rooms = cursor.fetchall()
    keyboard = InlineKeyboardBuilder()
    if rooms:
        for (room_id,) in rooms:
            keyboard.button(text=f"Присоединиться к комнате {room_id}", callback_data=f"join:{room_id}")
    else:
        keyboard.button(text="Нет доступных комнат", callback_data="back_to_main")
    keyboard.button(text="Назад", callback_data="back_to_main")
    keyboard.adjust(1)
    await callback.message.edit_text("Выберите комнату для присоединения:", reply_markup=keyboard.as_markup())

@dp.message(StateFilter(None))  # Срабатывает только если состояние FSM не установлено
async def handle_join_room_id(message: Message):
    room_id = message.text.strip()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="back_to_main")
    keyboard.adjust(1)
    if not room_id.isdigit():
        await message.answer("ID комнаты должен быть числом.", reply_markup=keyboard.as_markup())
        return

    cursor.execute("SELECT * FROM rooms WHERE room_id = ?", (room_id,))
    if cursor.fetchone() is None:
        await message.answer("Комната с таким ID не найдена.", reply_markup=keyboard.as_markup())
        return

    cursor.execute("SELECT room_id FROM participants WHERE user_id = ? AND room_id = ?", (message.from_user.id, room_id))
    existing_room = cursor.fetchone()

    if existing_room:
        await message.answer(f"Вы уже состоите в комнате {existing_room[0]}.", reply_markup=keyboard.as_markup())
        return

    cursor.execute("INSERT OR IGNORE INTO participants (room_id, user_id, user_name) VALUES (?, ?, ?)",
                   (room_id, message.from_user.id, message.from_user.full_name))
    conn.commit()

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="back_to_main")
    keyboard.adjust(1)
    await message.answer(f"Вы присоединились к комнате {room_id} как {message.from_user.full_name}!",
                         reply_markup=keyboard.as_markup())

async def show_admin_menu(message: Message, room_id: str):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Запустить игру", callback_data=f"start_game:{room_id}")
    keyboard.button(text="Посмотреть участников", callback_data=f"list_participants:{room_id}")
    keyboard.button(text="Напомнить подопечного", callback_data=f"view_assignment:{room_id}")
    keyboard.button(text="Управление своими желаниями", callback_data="manage_wishes")
    keyboard.button(text="Удалить участника", callback_data=f"remove_participant:{room_id}")
    keyboard.button(text="Удалить комнату", callback_data=f"delete_room:{room_id}")
    keyboard.button(text="Назад", callback_data="back_to_main")
    keyboard.adjust(1)
    await message.edit_text(f"Админское меню для комнаты {room_id}", reply_markup=keyboard.as_markup())

async def show_user_menu(message: Message, room_id: str):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Выйти из комнаты", callback_data=f"leave_room:{room_id}")
    keyboard.button(text="Посмотреть участников", callback_data=f"list_participants:{room_id}")
    keyboard.button(text="Напомнить подопечного", callback_data=f"view_assignment:{room_id}")
    keyboard.button(text="Управление своими желаниями", callback_data="manage_wishes")
    keyboard.button(text="Назад", callback_data="back_to_main")
    keyboard.adjust(1)
    await message.edit_text(f"Меню участника для комнаты {room_id}", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data.startswith("manage_wishes"))
async def manage_wishes(callback: CallbackQuery):
    # Получаем room_id пользователя
    cursor.execute("SELECT room_id FROM participants WHERE user_id = ?", (callback.from_user.id,))
    user_rooms = cursor.fetchone()
    room_id = user_rooms[0] if user_rooms else '0'  # Задаём 0 или другое значение по умолчанию, если комната не найдена

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Отобразить", callback_data="show_wishes")
    keyboard.button(text="Добавить", callback_data="add_wish")
    keyboard.button(text="Изменить", callback_data="edit_wish")
    keyboard.button(text="Удалить", callback_data="delete_wish")
    keyboard.button(text="Назад", callback_data=f"room_menu:{room_id}")  # Исправленное значение callback
    keyboard.adjust(1)
    await callback.message.edit_text("Управление своими желаниями", reply_markup=keyboard.as_markup())


@dp.callback_query(lambda c: c.data == "edit_wish")
async def choose_wish_to_edit(callback: CallbackQuery):
    cursor.execute("SELECT wish, rowid FROM wishes WHERE user_id = ?", (callback.from_user.id,))
    wishes = cursor.fetchall()
    keyboard = InlineKeyboardBuilder()
    for wish, rowid in wishes:
        keyboard.button(text=wish, callback_data=f"edit_wish:{rowid}")
    keyboard.button(text="Назад", callback_data="manage_wishes")
    keyboard.adjust(1)
    await callback.message.edit_text("Выберите желание для редактирования:", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data == "delete_wish")
async def choose_wish_to_delete(callback: CallbackQuery):
    cursor.execute("SELECT wish, rowid FROM wishes WHERE user_id = ?", (callback.from_user.id,))
    wishes = cursor.fetchall()
    keyboard = InlineKeyboardBuilder()
    for wish, rowid in wishes:
        keyboard.button(text=wish, callback_data=f"delete_wish:{rowid}")
    keyboard.button(text="Назад", callback_data="manage_wishes")
    keyboard.adjust(1)
    await callback.message.edit_text("Выберите желание для удаления:", reply_markup=keyboard.as_markup())

@dp.message(StateFilter(WishStates.adding))
async def handle_add_wish(message: Message, state: FSMContext):
    wish = message.text.strip()
    cursor.execute("INSERT OR IGNORE INTO wishes (user_id, wish) VALUES (?, ?)", (message.from_user.id, wish))
    conn.commit()

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="manage_wishes")
    keyboard.adjust(1)
    await message.answer("Желание добавлено!", reply_markup=keyboard.as_markup())

    await state.clear()

@dp.callback_query(lambda c: c.data == "add_wish")
async def add_wish(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите новое желание для добавления:")
    await state.set_state(WishStates.adding)

@dp.callback_query(lambda c: c.data.startswith("edit_wish:"))
async def start_editing_wish(callback: CallbackQuery, state: FSMContext):
    rowid = callback.data.split(":")[1]
    # Установка текущего состояния с использованием FSMContext
    await state.set_state(WishStates.editing)
    await state.update_data(wish_id=rowid)  # Сохраняем ID желания для последующего использования
    await callback.message.edit_text("Введите новый текст желания:")

@dp.message(StateFilter(WishStates.editing))
async def handle_edit_wish(message: Message, state: FSMContext):
    new_wish = message.text.strip()
    user_data = await state.get_data()
    wish_id = user_data['wish_id']
    cursor.execute("UPDATE wishes SET wish = ? WHERE rowid = ?", (new_wish, wish_id))
    conn.commit()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="manage_wishes")
    keyboard.adjust(1)
    await state.clear()
    await message.answer("Желание обновлено!", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data.startswith("delete_wish:"))
async def delete_wish(callback: CallbackQuery):
    rowid = callback.data.split(":")[1]
    cursor.execute("DELETE FROM wishes WHERE rowid = ?", (rowid,))
    conn.commit()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="manage_wishes")
    keyboard.adjust(1)
    await callback.message.edit_text("Желание удалено.", reply_markup=keyboard.as_markup())


@dp.callback_query(lambda c: c.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Мои комнаты", callback_data="my_rooms")
    keyboard.button(text="Создать комнату", callback_data="create_room")
    keyboard.button(text="Присоединиться к комнате", callback_data="join_room")
    keyboard.button(text="Установить имя", callback_data="set_display_name")
    keyboard.adjust(1)
    await callback.message.edit_text("Добро пожаловать в игру 'Секретный Санта'!  Выберите действие:", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data.startswith("leave_room"))
async def leave_room(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    cursor.execute("SELECT admin_id FROM rooms WHERE room_id = ?", (room_id,))
    admin_id = cursor.fetchone()

    if admin_id and admin_id[0] == callback.from_user.id:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Назад", callback_data="room_menu:" + room_id)
        keyboard.adjust(1)
        await callback.message.edit_text(
            "Вы администратор комнаты и не можете выйти из нее. Удалите комнату, если хотите выйти.",
            reply_markup=keyboard.as_markup()
        )
        return

    cursor.execute("DELETE FROM participants WHERE room_id = ? AND user_id = ?", (room_id, callback.from_user.id))
    conn.commit()

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="my_rooms")
    keyboard.adjust(1)
    await callback.message.edit_text(
        f"Вы покинули комнату {room_id}.",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("back_to_room"))
async def back_to_room(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    await room_menu(callback, room_id)  # Обновленный вызов с room_id

@dp.callback_query(lambda c: c.data == "show_wishes")
async def show_wishes(callback: CallbackQuery):
    cursor.execute("SELECT wish FROM wishes WHERE user_id = ?", (callback.from_user.id,))
    wishes = cursor.fetchall()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="manage_wishes")
    keyboard.adjust(1)
    if wishes:
        wish_list = "\n".join([w[0] for w in wishes])
        await callback.message.edit_text(f"Ваши желания:\n{wish_list}", reply_markup=keyboard.as_markup())
    else:
        await callback.message.edit_text("У вас пока нет желаний.", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data == "edit_wish")
async def edit_wish(callback: CallbackQuery):
    await callback.message.edit_text("Введите новое желание для добавления:")

@dp.callback_query(lambda c: c.data == "delete_wish")
async def delete_wish(callback: CallbackQuery):
    cursor.execute("DELETE FROM wishes WHERE user_id = ?", (callback.from_user.id,))
    conn.commit()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="my_rooms")
    keyboard.adjust(1)
    await callback.message.edit_text("Все ваши желания удалены.", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data.startswith("list_participants"))
async def list_participants(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    cursor.execute("SELECT user_name FROM participants WHERE room_id = ?", (room_id,))
    rows = cursor.fetchall()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data=f"room_menu:{room_id}")
    keyboard.adjust(1)
    if not rows:
        await callback.message.edit_text("Список участников пуст или комнаты не существует.", reply_markup=keyboard.as_markup())
    else:
        participant_names = "\n".join([row[0] for row in rows])
        await callback.message.edit_text(f"Список участников комнаты {room_id}:\n{participant_names}", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data.startswith("start_game"))
async def start_game(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    cursor.execute("SELECT admin_id FROM rooms WHERE room_id = ?", (room_id,))
    admin = cursor.fetchone()

    if admin is None or admin[0] != callback.from_user.id:
        await callback.message.edit_text("Только администратор комнаты может начать игру.")
        return

    cursor.execute("SELECT user_id, user_name FROM participants WHERE room_id = ?", (room_id,))
    participants = cursor.fetchall()

    if len(participants) < 2:
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="Назад", callback_data=f"room_menu:{room_id}")
        keyboard.adjust(1)
        await callback.message.edit_text("Недостаточно участников для игры. Минимум 2.", reply_markup=keyboard.as_markup())
        return

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Да", callback_data=f"confirm_start:{room_id}")
    keyboard.button(text="Нет", callback_data=f"room_menu:{room_id}")
    keyboard.adjust(1)

    await callback.message.edit_text("Вы уверены, что хотите начать новую игру? Это перезапишет предыдущие результаты.", reply_markup=keyboard.as_markup())

@dp.callback_query(lambda c: c.data.startswith("confirm_start"))
async def confirm_start_game(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    cursor.execute("SELECT user_id, user_name FROM participants WHERE room_id = ?", (room_id,))
    participants = cursor.fetchall()

    givers = participants[:]
    receivers = participants[:]
    random.shuffle(receivers)

    while any(g[0] == r[0] for g, r in zip(givers, receivers)):
        random.shuffle(receivers)

    # Сохраняем пары в таблицу assignments
    cursor.executemany(
        "INSERT OR REPLACE INTO assignments (room_id, giver_id, receiver_id) VALUES (?, ?, ?)",
        [(room_id, g[0], r[0]) for g, r in zip(givers, receivers)]
    )
    conn.commit()

    for giver_id, receiver_id in zip([g[0] for g in givers], [r[0] for r in receivers]):
        receiver_name = next(p[1] for p in participants if p[0] == receiver_id)
        try:
            await bot.send_message(giver_id, f"Вы дарите подарок: {receiver_name}!")
        except Exception as e:
            print(f"Не удалось отправить сообщение {giver_id}: {e}")

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Посмотреть желания подопечного", callback_data=f"view_wishlist:{room_id}")
    keyboard.button(text="Напомнить подопечного", callback_data=f"view_assignment:{room_id}")
    keyboard.button(text="Назад", callback_data=f"room_menu:{room_id}")
    keyboard.adjust(1)

    await callback.message.edit_text(
        f"Игра началась в комнате {room_id}! Каждому участнику отправлено имя того, кому он дарит подарок.",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("view_assignment"))
async def view_assignment(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    cursor.execute(
        "SELECT receiver_id FROM assignments WHERE room_id = ? AND giver_id = ?",
        (room_id, callback.from_user.id)
    )
    assignment = cursor.fetchone()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Посмотреть желания подопечного", callback_data=f"view_wishlist:{room_id}")
    keyboard.button(text="Назад", callback_data=f"room_menu:{room_id}")
    keyboard.adjust(1)
    if assignment:
        cursor.execute(
            "SELECT user_name FROM participants WHERE room_id = ? AND user_id = ?",
            (room_id, assignment[0])
        )
        receiver_name = cursor.fetchone()
        if receiver_name:
            await callback.message.edit_text(
                f"Вы дарите подарок: {receiver_name[0]}.",
                reply_markup=keyboard.as_markup()
            )
        else:
            await callback.message.edit_text(
                "Ошибка: Не удалось найти подопечного в комнате.",
                reply_markup=keyboard.as_markup()
            )
    else:
        await callback.message.edit_text(
            "Дождитесь проведения розыгрыша!",
            reply_markup=keyboard.as_markup()
        )

@dp.callback_query(lambda c: c.data.startswith("view_wishlist"))
async def view_wishlist(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    cursor.execute(
        "SELECT receiver_id FROM assignments WHERE room_id = ? AND giver_id = ?",
        (room_id, callback.from_user.id)
    )
    receiver_id = cursor.fetchone()
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data=f"room_menu:{room_id}")
    keyboard.adjust(1)
    if receiver_id:
        cursor.execute(
            "SELECT user_name FROM participants WHERE user_id = ?",
            (receiver_id[0],)
        )
        receiver_name = cursor.fetchone()

        cursor.execute(
            "SELECT wish FROM wishes WHERE user_id = ?",
            (receiver_id[0],)
        )
        wishes = cursor.fetchall()

        wishlist_text = "\n".join([wish[0] for wish in wishes]) if wishes else "Список желаний пуст."

        if receiver_name:
            await callback.message.edit_text(
                f"Список желаний вашего подопечного ({receiver_name[0]}):\n{wishlist_text}",
                reply_markup=keyboard.as_markup()
            )
        else:
            await callback.message.edit_text(
                "Ошибка: Не удалось найти подопечного.",
                reply_markup=keyboard.as_markup()
            )
    else:
        await callback.message.edit_text(
            "Ошибка: Не удалось найти подопечного.",
            reply_markup=keyboard.as_markup()
        )


@dp.callback_query(lambda c: c.data.startswith("delete_room"))
async def delete_room(callback: CallbackQuery):
    room_id = callback.data.split(":")[1]
    cursor.execute("DELETE FROM participants WHERE room_id = ?", (room_id,))
    cursor.execute("DELETE FROM rooms WHERE room_id = ?", (room_id,))
    conn.commit()

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="Назад", callback_data="my_rooms")
    keyboard.adjust(1)

    await callback.message.edit_text(f"Комната {room_id} удалена.", reply_markup=keyboard.as_markup())


# Запуск бота
if __name__ == "__main__":
    import asyncio

    asyncio.run(dp.start_polling(bot))
