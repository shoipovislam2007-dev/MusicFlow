import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery, FSInputFile, Audio
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "8973047993:AAGGJWwmcMRK9eiBOYM8sOKXPs_zuTHhh78"
ADMIN_ID = 7921694564  # ← ЗАМЕНИ на свой Telegram ID
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect("music_bot.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            file_id TEXT NOT NULL,
            added_by INTEGER NOT NULL,
            is_public INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            stars_donated INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect("music_bot.db")
    cur = conn.cursor()
    cur.execute(query, params)
    result = cur.fetchall() if fetch else None
    conn.commit()
    conn.close()
    return result
# ==================== СОСТОЯНИЯ ====================
class AddTrack(StatesGroup):
    choosing_category = State()
    waiting_audio = State()
    waiting_title = State()
class DonateState(StatesGroup):
    choosing_amount = State()
# ==================== КАТЕГОРИИ ====================
ADMIN_CATEGORIES = ["lofi", "classic", "phonk", "rock", "chill"]
# ==================== КЛАВИАТУРЫ ====================
def main_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="🎧 Lofi", callback_data="cat:lofi"),
         InlineKeyboardButton(text="🎼 Classic", callback_data="cat:classic")],
        [InlineKeyboardButton(text="🔥 Phonk", callback_data="cat:phonk"),
         InlineKeyboardButton(text="🎸 Rock", callback_data="cat:rock")],
        [InlineKeyboardButton(text="🌙 Chill", callback_data="cat:chill")],
        [InlineKeyboardButton(text="⭐ Мой плейлист", callback_data="my_playlist")],
        [InlineKeyboardButton(text="➕ Добавить трек", callback_data="add_track")],
        [InlineKeyboardButton(text="💖 Поддержать (Stars)", callback_data="donate")],
    ]
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
def category_menu(category: str, tracks, user_id: int, is_personal=False) -> InlineKeyboardMarkup:
    kb = []
    for track_id, title, _ in tracks:
        row = [InlineKeyboardButton(text=f"▶️ {title[:35]}", callback_data=f"play:{track_id}")]
        # Кнопка удаления: админ может удалять из общих, юзер — из своих
        if is_personal or user_id == ADMIN_ID:
            row.append(InlineKeyboardButton(text="🗑", callback_data=f"del:{track_id}"))
        kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
def donate_menu() -> InlineKeyboardMarkup:
    amounts = [10, 25, 50, 75, 100]
    kb = [[InlineKeyboardButton(text=f"⭐ {a} Stars", callback_data=f"pay:{a}")] for a in amounts]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
def add_track_menu(user_id: int) -> InlineKeyboardMarkup:
    kb = []
    if user_id == ADMIN_ID:
        for c in ADMIN_CATEGORIES:
            kb.append([InlineKeyboardButton(text=f"📁 {c.capitalize()}", callback_data=f"addcat:{c}")])
    kb.append([InlineKeyboardButton(text="⭐ В мой плейлист", callback_data="addcat:personal")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)
def admin_panel() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="💰 Донаты", callback_data="admin_donates")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
# ==================== ХЕНДЛЕРЫ ====================
@router.message(CommandStart())
async def start_cmd(message: Message):
    user = message.from_user
    db_query(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user.id, user.username or "")
    )
    text = (
        f"🎵 <b>Привет, {user.first_name}!</b>\n\n"
        f"Добро пожаловать в <b>Music Bot</b> — твой карманный музыкальный плеер.\n\n"
        f"🎧 Выбирай жанр\n"
        f"⭐ Создавай свой плейлист\n"
        f"💖 Поддержи разработчика звёздами\n\n"
        f"<i>Выбери раздел ниже 👇</i>"
    )
    await message.answer(text, reply_markup=main_menu(user.id))
@router.callback_query(F.data == "back_main")
async def back_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text(
        "🎵 <b>Главное меню</b>\n\nВыбери раздел:",
        reply_markup=main_menu(cb.from_user.id)
    )
    await cb.answer()
# --- Категории (публичные) ---
@router.callback_query(F.data.startswith("cat:"))
async def show_category(cb: CallbackQuery):
    category = cb.data.split(":")[1]
    tracks = db_query(
        "SELECT id, title, file_id FROM tracks WHERE category=? AND is_public=1",
        (category,), fetch=True
    )
    if not tracks:
        await cb.message.edit_text(
            f"📭 В разделе <b>{category.capitalize()}</b> пока пусто.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
            ])
        )
    else:
        await cb.message.edit_text(
            f"🎼 <b>{category.capitalize()}</b>\nТреков: {len(tracks)}\n\nВыбери, что послушать:",
            reply_markup=category_menu(category, tracks, cb.from_user.id)
        )
    await cb.answer()
