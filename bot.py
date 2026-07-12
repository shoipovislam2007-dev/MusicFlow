import asyncio
import logging
import os
import json
import random
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime
import aiohttp
import aiofiles

# ---------- НАСТРОЙКИ ----------
API_TOKEN = os.getenv('API_TOKEN', '8973047993:AAGGJWwmcMRK9eiBOYM8sOKXPs_zuTHhh78')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7921694564))
MUSIC_FOLDER = 'music_files'

# Создаем папку для музыки
os.makedirs(MUSIC_FOLDER, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=storage)

# ---------- КАТЕГОРИИ ----------
CATEGORIES = {
    "classical": {"name": "Классика", "emoji": "🎻"},
    "lofi": {"name": "Lo-Fi", "emoji": "🎧"},
    "nature": {"name": "Природа", "emoji": "🌿"},
    "other": {"name": "Другое", "emoji": "🎵"}
}

# ---------- FSM ----------
class AdminStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_file = State()
    waiting_for_delete = State()
    waiting_for_playlist_name = State()
    waiting_for_playlist_track = State()

# ---------- РАБОТА С ДАННЫМИ ----------
def load_data():
    """Загружает данные из JSON файла"""
    data_file = 'music_data.json'
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    """Сохраняет данные в JSON файл"""
    data_file = 'music_data.json'
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_track_path(filename):
    """Возвращает полный путь к файлу трека"""
    return os.path.join(MUSIC_FOLDER, filename)

# ---------- КЛАВИАТУРЫ ----------
def get_main_menu():
    builder = InlineKeyboardBuilder()
    
    # Кнопки категорий
    for key, cat in CATEGORIES.items():
        builder.add(InlineKeyboardButton(
            text=f"{cat['emoji']} {cat['name']}",
            callback_data=f"play_{key}"
        ))
    
    builder.adjust(2)
    
    builder.row(
        InlineKeyboardButton(text="🎲 Случайный трек", callback_data="random"),
        width=1
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
        width=1
    )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu"),
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
    
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        width=1
    )
    
    return builder.as_markup()

def get_admin_delete_buttons():
    builder = InlineKeyboardBuilder()
    
    for key, cat in CATEGORIES.items():
        builder.add(InlineKeyboardButton(
            text=f"{cat['emoji']} {cat['name']}",
            callback_data=f"delcat_{key}"
        ))
    
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        width=1
    )
    
    return builder.as_markup()

# ---------- КОМАНДЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome = (
        "🎵 *Музыкальный бот*\n\n"
        "📌 *Категории:*\n"
        "• 🎻 Классика\n"
        "• 🎧 Lo-Fi\n"
        "• 🌿 Природа\n"
        "• 🎵 Другое\n\n"
        "🎲 Случайный трек\n"
        "⚙️ Управление (только админ)"
    )
    
    await message.answer(welcome, reply_markup=get_main_menu(), parse_mode="Markdown")
    
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 *Режим администратора*", parse_mode="Markdown")

@dp.message(Command("menu"))
async def cmd_menu(message: types.Message):
    await message.answer("📋 *Главное меню*", reply_markup=get_main_menu(), parse_mode="Markdown")

@dp.message(Command("random"))
async def cmd_random(message: types.Message):
    data = load_data()
    all_tracks = []
    
    for category, tracks in data.items():
        if category in CATEGORIES:
            for track_id, track in tracks.items():
                all_tracks.append((category, track_id, track))
    
    if not all_tracks:
        await message.answer("❌ *Нет треков в библиотеке*", parse_mode="Markdown")
        return
    
    category, track_id, track = random.choice(all_tracks)
    
    # Путь к файлу
    file_path = get_track_path(track['filename'])
    
    if not os.path.exists(file_path):
        await message.answer("❌ *Файл не найден*", parse_mode="Markdown")
        return
    
    try:
        audio_file = FSInputFile(file_path)
        await message.answer_audio(
            audio_file,
            caption=(
                f"🎲 *Случайный трек*\n\n"
                f"🎵 {track.get('title', 'Без названия')}\n"
                f"📁 {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}"
            ),
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"❌ *Ошибка:* {str(e)}", parse_mode="Markdown")

