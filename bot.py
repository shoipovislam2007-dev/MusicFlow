import asyncio
import logging
import os
import json
import random
import time
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime

# ---------- НАСТРОЙКИ ----------
API_TOKEN = os.getenv('API_TOKEN', '8973047993:AAGGJWwmcMRK9eiBOYM8sOKXPs_zuTHhh78')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7921694564))
STORAGE_FILE = 'music_library.json'
USER_PLAYLISTS_FILE = 'user_playlists.json'

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# ---------- КАТЕГОРИИ ----------
CATEGORIES = {
    "classical": {"name": "Классика", "emoji": "🎻", "protected": True},
    "lofi": {"name": "Lo-Fi Chill", "emoji": "🎧", "protected": True},
    "nature": {"name": "Природа", "emoji": "🌿", "protected": True}
}

# ---------- FSM ----------
class AdminStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_file = State()
    waiting_for_delete = State()
    waiting_for_playlist_name = State()
    waiting_for_playlist_track = State()
    waiting_for_playlist_delete = State()

# ---------- РАБОТА С БАЗОЙ ----------
def load_library():
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_library(library):
    with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
        json.dump(library, f, indent=2, ensure_ascii=False)

def load_user_playlists():
    if os.path.exists(USER_PLAYLISTS_FILE):
        try:
            with open(USER_PLAYLISTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_playlists(playlists):
    with open(USER_PLAYLISTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(playlists, f, indent=2, ensure_ascii=False)

def get_track_duration(seconds):
    if not seconds:
        return "0:00"
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

# ---------- КЛАВИАТУРЫ ----------
def get_main_menu():
    builder = InlineKeyboardBuilder()
    
    for key, cat in CATEGORIES.items():
        builder.add(InlineKeyboardButton(
            text=f"{cat['emoji']} {cat['name']}",
            callback_data=f"play_{key}"
        ))
    
    builder.adjust(3)
    
    builder.row(
        InlineKeyboardButton(text="🎲 Случайный трек", callback_data="random"),
        InlineKeyboardButton(text="📋 Мои плейлисты", callback_data="my_playlists"),
        width=2
    )
    
    builder.row(
        InlineKeyboardButton(text="➕ Создать плейлист", callback_data="create_playlist"),
        width=2
    )
    
    builder.row(
        InlineKeyboardButton(text="⚙️ Управление", callback_data="admin_panel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_panel():
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="📥 Добавить трек", callback_data="admin_add"),
        InlineKeyboardButton(text="🗑 Удалить трек", callback_data="admin_delete"),
        width=2
    )
    
    builder.row(
        InlineKeyboardButton(text="📊 Список треков", callback_data="admin_list"),
        InlineKeyboardButton(text="📈 Статистика", callback_data="admin_stats"),
        width=2
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu"),
        width=1
    )
    
    return builder.as_markup()

def get_category_buttons():
    builder = InlineKeyboardBuilder()
    
    for key, cat in CATEGORIES.items():
        builder.add(InlineKeyboardButton(
            text=f"{cat['emoji']} {cat['name']}",
            callback_data=f"cat_{key}"
        ))
    
    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        width=1
    )
    
    return builder.as_markup()

def get_playlist_menu(user_id):
    playlists = load_user_playlists()
    user_playlists = playlists.get(str(user_id), {})
    
    builder = InlineKeyboardBuilder()
    
    if user_playlists:
        for name, tracks in user_playlists.items():
            count = len(tracks)
            builder.add(InlineKeyboardButton(
                text=f"📁 {name} ({count})",
                callback_data=f"open_playlist_{name}"
            ))
        builder.adjust(2)
    
    builder.row(
        InlineKeyboardButton(text="➕ Создать новый", callback_data="create_playlist"),
        width=1
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"),
        width=1
    )
    
    return builder.as_markup()

def get_playlist_tracks_buttons(playlist_name, user_id, tracks):
    builder = InlineKeyboardBuilder()
    
    for i, track in enumerate(tracks[:20], 1):
        title = track.get('title', 'Без названия')[:30]
        callback_data = f"playlist_track_{playlist_name}|||{i-1}"
        builder.add(InlineKeyboardButton(
            text=f"▶️ {i}. {title}",
            callback_data=callback_data
        ))
    
    if len(tracks) > 20:
        builder.add(InlineKeyboardButton(
            text=f"... и еще {len(tracks) - 20} треков",
            callback_data="noop"
        ))
    
    builder.adjust(1)
    
    builder.row(
        InlineKeyboardButton(text="➕ Добавить трек", callback_data=f"add_to_playlist_{playlist_name}"),
        width=1
    )
    
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить трек", callback_data=f"delete_from_playlist_{playlist_name}"),
        InlineKeyboardButton(text="🔀 Случайный", callback_data=f"random_playlist_{playlist_name}"),
        width=2
    )
    
    builder.row(
        InlineKeyboardButton(text="❌ Удалить плейлист", callback_data=f"remove_playlist_{playlist_name}"),
        width=1
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад к плейлистам", callback_data="my_playlists"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_delete_buttons():
    builder = InlineKeyboardBuilder()
    
    for key, cat in CATEGORIES.items():
        builder.add(InlineKeyboardButton(
            text=f"{cat['emoji']} {cat['name']}",
            callback_data=f"cat_delete_{key}"
        ))
    
    builder.adjust(3)
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        width=1
    )
    
    return builder.as_markup()

