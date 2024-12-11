from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb(is_in_room=False, is_admin=False):
    if is_in_room:
        buttons = [
            [InlineKeyboardButton(text="Выйти из комнаты", callback_data="leave_room")],
            [InlineKeyboardButton(text="Управление желаниями", callback_data="wish_menu")],
            [InlineKeyboardButton(text="Посмотреть участников", callback_data="show_members")],
        ]
        if is_admin:
            buttons.append([InlineKeyboardButton(text="Статус участников", callback_data="show_members_status")])
            buttons.append([InlineKeyboardButton(text="Shuffle", callback_data="shuffle")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать комнату", callback_data="create_room")],
        [InlineKeyboardButton(text="Войти в комнату", callback_data="enter_room")]
    ])
# 6929619724:AAFZDoS7WtuHUNDV6_VCuFXbV5RA56Bgvh0