# ---------- АДМИН КОМАНДЫ ----------
@dp.message(Command("add"))
async def admin_add(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ *Доступ запрещен*", parse_mode="Markdown")
        return
    
    await message.answer(
        "📥 *Добавление трека*\n\n"
        "Выбери категорию:",
        reply_markup=get_category_buttons(),
        parse_mode="Markdown"
    )

@dp.message(Command("delete"))
async def admin_delete(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ *Доступ запрещен*", parse_mode="Markdown")
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
        await message.answer("⛔ *Доступ запрещен*", parse_mode="Markdown")
        return
    
    data = load_data()
    if not data:
        await message.answer("📊 *Библиотека пуста*", parse_mode="Markdown")
        return
    
    text = "📊 *Список треков*\n\n"
    total = 0
    
    for category, tracks in data.items():
        if category in CATEGORIES:
            cat_name = CATEGORIES[category]['name']
            cat_emoji = CATEGORIES[category]['emoji']
            text += f"📁 *{cat_emoji} {cat_name}* ({len(tracks)} треков)\n"
            
            for track_id, track in tracks.items():
                text += f"  • {track.get('title', 'Без названия')}\n"
            
            text += "\n"
            total += len(tracks)
    
    text += f"📌 *Всего:* {total}"
    
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.answer(part, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")

# ---------- ОБРАБОТКА ТЕКСТА ----------
@dp.message()
async def handle_text(message: types.Message):
    help_text = (
        "🎵 *Команды бота*\n\n"
        "📌 /start - Главное меню\n"
        "📌 /menu - Показать меню\n"
        "📌 /random - Случайный трек\n"
        "📌 /add - Добавить трек (админ)\n"
        "📌 /delete - Удалить трек (админ)\n"
        "📌 /list - Список треков (админ)"
    )
    await message.answer(help_text, parse_mode="Markdown", reply_markup=get_main_menu())

# ---------- CALLBACK ЗАПРОСЫ ----------
@dp.callback_query(F.data.startswith("play_"))
async def play_category(callback: types.CallbackQuery):
    category = callback.data.split("_")[1]
    
    if category == "list" or category == "track":
        return
    
    data = load_data()
    
    if category not in data or not data[category]:
        await callback.answer("❌ В этой категории нет треков!")
        return
    
    # Выбираем случайный трек из категории
    track_id = random.choice(list(data[category].keys()))
    track = data[category][track_id]
    
    file_path = get_track_path(track['filename'])
    
    if not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден!")
        return
    
    try:
        audio_file = FSInputFile(file_path)
        await callback.message.answer_audio(
            audio_file,
            caption=(
                f"🎵 *{track.get('title', 'Без названия')}*\n"
                f"📁 {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}"
            ),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🎲 Другой трек", callback_data=f"play_{category}")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")]
                ]
            )
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}")