# ---------- ОБРАБОТКА ТЕКСТА ----------
@dp.message()
async def handle_text_message(message: types.Message):
    help_text = (
        "🎵 *Music Flow - Помощь*\n\n"
        "📌 *Основные команды:*\n"
        "• `/start` - Запустить бота\n"
        "• `/menu` - Показать главное меню\n"
        "• `/random` - Случайный трек\n\n"
        "📋 *Плейлисты:*\n"
        "• Нажми 'Мои плейлисты' в меню\n"
        "• Создавай свои плейлисты\n"
        "• Добавляй любимые треки\n\n"
        "🎵 *Категории:*\n"
        "• 🎻 Классика\n"
        "• 🎧 Lo-Fi Chill\n"
        "• 🌿 Природа\n\n"
        "👑 *Админ-команды:*\n"
        "• `/add` - Добавить трек\n"
        "• `/delete` - Удалить трек\n"
        "• `/list` - Список треков"
    )
    
    await message.answer(
        help_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )

# ---------- КОМАНДЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "🎵 *Добро пожаловать в Music Flow*\n\n"
        "✨ Твой персональный музыкальный бот\n\n"
        "📌 *Основные категории:*\n"
        "• 🎻 Классика\n"
        "• 🎧 Lo-Fi Chill\n"
        "• 🌿 Природа\n\n"
        "📋 Создавай свои плейлисты\n"
        "⚡ Мгновенная загрузка\n"
    )
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )
    
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👑 *Режим администратора активен*",
            parse_mode="Markdown"
        )

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer(
        "📋 *Главное меню*",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )

@dp.message(Command("random"))
async def cmd_random(message: types.Message):
    library = load_library()
    all_tracks = []
    
    for category, tracks in library.items():
        for track_id, track_data in tracks.items():
            all_tracks.append((category, track_id, track_data))
    
    if not all_tracks:
        await message.answer(
            "🎵 *Библиотека пуста*\n\n"
            "Добавьте первые треки через админ-панель!",
            parse_mode="Markdown"
        )
        return
    
    category, track_id, track_data = random.choice(all_tracks)
    
    try:
        await message.answer_audio(
            track_data['file_id'],
            caption=(
                f"🎲 *Случайный трек*\n\n"
                f"🎵 *Название:* {track_data.get('title', 'Без названия')}\n"
                f"📁 *Категория:* {CATEGORIES[category]['name']}\n"
                f"⏱ *Длительность:* {get_track_duration(track_data.get('duration', 0))}"
            ),
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logging.error(f"Ошибка при воспроизведении: {e}")
        await message.answer(
            "❌ *Ошибка при воспроизведении трека*\n\n"
            "Возможно, файл был удален. Попробуйте другой трек.",
            parse_mode="Markdown"
        )

# ---------- АДМИН-КОМАНДЫ ----------
@dp.message(Command("add"))
async def admin_add_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    
    await message.answer(
        "📥 *Добавление нового трека*\n\n"
        "Выбери категорию:",
        reply_markup=get_category_buttons(),
        parse_mode="Markdown"
    )

@dp.message(Command("delete"))
async def admin_delete_start(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    
    await message.answer(
        "🗑 *Удаление трека*\n\n"
        "Выбери категорию:",
        reply_markup=get_admin_delete_buttons(),
        parse_mode="Markdown"
    )

@dp.message(Command("list"))
async def admin_list(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    
    library = load_library()
    if not library:
        await message.answer("📊 *Библиотека пуста*", parse_mode="Markdown")
        return
    
    text = "📊 *Список всех треков*\n\n"
    total = 0
    
    for category, tracks in library.items():
        cat_name = CATEGORIES.get(category, {}).get('name', category)
        cat_emoji = CATEGORIES.get(category, {}).get('emoji', '🎵')
        text += f"📁 *{cat_emoji} {cat_name}* ({len(tracks)} треков)\n"
        
        for track_id, track_data in tracks.items():
            duration = get_track_duration(track_data.get('duration', 0))
            text += f"  • `{track_id}` — {track_data.get('title', 'Без названия')} [{duration}]\n"
        
        text += "\n"
        total += len(tracks)
    
    text += f"\n📌 *Всего треков:* {total}"
    
    # Разбиваем на части, если текст слишком длинный
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.answer(part, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")

# ---------- CALLBACK-ЗАПРОСЫ ----------
@dp.callback_query(F.data.startswith("playlist_track_"))
async def play_playlist_track(callback: types.CallbackQuery):
    data_parts = callback.data.replace("playlist_track_", "").split("|||")
    
    if len(data_parts) != 2:
        await callback.answer("❌ Ошибка!")
        return
    
    playlist_name = data_parts[0]
    try:
        track_index = int(data_parts[1])
    except ValueError:
        await callback.answer("❌ Ошибка!")
        return
    
    user_id = str(callback.from_user.id)
    playlists = load_user_playlists()
    
    if user_id not in playlists or playlist_name not in playlists[user_id]:
        await callback.answer("❌ Плейлист не найден!")
        return
    
    tracks = playlists[user_id][playlist_name]
    
    if track_index < 0 or track_index >= len(tracks):
        await callback.answer("❌ Трек не найден!")
        return
    
    track_data = tracks[track_index]
    
    try:
        await callback.message.answer_audio(
            track_data['file_id'],
            caption=(
                f"🎵 *{track_data.get('title', 'Без названия')}*\n"
                f"📁 *Плейлист:* {playlist_name}\n"
                f"⏱ *Длительность:* {get_track_duration(track_data.get('duration', 0))}"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад в плейлист", callback_data=f"open_playlist_{playlist_name}")]
                ]
            )
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка воспроизведения из плейлиста: {e}")
        await callback.answer("❌ Ошибка при воспроизведении трека!")

@dp.callback_query(F.data.startswith("play_"))
async def play_category_track(callback: types.CallbackQuery):
    category = callback.data.split("_")[1]
    
    if category in ["playlist", "playlist_track"]:
        return
    
    library = load_library()
    
    if category not in library or not library[category]:
        await callback.answer("❌ В этой категории пока нет треков!")
        return
    
    track_id = random.choice(list(library[category].keys()))
    track_data = library[category][track_id]
    
    try:
        await callback.message.answer_audio(
            track_data['file_id'],
            caption=(
                f"🎵 *Сейчас играет*\n\n"
                f"*Название:* {track_data.get('title', 'Без названия')}\n"
                f"📁 *Категория:* {CATEGORIES[category]['name']}\n"
                f"⏱ *Длительность:* {get_track_duration(track_data.get('duration', 0))}"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎲 Другой трек", callback_data=f"play_{category}")],
                    [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_to_menu")]
                ]
            )
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка воспроизведения: {e}")
        await callback.answer("❌ Ошибка при воспроизведении трека!")

@dp.callback_query(F.data == "random")
async def random_track(callback: types.CallbackQuery):
    library = load_library()
    all_tracks = []
    
    for category, tracks in library.items():
        for track_id, track_data in tracks.items():
            all_tracks.append((category, track_id, track_data))
    
    if not all_tracks:
        await callback.answer("❌ Нет треков в библиотеке!")
        return
    
    category, track_id, track_data = random.choice(all_tracks)
    
    try:
        await callback.message.answer_audio(
            track_data['file_id'],
            caption=(
                f"🎲 *Случайный трек*\n\n"
                f"*Название:* {track_data.get('title', 'Без названия')}\n"
                f"📁 *Категория:* {CATEGORIES[category]['name']}\n"
                f"⏱ *Длительность:* {get_track_duration(track_data.get('duration', 0))}\n"
            ),
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка воспроизведения: {e}")
        await callback.answer("❌ Ошибка при воспроизведении трека!")

# ---------- АДМИН-ДОБАВЛЕНИЕ ----------
@dp.callback_query(F.data.startswith("cat_"))
async def admin_choose_category(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    if callback.data.startswith("cat_delete_"):
        return
    
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    await state.set_state(AdminStates.waiting_for_file)
    
    await callback.message.answer(
        f"📤 *Отправь аудиофайл*\n\n"
        f"📁 Категория: {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}\n\n"
        f"⚡ *Быстрое добавление:*\n"
        f"• Файл НЕ скачивается на сервер\n"
        f"• Хранится в Telegram Cloud\n"
        f"• Мгновенное воспроизведение\n\n"
        f"💡 В подписи к файлу укажи название трека",
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.message(AdminStates.waiting_for_file, F.audio)
async def admin_receive_audio(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    
    data = await state.get_data()
    category = data.get('category')
    
    if not category:
        await message.answer("❌ Ошибка! Выбери категорию заново через /add")
        await state.clear()
        return
    
    audio = message.audio
    title = message.caption or audio.file_name or audio.title or "Без названия"
    
    library = load_library()
    if category not in library:
        library[category] = {}
    
    track_id = str(int(time.time()))
    library[category][track_id] = {
        "file_id": audio.file_id,
        "title": title,
        "duration": audio.duration,
        "added_by": message.from_user.id,
        "added_by_name": message.from_user.full_name,
        "added_date": datetime.now().isoformat()
    }
    
    save_library(library)
    
    duration = get_track_duration(audio.duration)
    await message.answer(
        f"✅ *Трек успешно добавлен!*\n\n"
        f"📁 *Категория:* {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}\n"
        f"🎵 *Название:* {title}\n"
        f"⏱ *Длительность:* {duration}\n"
        f"👤 *Добавил:* {message.from_user.full_name}\n\n"
        f"⚡ *Трек загружается мгновенно!*",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
    await state.clear()

@dp.message(AdminStates.waiting_for_file)
async def admin_wrong_file(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "❌ *Неверный формат*\n\n"
            "Отправь именно аудиофайл.",
            parse_mode="Markdown"
        )

# ---------- ПЛЕЙЛИСТЫ ПОЛЬЗОВАТЕЛЕЙ ----------
@dp.callback_query(F.data == "my_playlists")
async def show_my_playlists(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    playlists = load_user_playlists()
    
    if user_id not in playlists or not playlists[user_id]:
        await callback.message.answer(
            "📋 *У тебя пока нет плейлистов*\n\n"
            "Создай свой первый плейлист!",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Создать плейлист", callback_data="create_playlist")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
                ]
            ),
            parse_mode="Markdown"
        )
    else:
        await callback.message.answer(
            "📋 *Твои плейлисты*",
            reply_markup=get_playlist_menu(callback.from_user.id),
            parse_mode="Markdown"
        )
    
    await callback.answer()

@dp.callback_query(F.data == "create_playlist")
async def create_playlist_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📝 *Создание нового плейлиста*\n\n"
        "Напиши название для нового плейлиста:",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_playlist_name)
    await callback.answer()

@dp.message(AdminStates.waiting_for_playlist_name)
async def create_playlist_name(message: types.Message, state: FSMContext):
    playlist_name = message.text.strip()
    
    if len(playlist_name) > 30:
        await message.answer("❌ Название слишком длинное (максимум 30 символов)")
        return
    
    user_id = str(message.from_user.id)
    playlists = load_user_playlists()
    
    if user_id not in playlists:
        playlists[user_id] = {}
    
    if playlist_name in playlists[user_id]:
        await message.answer("❌ Плейлист с таким названием уже существует!")
        return
    
    playlists[user_id][playlist_name] = []
    save_user_playlists(playlists)
    
    await message.answer(
        f"✅ *Плейлист создан!*\n\n"
        f"📁 Название: {playlist_name}\n\n"
        f"Теперь ты можешь добавлять в него треки.",
        reply_markup=get_playlist_menu(message.from_user.id),
        parse_mode="Markdown"
    )
    await state.clear()

@dp.callback_query(F.data.startswith("open_playlist_"))
async def open_playlist(callback: types.CallbackQuery):
    playlist_name = callback.data.replace("open_playlist_", "")
    user_id = str(callback.from_user.id)
    
    playlists = load_user_playlists()
    
    if user_id not in playlists or playlist_name not in playlists[user_id]:
        await callback.answer("❌ Плейлист не найден!")
        return
    
    tracks = playlists[user_id][playlist_name]
    
    if not tracks:
        text = f"📁 *{playlist_name}*\n\n"
        text += "В плейлисте пока нет треков.\n"
        text += "Нажми 'Добавить трек', чтобы добавить музыку."
    else:
        text = f"📁 *{playlist_name}* ({len(tracks)} треков)\n\n"
        text += "▶️ Нажми на трек, чтобы прослушать"
    
    await callback.message.answer(
        text,
        reply_markup=get_playlist_tracks_buttons(playlist_name, callback.from_user.id, tracks),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("add_to_playlist_"))
async def add_to_playlist(callback: types.CallbackQuery, state: FSMContext):
    playlist_name = callback.data.replace("add_to_playlist_", "")
    await state.update_data(playlist_name=playlist_name)
    
    await callback.message.answer(
        f"🎵 *Добавление трека в плейлист*\n\n"
        f"📁 Плейлист: {playlist_name}\n\n"
        "Отправь аудиофайл, который хочешь добавить.\n"
        "В подписи к файлу укажи название трека.\n\n"
        "⚡ *Файл не скачивается, загружается мгновенно!*",
        parse_mode="Markdown"
    )
    await state.set_state(AdminStates.waiting_for_playlist_track)
    await callback.answer()

@dp.message(AdminStates.waiting_for_playlist_track, F.audio)
async def add_track_to_playlist(message: types.Message, state: FSMContext):
    data = await state.get_data()
    playlist_name = data.get('playlist_name')
    
    if not playlist_name:
        await message.answer("❌ Ошибка! Попробуй снова.")
        await state.clear()
        return
    
    user_id = str(message.from_user.id)
    playlists = load_user_playlists()
    
    if user_id not in playlists or playlist_name not in playlists[user_id]:
        await message.answer("❌ Плейлист не найден!")
        await state.clear()
        return
    
    audio = message.audio
    title = message.caption or audio.file_name or audio.title or "Без названия"
    
    track_data = {
        "file_id": audio.file_id,
        "title": title,
        "duration": audio.duration,
        "added_by": message.from_user.id,
        "added_by_name": message.from_user.full_name,
        "added_date": datetime.now().isoformat()
    }
    
    playlists[user_id][playlist_name].append(track_data)
    save_user_playlists(playlists)
    
    duration = get_track_duration(audio.duration)
    tracks = playlists[user_id][playlist_name]
    
    await message.answer(
        f"✅ *Трек добавлен в плейлист!*\n\n"
        f"📁 Плейлист: {playlist_name}\n"
        f"🎵 Название: {title}\n"
        f"⏱ Длительность: {duration}\n\n"
        f"⚡ *Трек загружается мгновенно!*",
        parse_mode="Markdown"
    )
    
    text = f"📁 *{playlist_name}* ({len(tracks)} треков)\n\n"
    text += "▶️ Нажми на трек, чтобы прослушать"
    
    await message.answer(
        text,
        reply_markup=get_playlist_tracks_buttons(playlist_name, message.from_user.id, tracks),
        parse_mode="Markdown"
    )
    await state.clear()

@dp.message(AdminStates.waiting_for_playlist_track)
async def wrong_track_for_playlist(message: types.Message):
    await message.answer(
        "❌ Отправь именно аудиофайл!",
        parse_mode="Markdown"
    )

# ---------- ОСТАЛЬНЫЕ ОБРАБОТЧИКИ ----------
@dp.callback_query(F.data.startswith("delete_from_playlist_"))
async def delete_from_playlist(callback: types.CallbackQuery, state: FSMContext):
    playlist_name = callback.data.replace("delete_from_playlist_", "")
    user_id = str(callback.from_user.id)
    
    playlists = load_user_playlists()
    
    if user_id not in playlists or playlist_name not in playlists[user_id]:
        await callback.answer("❌ Плейлист не найден!")
        return
    
    tracks = playlists[user_id][playlist_name]
    
    if not tracks:
        await callback.answer("❌ В плейлисте нет треков!")
        return
    
    text = f"🗑 *Удаление трека из '{playlist_name}'*\n\n"
    text += "Отправь номер трека, который хочешь удалить:\n\n"
    
    for i, track in enumerate(tracks, 1):
        text += f"{i}. {track.get('title', 'Без названия')}\n"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await state.update_data(playlist_name=playlist_name)
    await state.set_state(AdminStates.waiting_for_playlist_delete)
    await callback.answer()

@dp.message(AdminStates.waiting_for_playlist_delete)
async def confirm_delete_from_playlist(message: types.Message, state: FSMContext):
    data = await state.get_data()
    playlist_name = data.get('playlist_name')
    
    if not playlist_name:
        await message.answer("❌ Ошибка! Попробуй снова.")
        await state.clear()
        return
    
    user_id = str(message.from_user.id)
    playlists = load_user_playlists()
    
    if user_id not in playlists or playlist_name not in playlists[user_id]:
        await message.answer("❌ Плейлист не найден!")
        await state.clear()
        return
    
    try:
        track_index = int(message.text.strip()) - 1
        tracks = playlists[user_id][playlist_name]
        
        if track_index < 0 or track_index >= len(tracks):
            await message.answer("❌ Неверный номер трека!")
            return
        
        deleted_track = tracks.pop(track_index)
        save_user_playlists(playlists)
        
        await message.answer(
            f"✅ *Трек удален из плейлиста!*\n\n"
            f"🎵 {deleted_track.get('title', 'Без названия')}",
            parse_mode="Markdown"
        )
        
        if tracks:
            text = f"📁 *{playlist_name}* ({len(tracks)} треков)\n\n"
            text += "▶️ Нажми на трек, чтобы прослушать"
            await message.answer(
                text,
                reply_markup=get_playlist_tracks_buttons(playlist_name, message.from_user.id, tracks),
                parse_mode="Markdown"
            )
        else:
            await message.answer(
                f"📁 *{playlist_name}*\n\n"
                "В плейлисте больше нет треков.",
                reply_markup=get_playlist_menu(message.from_user.id),
                parse_mode="Markdown"
            )
            
    except ValueError:
        await message.answer("❌ Отправь номер трека (число)!")
    
    await state.clear()

@dp.callback_query(F.data.startswith("random_playlist_"))
async def random_from_playlist(callback: types.CallbackQuery):
    playlist_name = callback.data.replace("random_playlist_", "")
    user_id = str(callback.from_user.id)
    
    playlists = load_user_playlists()
    
    if user_id not in playlists or playlist_name not in playlists[user_id]:
        await callback.answer("❌ Плейлист не найден!")
        return
    
    tracks = playlists[user_id][playlist_name]
    
    if not tracks:
        await callback.answer("❌ В плейлисте нет треков!")
        return
    
    track_data = random.choice(tracks)
    
    try:
        await callback.message.answer_audio(
            track_data['file_id'],
            caption=(
                f"🎲 *Случайный трек из '{playlist_name}'*\n\n"
                f"🎵 *Название:* {track_data.get('title', 'Без названия')}\n"
                f"⏱ *Длительность:* {get_track_duration(track_data.get('duration', 0))}"
            ),
            parse_mode="Markdown"
        )
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка воспроизведения: {e}")
        await callback.answer("❌ Ошибка при воспроизведении трека!")

@dp.callback_query(F.data.startswith("remove_playlist_"))
async def remove_playlist(callback: types.CallbackQuery):
    playlist_name = callback.data.replace("remove_playlist_", "")
    user_id = str(callback.from_user.id)
    
    playlists = load_user_playlists()
    
    if user_id not in playlists or playlist_name not in playlists[user_id]:
        await callback.answer("❌ Плейлист не найден!")
        return
    
    del playlists[user_id][playlist_name]
    save_user_playlists(playlists)
    
    await callback.message.answer(
        f"✅ *Плейлист удален!*\n\n"
        f"📁 {playlist_name}",
        reply_markup=get_playlist_menu(callback.from_user.id),
        parse_mode="Markdown"
    )
    await callback.answer()

# ---------- АДМИН-ПАНЕЛЬ ----------
@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    await callback.message.answer(
        "⚙️ *Панель управления*\n\n"
        "Выберите действие:",
        reply_markup=get_admin_panel(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_add")
async def admin_add_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    await callback.message.answer(
        "📥 *Добавление трека*\n\n"
        "Выбери категорию для нового трека:",
        reply_markup=get_category_buttons(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_delete")
async def admin_delete_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    await callback.message.answer(
        "🗑 *Удаление трека из основных категорий*\n\n"
        "Выбери категорию:",
        reply_markup=get_admin_delete_buttons(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cat_delete_"))
async def admin_delete_category(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    category = callback.data.replace("cat_delete_", "")
    await state.update_data(category=category)
    await state.set_state(AdminStates.waiting_for_delete)
    
    library = load_library()
    
    if category not in library or not library[category]:
        await callback.answer("❌ В этой категории нет треков!")
        return
    
    text = f"🗑 *Удаление трека из {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}*\n\n"
    text += "Отправь ID трека для удаления:\n\n"
    
    for track_id, track_data in library[category].items():
        duration = get_track_duration(track_data.get('duration', 0))
        text += f"• `{track_id}` — {track_data.get('title', 'Без названия')} [{duration}]\n"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.message(AdminStates.waiting_for_delete)
async def admin_delete_track(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Доступ запрещен!")
        return
    
    data = await state.get_data()
    category = data.get('category')
    
    if not category:
        await message.answer("❌ Ошибка! Попробуй снова.")
        await state.clear()
        return
    
    track_id = message.text.strip()
    library = load_library()
    
    if category not in library or track_id not in library[category]:
        await message.answer(
            f"❌ *Трек не найден*\n\n"
            f"Проверь ID и попробуй снова.",
            parse_mode="Markdown"
        )
        return
    
    del library[category][track_id]
    if not library[category]:
        del library[category]
    
    save_library(library)
    
    await message.answer(
        f"✅ *Трек удален!*",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
    await state.clear()

@dp.callback_query(F.data == "admin_list")
async def admin_list_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    library = load_library()
    if not library:
        await callback.message.answer("📊 *Библиотека пуста*", parse_mode="Markdown")
        await callback.answer()
        return
    
    text = "📊 *Список всех треков в основных категориях*\n\n"
    total = 0
    
    for category, tracks in library.items():
        cat_name = CATEGORIES.get(category, {}).get('name', category)
        cat_emoji = CATEGORIES.get(category, {}).get('emoji', '🎵')
        text += f"📁 *{cat_emoji} {cat_name}* ({len(tracks)} треков)\n"
        
        for track_id, track_data in tracks.items():
            duration = get_track_duration(track_data.get('duration', 0))
            text += f"  • `{track_id}` — {track_data.get('title', 'Без названия')} [{duration}]\n"
        
        text += "\n"
        total += len(tracks)
    
    text += f"\n📌 *Всего треков:* {total}"
    
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await callback.message.answer(part, parse_mode="Markdown")
    else:
        await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    library = load_library()
    playlists = load_user_playlists()
    
    total_tracks = sum(len(tracks) for tracks in library.values())
    total_users = len(playlists)
    total_playlists = sum(len(pl) for pl in playlists.values())
    total_user_tracks = sum(len(tracks) for pl in playlists.values() for tracks in pl.values())
    
    stats_text = "📈 *Статистика*\n\n"
    stats_text += f"🎵 *Основные треки:* {total_tracks}\n"
    stats_text += f"📁 *Категорий:* {len(CATEGORIES)}\n"
    stats_text += f"👤 *Пользователей:* {total_users}\n"
    stats_text += f"📋 *Плейлистов:* {total_playlists}\n"
    stats_text += f"🎵 *Треков в плейлистах:* {total_user_tracks}\n\n"
    
    stats_text += "*По основным категориям:*\n"
    for key, cat in CATEGORIES.items():
        count = len(library.get(key, {}))
        stats_text += f"{cat['emoji']} {cat['name']}: {count} треков\n"
    
    await callback.message.answer(stats_text, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await callback.message.answer(
        "📋 *Главное меню*",
        reply_markup=get_main_menu(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "❌ *Действие отменено*",
        parse_mode="Markdown",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    await callback.answer()

# ---------- ЗАПУСК ----------
async def main():
    print("🎵 Music Flow Bot")
    print("=" * 40)
    print("📌 Основные категории:")
    print("  🎻 Классика")
    print("  🎧 Lo-Fi Chill")
    print("  🌿 Природа")
    print("\n📌 Команды:")
    print("  /start   - Главное меню")
    print("  /menu    - Показать меню")
    print("  /random  - Случайный трек")
    print("\n📌 Админ-команды:")
    print("  /add      - Добавить трек")
    print("  /delete   - Удалить трек")
    print("  /list     - Список треков")
    print("=" * 40)
    print("🤖 Бот запущен!")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