# --- Мой плейлист ---
@router.callback_query(F.data == "my_playlist")
async def my_playlist(cb: CallbackQuery):
    tracks = db_query(
        "SELECT id, title, file_id FROM tracks WHERE category=? AND added_by=?",
        (f"personal_{cb.from_user.id}", cb.from_user.id), fetch=True
    )
    if not tracks:
        await cb.message.edit_text(
            "⭐ <b>Твой плейлист пуст</b>\n\nДобавь свой первый трек через кнопку «➕ Добавить трек».",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить", callback_data="add_track")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")]
            ])
        )
    else:
        await cb.message.edit_text(
            f"⭐ <b>Мой плейлист</b>\nТреков: {len(tracks)}",
            reply_markup=category_menu("personal", tracks, cb.from_user.id, is_personal=True)
        )
    await cb.answer()
# --- Воспроизведение трека ---
@router.callback_query(F.data.startswith("play:"))
async def play_track(cb: CallbackQuery):
    track_id = int(cb.data.split(":")[1])
    row = db_query("SELECT title, file_id FROM tracks WHERE id=?", (track_id,), fetch=True)
    if not row:
        await cb.answer("Трек не найден 😕", show_alert=True)
        return
    title, file_id = row[0]
    try:
        await cb.message.answer_audio(audio=file_id, caption=f"🎧 <b>{title}</b>")
        await cb.answer("▶️ Играет!")
    except Exception as e:
        await cb.answer(f"Ошибка воспроизведения: {e}", show_alert=True)
# --- Удаление трека ---
@router.callback_query(F.data.startswith("del:"))
async def delete_track(cb: CallbackQuery):
    track_id = int(cb.data.split(":")[1])
    row = db_query("SELECT category, added_by FROM tracks WHERE id=?", (track_id,), fetch=True)
    if not row:
        await cb.answer("Трек уже удалён", show_alert=True)
        return
    category, added_by = row[0]
    is_personal = category.startswith("personal_")
    # Права: админ удаляет всё, юзер — только свои личные
    if cb.from_user.id != ADMIN_ID and not (is_personal and added_by == cb.from_user.id):
        await cb.answer("⛔ У тебя нет прав удалять этот трек", show_alert=True)
        return
    db_query("DELETE FROM tracks WHERE id=?", (track_id,))
    await cb.answer("🗑 Трек удалён")
    # Обновим список
    if is_personal:
        await my_playlist(cb)
    else:
        cb.data = f"cat:{category}"
        await show_category(cb)
# --- Добавление трека ---
@router.callback_query(F.data == "add_track")
async def add_track_start(cb: CallbackQuery):
    await cb.message.edit_text(
        "➕ <b>Куда добавить трек?</b>",
        reply_markup=add_track_menu(cb.from_user.id)
    )
    await cb.answer()
@router.callback_query(F.data.startswith("addcat:"))
async def add_track_category(cb: CallbackQuery, state: FSMContext):
    category = cb.data.split(":")[1]
    # Проверка прав на публичные категории
    if category in ADMIN_CATEGORIES and cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔ Только админ может добавлять в общие разделы", show_alert=True)
        return
    if category == "personal":
        category = f"personal_{cb.from_user.id}"
    await state.update_data(category=category)
    await state.set_state(AddTrack.waiting_audio)
    await cb.message.edit_text(
        "🎵 Отправь <b>аудиофайл</b> (mp3), который хочешь добавить.\n\n"
        "<i>Для отмены — /cancel</i>"
    )
    await cb.answer()
@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.", reply_markup=main_menu(message.from_user.id))
@router.message(AddTrack.waiting_audio, F.audio)
async def add_track_audio(message: Message, state: FSMContext):
    await state.update_data(file_id=message.audio.file_id, default_title=message.audio.title or "Без названия")
    await state.set_state(AddTrack.waiting_title)
    await message.answer(
        f"📝 Введи название трека (или отправь <code>-</code>, чтобы использовать «{message.audio.title or 'Без названия'}»):"
    )
@router.message(AddTrack.waiting_audio)
async def add_track_wrong(message: Message):
    await message.answer("⚠️ Отправь именно аудиофайл (mp3).")