@dp.callback_query(F.data == "random")
async def random_track(callback: types.CallbackQuery):
    data = load_data()
    all_tracks = []
    
    for category, tracks in data.items():
        if category in CATEGORIES:
            for track_id, track in tracks.items():
                all_tracks.append((category, track_id, track))
    
    if not all_tracks:
        await callback.answer("❌ Нет треков!")
        return
    
    category, track_id, track = random.choice(all_tracks)
    file_path = get_track_path(track['filename'])
    
    if not os.path.exists(file_path):
        await callback.answer("❌ Файл не найден!")
        return
    
    try:
        audio_file = FSInputFile(file_path)
        await callback.message.answer_audio(
            audio_file,
            caption=(
                f"🎲 *Случайный трек*\n\n"
                f"🎵 {track.get('title', 'Без названия')}\n"
                f"📁 {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}"
            ),
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await callback.answer(f"❌ Ошибка: {str(e)[:50]}")

# ---------- АДМИН-ДОБАВЛЕНИЕ ----------
@dp.callback_query(F.data.startswith("cat_"))
async def admin_choose_category(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    if callback.data.startswith("delcat_"):
        return
    
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    await state.set_state(AdminStates.waiting_for_file)
    
    await callback.message.answer(
        f"📤 *Отправь MP3 файл*\n\n"
        f"📁 Категория: {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}\n\n"
        f"💡 В подписи к файлу укажи название трека\n"
        f"📝 Пример: 'Мой любимый трек'\n\n"
        f"⚠️ Файл будет сохранен на сервере",
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
    
    # Получаем название из подписи или имени файла
    title = message.caption or audio.file_name or "Без названия"
    
    # Скачиваем файл
    try:
        file = await bot.get_file(audio.file_id)
        file_path = file.file_path
        
        # Генерируем имя файла
        timestamp = int(datetime.now().timestamp())
        safe_title = ''.join(c for c in title if c.isalnum() or c in ' ._-')[:50]
        filename = f"{timestamp}_{safe_title}.mp3"
        local_path = get_track_path(filename)
        
        # Скачиваем файл
        url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_path}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(local_path, 'wb') as f:
                        await f.write(await response.read())
                else:
                    await message.answer("❌ Ошибка скачивания файла!")
                    return
        
        # Сохраняем в JSON
        music_data = load_data()
        if category not in music_data:
            music_data[category] = {}
        
        track_id = str(timestamp)
        music_data[category][track_id] = {
            "title": title,
            "filename": filename,
            "duration": audio.duration,
            "added_date": datetime.now().isoformat()
        }
        
        save_data(music_data)
        
        await message.answer(
            f"✅ *Трек добавлен!*\n\n"
            f"📁 Категория: {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}\n"
            f"🎵 Название: {title}\n"
            f"⏱ Длительность: {audio.duration//60}:{audio.duration%60:02d}",
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await message.answer(f"❌ *Ошибка:* {str(e)}", parse_mode="Markdown")
        await state.clear()

@dp.message(AdminStates.waiting_for_file)
async def admin_wrong_file(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("❌ *Отправь именно аудиофайл*", parse_mode="Markdown")

# ---------- АДМИН-УДАЛЕНИЕ ----------
@dp.callback_query(F.data.startswith("delcat_"))
async def admin_delete_category(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    await state.set_state(AdminStates.waiting_for_delete)
    
    data = load_data()
    
    if category not in data or not data[category]:
        await callback.answer("❌ В этой категории нет треков!")
        return
    
    text = f"🗑 *Удаление трека из {CATEGORIES[category]['emoji']} {CATEGORIES[category]['name']}*\n\n"
    text += "Отправь номер трека:\n\n"
    
    i = 1
    for track_id, track in data[category].items():
        text += f"{i}. {track.get('title', 'Без названия')}\n"
        i += 1
    
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
    
    try:
        track_num = int(message.text.strip()) - 1
        music_data = load_data()
        
        if category not in music_data:
            await message.answer("❌ Категория не найдена!")
            return
        
        tracks = list(music_data[category].items())
        
        if track_num < 0 or track_num >= len(tracks):
            await message.answer("❌ Неверный номер!")
            return
        
        track_id, track = tracks[track_num]
        
        # Удаляем файл
        file_path = get_track_path(track['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Удаляем из JSON
        del music_data[category][track_id]
        if not music_data[category]:
            del music_data[category]
        
        save_data(music_data)
        
        await message.answer(
            f"✅ *Трек удален!*\n\n"
            f"🎵 {track.get('title', 'Без названия')}",
            parse_mode="Markdown",
            reply_markup=get_main_menu()
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Отправь номер (число)!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
        await state.clear()

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
        "📥 *Выбери категорию*",
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
        "🗑 *Выбери категорию*",
        reply_markup=get_admin_delete_buttons(),
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_list")
async def admin_list_callback(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен!")
        return
    
    data = load_data()
    if not data:
        await callback.message.answer("📊 *Библиотека пуста*", parse_mode="Markdown")
        await callback.answer()
        return
    
    text = "📊 *Список треков*\n\n"
    total = 0
    
    for category, tracks in data.items():
        if category in CATEGORIES:
            cat_name = CATEGORIES[category]['name']
            cat_emoji = CATEGORIES[category]['emoji']
            text += f"📁 *{cat_emoji} {cat_name}* ({len(tracks)} треков)\n"
            
            for track_id, track in tracks.items():
                text += f"  • {track.get('title', 'Без названия')}\n"
            
            text += "\n"
            total += len(tracks)
    
    text += f"📌 *Всего:* {total}"
    
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await callback.message.answer(part, parse_mode="Markdown")
    else:
        await callback.message.answer(text, parse_mode="Markdown")
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

# ---------- ЗАПУСК ----------
async def main():
    print("🎵 Музыкальный бот")
    print("=" * 40)
    print("📌 Категории:")
    print("  🎻 Классика")
    print("  🎧 Lo-Fi")
    print("  🌿 Природа")
    print("  🎵 Другое")
    print("=" * 40)
    print("📌 Команды:")
    print("  /start  - Главное меню")
    print("  /menu   - Меню")
    print("  /random - Случайный трек")
    print("  /add    - Добавить трек (админ)")
    print("  /delete - Удалить трек (админ)")
    print("  /list   - Список треков (админ)")
    print("=" * 40)
    print("💾 Файлы хранятся в папке 'music_files'")
    print("📦 Данные в 'music_data.json'")
    print("🤖 Бот запущен!")

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