@router.message(AddTrack.waiting_title)
async def add_track_title(message: Message, state: FSMContext):
    data = await state.get_data()
    title = message.text.strip() if message.text.strip() != "-" else data["default_title"]
    category = data["category"]
    is_public = 0 if category.startswith("personal_") else 1
    db_query(
        "INSERT INTO tracks (category, title, file_id, added_by, is_public) VALUES (?, ?, ?, ?, ?)",
        (category, title, data["file_id"], message.from_user.id, is_public)
    )
    await state.clear()
    await message.answer(
        f"✅ Трек <b>{title}</b> добавлен!",
        reply_markup=main_menu(message.from_user.id)
    )
# --- Донаты через Telegram Stars ---
@router.callback_query(F.data == "donate")
async def donate_menu_cb(cb: CallbackQuery):
    text = (
        "💖 <b>Поддержи разработчика</b>\n\n"
        "Твои звёзды помогают развивать бота, добавлять новые фичи и держать сервер онлайн.\n\n"
        "Выбери сумму:"
    )
    await cb.message.edit_text(text, reply_markup=donate_menu())
    await cb.answer()
@router.callback_query(F.data.startswith("pay:"))
async def send_invoice(cb: CallbackQuery):
    amount = int(cb.data.split(":")[1])
    prices = [LabeledPrice(label=f"Поддержка {amount} ⭐", amount=amount)]
    await cb.message.answer_invoice(
        title="Поддержка бота 💖",
        description=f"Спасибо за поддержку! Ты даришь {amount} звёзд разработчику.",
        payload=f"donate_{cb.from_user.id}_{amount}",
        provider_token="",  # Для Stars оставляем пустым
        currency="XTR",     # Валюта Telegram Stars
        prices=prices,
    )
    await cb.answer()
@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)
@router.message(F.successful_payment)
async def success_payment(message: Message):
    amount = message.successful_payment.total_amount
    db_query(
        "UPDATE users SET stars_donated = stars_donated + ? WHERE user_id = ?",
        (amount, message.from_user.id)
    )
    await message.answer(
        f"🌟 <b>Спасибо огромное за {amount} звёзд!</b>\n"
        f"Ты крутой(ая) 💖\n\n"
        f"Твоя поддержка бесценна!",
        reply_markup=main_menu(message.from_user.id)
    )
    # Уведомление админу
    try:
        await bot.send_message(
            ADMIN_ID,
            f"💰 Новый донат!\n"
            f"От: @{message.from_user.username or message.from_user.id}\n"
            f"Сумма: {amount} ⭐"
        )
    except Exception:
        pass
# --- Админ-панель ---
@router.callback_query(F.data == "admin_panel")
async def admin_panel_cb(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await cb.message.edit_text("👑 <b>Админ-панель</b>", reply_markup=admin_panel())
    await cb.answer()
@router.callback_query(F.data == "admin_stats")
async def admin_stats(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔", show_alert=True)
        return
    users = db_query("SELECT COUNT(*) FROM users", fetch=True)[0][0]
    tracks_public = db_query("SELECT COUNT(*) FROM tracks WHERE is_public=1", fetch=True)[0][0]
    tracks_personal = db_query("SELECT COUNT(*) FROM tracks WHERE is_public=0", fetch=True)[0][0]
    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"🎼 Публичных треков: <b>{tracks_public}</b>\n"
        f"⭐ Личных плейлистов (треков): <b>{tracks_personal}</b>"
    )
    await cb.message.edit_text(text, reply_markup=admin_panel())
    await cb.answer()
@router.callback_query(F.data == "admin_donates")
async def admin_donates(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔", show_alert=True)
        return
    total = db_query("SELECT SUM(stars_donated) FROM users", fetch=True)[0][0] or 0
    top = db_query(
        "SELECT username, stars_donated FROM users WHERE stars_donated>0 ORDER BY stars_donated DESC LIMIT 10",
        fetch=True
    )
    text = f"💰 <b>Донаты</b>\n\nВсего собрано: <b>{total} ⭐</b>\n\n<b>Топ поддержавших:</b>\n"
    if top:
        for i, (uname, stars) in enumerate(top, 1):
            text += f"{i}. @{uname or 'аноним'} — {stars} ⭐\n"
    else:
        text += "<i>Пока никто не донатил</i>"
    await cb.message.edit_text(text, reply_markup=admin_panel())
    await cb.answer()
# ==================== ЗАПУСК ====================
async def main():
    init_db()
    dp.include_router(router)
    print("🎵 Music Bot запущен!")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)
if __name__ == "__main__":
    asyncio.run(main())
